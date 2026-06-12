"""LayoutEngine — orchestrates measure -> constrain -> solve -> verify -> adapt."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from modelforge.deck.layout.grid import GridSystem
from modelforge.deck.layout.overflow import AdaptiveOverflowHandler
from modelforge.deck.layout.patterns import PATTERN_REGISTRY, get_pattern
from modelforge.deck.layout.solver import SlideLayoutSolver
from modelforge.deck.layout.types import BoundingBox, LayoutResult, ResolvedPosition

if TYPE_CHECKING:
    from modelforge.deck.ir.brand_kit import BrandKit
    from modelforge.deck.ir.elements.base import Position
    from modelforge.deck.ir.presentation import Presentation
    from modelforge.deck.ir.slides.base import BaseSlide
    from modelforge.deck.layout.text_measurer import TextMeasurer
    from modelforge.deck.themes.registry import ThemeRegistry
    from modelforge.deck.themes.types import ResolvedTheme, SlideMaster

logger = logging.getLogger(__name__)


# Mapping from element type to region name
_ELEMENT_TO_REGION: dict[str, str] = {
    "heading": "title",
    "subheading": "subtitle",
    "bullet_list": "bullets",
    "numbered_list": "bullets",
    "body_text": "content",
    "footnote": "footnote",
    "chart": "chart_area",
    "table": "table_area",
    "image": "image_area",
    "kpi_card": "stat_cards",
    "metric_group": "stat_cards",
}

# When a pattern does not define an element's primary region, try these
# alternatives (in order) before giving up. This is the repair for the
# composer/pattern contract: a bullet_list on a pattern that only has a
# "content" region still gets positioned (and rendered) instead of being
# silently dropped.
_REGION_FALLBACKS: dict[str, tuple[str, ...]] = {
    "bullets": ("content",),
    "content": ("bullets",),
    "subtitle": ("content", "bullets"),
    "chart_area": ("content", "bullets"),
    "table_area": ("content", "bullets"),
    "stat_cards": ("content", "bullets"),
    "image_area": ("content",),
}

# Content-carrying regions that get distributed across the two columns of a
# two-column pattern (left_column / right_column).
_COLUMN_CONTENT_REGIONS: frozenset[str] = frozenset(
    {"bullets", "content", "chart_area", "table_area", "stat_cards", "image_area"}
)


def assign_element_regions(
    slide: Any, available_regions: set[str]
) -> list[tuple[Any, str | None]]:
    """Assign every slide element to a layout region.

    The single source of truth used by BOTH the measuring pass and the
    position-application pass, so measurements and positions always agree.

    Rules:
        1. Element type maps to its primary region via _ELEMENT_TO_REGION.
        2. On two-column patterns, content-carrying elements are dealt
           left-to-right in document order (1st -> left_column,
           2nd -> right_column, extras stack into right_column).
        3. If the pattern lacks the primary region, _REGION_FALLBACKS is
           consulted; elements that still cannot be placed get None (the
           renderer raises loudly on those).
    """
    assignments: list[tuple[Any, str | None]] = []
    two_column = (
        "left_column" in available_regions and "right_column" in available_regions
    )
    column_order = ("left_column", "right_column")
    column_idx = 0

    for elem in slide.elements:
        etype = getattr(elem, "type", None)
        if hasattr(etype, "value"):
            etype = etype.value
        primary = _ELEMENT_TO_REGION.get(etype) if etype is not None else None
        if primary is None:
            assignments.append((elem, None))
            continue

        if two_column and primary in _COLUMN_CONTENT_REGIONS:
            region = column_order[column_idx] if column_idx < 2 else column_order[1]
            column_idx += 1
            assignments.append((elem, region))
            continue

        if primary in available_regions:
            assignments.append((elem, primary))
            continue

        fallback = next(
            (fb for fb in _REGION_FALLBACKS.get(primary, ()) if fb in available_regions),
            None,
        )
        assignments.append((elem, fallback))

    return assignments


class LayoutEngine:
    """Orchestrates the layout pipeline for slides and presentations.

    Pipeline per slide:
        1. Select pattern from PATTERN_REGISTRY
        2. Get SlideMaster from theme
        3. Measure all text elements
        4. Create regions and constraints
        5. Solve constraints
        6. Check overflow and run adaptive cascade if needed
        7. Apply positions to slide elements

    Args:
        text_measurer: TextMeasurer for measuring text dimensions.
        theme_registry: ThemeRegistry for resolving themes.
    """

    def __init__(self, text_measurer: Any, theme_registry: Any) -> None:
        self._measurer = text_measurer
        self._theme_registry = theme_registry

    def layout_slide(
        self,
        slide: Any,
        theme: Any,
        grid: GridSystem | None = None,
    ) -> LayoutResult:
        """Layout a single slide using the appropriate pattern.

        Args:
            slide: BaseSlide to layout.
            theme: ResolvedTheme with spacing, typography.
            grid: Optional GridSystem; created from theme.spacing if None.

        Returns:
            LayoutResult with resolved positions for each region.
        """
        if grid is None:
            grid = self._create_grid(theme)

        # 1. Select pattern
        slide_type = slide.slide_type
        if hasattr(slide_type, "value"):
            slide_type = slide_type.value

        pattern = get_pattern(slide_type)

        # 2. Get slide master
        master = theme.slide_masters.get(slide_type) or theme.slide_masters.get("default")

        # 3. Measure elements
        measurements = self._measure_elements(slide, theme, master, grid, pattern)

        # 4. Create regions and constraints
        regions = pattern.create_regions()
        constraints = pattern.create_constraints(regions, grid, measurements, theme)

        # 5. Solve
        solver = SlideLayoutSolver()
        solver.add_constraints(constraints)
        positions = solver.solve(regions)

        # 6. Handle infeasible or overflow
        if positions is None:
            logger.warning("Infeasible constraints for slide type %s, triggering overflow", slide_type)
            # Create fallback positions and run overflow handler
            overflow_handler = AdaptiveOverflowHandler(self._measurer)
            fallback_positions = self._fallback_positions(regions, grid)
            result = overflow_handler.handle(
                slide, fallback_positions, measurements, theme, grid, pattern
            )
            self._apply_positions(result.slide, result.positions)
            return result

        # Check for overflow
        overflow_handler = AdaptiveOverflowHandler(self._measurer)
        overflow_regions = overflow_handler.detect_overflow(positions, measurements)

        if overflow_regions:
            result = overflow_handler.handle(
                slide, positions, measurements, theme, grid, pattern
            )
            self._apply_positions(result.slide, result.positions)
            return result

        # 7. No overflow — apply positions and return
        self._apply_positions(slide, positions)
        return LayoutResult(slide=slide, positions=positions, overflow=False)

    def layout_presentation(
        self,
        presentation: Any,
        brand_kit: Any | None = None,
    ) -> list[LayoutResult]:
        """Layout all slides in a presentation.

        Args:
            presentation: Presentation with slides and theme.
            brand_kit: Optional BrandKit overlay.

        Returns:
            List of LayoutResult, one per slide (split slides flattened).
        """
        # Resolve theme
        bk = brand_kit or getattr(presentation, "brand_kit", None)
        theme = self._theme_registry.get_theme(presentation.theme, bk)

        # Create grid from theme
        grid = self._create_grid(theme)

        results: list[LayoutResult] = []
        for slide in presentation.slides:
            result = self.layout_slide(slide, theme, grid)
            results.append(result)

            # Flatten split slides
            if result.split_slides:
                for split_slide in result.split_slides[1:]:  # Skip first (it's the original)
                    split_result = self.layout_slide(split_slide, theme, grid)
                    results.append(split_result)

        return results

    def _create_grid(self, theme: Any) -> GridSystem:
        """Create a GridSystem from theme spacing."""
        spacing = theme.spacing
        return GridSystem(
            margin_left=spacing.margin_left,
            margin_right=spacing.margin_right,
            margin_top=spacing.margin_top,
            margin_bottom=spacing.margin_bottom,
            gutter=spacing.gutter,
        )

    def _measure_elements(
        self,
        slide: Any,
        theme: Any,
        master: Any | None,
        grid: GridSystem,
        pattern: Any,
    ) -> dict[str, BoundingBox]:
        """Measure all elements on a slide, returning region->BoundingBox map.

        Uses assign_element_regions() (the same assignment the renderer pass
        uses) so every element that will be positioned is also measured.
        Multiple elements sharing one region accumulate: max width, summed
        heights (plus an element gap between them).
        """
        measurements: dict[str, BoundingBox] = {}
        available = {r.name for r in pattern.create_regions()}
        stack_gap = getattr(theme.spacing, "element_gap", 0.2)

        for elem, region_name in assign_element_regions(slide, available):
            if region_name is None:
                continue

            # Get font settings from slide master
            font_family, font_size = self._get_font_settings(
                region_name, master, theme
            )

            # Columns are roughly half the content width
            if region_name in ("left_column", "right_column"):
                max_width = grid.column_span_width(0, 6)
            else:
                max_width = grid.content_width

            content = getattr(elem, "content", None)
            if content is not None and hasattr(content, "items"):
                # Bullet list or numbered list
                bbox = self._measurer.measure_bullet_list(
                    content.items,
                    font_family,
                    font_size,
                    max_width_inches=max_width,
                )
            elif content is not None and hasattr(content, "text"):
                bbox = self._measurer.measure_text(
                    content.text,
                    font_family,
                    font_size,
                    max_width_inches=max_width,
                )
            else:
                # Non-text elements (chart, table, image) get default size
                bbox = BoundingBox(
                    width_inches=max_width,
                    height_inches=4.0,
                )

            prev = measurements.get(region_name)
            if prev is None:
                measurements[region_name] = bbox
            else:
                # Stack: same region holds several elements
                measurements[region_name] = BoundingBox(
                    width_inches=max(prev.width_inches, bbox.width_inches),
                    height_inches=prev.height_inches + stack_gap + bbox.height_inches,
                )

        return measurements

    def _get_font_settings(
        self,
        region_name: str,
        master: Any | None,
        theme: Any,
    ) -> tuple[str, int]:
        """Get font family and size for a region.

        Checks slide master first, falls back to theme typography defaults.
        """
        if master is not None:
            style = master.regions.get(region_name)
            if style is not None:
                family = style.font_family or theme.typography.heading_family
                size = style.font_size or theme.typography.scale.get("body", 18)
                return family, size

        # Fallback to theme defaults
        region_to_scale: dict[str, str] = {
            "title": "h2",
            "subtitle": "subtitle",
            "bullets": "body",
            "content": "body",
            "footnote": "footnote",
            "chart_area": "body",
            "table_area": "body",
            "image_area": "body",
            "stat_cards": "body",
        }
        scale_key = region_to_scale.get(region_name, "body")

        if scale_key.startswith("h"):
            family = theme.typography.heading_family
        else:
            family = theme.typography.body_family

        size = theme.typography.scale.get(scale_key, 18)
        return family, size

    def _apply_positions(
        self,
        slide: Any,
        positions: dict[str, ResolvedPosition],
    ) -> None:
        """Apply resolved positions to slide elements as Position objects.

        Uses the same element->region assignment as the measuring pass.
        When several elements share one region they are stacked vertically
        inside it (even split with a small gap) instead of overlapping.
        """
        from modelforge.deck.ir.elements.base import Position

        groups: dict[str, list[Any]] = {}
        for elem, region_name in assign_element_regions(slide, set(positions.keys())):
            if region_name is None:
                continue
            if positions.get(region_name) is None:
                continue
            groups.setdefault(region_name, []).append(elem)

        for region_name, elems in groups.items():
            pos = positions[region_name]
            if len(elems) == 1:
                elems[0].position = Position(
                    x=pos.x,
                    y=pos.y,
                    width=pos.width,
                    height=pos.height,
                )
                continue

            # Stack multiple elements vertically within the region
            gap = 0.1
            each_height = max(
                (pos.height - gap * (len(elems) - 1)) / len(elems), 0.2
            )
            for i, elem in enumerate(elems):
                elem.position = Position(
                    x=pos.x,
                    y=pos.y + i * (each_height + gap),
                    width=pos.width,
                    height=each_height,
                )

    def _fallback_positions(
        self,
        regions: list[Any],
        grid: GridSystem,
    ) -> dict[str, ResolvedPosition]:
        """Create fallback positions when constraints are infeasible.

        Distributes regions evenly in the content area.
        """
        n = len(regions)
        if n == 0:
            return {}

        region_height = grid.content_height / n
        result: dict[str, ResolvedPosition] = {}

        for i, region in enumerate(regions):
            result[region.name] = ResolvedPosition(
                x=grid.content_left,
                y=grid.content_top + i * region_height,
                width=grid.content_width,
                height=region_height,
            )

        return result

"""Section divider layout pattern — centered title and subtitle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import kiwisolver

from modelforge.deck.layout.patterns.base import BaseLayoutPattern
from modelforge.deck.layout.types import BoundingBox, LayoutRegion

if TYPE_CHECKING:
    from modelforge.deck.layout.grid import GridSystem
    from modelforge.deck.themes.types import ResolvedTheme


class SectionDividerPattern(BaseLayoutPattern):
    """Layout for section dividers, key messages, and quote slides.

    Title, subtitle, and optional body content centered horizontally and
    vertically in the content area. Large title (h1 scale), smaller subtitle,
    body content (body_text / bullet_list) below.

    Regions:
        - title: Centered, large.
        - subtitle: Centered, below title.
        - content: Centered, below subtitle (zero height when unused).
    """

    def create_regions(self) -> list[LayoutRegion]:
        return [
            LayoutRegion("title"),
            LayoutRegion("subtitle"),
            LayoutRegion("content"),
        ]

    def create_constraints(
        self,
        regions: list[LayoutRegion],
        grid: GridSystem,
        measurements: dict[str, BoundingBox],
        theme: ResolvedTheme,
    ) -> list[Any]:
        title = self._region_by_name(regions, "title")
        subtitle = self._region_by_name(regions, "subtitle")
        content = self._region_by_name(regions, "content")
        assert title is not None and subtitle is not None and content is not None

        constraints = self._base_constraints(regions, grid)
        gap = theme.spacing.section_gap

        title_meas = measurements.get("title", BoundingBox(width_inches=10.0, height_inches=1.2))
        subtitle_meas = measurements.get("subtitle", BoundingBox(width_inches=10.0, height_inches=0.5))
        content_meas = measurements.get("content", BoundingBox(width_inches=10.0, height_inches=0.0))

        # Full width for all three
        constraints.extend(self._full_width_constraint(title, grid))
        constraints.extend(self._full_width_constraint(subtitle, grid))
        constraints.extend(self._full_width_constraint(content, grid))

        # Heights from measurements
        constraints.append(
            (title.height == title_meas.height_inches) | kiwisolver.strength.strong
        )
        constraints.append(
            (subtitle.height == subtitle_meas.height_inches) | kiwisolver.strength.strong
        )
        constraints.append(
            (content.height == content_meas.height_inches) | kiwisolver.strength.strong
        )

        # Vertically center the title+subtitle+content block
        total_block_height = title_meas.height_inches + gap + subtitle_meas.height_inches
        if content_meas.height_inches > 0:
            total_block_height += gap + content_meas.height_inches
        block_top = grid.content_top + max(
            (grid.content_height - total_block_height) / 2, 0.0
        )
        constraints.append(
            (title.top == block_top) | kiwisolver.strength.medium
        )

        # Subtitle below title, content below subtitle, with section gap
        constraints.append(self._spacing_constraint(title, subtitle, gap))
        constraints.append(self._spacing_constraint(subtitle, content, gap))

        return constraints

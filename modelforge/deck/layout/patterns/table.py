"""Table slide layout pattern — title, table area, footnote."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import kiwisolver

from modelforge.deck.layout.patterns.base import BaseLayoutPattern
from modelforge.deck.layout.types import BoundingBox, LayoutRegion

if TYPE_CHECKING:
    from modelforge.deck.layout.grid import GridSystem
    from modelforge.deck.themes.types import ResolvedTheme


class TableSlidePattern(BaseLayoutPattern):
    """Layout for table slides: title, optional body content, full-width
    flexible table area, footnote.

    Regions:
        - title: Full width at top.
        - content: Full width below title (body text; zero height when unused).
        - table_area: Full width, flexible height.
        - footnote: Full width at bottom.
    """

    def create_regions(self) -> list[LayoutRegion]:
        return [
            LayoutRegion("title"),
            LayoutRegion("content"),
            LayoutRegion("table_area"),
            LayoutRegion("footnote"),
        ]

    def create_constraints(
        self,
        regions: list[LayoutRegion],
        grid: GridSystem,
        measurements: dict[str, BoundingBox],
        theme: ResolvedTheme,
    ) -> list[Any]:
        title = self._region_by_name(regions, "title")
        content = self._region_by_name(regions, "content")
        table = self._region_by_name(regions, "table_area")
        footnote = self._region_by_name(regions, "footnote")
        assert all(r is not None for r in [title, content, table, footnote])

        constraints = self._base_constraints(regions, grid)
        gap = theme.spacing.element_gap

        # Title at top, full width
        constraints.extend(self._full_width_constraint(title, grid))
        constraints.append(
            (title.top == grid.content_top) | kiwisolver.strength.required
        )
        title_meas = measurements.get("title", BoundingBox(width_inches=10.0, height_inches=0.6))
        constraints.append(
            (title.height == title_meas.height_inches) | kiwisolver.strength.strong
        )

        # Content (body text): full width, below title, zero height when unused
        constraints.extend(self._full_width_constraint(content, grid))
        constraints.append(self._spacing_constraint(title, content, gap))
        content_meas = measurements.get("content", BoundingBox(width_inches=10.0, height_inches=0.0))
        constraints.append(
            (content.height == content_meas.height_inches) | kiwisolver.strength.strong
        )

        # Table area: full width, flexible height, below content
        constraints.extend(self._full_width_constraint(table, grid))
        constraints.append(self._spacing_constraint(content, table, gap))

        table_meas = measurements.get("table_area", BoundingBox(width_inches=10.0, height_inches=3.5))
        constraints.append(
            (table.height == table_meas.height_inches) | kiwisolver.strength.medium
        )

        # Footnote at bottom, full width
        constraints.extend(self._full_width_constraint(footnote, grid))
        footnote_meas = measurements.get("footnote", BoundingBox(width_inches=10.0, height_inches=0.3))
        constraints.append(
            (footnote.height == footnote_meas.height_inches) | kiwisolver.strength.strong
        )
        constraints.append(self._spacing_constraint(table, footnote, gap))
        constraints.append(
            (footnote.bottom <= grid.content_bottom) | kiwisolver.strength.required
        )

        return constraints

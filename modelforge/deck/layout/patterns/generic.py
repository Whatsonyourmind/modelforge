"""Generic fallback layout pattern — title and content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import kiwisolver

from modelforge.deck.layout.patterns.base import BaseLayoutPattern
from modelforge.deck.layout.types import BoundingBox, LayoutRegion

if TYPE_CHECKING:
    from modelforge.deck.layout.grid import GridSystem
    from modelforge.deck.themes.types import ResolvedTheme


class GenericPattern(BaseLayoutPattern):
    """Fallback layout for any slide type without a dedicated pattern.

    Vertical stack: title at top, body content below, bullet lists below
    that. Regions that have nothing assigned collapse to zero height.

    Regions:
        - title: Full width at top.
        - content: Full width, below title (body text / charts / tables).
        - bullets: Full width, below content (bullet / numbered lists).
    """

    def create_regions(self) -> list[LayoutRegion]:
        return [
            LayoutRegion("title"),
            LayoutRegion("content"),
            LayoutRegion("bullets"),
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
        bullets = self._region_by_name(regions, "bullets")
        assert title is not None and content is not None and bullets is not None

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

        # Content: full width, below title. Default 4.0in tall when measured
        # content exists historically; collapses to zero when nothing is
        # assigned so the bullets region moves up.
        constraints.extend(self._full_width_constraint(content, grid))
        constraints.append(self._spacing_constraint(title, content, gap))

        content_meas = measurements.get("content", BoundingBox(width_inches=10.0, height_inches=0.0))
        constraints.append(
            (content.height == content_meas.height_inches) | kiwisolver.strength.medium
        )
        constraints.append(
            (content.bottom <= grid.content_bottom) | kiwisolver.strength.required
        )

        # Bullets: full width, below content; zero height when unused
        constraints.extend(self._full_width_constraint(bullets, grid))
        constraints.append(self._spacing_constraint(content, bullets, gap))

        bullets_meas = measurements.get("bullets", BoundingBox(width_inches=10.0, height_inches=0.0))
        constraints.append(
            (bullets.height == bullets_meas.height_inches) | kiwisolver.strength.medium
        )
        constraints.append(
            (bullets.bottom <= grid.content_bottom) | kiwisolver.strength.required
        )

        return constraints

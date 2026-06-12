"""Stats callout layout pattern — title and stat cards region."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import kiwisolver

from modelforge.deck.layout.patterns.base import BaseLayoutPattern
from modelforge.deck.layout.types import BoundingBox, LayoutRegion

if TYPE_CHECKING:
    from modelforge.deck.layout.grid import GridSystem
    from modelforge.deck.themes.types import ResolvedTheme


class StatsCalloutPattern(BaseLayoutPattern):
    """Layout for stats/KPI slides: title and stat cards region.

    The stat_cards region is full width below the title. The renderer
    subdivides it internally into individual stat cards.

    Regions:
        - title: Full width at top.
        - stat_cards: Full width below title, fills remaining space.
        - content: Full width below stat cards (commentary; zero height when unused).
    """

    def create_regions(self) -> list[LayoutRegion]:
        return [
            LayoutRegion("title"),
            LayoutRegion("stat_cards"),
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
        stats = self._region_by_name(regions, "stat_cards")
        content = self._region_by_name(regions, "content")
        assert title is not None and stats is not None and content is not None

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

        # Stat cards: full width, fills remaining space below title
        constraints.extend(self._full_width_constraint(stats, grid))
        constraints.append(self._spacing_constraint(title, stats, gap))

        stats_meas = measurements.get("stat_cards", BoundingBox(width_inches=10.0, height_inches=4.0))
        constraints.append(
            (stats.height == stats_meas.height_inches) | kiwisolver.strength.medium
        )
        constraints.append(
            (stats.bottom <= grid.content_bottom) | kiwisolver.strength.required
        )

        # Content (commentary): full width below stat cards, zero when unused
        constraints.extend(self._full_width_constraint(content, grid))
        content_meas = measurements.get("content", BoundingBox(width_inches=10.0, height_inches=0.0))
        constraints.append(
            (content.height == content_meas.height_inches) | kiwisolver.strength.strong
        )
        constraints.append(self._spacing_constraint(stats, content, gap))
        constraints.append(
            (content.bottom <= grid.content_bottom) | kiwisolver.strength.required
        )

        return constraints

"""Title slide layout pattern — centered title and subtitle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import kiwisolver

from modelforge.deck.layout.patterns.base import BaseLayoutPattern
from modelforge.deck.layout.types import BoundingBox, LayoutRegion

if TYPE_CHECKING:
    from modelforge.deck.layout.grid import GridSystem
    from modelforge.deck.themes.types import ResolvedTheme


class TitleSlidePattern(BaseLayoutPattern):
    """Layout for title slides: large centered title, subtitle below.

    Regions:
        - title: Centered in top 60% of content area, full width.
        - subtitle: Below title with section_gap spacing, centered.
        - content: Below subtitle (byline / body text; zero height when unused).
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

        title_meas = measurements.get("title", BoundingBox(width_inches=10.0, height_inches=1.0))
        subtitle_meas = measurements.get("subtitle", BoundingBox(width_inches=10.0, height_inches=0.5))
        content_meas = measurements.get("content", BoundingBox(width_inches=10.0, height_inches=0.0))

        # Full width for all
        constraints.extend(self._full_width_constraint(title, grid))
        constraints.extend(self._full_width_constraint(subtitle, grid))
        constraints.extend(self._full_width_constraint(content, grid))

        # Title height from measurement (strong)
        constraints.append(
            (title.height == title_meas.height_inches) | kiwisolver.strength.strong
        )

        # Subtitle height from measurement (strong)
        constraints.append(
            (subtitle.height == subtitle_meas.height_inches) | kiwisolver.strength.strong
        )

        # Content (byline) height from measurement (strong)
        constraints.append(
            (content.height == content_meas.height_inches) | kiwisolver.strength.strong
        )

        # Title centered vertically in top 60% of content area
        top_zone_height = grid.content_height * 0.6
        title_center_y = grid.content_top + (top_zone_height - title_meas.height_inches) / 2
        constraints.append(
            (title.top == title_center_y) | kiwisolver.strength.medium
        )

        # Subtitle below title, content below subtitle, with section gap
        constraints.append(self._spacing_constraint(title, subtitle, gap))
        constraints.append(self._spacing_constraint(subtitle, content, gap))

        return constraints

"""Deal overview slide renderer -- one-pager with key metrics and traffic lights."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from modelforge.deck.ir.elements.base import Position
from modelforge.deck.rendering.slide_renderers.base import (
    BaseFinanceSlideRenderer,
    _infer_format,
)

if TYPE_CHECKING:
    from pptx.slide import Slide

    from modelforge.deck.ir.slides.base import BaseSlide
    from modelforge.deck.themes.types import ResolvedTheme

logger = logging.getLogger(__name__)

# Known traffic-light status keywords.
_TRAFFIC_STATUSES = frozenset({"green", "yellow", "red"})


class DealOverviewRenderer(BaseFinanceSlideRenderer):
    """Renders deal overview one-pager with metrics grid and traffic-light indicators.

    Consumes BOTH contract shapes:
        - table elements (metrics table + optional traffic-light status table),
        - text elements (bullet_list / numbered_list / body_text) and
          metric_group KPI strips, as emitted by the IC-memo and teaser
          composers.
    Nothing the composer emits is silently dropped.
    """

    def render(self, slide: Slide, ir_slide: BaseSlide, theme: ResolvedTheme) -> None:
        elements = ir_slide.elements

        # Title
        title = self._find_heading(elements) or "Deal Overview"
        title_pos = Position(x=0.75, y=0.4, width=11.8, height=0.8)
        self._add_title(slide, title, theme, title_pos)

        # Find all table elements
        tables = self._find_table_elements(elements)

        # Classify tables: metrics table vs status table
        metrics_table = None
        status_table = None

        for tbl in tables:
            content = tbl.content
            if self._is_status_table(content):
                status_table = tbl
            elif metrics_table is None:
                metrics_table = tbl

        # Render metrics table
        if metrics_table:
            content = metrics_table.content
            col_formats = [_infer_format(h) for h in content.headers]
            m_pos = Position(x=0.75, y=1.5, width=5.5, height=3.5)
            self._add_table(
                slide,
                headers=content.headers,
                rows=[list(r) for r in content.rows],
                theme=theme,
                position=m_pos,
                column_formats=col_formats,
                footer_row=list(content.footer_row) if content.footer_row else None,
            )

        # Render status indicators with traffic lights
        if status_table:
            content = status_table.content
            # Render as a table first
            s_pos = Position(x=7.0, y=1.5, width=4.5, height=2.5)
            self._add_table(
                slide,
                headers=content.headers,
                rows=[list(r) for r in content.rows],
                theme=theme,
                position=s_pos,
            )

            # Add traffic-light circles next to each status row
            for row_idx, row in enumerate(content.rows):
                # Look for a status value in the row
                for val in row:
                    if isinstance(val, str) and val.lower() in _TRAFFIC_STATUSES:
                        indicator_pos = Position(
                            x=11.8,
                            y=2.0 + row_idx * 0.6,
                            width=0.25,
                            height=0.25,
                        )
                        self._add_shape_indicator(slide, val, indicator_pos)
                        break

        # Render text content (bullet_list / numbered_list / body_text) and
        # metric_group strips — the composer contract for IC-memo deal
        # overview and teaser company snapshot slides.
        from modelforge.deck.rendering.element_renderers import render_element

        text_elements = self._find_text_elements(elements)
        metric_groups = []
        for e in elements:
            etype = getattr(e, "type", None)
            if hasattr(etype, "value"):
                etype = etype.value
            if etype == "metric_group":
                metric_groups.append(e)

        # Text below tables (if any), otherwise filling the content area.
        y_offset = 5.2 if tables else 1.5
        text_bottom = 6.9 if not metric_groups else 5.0
        if text_elements:
            n = len(text_elements)
            available = max(text_bottom - y_offset, 0.5)
            each_height = max((available - 0.15 * (n - 1)) / n, 0.5)
            for elem in text_elements:
                pos = Position(x=0.75, y=y_offset, width=11.8, height=each_height)
                render_element(slide, elem, pos, theme)
                y_offset += each_height + 0.15

        # KPI strip along the bottom of the slide.
        kpi_y = 5.2
        for elem in metric_groups:
            pos = Position(x=0.75, y=kpi_y, width=11.8, height=1.6)
            render_element(slide, elem, pos, theme)
            kpi_y += 1.75

    @staticmethod
    def _is_status_table(content) -> bool:
        """Check if table contains traffic-light status values."""
        for row in content.rows:
            for val in row:
                if isinstance(val, str) and val.lower() in _TRAFFIC_STATUSES:
                    return True
        return False


__all__ = ["DealOverviewRenderer"]

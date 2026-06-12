"""Waterfall chart slide renderer -- delegates to the chart-renderer registry.

E2 extraction note:
    The original DeckForge implementation delegated directly to the
    Plotly-based ``WaterfallChartRenderer`` (``chart_renderers/waterfall.py``),
    which was EXCLUDED from extraction (plotly/kaleido dependency).
    Delegation now goes through the registry (``CHART_RENDERERS``), which
    currently maps "waterfall" to ``PendingNativeChartRenderer``; the
    NativeCharts phase fills the gap in ``chart_renderers/native_ib.py`` and
    this slide renderer picks it up transparently.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from modelforge.deck.ir.elements.base import Position
from modelforge.deck.rendering.chart_renderers import CHART_RENDERERS
from modelforge.deck.rendering.slide_renderers.base import BaseFinanceSlideRenderer

if TYPE_CHECKING:
    from pptx.slide import Slide

    from modelforge.deck.ir.slides.base import BaseSlide
    from modelforge.deck.themes.types import ResolvedTheme

logger = logging.getLogger(__name__)


class WaterfallSlideRenderer(BaseFinanceSlideRenderer):
    """Renders a waterfall chart slide by delegating to the registry's waterfall renderer."""

    def render(self, slide: Slide, ir_slide: BaseSlide, theme: ResolvedTheme) -> None:
        elements = ir_slide.elements

        # Title
        title = self._find_heading(elements) or "Waterfall Chart"
        title_pos = Position(x=0.75, y=0.4, width=11.8, height=0.8)
        self._add_title(slide, title, theme, title_pos)

        # Find chart element
        chart_elem = self._find_chart_element(elements, chart_type="waterfall")
        if chart_elem is None:
            # Try any chart element
            chart_elem = self._find_chart_element(elements)

        if chart_elem is None:
            raise ValueError(
                "WaterfallSlideRenderer: no chart element on the "
                "waterfall_chart slide — the composer must emit the "
                "waterfall chart data."
            )

        # Leave room for commentary text below the chart when present.
        text_elements = self._find_text_elements(elements)
        chart_height = 4.6 if text_elements else 5.0

        chart_data = chart_elem.chart_data
        chart_pos = Position(x=0.75, y=1.5, width=11.8, height=chart_height)

        # Delegate to the registry's waterfall renderer (native rewrite
        # pending -- see chart_renderers/native_ib.py).
        CHART_RENDERERS["waterfall"].render(slide, chart_data, chart_pos, theme)

        # Commentary (e.g. capital-activity summary) below the chart — the
        # composer emits it, so it must be displayed, not dropped.
        if text_elements:
            from modelforge.deck.rendering.element_renderers import render_element

            y_offset = 1.5 + chart_height + 0.15
            for elem in text_elements:
                pos = Position(x=0.75, y=y_offset, width=11.8, height=0.55)
                render_element(slide, elem, pos, theme)
                y_offset += 0.6


__all__ = ["WaterfallSlideRenderer"]

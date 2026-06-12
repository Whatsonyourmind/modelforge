"""Chart renderer registry -- maps chart_type strings to renderer instances.

Usage:
    from modelforge.deck.rendering.chart_renderers import render_chart
    render_chart(slide, chart_data, position, theme)

E2 extraction note:
    The NATIVE (editable python-pptx) chart renderers were extracted from
    DeckForge unchanged. The STATIC chart renderers (waterfall, funnel,
    treemap, tornado, football_field, sensitivity_table, heatmap, sankey,
    gantt, sunburst) depended on plotly/kaleido (``static_base.py`` + one
    module each) and were EXCLUDED from the extraction.

    NativeCharts phase: the four signature IB chart types (waterfall,
    tornado, football_field, sensitivity_table) now have native python-pptx
    implementations in ``native_ib.py`` and are registered below. The
    remaining six (funnel, treemap, heatmap, sankey, gantt, sunburst) are
    still mapped to ``PendingNativeChartRenderer``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modelforge.deck.rendering.chart_renderers.base import BaseChartRenderer
from modelforge.deck.rendering.chart_renderers.category import (
    AreaChartRenderer,
    BarChartRenderer,
    LineChartRenderer,
)
from modelforge.deck.rendering.chart_renderers.combo import ComboChartRenderer
from modelforge.deck.rendering.chart_renderers.native_ib import (
    FootballFieldChartRenderer,
    SensitivityTableRenderer,
    TornadoChartRenderer,
    WaterfallChartRenderer,
)
from modelforge.deck.rendering.chart_renderers.placeholder import PlaceholderChartRenderer
from modelforge.deck.rendering.chart_renderers.proportional import (
    DonutChartRenderer,
    PieChartRenderer,
)
from modelforge.deck.rendering.chart_renderers.radar import RadarChartRenderer
from modelforge.deck.rendering.chart_renderers.scatter import (
    BubbleChartRenderer,
    ScatterChartRenderer,
)

if TYPE_CHECKING:
    from pptx.slide import Slide

    from modelforge.deck.ir.elements.base import Position
    from modelforge.deck.themes.types import ResolvedTheme

__all__ = [
    "CHART_RENDERERS",
    "BaseChartRenderer",
    "FootballFieldChartRenderer",
    "PendingNativeChartRenderer",
    "SensitivityTableRenderer",
    "TornadoChartRenderer",
    "WaterfallChartRenderer",
    "render_chart",
]


# ── REGISTRY GAP (E2 extraction) ──────────────────────────────────────────────
# The original DeckForge renderers for the chart types below were static
# Plotly/kaleido PNG exporters. plotly/kaleido are intentionally NOT
# modelforge dependencies, so those modules were excluded from extraction.
# The NativeCharts phase will implement native python-pptx replacements in
# ``native_ib.py`` and swap these stubs out of the registry.


class PendingNativeChartRenderer(BaseChartRenderer):
    """Stub for an excluded static (Plotly-based) chart renderer.

    ``render()`` raises NotImplementedError until the NativeCharts phase
    fills the gap (see ``native_ib.py``).
    """

    def __init__(self, chart_type: str) -> None:
        self.chart_type = chart_type

    def render(
        self,
        slide: Slide,
        chart_data: object,
        position: Position,
        theme: ResolvedTheme,
    ) -> None:
        raise NotImplementedError(
            "native rewrite pending \u2014 see deck/rendering/chart_renderers/native_ib.py"
        )


# ── Registry ──────────────────────────────────────────────────────────────────

CHART_RENDERERS: dict[str, BaseChartRenderer] = {
    # Category-based (native editable)
    "bar": BarChartRenderer(),
    "stacked_bar": BarChartRenderer(),
    "grouped_bar": BarChartRenderer(),
    "horizontal_bar": BarChartRenderer(),
    "line": LineChartRenderer(),
    "multi_line": LineChartRenderer(),
    "area": AreaChartRenderer(),
    "stacked_area": AreaChartRenderer(),
    # Proportional (native editable)
    "pie": PieChartRenderer(),
    "donut": DonutChartRenderer(),
    # Scatter/Bubble (native editable)
    "scatter": ScatterChartRenderer(),
    "bubble": BubbleChartRenderer(),
    # Combo (native editable -- bar + line overlay)
    "combo": ComboChartRenderer(),
    # Radar (native editable)
    "radar": RadarChartRenderer(),
    # ── Signature IB charts (native python-pptx -- NativeCharts phase) ───────
    # Implemented in native_ib.py: invisible-base stacked-bar trick for
    # waterfall/tornado/football_field; sensitivity_table is a native table.
    "waterfall": WaterfallChartRenderer(),
    "tornado": TornadoChartRenderer(),
    "football_field": FootballFieldChartRenderer(),
    "sensitivity_table": SensitivityTableRenderer(),
    # ── REGISTRY GAP: static Plotly renderers excluded (E2) ──────────────────
    # Native rewrites pending -- see native_ib.py (NativeCharts phase).
    "funnel": PendingNativeChartRenderer("funnel"),
    "treemap": PendingNativeChartRenderer("treemap"),
    "heatmap": PendingNativeChartRenderer("heatmap"),
    "sankey": PendingNativeChartRenderer("sankey"),
    "gantt": PendingNativeChartRenderer("gantt"),
    "sunburst": PendingNativeChartRenderer("sunburst"),
}


def render_chart(
    slide: Slide,
    chart_data: object,
    position: Position,
    theme: ResolvedTheme,
) -> None:
    """Dispatch chart rendering to the appropriate renderer.

    Looks up chart_data.chart_type in CHART_RENDERERS and calls render().
    Falls back to PlaceholderChartRenderer for unknown types.
    """
    chart_type = getattr(chart_data, "chart_type", "unknown")
    renderer = CHART_RENDERERS.get(chart_type, PlaceholderChartRenderer())
    renderer.render(slide, chart_data, position, theme)

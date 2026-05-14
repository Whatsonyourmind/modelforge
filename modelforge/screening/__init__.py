"""Deal-screening engine.

Filter a list of deal specs (YAML files) by criteria — IRR threshold, leverage
ceiling, sector, geography, deal size, vintage — without building each model.

Per Rogo's "Screenings" feature parity:
    https://rogo.ai/news/march-product-update

The screener works at the spec layer: it parses YAML, extracts headline
financial metrics, evaluates filter conditions, ranks by configurable
weights, returns the top-N matching deals.

Usage::

    from modelforge.screening import screen
    results = screen(
        spec_dir="datarooms/",
        filters={"sector": "industrials", "ebitda_margin_min": 0.20},
        rank_by={"irr_base": 0.5, "leverage_max": -0.3, "deal_size": 0.2},
        top_n=10,
    )
"""

from modelforge.screening.engine import screen, ScreenResult, ScreenCriteria

__all__ = ["screen", "ScreenResult", "ScreenCriteria"]

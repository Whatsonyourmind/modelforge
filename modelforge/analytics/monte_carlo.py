"""Monte Carlo simulation on the primary output.

Given the same factor list used for the sensitivity tornado, draws
``n_runs`` random samples per factor from a configurable distribution
(triangular by default) and aggregates them into a distribution over
the primary output. Results render as a MonteCarlo sheet with stats
(P5/P25/P50/P75/P95, mean, std) and a native Excel histogram chart.

Like the sensitivity tornado, MC uses the per-factor elasticity
coefficient to map a driver shock to an output delta — an approximation
that ships across all 8 templates without a per-template shadow engine.
v0.4.2 will replace with exact workbook recomputation. Results are
written as values (not formulas) per the PRD AC for US-002.

Distributions
-------------
* ``triangular(low_shock, 0, high_shock)`` — default. Captures asymmetry
  in the factor's shock envelope directly.
* ``normal(mean=0, std=(high_shock-low_shock)/4)`` — assumes ±2σ covers
  the declared range.
* ``lognormal(mean=0, sigma=(high_shock-low_shock)/4)`` — for drivers
  that must stay non-negative (rates, multiples).

All factors are drawn independently. Correlation structure is a v0.4.2
follow-up once shadow engines enable joint distributions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from openpyxl import load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.analytics.factors import SensitivityFactor, default_factors_for
from modelforge.analytics.sensitivity import (
    PrimaryOutputLoc,
    _ELASTICITY_REGISTRY,
    _driver_exists,
    _elasticity_for,
    _find_primary_output,
)
from modelforge.builder import styles


Distribution = Literal["triangular", "normal", "lognormal"]


@dataclass
class MCConfig:
    n_runs: int = 1000
    distribution: Distribution = "triangular"
    seed: int = 20260417  # deterministic by default


@dataclass
class MCResult:
    n_runs: int
    distribution: Distribution
    samples: np.ndarray  # shape (n_runs,) — simulated output deltas as fractional
    factor_contributions: dict[str, np.ndarray]  # per-factor delta draws

    @property
    def mean(self) -> float:
        return float(np.mean(self.samples))

    @property
    def std(self) -> float:
        return float(np.std(self.samples))

    def percentile(self, p: float) -> float:
        return float(np.percentile(self.samples, p))


def _draw_shocks(
    rng: np.random.Generator,
    low: float,
    high: float,
    n: int,
    distribution: Distribution,
) -> np.ndarray:
    if distribution == "triangular":
        return rng.triangular(left=low, mode=0.0, right=high, size=n)
    if distribution == "normal":
        sigma = (high - low) / 4.0 if high > low else abs(high) / 2.0
        return rng.normal(loc=0.0, scale=max(sigma, 1e-9), size=n)
    if distribution == "lognormal":
        sigma = (high - low) / 4.0 if high > low else abs(high) / 2.0
        # Shift so mean(shock)=0 approximately
        draws = rng.lognormal(mean=0.0, sigma=max(sigma, 1e-9), size=n)
        return draws - draws.mean()
    raise ValueError(f"Unknown distribution: {distribution}")


def run_monte_carlo(
    factors: list[SensitivityFactor],
    config: MCConfig,
) -> MCResult:
    """Simulate output deltas using per-factor elasticities.

    Output delta per draw = sum_i (elasticity_i * shock_i). This is a
    linear MC in the neighborhood of the base. Fractional — multiply by
    ``primary_output`` in the sheet to express as absolute delta.
    """
    rng = np.random.default_rng(config.seed)
    total = np.zeros(config.n_runs, dtype=float)
    contributions: dict[str, np.ndarray] = {}
    for f in factors:
        e = _elasticity_for(f.driver_name)
        shocks = _draw_shocks(rng, f.low_shock, f.high_shock,
                              config.n_runs, config.distribution)
        contrib = e * shocks
        contributions[f.driver_name] = contrib
        total += contrib
    return MCResult(
        n_runs=config.n_runs,
        distribution=config.distribution,
        samples=total,
        factor_contributions=contributions,
    )


# ─── Sheet emission ───────────────────────────────────────────────────────────


_SHEET_NAME = "MonteCarlo"
_N_BINS = 30


def _emit_sheet(
    wb,
    primary_loc: PrimaryOutputLoc,
    factors: list[SensitivityFactor],
    result: MCResult,
) -> Worksheet:
    if _SHEET_NAME in wb.sheetnames:
        del wb[_SHEET_NAME]
    ws = wb.create_sheet(_SHEET_NAME)

    for col, w in {"A": 14, "B": 32, "C": 14, "D": 14, "E": 14,
                   "F": 14, "G": 14, "H": 14}.items():
        ws.column_dimensions[col].width = w

    # ── Title block
    ws.cell(row=1, column=1, value="Monte Carlo").font = styles.font_title
    ws.cell(row=2, column=1, value="Simulazione Monte Carlo").font = styles.font_label_it
    ws.cell(
        row=3, column=1,
        value=(
            f"{result.n_runs:,}-run {result.distribution} simulation on "
            f"{primary_loc.label}. Factors drawn independently; per-factor "
            f"elasticities define the linear response. Output deltas are "
            f"fractional — apply to base 'primary_output' named range to "
            f"express as absolute. v0.4.2 will replace elasticity heuristic "
            f"with exact workbook recompute per draw (and add correlation "
            f"structure)."
        ),
    ).font = styles.font_label_it

    # ── Base output reference
    ws.cell(row=5, column=1, value="Base output").font = styles.font_subheader
    ws.cell(row=5, column=2, value=primary_loc.label).font = styles.font_subheader
    c_base = ws.cell(row=5, column=3, value="=primary_output")
    styles.style_formula(c_base, number_format=styles.FMT_PCT_2DP)
    c_base.font = styles.font_subheader

    # ── Distribution stats
    stats_row = 8
    ws.cell(row=stats_row, column=1, value="Statistic").font = styles.font_header \
        if hasattr(styles, "font_header") else styles.font_subheader
    ws.cell(row=stats_row, column=2, value="Δ output (frac)")
    ws.cell(row=stats_row, column=3, value="Absolute output")
    for i, c in enumerate(("Statistic", "Δ output (frac)",
                           "Absolute output"), start=1):
        cell = ws.cell(row=stats_row, column=i, value=c)
        styles.style_header(cell)

    rows = [
        ("Mean", result.mean),
        ("Std", result.std),
        ("P5", result.percentile(5)),
        ("P25", result.percentile(25)),
        ("P50 (median)", result.percentile(50)),
        ("P75", result.percentile(75)),
        ("P95", result.percentile(95)),
        ("Min", float(np.min(result.samples))),
        ("Max", float(np.max(result.samples))),
    ]
    for i, (label, frac) in enumerate(rows):
        r = stats_row + 1 + i
        ws.cell(row=r, column=1, value=label).font = styles.font_subheader
        # Col B — fractional delta (hardcoded, numeric)
        fc = ws.cell(row=r, column=2, value=frac)
        styles.style_input(fc, number_format=styles.FMT_PCT_2DP)
        fc.comment = Comment(
            f"Computed from {result.n_runs:,} {result.distribution} draws "
            f"across {len(factors)} factors. Seed={20260417}. "
            f"Rebuild to regenerate.",
            "ModelForge",
        )
        # Col C — absolute (formula on base * (1 + frac))
        ac = ws.cell(row=r, column=3, value=f"=primary_output*(1+B{r})")
        styles.style_formula(ac, number_format=styles.FMT_PCT_2DP)

    # ── Histogram bins
    hist_row = stats_row + 1 + len(rows) + 2
    ws.cell(row=hist_row, column=1, value="Histogram bins").font = styles.font_subheader
    for i, c in enumerate(("Bin low (Δ)", "Bin high (Δ)", "Count"), start=1):
        cell = ws.cell(row=hist_row + 1, column=i, value=c)
        styles.style_header(cell)

    counts, edges = np.histogram(result.samples, bins=_N_BINS)
    for i in range(_N_BINS):
        r = hist_row + 2 + i
        ws.cell(row=r, column=1, value=float(edges[i])).number_format = styles.FMT_PCT_2DP
        ws.cell(row=r, column=2, value=float(edges[i + 1])).number_format = styles.FMT_PCT_2DP
        cc = ws.cell(row=r, column=3, value=int(counts[i]))
        cc.number_format = styles.FMT_INTEGER
    hist_first = hist_row + 2
    hist_last = hist_row + 2 + _N_BINS - 1

    # ── Histogram chart
    chart = BarChart()
    chart.type = "col"
    chart.style = 11
    chart.title = f"Monte Carlo — Δ {primary_loc.label}"
    chart.y_axis.title = "Count"
    chart.x_axis.title = "Δ output (fractional)"
    count_ref = Reference(ws, min_col=3, min_row=hist_row + 1,
                          max_col=3, max_row=hist_last)
    bins_ref = Reference(ws, min_col=1, min_row=hist_first,
                         max_col=1, max_row=hist_last)
    chart.add_data(count_ref, titles_from_data=True)
    chart.set_categories(bins_ref)
    chart.height = 9
    chart.width = 18
    chart.dataLabels = DataLabelList(showVal=False)
    ws.add_chart(chart, f"E{stats_row}")

    ws.freeze_panes = "A9"
    ws.print_title_rows = f"{stats_row}:{stats_row}"
    return ws


# ─── Public API ───────────────────────────────────────────────────────────────


def append_monte_carlo_sheet(
    xlsx_path: Path | str,
    spec,
    factors: Optional[list[SensitivityFactor]] = None,
    config: Optional[MCConfig] = None,
) -> Optional[Path]:
    """Append a MonteCarlo sheet + histogram chart to a built workbook.

    Returns the xlsx path on success, or None if sensitivity's primary
    output couldn't be located (same degradation contract).
    """
    xlsx_path = Path(xlsx_path)
    wb = load_workbook(xlsx_path, data_only=False, keep_links=True)
    primary_loc = _find_primary_output(wb)
    if primary_loc is None:
        return None

    if factors is None:
        factors = default_factors_for(getattr(spec, "model_type", ""))
    applicable = [f for f in factors if _driver_exists(wb, f.driver_name)]
    if not applicable:
        return None

    if config is None:
        config = MCConfig()

    result = run_monte_carlo(applicable, config)
    _emit_sheet(wb, primary_loc, applicable, result)
    wb.save(xlsx_path)
    return xlsx_path


__all__ = [
    "MCConfig",
    "MCResult",
    "run_monte_carlo",
    "append_monte_carlo_sheet",
]

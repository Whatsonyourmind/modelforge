"""Portfolio Review spec — Template 16 (v0.10 PREVIEW).

Quarterly portfolio review aggregator. Different shape from per-deal
templates: N portfolio companies × M monitoring metrics, in one workbook.

Used by MM credit funds and PE shops for quarterly portfolio committee
review. Surfaces the metrics that matter on review day: covenant cushion,
leverage trend, EBITDA actual-vs-plan, next covenant test, cash-trap status.

v0.10 PREVIEW — feature-complete spec, minimal renderer.
v0.11 adds: trend sparklines, covenant cushion heatmap, automated
exception flagging, narrative comment fields.

v0.12 — fund-level performance: capital-call / distribution / NAV cashflow
stream feeds a Fund Returns sheet (MOIC, DPI, RVPI, TVPI == DPI+RVPI, gross
IRR; net IRR/MOIC when 2/20-over-pref terms are supplied). The monitor is no
longer covenant-only.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from modelforge.spec.base import ModelMeta, Target


class PortcoLine(BaseModel):
    """One row of the portfolio review — one company, one quarter."""

    portco_id: str = Field(pattern=r"^PC-\d{3,}$")
    name: str
    sector: str = ""
    country: str = ""

    entry_date: Optional[date] = None
    entry_leverage: Optional[float] = Field(default=None, description="Net debt / EBITDA at entry")
    entry_ev: Optional[float] = Field(default=None, description="EV at entry, in spec.meta.unit_scale")
    entry_ebitda: Optional[float] = None

    current_leverage: Optional[float] = None
    current_ebitda_ltm: Optional[float] = None
    current_revenue_ltm: Optional[float] = None

    plan_ebitda_q: Optional[float] = Field(default=None, description="Current quarter EBITDA plan")
    actual_ebitda_q: Optional[float] = Field(default=None, description="Current quarter EBITDA actual")

    covenant_cushion_pct: Optional[float] = Field(
        default=None, ge=-100.0, le=500.0,
        description="Lowest covenant cushion across the package, in %",
    )
    next_covenant_test_date: Optional[date] = None
    cash_trap_active: bool = False

    rating_internal: Optional[Literal["1", "2", "3", "4", "5"]] = None
    """Internal portfolio rating, 1=outperform, 5=workout."""

    narrative: str = ""
    """Optional brief commentary for the IC."""


class FundCashflow(BaseModel):
    """One period of the fund's own (LP-facing) cashflow stream.

    Capital calls and distributions are entered as POSITIVE magnitudes (the
    sign convention for the IRR vector is applied by the builder: a period's
    net LP cashflow is ``distribution - capital_call``, and the terminal NAV is
    appended as a realisation inflow). ``nav`` is the fund's residual net asset
    value AT THE END of the period — only the final period's NAV enters TVPI /
    IRR as residual value (interim NAVs are carried for the J-curve / audit).
    """

    period: int = Field(ge=0, description="0-indexed period (year) of the fund's life")
    capital_call: float = Field(default=0.0, ge=0.0, description="Capital drawn this period (paid-in), positive")
    distribution: float = Field(default=0.0, ge=0.0, description="Cash distributed to LPs this period, positive")
    nav: float = Field(default=0.0, ge=0.0, description="Residual fund NAV at end of period, positive")


class PortfolioReviewSpec(BaseModel):
    """Quarterly portfolio review — N portcos × metrics matrix.

    The `target` field is required by the ingest pipeline shape convention
    (every template's first section is "target"); for the portfolio review
    it represents the FUND being reviewed rather than a specific deal subject.
    Optional in v0.10 — manual builds can pass meta + portfolio only.
    """

    model_type: Literal["portfolio_review"] = "portfolio_review"
    meta: ModelMeta
    target: Optional[Target] = None
    """The fund being reviewed. Optional for v0.10 manual builds; required
    when ingesting via the LLM-based dataroom pipeline."""

    review_quarter: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    """E.g. '2026-Q2'."""

    portfolio: list[PortcoLine] = Field(min_length=1)

    fund_name: str = ""
    fund_vintage: Optional[int] = None
    fund_aum: Optional[float] = None

    # ── Fund-level performance (v0.12) ───────────────────────────────────────
    fund_cashflows: list[FundCashflow] = Field(
        default_factory=list,
        description="Fund-level capital-call / distribution / NAV stream. When "
        "non-empty, the workbook emits a Fund Returns sheet (MOIC, DPI, RVPI, "
        "TVPI, gross & net IRR). Empty = covenant-monitor-only (back-compat).",
    )
    mgmt_fee_rate: Optional[float] = Field(
        default=None, ge=0.0, le=0.10,
        description="Annual management fee on committed capital (e.g. 0.02 = 2%). "
        "Drives the gross-to-net bridge when set with carry_rate.",
    )
    carry_rate: Optional[float] = Field(
        default=None, ge=0.0, le=0.50,
        description="Carried-interest rate (e.g. 0.20 = 20%) above the preferred return.",
    )
    pref_rate: Optional[float] = Field(
        default=None, ge=0.0, le=0.30,
        description="LP preferred return / hurdle (e.g. 0.08 = 8%), European whole-fund waterfall.",
    )
    fund_committed: Optional[float] = Field(
        default=None, gt=0.0,
        description="Committed capital for fee/carry base, in meta.unit_scale. "
        "Defaults to total capital called when omitted.",
    )

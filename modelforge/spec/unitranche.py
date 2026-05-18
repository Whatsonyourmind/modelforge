"""Unitranche LBO spec — Template 1.

Italian mid-market direct lending, most common deliverable.
Structure:
    - Operating projections (Revenue → EBITDA → EBIT → Net Income)
    - Debt structure (senior unitranche, optional super-senior RCF)
    - Covenants (leverage, ICR)
    - Returns (lender IRR, MoIC, APR)
    - Scenarios (WORST/BASE/BEST)

Every number here is either:
    - an Assumption (A-id, with rationale + confidence), OR
    - computed by a formula in the builder (not stored here)

The builder reads this spec and emits openpyxl cells with formulas,
named ranges, cell comments, and graph edges.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.risk_block import RiskAnalysisSpec
from modelforge.spec.base import (
    Assumption,
    Label,
    ModelMeta,
    Source,
    Target,
)


# ─────────────────────────────────────────────────────────────────────────────
# Projection horizon
# ─────────────────────────────────────────────────────────────────────────────


class ProjectionHorizon(BaseModel):
    historical_years: int = Field(ge=1, le=5, default=3)
    projection_years: int = Field(ge=3, le=10, default=7)  # Typical unitranche tenor

    @property
    def total_columns(self) -> int:
        return self.historical_years + self.projection_years


# ─────────────────────────────────────────────────────────────────────────────
# Operating projections (assumption-driven)
# ─────────────────────────────────────────────────────────────────────────────


class OperatingAssumptions(BaseModel):
    """Year-indexed operating drivers.

    Each driver is a single Assumption. For year-varying drivers, use a
    sequence keyed by projection year (Y1, Y2, ... YN).

    All growth/margin figures are decimals (0.05 = 5%).
    """

    # Growth: one assumption per projection year to allow realistic taper.
    revenue_growth_by_year: list[Assumption]

    # Margin trajectory: one per projection year.
    ebitda_margin_by_year: list[Assumption]

    # D&A as % of revenue.
    da_pct_revenue: Assumption

    # Capex as % of revenue (maintenance + growth split into two drivers).
    maintenance_capex_pct_revenue: Assumption
    growth_capex_pct_revenue: Assumption

    # Working capital (change in NWC as % of change in revenue).
    nwc_pct_revenue_delta: Assumption

    # Tax rate.
    effective_tax_rate: Assumption


# ─────────────────────────────────────────────────────────────────────────────
# Debt structure
# ─────────────────────────────────────────────────────────────────────────────


class ReferenceRate(BaseModel):
    """Benchmark rate feeding the margin."""

    name: Literal["EURIBOR_3M", "EURIBOR_6M", "ESTR", "SOFR", "SONIA"] = "EURIBOR_6M"
    rate_decimal: Assumption  # e.g. 0.0285 = 2.85%


class DebtTranche(BaseModel):
    """A single debt tranche in the capital structure."""

    name: Label  # "Senior Unitranche" / "Unitranche Senior"
    seniority: Literal["senior", "mezz", "sub"] = "senior"
    amount: Assumption  # in EUR millions
    tenor_years: int = Field(ge=1, le=15)
    reference_rate: ReferenceRate
    margin_bps: Assumption  # spread over reference rate, bps
    floor_pct: Assumption  # reference rate floor (decimal); 0.0 if none
    amortization: Literal["bullet", "linear", "mandatory_1pct"] = "bullet"
    arrangement_fee_pct: Assumption  # upfront fee as % of commitment
    commitment_fee_bps: Assumption = Field(
        default_factory=lambda: Assumption(
            id="A-998",
            name="commitment_fee_bps_default",
            label=Label(en="Commitment fee (bps)", it="Commitment fee (bps)"),
            unit="bps",
            base=0,
            rationale="Most unitranche tranches are drawn at close; 0 unless specified.",
            confidence="L",
        )
    )
    oid_pct: Assumption = Field(
        default_factory=lambda: Assumption(
            id="A-997",
            name="oid_pct_default",
            label=Label(en="OID (%)", it="OID (%)"),
            unit="pct",
            base=0,
            rationale="OID set to zero unless explicitly structured.",
            confidence="L",
        )
    )


class RCF(BaseModel):
    """Optional super-senior Revolving Credit Facility."""

    enabled: bool = False
    amount: Optional[Assumption] = None
    undrawn_fee_bps: Optional[Assumption] = None
    margin_bps: Optional[Assumption] = None
    reference_rate: Optional[ReferenceRate] = None


class CashSweep(BaseModel):
    """Optional cash sweep mechanism.

    Bulge-bracket standard: mandatory prepayment of X% of positive FCF
    when leverage exceeds a trigger.
    """

    enabled: bool = True
    sweep_pct: Optional[Assumption] = None  # e.g. 0.50 = 50% sweep
    trigger_leverage: Optional[Assumption] = None  # e.g. 3.5x


class DebtStructure(BaseModel):
    tranches: list[DebtTranche]
    rcf: RCF = Field(default_factory=RCF)
    cash_sweep: CashSweep = Field(default_factory=CashSweep)

    @field_validator("tranches")
    @classmethod
    def at_least_one_tranche(cls, v: list[DebtTranche]) -> list[DebtTranche]:
        if not v:
            raise ValueError("At least one debt tranche required.")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Covenants
# ─────────────────────────────────────────────────────────────────────────────


class Covenant(BaseModel):
    name: Label
    kind: Literal["leverage", "icr", "dscr", "capex_cap"]
    threshold_by_year: list[Assumption]  # One per projection year
    test_frequency: Literal["quarterly", "semiannual", "annual"] = "quarterly"
    equity_cure: bool = True
    cure_limit_per_year: int = 1
    cure_limit_total: int = 2


# ─────────────────────────────────────────────────────────────────────────────
# Fees and expenses
# ─────────────────────────────────────────────────────────────────────────────


class Fees(BaseModel):
    """Transaction fees paid at close (EUR m)."""

    legal: Assumption
    advisory: Assumption
    other: Assumption


# ─────────────────────────────────────────────────────────────────────────────
# Exit assumptions (for lender APR calc, not equity IRR)
# ─────────────────────────────────────────────────────────────────────────────


class ExitAssumptions(BaseModel):
    """For lender APR and refinancing / repayment assumptions.

    Lender returns are driven mostly by coupon + fees; exit matters if
    early repayment (call protection, make-whole).
    """

    expected_hold_years: Assumption
    call_protection_years: int = 2
    make_whole_pct: Assumption  # % of par if repaid inside call protection


# ─────────────────────────────────────────────────────────────────────────────
# Top-level spec
# ─────────────────────────────────────────────────────────────────────────────


class UnitrancheSpec(BaseModel):
    """Full Unitranche LBO spec. Feeds the builder."""

    # Metadata and identification.
    model_type: Literal["unitranche"] = "unitranche"
    meta: ModelMeta
    target: Target
    horizon: ProjectionHorizon = Field(default_factory=ProjectionHorizon)

    # Sources and assumptions registries.
    sources: list[Source]

    # Operating and capital structure.
    operating: OperatingAssumptions
    debt: DebtStructure
    covenants: list[Covenant]
    fees: Fees
    exit: ExitAssumptions

    # Optional probabilistic-credit block (triggers RiskAnalysis sheet).
    risk_analysis: RiskAnalysisSpec | None = None

    # Last FY historical numbers (from sources, not assumptions).
    # These anchor the projections.
    historical_revenue_eur_m: list[float]  # len == historical_years
    historical_ebitda_eur_m: list[float]
    historical_net_debt_eur_m: float
    historical_net_debt_source_id: str = Field(pattern=r"^S-\d{3,}$")

    @field_validator("operating")
    @classmethod
    def ops_year_count_matches_horizon(cls, v: OperatingAssumptions, info):
        # Cross-field validation: proj year drivers must match horizon.
        horizon: ProjectionHorizon = info.data.get(
            "horizon", ProjectionHorizon()
        )
        py = horizon.projection_years
        if len(v.revenue_growth_by_year) != py:
            raise ValueError(
                f"revenue_growth_by_year must have {py} entries, got {len(v.revenue_growth_by_year)}"
            )
        if len(v.ebitda_margin_by_year) != py:
            raise ValueError(
                f"ebitda_margin_by_year must have {py} entries, got {len(v.ebitda_margin_by_year)}"
            )
        return v

    @field_validator("historical_revenue_eur_m")
    @classmethod
    def hist_revenue_len(cls, v: list[float], info):
        horizon: ProjectionHorizon = info.data.get(
            "horizon", ProjectionHorizon()
        )
        if len(v) != horizon.historical_years:
            raise ValueError(
                f"historical_revenue_eur_m must have {horizon.historical_years} entries"
            )
        return v

    @field_validator("historical_ebitda_eur_m")
    @classmethod
    def hist_ebitda_len(cls, v: list[float], info):
        horizon: ProjectionHorizon = info.data.get(
            "horizon", ProjectionHorizon()
        )
        if len(v) != horizon.historical_years:
            raise ValueError(
                f"historical_ebitda_eur_m must have {horizon.historical_years} entries"
            )
        return v

    def all_assumptions(self) -> list[Assumption]:
        """Flatten all assumptions in declaration order.

        Used by the Assumptions-sheet emitter to lay out rows and create
        named ranges. Order matters — keeps the sheet readable.
        """
        out: list[Assumption] = []

        # Operating drivers, year-varying first then scalar.
        out.extend(self.operating.revenue_growth_by_year)
        out.extend(self.operating.ebitda_margin_by_year)
        out.append(self.operating.da_pct_revenue)
        out.append(self.operating.maintenance_capex_pct_revenue)
        out.append(self.operating.growth_capex_pct_revenue)
        out.append(self.operating.nwc_pct_revenue_delta)
        out.append(self.operating.effective_tax_rate)

        # Debt structure.
        for tr in self.debt.tranches:
            out.append(tr.amount)
            out.append(tr.margin_bps)
            out.append(tr.floor_pct)
            out.append(tr.arrangement_fee_pct)
            out.append(tr.commitment_fee_bps)
            out.append(tr.oid_pct)
            out.append(tr.reference_rate.rate_decimal)
        if self.debt.rcf.enabled:
            if self.debt.rcf.amount:
                out.append(self.debt.rcf.amount)
            if self.debt.rcf.undrawn_fee_bps:
                out.append(self.debt.rcf.undrawn_fee_bps)
            if self.debt.rcf.margin_bps:
                out.append(self.debt.rcf.margin_bps)
            if self.debt.rcf.reference_rate:
                out.append(self.debt.rcf.reference_rate.rate_decimal)
        if self.debt.cash_sweep.enabled:
            if self.debt.cash_sweep.sweep_pct:
                out.append(self.debt.cash_sweep.sweep_pct)
            if self.debt.cash_sweep.trigger_leverage:
                out.append(self.debt.cash_sweep.trigger_leverage)

        # Covenants.
        for cov in self.covenants:
            out.extend(cov.threshold_by_year)

        # Fees and exit.
        out.append(self.fees.legal)
        out.append(self.fees.advisory)
        out.append(self.fees.other)
        out.append(self.exit.expected_hold_years)
        out.append(self.exit.make_whole_pct)

        return out

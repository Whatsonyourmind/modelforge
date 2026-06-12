"""3-Statement corporate model spec — Template 8.

P&L + Balance Sheet + Cash Flow Statement with integrity ties.
Used as base for LBO/DCF, and standalone for corporate finance deliverables.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target


class TSHorizon(BaseModel):
    historical_years: int = Field(ge=1, le=5, default=3)
    projection_years: int = Field(ge=3, le=10, default=5)

    @property
    def total_columns(self) -> int:
        return self.historical_years + self.projection_years


class PLAssumptions(BaseModel):
    revenue_growth_by_year: list[Assumption]
    ebitda_margin_by_year: list[Assumption]
    da_pct_revenue: Assumption
    interest_on_debt_pct: Assumption  # simplified effective interest rate
    effective_tax_rate: Assumption


class BSAssumptions(BaseModel):
    """Balance sheet driver assumptions."""

    # Working capital (as days)
    receivables_days: Assumption  # DSO
    inventory_days: Assumption
    payables_days: Assumption
    # Long-term
    capex_pct_revenue: Assumption
    dividend_payout_ratio: Assumption


class OpeningBalanceSheet(BaseModel):
    """Last historical BS values (anchors projections)."""

    cash_eur_m: float
    receivables_eur_m: float
    inventory_eur_m: float
    net_ppe_eur_m: float
    other_assets_eur_m: float = 0.0
    payables_eur_m: float
    debt_eur_m: float
    debt_annual_repayment_eur_m: float = 0.0  # scheduled linear paydown / yr (0 = flat)
    other_liabilities_eur_m: float = 0.0
    equity_eur_m: float  # historical equity — must balance


class ThreeStatementSpec(BaseModel):
    model_type: Literal["three_statement"] = "three_statement"
    meta: ModelMeta
    target: Target
    horizon: TSHorizon = Field(default_factory=TSHorizon)
    sources: list[Source]

    pl: PLAssumptions
    bs: BSAssumptions
    opening_bs: OpeningBalanceSheet

    historical_revenue_eur_m: list[float]
    historical_ebitda_eur_m: list[float]
    historical_net_debt_eur_m: float
    historical_net_debt_source_id: str = Field(pattern=r"^S-\d{3,}$")

    # ── Model parameters (lifted from former builder hardcodes) ──────────
    # All optional; defaults reproduce the prior hardcoded behaviour byte-
    # for-byte. Each is emitted as a visible, styled, overridable named-input
    # cell on the Model sheet and wired into the relevant formula.
    sbc_pct_revenue: Optional[float] = Field(default=0.01, ge=0.0, le=1.0)
    """Stock-based compensation as a fraction of revenue (non-cash, CFS
    add-back). Default 1% of revenue."""

    revolver_capacity_eur_m: Optional[float] = Field(default=100.0, ge=0.0)
    """Revolver facility capacity (EUR m). Commitment fee accrues on the
    undrawn portion of this capacity. Default 100m."""

    revolver_commitment_fee_pct: Optional[float] = Field(
        default=0.005, ge=0.0, le=1.0)
    """Annual commitment fee charged on the undrawn revolver capacity.
    Default 0.5%."""

    book_tax_diff_da_pct: Optional[float] = Field(default=0.05, ge=0.0, le=1.0)
    """Permanent/timing book-vs-tax D&A difference as a fraction of |D&A|,
    used to accrue the DTL each year. Default 5% of |D&A|."""

    nol_util_cap_pct: Optional[float] = Field(default=0.80, ge=0.0, le=1.0)
    """NOL carryforward utilisation cap as a fraction of positive EBT
    (e.g. IRC §172 / EU 80% limitation). Default 80%."""

    @field_validator("pl")
    @classmethod
    def pl_years_match(cls, v: PLAssumptions, info):
        horizon = info.data.get("horizon", TSHorizon())
        py = horizon.projection_years
        if len(v.revenue_growth_by_year) != py:
            raise ValueError(f"revenue_growth_by_year must have {py} entries")
        if len(v.ebitda_margin_by_year) != py:
            raise ValueError(f"ebitda_margin_by_year must have {py} entries")
        return v

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.extend(self.pl.revenue_growth_by_year)
        out.extend(self.pl.ebitda_margin_by_year)
        out.append(self.pl.da_pct_revenue)
        out.append(self.pl.interest_on_debt_pct)
        out.append(self.pl.effective_tax_rate)
        out.append(self.bs.receivables_days)
        out.append(self.bs.inventory_days)
        out.append(self.bs.payables_days)
        out.append(self.bs.capex_pct_revenue)
        out.append(self.bs.dividend_payout_ratio)
        return out

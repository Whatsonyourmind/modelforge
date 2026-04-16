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

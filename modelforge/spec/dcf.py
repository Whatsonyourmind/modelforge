"""DCF-WACC standalone valuation spec — Template 10 (US-004).

Emits an enterprise DCF with an explicit WACC build (Damodaran 2026
Italy ERP 6.7% baseline), FCF forecast from revenue/margin/capex/WC
assumptions, and a terminal value reconciliation (Gordon growth +
exit EV/EBITDA multiple).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, ModelMeta, Source, Target


class DCFHorizon(BaseModel):
    historical_years: int = Field(ge=1, le=5, default=3)
    projection_years: int = Field(ge=3, le=10, default=5)


class WACCInputs(BaseModel):
    """Standard WACC components. All as decimals (0.04 = 4%)."""

    risk_free_rate: Assumption        # 10Y Italian BTP baseline
    equity_risk_premium: Assumption   # Damodaran 2026 Italy: 6.7%
    beta_levered: Assumption          # levered beta
    pretax_cost_of_debt: Assumption
    target_debt_weight: Assumption    # D / (D + E)
    effective_tax_rate: Assumption


class FCFInputs(BaseModel):
    revenue_growth_by_year: list[Assumption]
    ebitda_margin_by_year: list[Assumption]
    da_pct_revenue: Assumption
    capex_pct_revenue: Assumption
    nwc_pct_revenue_delta: Assumption  # Δ NWC as % of Δ revenue


class TerminalValue(BaseModel):
    terminal_growth_pct: Assumption
    exit_ev_ebitda_x: Assumption


class DCFSpec(BaseModel):
    model_type: Literal["dcf"] = "dcf"
    meta: ModelMeta
    target: Target
    horizon: DCFHorizon = Field(default_factory=DCFHorizon)
    sources: list[Source]

    wacc: WACCInputs
    fcf: FCFInputs
    terminal: TerminalValue

    net_debt_eur_m: float
    net_debt_source_id: str = Field(pattern=r"^S-\d{3,}$")
    shares_outstanding_m: float = 0.0
    valuation_date_price_eur: float = 0.0

    @field_validator("fcf")
    @classmethod
    def fcf_years_match(cls, v: FCFInputs, info):
        horizon = info.data.get("horizon", DCFHorizon())
        py = horizon.projection_years
        if len(v.revenue_growth_by_year) != py:
            raise ValueError(f"revenue_growth_by_year must have {py} entries")
        if len(v.ebitda_margin_by_year) != py:
            raise ValueError(f"ebitda_margin_by_year must have {py} entries")
        return v

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.extend(self.fcf.revenue_growth_by_year)
        out.extend(self.fcf.ebitda_margin_by_year)
        out.append(self.fcf.da_pct_revenue)
        out.append(self.fcf.capex_pct_revenue)
        out.append(self.fcf.nwc_pct_revenue_delta)
        out.append(self.wacc.risk_free_rate)
        out.append(self.wacc.equity_risk_premium)
        out.append(self.wacc.beta_levered)
        out.append(self.wacc.pretax_cost_of_debt)
        out.append(self.wacc.target_debt_weight)
        out.append(self.wacc.effective_tax_rate)
        out.append(self.terminal.terminal_growth_pct)
        out.append(self.terminal.exit_ev_ebitda_x)
        return out

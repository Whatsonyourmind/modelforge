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


class ComparableBeta(BaseModel):
    """A single public comparable for Hamada unlever/relever analysis."""

    name: str
    beta_levered: float
    debt_to_equity: float   # D/E ratio for unlevering
    marginal_tax_rate: float = 0.28  # default Italian


class WACCInputs(BaseModel):
    """Standard WACC components. All as decimals (0.04 = 4%).

    v0.7 additions (Damodaran / bulge-bracket CRP methodology):
      - mature_erp (optional): developed-market ERP baseline
      - sovereign_default_spread (optional): sovereign CDS-implied spread
      - equity_bond_vol_ratio (optional): σ_equity/σ_bond scalar (typical 1.5)
      - lambda_country_exposure (optional): revenue-weighted country factor

    When present, effective ERP = mature_erp + sovereign_default_spread
                                    × equity_bond_vol_ratio × lambda_country_exposure.
    Falls back to equity_risk_premium for legacy specs.

    v0.7 Hamada beta support:
      - comparable_betas (optional): list of public comps for unlever/relever.
        When present, the ComparableBetas sheet computes unlevered β per
        comp, takes median, and relevers to target capital structure.
        The resulting β_relevered overrides beta_levered.
    """

    risk_free_rate: Assumption        # 10Y Italian BTP baseline
    equity_risk_premium: Assumption   # Damodaran 2026 Italy: 6.7% (legacy single-number)
    beta_levered: Assumption          # levered beta (used if comparable_betas unset)
    pretax_cost_of_debt: Assumption
    target_debt_weight: Assumption    # D / (D + E)
    effective_tax_rate: Assumption

    # v0.7 optional: Damodaran CRP methodology
    mature_erp: Assumption | None = None
    sovereign_default_spread: Assumption | None = None
    equity_bond_vol_ratio: Assumption | None = None
    lambda_country_exposure: Assumption | None = None

    # v0.7 optional: Hamada comparable-beta analysis
    comparable_betas: list[ComparableBeta] = Field(default_factory=list)


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

    # v0.6: preferred representation — wrap bridge quantities as
    # Assumptions so the Valuation sheet references named ranges with
    # source attribution instead of hardcoded literals.
    net_debt_assum: Assumption | None = None
    shares_outstanding_assum: Assumption | None = None
    current_price_assum: Assumption | None = None

    # v0.7: full EV→Equity bridge (Footnotes Analyst standard for
    # fairness opinions). Each optional — when absent, the bridge row
    # reads zero and is a neutral reminder to the reader. When set,
    # flows through with source attribution.
    minority_interest_assum: Assumption | None = None
    pension_deficit_assum: Assumption | None = None
    preferred_equity_assum: Assumption | None = None
    cross_holdings_assum: Assumption | None = None
    lease_liability_ifrs16_assum: Assumption | None = None

    # v0.6: DCF convention toggle. True = mid-year (Macabacus default),
    # False = end-year. Controls explicit-period and TV discounting.
    mid_year_convention: bool = True

    # v0.7: stub-period support. If stub_period_days < 365, first
    # projection period is prorated (FCF × stub_days/365) and the
    # cumulative discount factor uses fractional stub_years.
    stub_period_days: int = 365

    # v0.7: two-stage DCF fade period. If >0, adds a fade block
    # between explicit horizon and terminal where growth linearly
    # converges from last-explicit-year growth to terminal_growth_pct.
    # Keeps the "hockey-stick terminal" problem out of the valuation.
    fade_years: int = 0

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
        for opt in (self.wacc.mature_erp,
                    self.wacc.sovereign_default_spread,
                    self.wacc.equity_bond_vol_ratio,
                    self.wacc.lambda_country_exposure):
            if opt is not None:
                out.append(opt)
        out.append(self.terminal.terminal_growth_pct)
        out.append(self.terminal.exit_ev_ebitda_x)
        for opt in (self.net_debt_assum,
                    self.shares_outstanding_assum,
                    self.current_price_assum,
                    self.minority_interest_assum,
                    self.pension_deficit_assum,
                    self.preferred_equity_assum,
                    self.cross_holdings_assum,
                    self.lease_liability_ifrs16_assum):
            if opt is not None:
                out.append(opt)
        return out

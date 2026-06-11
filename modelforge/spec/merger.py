"""M&A merger model spec — Template 9 (US-003).

Pro-forma merger with accretion-dilution, synergies, and cash/stock/mix
deal consideration. Produces EPS bridge waterfall (deal-impact view).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, ModelMeta, Source, Target


class MergerHorizon(BaseModel):
    projection_years: int = Field(ge=3, le=7, default=3)


class PartyFinancials(BaseModel):
    """Standalone snapshot — revenue / EBITDA / D&A / interest / tax / NI / shares / price.

    Pro-forma math walks EBITDA → EBIT → Pre-tax → Net income through the
    real D&A + interest + tax lines rather than collapsing them into a
    single multiplier (which inflates accretion on high-D&A industries
    like telecoms, utilities, industrials).
    """

    revenue_eur_m: float
    ebitda_eur_m: float
    da_eur_m: float = 0.0           # depreciation + amortization (positive number)
    interest_expense_eur_m: float = 0.0  # standalone interest (positive number)
    net_income_eur_m: float
    shares_outstanding_m: float
    share_price_eur: float
    net_debt_eur_m: float = 0.0


class DealStructure(BaseModel):
    """Deal consideration split."""

    offer_premium_pct: Assumption  # premium over target's current price
    cash_mix_pct: Assumption       # 1.0 = all cash, 0.0 = all stock
    financing_rate_pct: Assumption # cost of cash financing (new debt)
    effective_tax_rate: Assumption


class Synergies(BaseModel):
    revenue_synergies_eur_m: Assumption  # steady-state run-rate
    cost_synergies_eur_m: Assumption
    synergy_realization_y1_pct: Assumption
    integration_cost_eur_m: Assumption  # one-time, year 1


class PPAAllocation(BaseModel):
    """Purchase Price Allocation (PPA) — bulge-bracket standard block.

    Goodwill = Equity Purchase Price − BV of Target Equity − Asset Write-ups + DTL
    Identifiable intangibles have useful lives; amortization flows through P&L.

    References: Macabacus PPA Steps I+II, WSP Merger Model.
    """

    target_bv_equity_eur_m: Assumption       # book value at close
    asset_writeup_ppe_eur_m: Assumption      # PP&E fair-value step-up
    intangibles_customer_list_eur_m: Assumption
    intangibles_technology_eur_m: Assumption
    intangibles_trade_name_eur_m: Assumption
    customer_list_useful_life_years: int = 10
    technology_useful_life_years: int = 7
    trade_name_useful_life_years: int = 15
    # DTL on asset step-ups (taxable non-deductible)
    dtl_rate_pct: Assumption


class BreakFees(BaseModel):
    """Break fees (bulge standard for cross-border deals).

    target_reverse_termination_pct: target pays acquirer if walks away
    acquirer_walk_fee_pct: acquirer pays target if fails to close
    """

    target_reverse_termination_pct: Assumption
    acquirer_walk_fee_pct: Assumption


class RegulatoryTimeline(BaseModel):
    """Regulatory clearance timeline affecting synergy start.

    Expected close months from sign (HSR/CMA/EU Merger Reg): typical 4-12m.
    Synergies start after close → delay NPV.
    """

    expected_close_months: int = 6
    regulatory_jurisdictions: list[str] = Field(default_factory=list)


class MergerSpec(BaseModel):
    model_type: Literal["merger"] = "merger"
    meta: ModelMeta
    target: Target
    horizon: MergerHorizon = Field(default_factory=MergerHorizon)
    sources: list[Source]

    acquirer_name: str
    acquirer: PartyFinancials
    target_financials: PartyFinancials

    deal: DealStructure
    synergies: Synergies

    # Standalone projection growth rates. Previously hard-coded inside the
    # ProForma sheet formula strings (3% / 4% / 3%), which made them invisible
    # to the analyst and untraceable to an auditor even though they drive the
    # accretion/dilution conclusion. Now OPTIONAL spec fields with those exact
    # defaults, so behaviour is byte-identical when absent. When set, they are
    # emitted as named-range assumption cells on the ProForma sheet and the
    # revenue / standalone-interest projection formulas read the named range
    # (override is live + visible on the sheet).
    acquirer_revenue_growth_pct: float = 0.03
    target_revenue_growth_pct: float = 0.04
    combined_interest_growth_pct: float = 0.03

    # Remaining ProForma / AccretionDilution growth hardcodes lifted to spec.
    # Both were embedded as the literal 3% inside the formula strings:
    #   combined_da_growth_pct      — ProForma "(−) Combined D&A" projection
    #                                 (=-combined_da_fy0*(1+0.03)^t)
    #   standalone_eps_growth_pct   — AccretionDilution "Acquirer standalone EPS"
    #                                 (=acq_net_income_fy0*(1+0.03)^t/acq_shares_m)
    # Defaults reproduce the prior 3% exactly (byte-identical when omitted);
    # when set they surface as named-range assumption cells and the formulas
    # read the named range (visible + overridable on the sheet).
    combined_da_growth_pct: float = 0.03
    standalone_eps_growth_pct: float = 0.03

    # Stock-deal collar bands — previously hard-coded ±15% / −20% inside the
    # DealStructure "Exchange ratio & collar" formula strings (×0.85 / ×1.15 /
    # ×0.80). Now OPTIONAL named-input multipliers with those exact defaults so
    # behaviour is byte-identical when absent; when set, the collar bound /
    # walk-away formulas read the named ranges (override is live + visible).
    collar_low_pct: float = 0.85
    collar_high_pct: float = 1.15
    walk_away_pct: float = 0.80

    # v0.7 additions — bulge-tier merger rigor
    ppa: PPAAllocation | None = None
    break_fees: BreakFees | None = None
    regulatory: RegulatoryTimeline | None = None

    def all_assumptions(self) -> list[Assumption]:
        out = [
            self.deal.offer_premium_pct,
            self.deal.cash_mix_pct,
            self.deal.financing_rate_pct,
            self.deal.effective_tax_rate,
            self.synergies.revenue_synergies_eur_m,
            self.synergies.cost_synergies_eur_m,
            self.synergies.synergy_realization_y1_pct,
            self.synergies.integration_cost_eur_m,
        ]
        if self.ppa:
            out += [
                self.ppa.target_bv_equity_eur_m,
                self.ppa.asset_writeup_ppe_eur_m,
                self.ppa.intangibles_customer_list_eur_m,
                self.ppa.intangibles_technology_eur_m,
                self.ppa.intangibles_trade_name_eur_m,
                self.ppa.dtl_rate_pct,
            ]
        if self.break_fees:
            out += [
                self.break_fees.target_reverse_termination_pct,
                self.break_fees.acquirer_walk_fee_pct,
            ]
        return out

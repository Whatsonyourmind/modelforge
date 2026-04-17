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

    def all_assumptions(self) -> list[Assumption]:
        return [
            self.deal.offer_premium_pct,
            self.deal.cash_mix_pct,
            self.deal.financing_rate_pct,
            self.deal.effective_tax_rate,
            self.synergies.revenue_synergies_eur_m,
            self.synergies.cost_synergies_eur_m,
            self.synergies.synergy_realization_y1_pct,
            self.synergies.integration_cost_eur_m,
        ]

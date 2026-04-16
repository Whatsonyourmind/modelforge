"""Real Estate DCF spec — Template 5.

NOI build → financing → equity waterfall.
Italian RE focus: PBSA student housing, logistics, manage-to-green retrofits
(hot 2026 thesis per DD Talks).

Equity waterfall tiers (standard PE RE):
    1. Return of capital (LP first)
    2. Preferred return (8-10% typical)
    3. Catch-up to GP (50/50 or similar)
    4. Promote split (80/20 LP/GP on remaining)
"""

from __future__ import annotations

from typing import Literal, Optional
from datetime import date

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target


class REHorizon(BaseModel):
    hold_years: int = Field(ge=3, le=15, default=7)


class PropertyAssumptions(BaseModel):
    """Physical asset parameters."""

    acquisition_price_eur_m: Assumption
    lettable_area_sqm: Assumption
    rent_eur_sqm_year1: Assumption
    vacancy_pct: Assumption
    rent_indexation_pct: Assumption
    opex_pct_gross_rent: Assumption  # property-level opex
    capex_pct_gross_rent: Assumption  # maintenance capex


class FinancingAssumptions(BaseModel):
    """Senior mortgage."""

    ltv_pct: Assumption  # loan-to-value at acquisition
    senior_interest_rate: Assumption  # all-in rate
    senior_tenor_years: int = 5
    senior_amortization: Literal["bullet", "linear"] = "bullet"
    arrangement_fee_pct: Assumption


class ExitAssumptions(BaseModel):
    exit_cap_rate: Assumption  # on exit-year NOI
    transaction_costs_pct: Assumption  # 2-3% typical


class WaterfallTier(BaseModel):
    """Hurdle tier in equity waterfall."""

    name: Label
    hurdle_irr_pct: Optional[Assumption] = None  # None = residual tier
    lp_share_pct: Assumption  # 100 = LP-first, 80 = promote split, etc.


class EquityWaterfall(BaseModel):
    """LP/GP promote structure."""

    lp_capital_commitment_pct: Assumption  # e.g. 0.95 = LP 95%, GP 5%
    tiers: list[WaterfallTier]  # Ordered: return of capital → pref → catch-up → residual


class RealEstateSpec(BaseModel):
    model_type: Literal["real_estate"] = "real_estate"
    meta: ModelMeta
    target: Target
    horizon: REHorizon = Field(default_factory=REHorizon)
    sources: list[Source]

    property: PropertyAssumptions
    financing: FinancingAssumptions
    exit: ExitAssumptions
    waterfall: EquityWaterfall

    # Historical not applicable for greenfield/acquisition
    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.append(self.property.acquisition_price_eur_m)
        out.append(self.property.lettable_area_sqm)
        out.append(self.property.rent_eur_sqm_year1)
        out.append(self.property.vacancy_pct)
        out.append(self.property.rent_indexation_pct)
        out.append(self.property.opex_pct_gross_rent)
        out.append(self.property.capex_pct_gross_rent)
        out.append(self.financing.ltv_pct)
        out.append(self.financing.senior_interest_rate)
        out.append(self.financing.arrangement_fee_pct)
        out.append(self.exit.exit_cap_rate)
        out.append(self.exit.transaction_costs_pct)
        out.append(self.waterfall.lp_capital_commitment_pct)
        for tier in self.waterfall.tiers:
            if tier.hurdle_irr_pct:
                out.append(tier.hurdle_irr_pct)
            out.append(tier.lp_share_pct)
        return out

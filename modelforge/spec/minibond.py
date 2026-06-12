"""Minibond spec — Template 2.

Italian minibond (Italian arranger territory). Key differences vs. Unitranche:
    - Issuer-centric (not sponsor)
    - Listed on ExtraMOT Pro (secondary liquidity)
    - Typically 6y amortizing (Italian market norm per Osservatorio Polimi)
    - ElTIF eligibility flag
    - Gross-to-net investor yield (withholding, transaction costs)
    - Multi-investor subscription (basket bond common)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import (
    Assumption, Label, ModelMeta, Source, Target,
)
from modelforge.spec.compliance import ComplianceContext


class ProjectionHorizon(BaseModel):
    historical_years: int = Field(ge=1, le=5, default=3)
    projection_years: int = Field(ge=3, le=10, default=7)

    @property
    def total_columns(self) -> int:
        return self.historical_years + self.projection_years


class IssuerOperating(BaseModel):
    """Issuer P&L projection drivers — simpler than Unitranche because
    minibond investors care most about coverage, not exit."""

    revenue_growth_by_year: list[Assumption]
    ebitda_margin_by_year: list[Assumption]
    da_pct_revenue: Assumption
    capex_pct_revenue: Assumption
    nwc_pct_revenue_delta: Assumption
    effective_tax_rate: Assumption


class BondCoupon(BaseModel):
    """Coupon can be fixed or floating."""

    kind: Literal["fixed", "floating"] = "fixed"
    fixed_rate: Optional[Assumption] = None  # decimal e.g. 0.0385
    # Floating variant
    reference_rate_name: Literal["EURIBOR_3M", "EURIBOR_6M", "ESTR"] = "EURIBOR_6M"
    reference_rate_value: Optional[Assumption] = None
    margin_bps: Optional[Assumption] = None
    floor_pct: Optional[Assumption] = None
    frequency_per_year: int = 2  # semi-annual default (Italian standard)


class BondStructure(BaseModel):
    """Terms of the minibond."""

    notional: Assumption  # EUR m face value
    tenor_years: int = Field(ge=3, le=10)
    coupon: BondCoupon
    amortization: Literal["bullet", "linear_from_year", "custom"] = "linear_from_year"
    amortization_start_year: int = 3  # linear amort starts here (1-indexed)
    call_protection_years: int = 3
    make_whole_pct: Assumption

    # Fees paid at issuance (deducted from proceeds)
    arrangement_fee_pct: Assumption
    legal_fees_eur_m: Assumption
    listing_fees_eur_m: Assumption
    rating_fees_eur_m: Assumption

    # Market placement
    listed_extramot_pro: bool = True
    eltif_eligible: bool = False
    basket_bond: bool = False  # multi-issuer syndicate
    subscribers: list[str] = Field(default_factory=list)  # e.g. ["A promotional institution", "An Italian private debt fund"]


class Covenant(BaseModel):
    name: Label
    kind: Literal["leverage", "icr", "dscr", "minimum_ebitda", "capex_cap"]
    threshold_by_year: list[Assumption]
    test_frequency: Literal["quarterly", "semiannual", "annual"] = "annual"


class InvestorAdjustments(BaseModel):
    """Gross-to-net yield adjustments for the Italian investor."""

    withholding_tax_pct: Assumption  # e.g. 0.26 for non-qualified subscribers
    transaction_cost_bps: Assumption  # one-off cost at entry


class MinibondSpec(BaseModel):
    """Full Minibond model spec."""

    model_type: Literal["minibond"] = "minibond"
    # Optional regulatory-compliance context, honored by the ComplianceCheck
    # sheet; defaults reproduce prior hardcodes when omitted.
    compliance: ComplianceContext | None = None
    meta: ModelMeta
    target: Target  # issuer
    horizon: ProjectionHorizon = Field(default_factory=ProjectionHorizon)
    sources: list[Source]

    operating: IssuerOperating
    bond: BondStructure
    covenants: list[Covenant]
    investor_adjustments: InvestorAdjustments

    historical_revenue_eur_m: list[float]
    historical_ebitda_eur_m: list[float]
    historical_net_debt_eur_m: float
    historical_net_debt_source_id: str = Field(pattern=r"^S-\d{3,}$")

    @field_validator("operating")
    @classmethod
    def ops_year_match(cls, v: IssuerOperating, info):
        horizon = info.data.get("horizon", ProjectionHorizon())
        py = horizon.projection_years
        if len(v.revenue_growth_by_year) != py:
            raise ValueError(f"revenue_growth_by_year must have {py} entries")
        if len(v.ebitda_margin_by_year) != py:
            raise ValueError(f"ebitda_margin_by_year must have {py} entries")
        return v

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.extend(self.operating.revenue_growth_by_year)
        out.extend(self.operating.ebitda_margin_by_year)
        out.append(self.operating.da_pct_revenue)
        out.append(self.operating.capex_pct_revenue)
        out.append(self.operating.nwc_pct_revenue_delta)
        out.append(self.operating.effective_tax_rate)

        # Bond
        out.append(self.bond.notional)
        out.append(self.bond.make_whole_pct)
        out.append(self.bond.arrangement_fee_pct)
        out.append(self.bond.legal_fees_eur_m)
        out.append(self.bond.listing_fees_eur_m)
        out.append(self.bond.rating_fees_eur_m)

        c = self.bond.coupon
        if c.kind == "fixed" and c.fixed_rate:
            out.append(c.fixed_rate)
        else:
            if c.reference_rate_value:
                out.append(c.reference_rate_value)
            if c.margin_bps:
                out.append(c.margin_bps)
            if c.floor_pct:
                out.append(c.floor_pct)

        # Covenants
        for cov in self.covenants:
            out.extend(cov.threshold_by_year)

        # Investor adjustments
        out.append(self.investor_adjustments.withholding_tax_pct)
        out.append(self.investor_adjustments.transaction_cost_bps)

        return out

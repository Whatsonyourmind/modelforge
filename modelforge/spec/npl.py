"""NPL Portfolio Recovery Waterfall — Template 6.

Italian NPL/UTP market (~€22bn/yr secondary volume, Cherry Bank/Apollo territory).
Structure: GBV → collection curve → recovery proceeds → servicing fees → net to fund → IRR.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target


class NPLHorizon(BaseModel):
    collection_years: int = Field(ge=5, le=15, default=10)


class PortfolioAssumptions(BaseModel):
    """Portfolio-level attributes."""

    gbv_eur_m: Assumption  # Gross Book Value at purchase
    purchase_price_pct_gbv: Assumption  # e.g. 0.15 = 15 cents on the euro
    secured_pct_gbv: Assumption  # portion secured by collateral
    unsecured_pct_gbv: Assumption
    # Collection curve: year-by-year cumulative gross collection as % of GBV
    cumulative_collection_curve_pct: list[Assumption]  # len == collection_years


class ServicingFees(BaseModel):
    """Master servicer / special servicer fees."""

    servicing_fee_pct_collections: Assumption  # e.g. 0.08 = 8% of gross collections
    setup_fee_pct_gbv: Assumption  # one-off at close
    legal_fee_pct_collections: Assumption
    data_tape_cost_eur_m: Assumption  # one-off


class CapitalStructure(BaseModel):
    """Acquisition financing for the NPL fund."""

    senior_note_pct_purchase: Assumption  # senior tranche of the purchase finance
    senior_note_rate: Assumption
    senior_note_tenor_years: int = 5
    mezz_note_pct_purchase: Assumption
    mezz_note_rate: Assumption


class NPLSpec(BaseModel):
    model_type: Literal["npl"] = "npl"
    meta: ModelMeta
    target: Target  # NPL portfolio descriptor
    horizon: NPLHorizon = Field(default_factory=NPLHorizon)
    sources: list[Source]

    portfolio: PortfolioAssumptions
    servicing: ServicingFees
    capital: CapitalStructure
    effective_tax_rate: Assumption

    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    @field_validator("portfolio")
    @classmethod
    def curve_matches_years(cls, v: PortfolioAssumptions, info):
        horizon = info.data.get("horizon", NPLHorizon())
        if len(v.cumulative_collection_curve_pct) != horizon.collection_years:
            raise ValueError(
                f"cumulative_collection_curve_pct must have {horizon.collection_years} entries"
            )
        return v

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.append(self.portfolio.gbv_eur_m)
        out.append(self.portfolio.purchase_price_pct_gbv)
        out.append(self.portfolio.secured_pct_gbv)
        out.append(self.portfolio.unsecured_pct_gbv)
        out.extend(self.portfolio.cumulative_collection_curve_pct)
        out.append(self.servicing.servicing_fee_pct_collections)
        out.append(self.servicing.setup_fee_pct_gbv)
        out.append(self.servicing.legal_fee_pct_collections)
        out.append(self.servicing.data_tape_cost_eur_m)
        out.append(self.capital.senior_note_pct_purchase)
        out.append(self.capital.senior_note_rate)
        out.append(self.capital.mezz_note_pct_purchase)
        out.append(self.capital.mezz_note_rate)
        out.append(self.effective_tax_rate)
        return out

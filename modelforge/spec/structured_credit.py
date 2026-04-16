"""Structured Credit spec — Template 7.

Securitization tranche waterfall (Italian legge 130/1999 structure).
Each tranche: attachment point, detachment point, coupon, priority.
Senior/mezz/junior + equity.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target


class SCHorizon(BaseModel):
    collection_years: int = Field(ge=3, le=15, default=7)


class CollateralPool(BaseModel):
    """Underlying collateral pool."""

    face_value_eur_m: Assumption  # total face value of securitized receivables
    weighted_avg_life_years: Assumption
    # Loss curve (cumulative default rate by year)
    cumulative_default_curve_pct: list[Assumption]  # len == collection_years
    recovery_pct_on_default: Assumption  # LGD inverted
    prepayment_rate_annual: Assumption


class SCTranche(BaseModel):
    """One securitization tranche."""

    name: Label
    rating: Literal["AAA", "AA", "A", "BBB", "BB", "B", "NR", "Equity"]
    attachment_point_pct: Assumption  # e.g. 0.20 = starts at 20% loss
    detachment_point_pct: Assumption  # e.g. 1.00 = senior through to top
    coupon_pct: Assumption  # annual coupon (fixed for simplicity)
    # size = (detachment - attachment) × pool face value


class StructuredCreditSpec(BaseModel):
    model_type: Literal["structured_credit"] = "structured_credit"
    meta: ModelMeta
    target: Target
    horizon: SCHorizon = Field(default_factory=SCHorizon)
    sources: list[Source]

    collateral: CollateralPool
    tranches: list[SCTranche]  # Ordered senior → mezz → junior → equity
    servicing_fee_pct_collections: Assumption
    effective_tax_rate: Assumption

    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    @field_validator("collateral")
    @classmethod
    def default_curve_matches_years(cls, v: CollateralPool, info):
        horizon = info.data.get("horizon", SCHorizon())
        if len(v.cumulative_default_curve_pct) != horizon.collection_years:
            raise ValueError(
                f"cumulative_default_curve_pct must have {horizon.collection_years} entries"
            )
        return v

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.append(self.collateral.face_value_eur_m)
        out.append(self.collateral.weighted_avg_life_years)
        out.extend(self.collateral.cumulative_default_curve_pct)
        out.append(self.collateral.recovery_pct_on_default)
        out.append(self.collateral.prepayment_rate_annual)
        for tr in self.tranches:
            out.append(tr.attachment_point_pct)
            out.append(tr.detachment_point_pct)
            out.append(tr.coupon_pct)
        out.append(self.servicing_fee_pct_collections)
        out.append(self.effective_tax_rate)
        return out

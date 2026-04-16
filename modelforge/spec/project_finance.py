"""Project Finance spec — Template 4.

Infrastructure / RE project finance. Key differences vs. corporate:
    - Construction phase (no revenue, capex-heavy, IDC capitalized)
    - Operating phase (contracted cash flows, CADS)
    - DSCR-driven debt sizing
    - Project-level cash waterfall (operating costs → senior debt → reserves → dividends)
    - Reserve accounts (DSRA, MMRA)
"""

from __future__ import annotations

from typing import Literal, Optional
from datetime import date

from pydantic import BaseModel, Field, field_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target


class PFHorizon(BaseModel):
    """Project Finance has explicit construction vs operating split."""

    construction_years: int = Field(ge=1, le=5, default=2)
    operating_years: int = Field(ge=5, le=30, default=15)

    @property
    def total_years(self) -> int:
        return self.construction_years + self.operating_years


class ConstructionPhase(BaseModel):
    """Construction phase assumptions."""

    total_capex_eur_m: Assumption  # all-in project cost
    capex_phasing_pct: list[Assumption]  # phasing across construction years (sums to 1.0)
    interest_during_construction_capitalized: bool = True
    commitment_fee_bps: Assumption  # on undrawn debt during construction


class OperatingPhase(BaseModel):
    """Operating phase revenue & cost drivers."""

    availability_payment_eur_m_yr1: Assumption  # or equivalent year-1 revenue
    revenue_indexation_pct: Assumption  # annual escalation (CPI-linked)
    opex_pct_revenue: Assumption
    opex_indexation_pct: Assumption
    maintenance_reserve_pct_revenue: Assumption


class PFDebt(BaseModel):
    """Project debt tranche."""

    name: Label
    amount: Assumption  # EUR m
    tenor_operating_years: int  # operating-years of amortization
    grace_years: int = 2  # no principal repayment for N years post-operating
    reference_rate: Assumption  # e.g. swap rate for infra
    margin_bps: Assumption
    arrangement_fee_pct: Assumption


class DSCRCovenant(BaseModel):
    """DSCR covenant per year."""

    threshold_by_year: list[Assumption]  # one per operating year
    lock_up_threshold: Assumption  # below this, no dividend


class EquityIRRTarget(BaseModel):
    target_irr: Assumption
    effective_tax_rate: Assumption


class ProjectFinanceSpec(BaseModel):
    model_type: Literal["project_finance"] = "project_finance"
    meta: ModelMeta
    target: Target  # project SPV
    horizon: PFHorizon = Field(default_factory=PFHorizon)
    sources: list[Source]

    construction: ConstructionPhase
    operating: OperatingPhase
    debt: PFDebt
    covenant: DSCRCovenant
    equity: EquityIRRTarget

    # Historical not applicable (greenfield) — use zero-length list
    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    @field_validator("construction")
    @classmethod
    def phasing_matches_years(cls, v: ConstructionPhase, info):
        horizon = info.data.get("horizon", PFHorizon())
        if len(v.capex_phasing_pct) != horizon.construction_years:
            raise ValueError(
                f"capex_phasing_pct must have {horizon.construction_years} entries"
            )
        return v

    @field_validator("covenant")
    @classmethod
    def dscr_matches_operating_years(cls, v: DSCRCovenant, info):
        horizon = info.data.get("horizon", PFHorizon())
        if len(v.threshold_by_year) != horizon.operating_years:
            raise ValueError(
                f"DSCR threshold_by_year must have {horizon.operating_years} entries"
            )
        return v

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.append(self.construction.total_capex_eur_m)
        out.extend(self.construction.capex_phasing_pct)
        out.append(self.construction.commitment_fee_bps)
        out.append(self.operating.availability_payment_eur_m_yr1)
        out.append(self.operating.revenue_indexation_pct)
        out.append(self.operating.opex_pct_revenue)
        out.append(self.operating.opex_indexation_pct)
        out.append(self.operating.maintenance_reserve_pct_revenue)
        out.append(self.debt.amount)
        out.append(self.debt.reference_rate)
        out.append(self.debt.margin_bps)
        out.append(self.debt.arrangement_fee_pct)
        out.extend(self.covenant.threshold_by_year)
        out.append(self.covenant.lock_up_threshold)
        out.append(self.equity.target_irr)
        out.append(self.equity.effective_tax_rate)
        return out

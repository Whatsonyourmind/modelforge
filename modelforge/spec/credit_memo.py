"""Credit Memo spec — Template 3.

Extends Unitranche with credit-specific analytics:
    - Downside EBITDA stress
    - Recovery waterfall (enterprise value → senior → mezz → equity)
    - PD / LGD / EL estimate
    - Rating-shadow mapping (Moody's / S&P equivalent)
    - Credit opinion narrative fields

Reuses Unitranche operating + debt structure but adds a CreditOpinion sheet.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from modelforge.spec.base import Assumption, Label
from modelforge.spec.compliance import ComplianceContext
from modelforge.spec.risk_block import RiskAnalysisSpec
from modelforge.spec.unitranche import (
    Covenant, DebtStructure, ExitAssumptions, Fees, OperatingAssumptions,
    ProjectionHorizon,
)
from modelforge.spec.base import ModelMeta, Source, Target


class CreditStress(BaseModel):
    """Downside stress parameters for credit analysis."""

    ebitda_stress_pct: Assumption  # e.g. -0.25 for 25% EBITDA decline
    stress_ebitda_multiple: Assumption  # exit multiple in stress (e.g. 5.0x)
    recovery_timeline_years: Assumption  # years from default to recovery
    liquidation_discount_pct: Assumption  # haircut on ent. value in liquidation


class RatingShadow(BaseModel):
    """Internal rating estimate + agency equivalents."""

    internal_rating: Literal["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"] = "BB"
    moodys_equivalent: str = "Ba2"
    sp_equivalent: str = "BB"
    probability_of_default_pct: Assumption  # PD over instrument life


class CreditMemoSpec(BaseModel):
    """Extends Unitranche with credit-memo-specific fields."""

    model_type: Literal["credit_memo"] = "credit_memo"
    meta: ModelMeta
    target: Target
    horizon: ProjectionHorizon = Field(default_factory=ProjectionHorizon)
    sources: list[Source]

    operating: OperatingAssumptions
    debt: DebtStructure
    covenants: list[Covenant]
    fees: Fees
    exit: ExitAssumptions
    stress: CreditStress
    rating: RatingShadow

    # Credit-opinion narrative
    credit_strengths: list[str] = Field(default_factory=list)
    credit_weaknesses: list[str] = Field(default_factory=list)
    mitigating_factors: list[str] = Field(default_factory=list)

    # Optional: triggers a RiskAnalysis sheet (Merton + KMV + IFRS 9 ECL)
    risk_analysis: RiskAnalysisSpec | None = None

    # Optional: regulatory & tax context for the ComplianceCheck sheet.
    # Omitted => defaults reproduce the previously-hardcoded Italian/EU values.
    compliance: ComplianceContext | None = None

    historical_revenue_eur_m: list[float]
    historical_ebitda_eur_m: list[float]
    historical_net_debt_eur_m: float
    historical_net_debt_source_id: str = Field(pattern=r"^S-\d{3,}$")

    def all_assumptions(self) -> list[Assumption]:
        # Inherit all Unitranche assumptions + credit-specific
        from modelforge.spec.unitranche import UnitrancheSpec
        # Reuse Unitranche's flattener for shared pieces
        dummy = UnitrancheSpec(
            meta=self.meta, target=self.target, horizon=self.horizon,
            sources=self.sources, operating=self.operating, debt=self.debt,
            covenants=self.covenants, fees=self.fees, exit=self.exit,
            historical_revenue_eur_m=self.historical_revenue_eur_m,
            historical_ebitda_eur_m=self.historical_ebitda_eur_m,
            historical_net_debt_eur_m=self.historical_net_debt_eur_m,
            historical_net_debt_source_id=self.historical_net_debt_source_id,
        )
        out = dummy.all_assumptions()
        # Credit-specific
        out.append(self.stress.ebitda_stress_pct)
        out.append(self.stress.stress_ebitda_multiple)
        out.append(self.stress.recovery_timeline_years)
        out.append(self.stress.liquidation_discount_pct)
        out.append(self.rating.probability_of_default_pct)
        return out

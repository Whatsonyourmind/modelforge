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

from modelforge.spec.base import Assumption, Confidence, Label, ModelMeta, Source, Target


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


# ──────────────────────────────────────────────────────────────────────────
# Spec-intended fallback defaults for the simplified-waterfall headline knobs.
# Used ONLY when neither an explicit Assumption nor a derivable tier is present.
# These match the documented "standard PE RE" intent (pref 9% Italian standard,
# 80/20 promote → GP carries 20%). They are the CORRECT values; the legacy
# builder literal of 8% pref was a v0.7 placeholder that diverged from intent.
# ──────────────────────────────────────────────────────────────────────────
_DEFAULT_LP_PREF_PCT = 0.09   # spec intent: 9% pref (tier2 base in the canonical example)
_DEFAULT_GP_PROMOTE_PCT = 0.20  # spec intent: 80/20 promote → GP gets 20% of residual


class EquityWaterfall(BaseModel):
    """LP/GP promote structure."""

    lp_capital_commitment_pct: Assumption  # e.g. 0.95 = LP 95%, GP 5%
    tiers: list[WaterfallTier]  # Ordered: return of capital → pref → catch-up → residual

    # ── Headline simplified-waterfall knobs (v0.8 parameterization) ──────────
    # OPTIONAL. When omitted (None) the effective value is RESOLVED from the
    # spec's real tiers if derivable, else from the spec-intended fallback
    # constant above. Surfacing them as explicit Assumptions lets a deal team
    # override the pref / promote directly as named-input cells on the sheet.
    lp_preferred_return_pct: Optional[Assumption] = None  # LP pref hurdle (e.g. 0.09)
    gp_promote_pct: Optional[Assumption] = None           # GP carry on residual (e.g. 0.20)

    # ── Resolvers ────────────────────────────────────────────────────────────
    # Each returns a concrete Assumption (the explicit one if supplied; otherwise
    # a synthesized default whose base is derived from the real tiers when
    # possible, else the spec-intended constant). The synthesized objects carry
    # stable ids/names so their named ranges are deterministic across builds.

    def _pref_from_tiers(self) -> Optional[float]:
        """Pull the preferred-return hurdle from a 'pref'-style tier, if present.

        Heuristic: the first tier whose 100%-LP hurdle is a positive IRR (i.e. a
        return-of-capital-then-pref tier). In the canonical RE waterfall this is
        the second tier (tier1 = return of capital at 0% hurdle). We take the
        first tier with a non-zero hurdle_irr_pct as the pref hurdle.
        """
        for tier in self.tiers:
            if tier.hurdle_irr_pct is not None and tier.hurdle_irr_pct.base > 0:
                return tier.hurdle_irr_pct.base
        return None

    def _promote_from_tiers(self) -> Optional[float]:
        """Derive GP promote % from the residual (open) tier's LP share.

        GP promote = 1 - lp_share on the final residual tier (the tier with no
        hurdle, i.e. the open promote band). Falls back to the lowest LP-share
        tier if no explicit residual tier exists.
        """
        residual = [t for t in self.tiers if t.hurdle_irr_pct is None]
        candidate = residual[-1] if residual else (
            min(self.tiers, key=lambda t: t.lp_share_pct.base) if self.tiers else None
        )
        if candidate is None:
            return None
        return 1.0 - candidate.lp_share_pct.base

    def resolved_lp_preferred_return(self) -> Assumption:
        if self.lp_preferred_return_pct is not None:
            return self.lp_preferred_return_pct
        base = self._pref_from_tiers()
        if base is None:
            base = _DEFAULT_LP_PREF_PCT
        return Assumption(
            id="A-040",
            name="lp_preferred_return_pct",
            label=Label(en="LP preferred return %", it="Rendimento preferenziale LP %"),
            unit="pct",
            base=base,
            rationale=(
                "LP preferred (hurdle) return, compounded annually on contributed "
                "capital before any GP promote. Resolved from the waterfall's pref "
                "tier when present, else the spec-intended 9% Italian-RE standard."
            ),
            confidence=Confidence.H,
        )

    def resolved_gp_promote(self) -> Assumption:
        if self.gp_promote_pct is not None:
            return self.gp_promote_pct
        base = self._promote_from_tiers()
        if base is None:
            base = _DEFAULT_GP_PROMOTE_PCT
        return Assumption(
            id="A-041",
            name="gp_promote_pct",
            label=Label(en="GP promote % (carry on residual)", it="Promote GP % (carry su residuo)"),
            unit="pct",
            base=base,
            rationale=(
                "GP promote (carried interest) on the residual band above the pref. "
                "LP share of residual = 1 - promote. Resolved from the residual "
                "tier's LP share when present, else the spec-intended 20% (80/20)."
            ),
            confidence=Confidence.H,
        )


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
        # Headline simplified-waterfall knobs (pref + GP promote). Surfaced as
        # named-range inputs so the Financing sheet's pref / promote cells are
        # spec-driven and overridable, not hardcoded literals.
        out.append(self.waterfall.resolved_lp_preferred_return())
        out.append(self.waterfall.resolved_gp_promote())
        for tier in self.waterfall.tiers:
            if tier.hurdle_irr_pct:
                out.append(tier.hurdle_irr_pct)
            out.append(tier.lp_share_pct)
        return out

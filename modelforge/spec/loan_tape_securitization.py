"""Loan-tape cash securitization spec — Template 19 (CLO / RMBS / ABS).

A *cash* securitization driven by a granular, stratified **loan tape** — the
engine that the two existing structured-credit templates deliberately do NOT
have, and which they should not be made to duplicate:

  * ``structured_credit`` (Template 7, ``sc_tranches``) is a STATIC,
    cumulative-loss capital-stack tranching (attachment / detachment / tranche
    loss% / IRR) — the synthetic / index-tranche convention. No collateral
    cashflow is projected; tranches simply absorb a terminal loss number.
  * ``npl`` (Template 6, ``npl_waterfall``) projects a single pool-level
    *collection curve* through a strict-priority cash waterfall — but the pool
    is one blended GBV line with no scheduled amortization, prepayment, default
    or recovery mechanics.

This template adds the genuinely-missing middle layer: a stratified loan tape
whose strata each amortize on their own WAM and default on their own CDR, a
pool cashflow projection (scheduled principal + CPR prepayment + CDR default +
lagged recoveries), and a sequential-pay **liability waterfall** that consumes
those cashflows with OC / IC triggers, a senior turbo, a reserve account and
excess spread to the residual — then per-note WAL / IRR / rating-proxy.

GROUNDING (all generic / synthetic — sell-side / rating-agency level of
fidelity, NOT a loan-by-loan cashflow engine):

  * The tape is *stratified* into representative lines (the institutional
    convention for a deal cashflow model). Each stratum projects its own
    performing-balance roll-forward; the pool is the sum of strata.
  * Scheduled amortization is straight-line to each stratum's WAM with a
    clean-up / call sweep at the deal's final period (so the pool fully
    redeems even when WAM exceeds the modelled horizon).
  * Defaults use an annual MDR == the stratum's annual CDR on the
    beginning-of-period performing balance; recoveries arrive with a fixed
    one-period lag at the pool ``recovery_pct`` (1 − severity), with the final
    period sweeping any not-yet-collected recovery so nothing leaks past
    maturity (recovery conservation is exact).
  * The liability side is acyclic by construction: note interest accrues on
    the beginning-of-period (prior-closing) note balance; sequential principal
    is allocated left-to-right from current-period collections; the senior
    turbo is funded out of the *already-computed* residual interest; so no
    same-period cell ever feeds back on itself (no iterative calc required).

Sign convention is costs-negative for fees / shortfalls in display, but the
waterfall arithmetic carries positive cash magnitudes through positive
allocation cells (documented per row).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target
from modelforge.spec.compliance import ComplianceContext
from modelforge.spec.risk_block import RiskAnalysisSpec


# ──────────────────────────────────────────────────────────────────────────
# Horizon
# ──────────────────────────────────────────────────────────────────────────
class SecuritizationHorizon(BaseModel):
    """Annual cashflow periods. t=0 is closing; t=1..periods are cashflow dates."""

    periods: int = Field(ge=3, le=15, default=8)
    recovery_lag_periods: int = Field(ge=0, le=3, default=1)


# ──────────────────────────────────────────────────────────────────────────
# Asset side — the stratified loan tape
# ──────────────────────────────────────────────────────────────────────────
class LoanStratum(BaseModel):
    """One representative line of the stratified loan tape.

    Each stratum amortizes on its OWN ``wam_years`` and defaults on its OWN
    ``cdr_pct`` — this is what makes the tape granular rather than a single
    blended pool line.
    """

    name: Label
    balance_eur_m: Assumption    # current unpaid principal balance (UPB) at close
    wac_pct: Assumption          # weighted-average gross coupon of the stratum
    wam_years: Assumption        # weighted-average remaining maturity (amort term)
    cdr_pct: Assumption          # annualized constant default rate of the stratum


class PoolAssumptions(BaseModel):
    """Pool-level cashflow drivers shared across strata."""

    cpr_pct: Assumption              # annual constant prepayment rate (pool-wide)
    recovery_pct: Assumption         # recovery on defaulted balance (1 − severity)
    servicing_fee_pct: Assumption    # servicing fee on performing balance (top of WF)
    senior_fees_eur_m: Assumption    # fixed trustee / admin fee per period (top of WF)


# ──────────────────────────────────────────────────────────────────────────
# Liability side — the notes (capital structure)
# ──────────────────────────────────────────────────────────────────────────
class SecuritizationNote(BaseModel):
    """One liability tranche (note). Order senior → mezz → … → residual.

    The LAST note must be the first-loss residual / equity certificate
    (``rating == "Equity"``); it carries no contractual coupon and receives
    excess spread + residual principal. Debt-note ``advance_pct`` values plus
    the equity residual must tile the pool (sum ≈ 1.0).
    """

    name: Label
    rating: Literal["AAA", "AA", "A", "BBB", "BB", "B", "NR", "Equity"]
    advance_pct: Assumption   # initial note balance as % of the initial pool UPB
    coupon_pct: Assumption    # annual note coupon (residual note: 0 — gets excess)


class CreditEnhancement(BaseModel):
    """Structural credit-enhancement features of the deal."""

    oc_trigger_pct: Assumption       # required OC ratio (pool / debt notes); breach → turbo
    ic_trigger_pct: Assumption       # required interest-coverage ratio; breach → turbo
    reserve_pct_initial: Assumption  # cash reserve as % of the initial pool balance, funded at close


# ──────────────────────────────────────────────────────────────────────────
# Spec
# ──────────────────────────────────────────────────────────────────────────
class LoanTapeSecuritizationSpec(BaseModel):
    model_type: Literal["loan_tape_securitization"] = "loan_tape_securitization"
    meta: ModelMeta
    # Optional regulatory-compliance context, honored by the ComplianceCheck sheet.
    compliance: ComplianceContext | None = None
    target: Target
    horizon: SecuritizationHorizon = Field(default_factory=SecuritizationHorizon)
    sources: list[Source]

    tape: list[LoanStratum]              # the stratified loan tape (≥ 1 stratum)
    pool: PoolAssumptions
    notes: list[SecuritizationNote]      # capital structure, senior → … → residual
    enhancement: CreditEnhancement
    effective_tax_rate: Assumption       # SPV tax (legge 130/1999 SPV is tax-neutral → 0)

    # Optional probabilistic-credit block (triggers RiskAnalysis sheet).
    risk_analysis: RiskAnalysisSpec | None = None

    # Optional free-form screening passthrough (read by the screening engine;
    # ignored by the builder). Mirrors development_re / bank_fig.
    screening: Optional[dict[str, Any]] = None

    # Historical anchors (unused by the cashflow engine; kept for ingest parity).
    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    @field_validator("tape")
    @classmethod
    def _tape_nonempty(cls, v: list[LoanStratum]) -> list[LoanStratum]:
        if not v:
            raise ValueError("loan tape must contain at least one stratum")
        return v

    @field_validator("notes")
    @classmethod
    def _notes_shape(cls, v: list[SecuritizationNote]) -> list[SecuritizationNote]:
        if len(v) < 2:
            raise ValueError("need at least one debt note plus the residual note")
        if v[-1].rating != "Equity":
            raise ValueError(
                "the LAST note must be the first-loss residual (rating='Equity')"
            )
        for n in v[:-1]:
            if n.rating == "Equity":
                raise ValueError("only the last note may carry rating='Equity'")
        return v

    @model_validator(mode="after")
    def _advances_tile_pool(self) -> "LoanTapeSecuritizationSpec":
        # Initial note balances must tile the pool: Σ advance_pct ≈ 1.0
        # (the residual note's advance_pct closes the structure to 100%).
        total = sum(n.advance_pct.base for n in self.notes)
        if abs(total - 1.0) > 0.005:
            raise ValueError(
                f"note advance_pct must sum to 1.0 (got {total:.4f}); the residual "
                "note closes the capital structure to 100% of the pool"
            )
        return self

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        for s in self.tape:
            out.append(s.balance_eur_m)
            out.append(s.wac_pct)
            out.append(s.wam_years)
            out.append(s.cdr_pct)
        out.append(self.pool.cpr_pct)
        out.append(self.pool.recovery_pct)
        out.append(self.pool.servicing_fee_pct)
        out.append(self.pool.senior_fees_eur_m)
        for n in self.notes:
            out.append(n.advance_pct)
            out.append(n.coupon_pct)
        out.append(self.enhancement.oc_trigger_pct)
        out.append(self.enhancement.ic_trigger_pct)
        out.append(self.enhancement.reserve_pct_initial)
        out.append(self.effective_tax_rate)
        return out

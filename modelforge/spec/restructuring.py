"""Restructuring / Chapter 11 model — Pydantic spec.

Captures the inputs for a corporate restructuring / DIP financing model:
  * Pre-petition claims by class (with priority + secured/unsecured + collateral)
  * DIP financing facility (senior over everyone, super-priority)
  * Plan of reorganization waterfall (absolute-priority rule)
  * Recovery rates by class (% of allowed claim)
  * Exit financing (mini-perm or take-out)
  * Equity allocation post-emergence (new equity for unsecured creditors)
  * Operating projections through restructuring period
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

from modelforge.spec.base import Source, Assumption, Scenario


# Priority classes following US Bankruptcy Code § 507(a) waterfall
ClaimPriority = Literal[
    "dip",               # Super-priority (DIP financing)
    "admin",             # § 503(b) administrative expenses (lawyers, accountants)
    "priority_unsecured",  # § 507(a) priority unsecured (taxes, wages limit)
    "secured_1l",        # First-lien secured
    "secured_2l",        # Second-lien secured
    "unsecured_senior",  # Senior unsecured (bonds, term loans)
    "unsecured_sub",     # Subordinated unsecured
    "trade",             # Trade claims (often impaired)
    "equity_preferred",  # Preferred equity (typically wiped)
    "equity_common",     # Common equity (typically wiped)
]


class ClaimClass(BaseModel):
    """One claim class in the restructuring."""
    model_config = ConfigDict(extra="forbid")

    class_id: str  # C-### or descriptive (C-1L-Term-Loan)
    priority: ClaimPriority
    description: str  # e.g. "Senior Secured Term Loan B"
    allowed_amount: Decimal  # total $ allowed by court
    collateral_value: Optional[Decimal] = None  # for secured classes
    contractual_rate: Optional[Decimal] = None  # original instrument coupon
    post_petition_interest: bool = False  # accrues only if oversecured
    impaired: bool = True  # impaired classes vote on plan
    source_id: Optional[str] = None


class DIPFacility(BaseModel):
    """DIP financing facility — super-priority funding during Chapter 11."""
    model_config = ConfigDict(extra="forbid")

    facility_size: Decimal
    drawn: Decimal = Decimal("0")
    coupon: Decimal  # typically L+5-8% + OID
    upfront_fee_pct: Decimal = Decimal("0.025")  # 2-2.5% standard
    maturity_months: int = 12  # typical 6-18 months
    super_priority: bool = True  # § 364(c)(1)
    primed_liens: list[str] = Field(default_factory=list)  # lien priming under § 364(d)


class PlanRecovery(BaseModel):
    """Recovery for one claim class under the plan."""
    model_config = ConfigDict(extra="forbid")

    class_id: str  # references ClaimClass.class_id
    cash_distribution: Decimal = Decimal("0")
    new_equity_pct: Decimal = Decimal("0")  # % of post-emergence equity
    new_debt_face: Decimal = Decimal("0")  # take-back paper
    recovery_pct: Optional[Decimal] = None  # auto-computed if None
    votes_required: bool = True


class RestructuringSpec(BaseModel):
    """Top-level restructuring model spec."""
    model_config = ConfigDict(extra="forbid")

    model_type: Literal["restructuring"] = "restructuring"
    # Identification
    debtor_name: str
    case_number: Optional[str] = None  # bankruptcy case identifier
    jurisdiction: Literal["US_DE", "US_SDNY", "US_TX", "UK_HC", "IT_CRT_FIN", "Other"] = "US_DE"
    filing_date: str  # ISO YYYY-MM-DD

    # Pre-petition capital structure
    claim_classes: list[ClaimClass] = Field(min_length=1)

    # DIP
    dip_facility: Optional[DIPFacility] = None

    # Plan of reorganization
    plan_recoveries: list[PlanRecovery] = Field(default_factory=list)
    enterprise_value_post: Decimal  # negotiated EV of reorganized debtor
    cash_at_emergence: Decimal = Decimal("0")
    new_debt_at_emergence: Decimal = Decimal("0")

    # Timing
    months_in_chapter11: int = 18  # typical 12-24
    confirmation_date_target: str  # ISO

    # Standard plumbing
    sources: list[Source] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)


# ── Helper computations ────────────────────────────────────────────────


def compute_absolute_priority_waterfall(spec: RestructuringSpec) -> list[dict]:
    """Apply absolute-priority rule to enterprise value.

    Returns list of {class_id, allowed, recovered, recovery_pct} ordered by priority.

    APR: each senior class is paid in full before subordinate class gets anything,
    unless seniors consent otherwise. This is the strict reading; in practice
    distressed deals often violate APR by mutual consent (e.g. equity gets
    "tip" payments to avoid drawn-out litigation).
    """
    # Priority sort order — DIP first, common last
    priority_order = list(ClaimPriority.__args__)
    classes_sorted = sorted(
        spec.claim_classes,
        key=lambda c: priority_order.index(c.priority) if c.priority in priority_order else 99
    )

    # Distributable value = EV + cash at emergence + new debt at emergence
    distributable = spec.enterprise_value_post + spec.cash_at_emergence + spec.new_debt_at_emergence
    # DIP super-priority — paid in cash first
    if spec.dip_facility:
        distributable -= spec.dip_facility.drawn

    results = []
    remaining = distributable
    for cls in classes_sorted:
        allowed = cls.allowed_amount
        recovered = min(remaining, allowed)
        recovery_pct = (recovered / allowed) if allowed > 0 else Decimal("0")
        results.append({
            "class_id": cls.class_id,
            "priority": cls.priority,
            "allowed": allowed,
            "recovered": recovered,
            "recovery_pct": recovery_pct,
        })
        remaining -= recovered
        if remaining <= 0:
            remaining = Decimal("0")

    return results


def compute_total_dip_cost(dip: DIPFacility) -> Decimal:
    """Annualized DIP cost = drawn × coupon + facility × upfront fee (one-time)."""
    if dip is None:
        return Decimal("0")
    interest_annual = dip.drawn * dip.coupon
    upfront = dip.facility_size * dip.upfront_fee_pct
    return interest_annual + upfront

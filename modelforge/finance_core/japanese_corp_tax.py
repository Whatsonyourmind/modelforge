"""Japanese corporate-tax computations: National Corporation Tax,
Local Corporation Tax, Enterprise Tax (Business Tax), Special Local
Corporate Tax, R&D tax credit, loss carryforward.

Pure Python, deterministic, follows ``italian_tax.py`` pattern.

References:
    - National Corporation Tax: 23.2% on income exceeding ¥8M (standard);
      15% on first ¥8M for SMEs with capital ≤ ¥100M
    - Local Corporation Tax: 10.3% of National Corp Tax (applied to NCT)
    - Enterprise Tax (Business Tax): 1.18% (size-based portion for large
      enterprises with capital ≥ ¥100M) + 7.0% (income-based, varies by
      prefecture, ~0.495-1.18% on income for large; SMEs 3.5-7.0%)
    - Special Local Corporate Tax: 260% of standard income-based ET
    - R&D tax credit: General R&D 6-14% of expenditure, capped at 25% of
      corporate tax (Article 42-4 RTPL)
    - Loss carryforward: 10 years (post-2018); 50% income limitation for
      large enterprises, 100% for SMEs

NOTE: v0 scaffold. Combined effective rate (NCT+LCT+ET) typically ~30-31%
for large enterprises; ~21-23% for SMEs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


# ── Rates snapshot (2026-05-14, Reiwa 6 tax reform) ──────────────────────

NCT_STANDARD_RATE = Decimal("0.232")   # 23.2% on income > ¥8M
NCT_SME_REDUCED_RATE = Decimal("0.15")  # 15% on first ¥8M for SMEs
SME_INCOME_THRESHOLD = Decimal("8000000")  # ¥8M

LCT_RATE = Decimal("0.103")            # 10.3% of NCT

ET_INCOME_LARGE_LOW = Decimal("0.00495")  # 0.495% on income < ¥4M (large)
ET_INCOME_LARGE_MID = Decimal("0.00835")  # 0.835% on ¥4-8M
ET_INCOME_LARGE_HIGH = Decimal("0.0118")  # 1.18% on > ¥8M
ET_INCOME_SME = Decimal("0.07")            # 7% standard for SMEs (income-based)
SLCT_MULTIPLIER = Decimal("2.60")          # 260% of ET

RD_BASE_RATE = Decimal("0.10")  # general R&D ~6-14%; midpoint 10%
RD_TAX_CREDIT_CAP_PCT = Decimal("0.25")  # 25% of corp tax

CAPITAL_SME_THRESHOLD = Decimal("100000000")  # ¥100M

LOSSES_CF_YEARS = 10
LOSSES_CF_LIMIT_LARGE = Decimal("0.50")  # 50% income limit for large
LOSSES_CF_LIMIT_SME = Decimal("1.00")     # 100% for SMEs


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JapaneseTaxInputs:
    """Single-period inputs for Japanese CT calc."""
    pretax_book_income: Decimal
    capital: Decimal = Decimal("0")  # ¥; <¥100M = SME
    permanent_disallowances: Decimal = Decimal("0")
    losses_brought_forward: Decimal = Decimal("0")
    losses_age_years: int = 0  # if > 10, losses expire
    rd_qualifying_expenditure: Decimal = Decimal("0")
    prefecture: str = "Tokyo"  # informational


@dataclass
class JapaneseTaxOutput:
    """Computed Japanese CT position."""
    taxable_income: Decimal
    losses_used: Decimal
    national_corp_tax: Decimal
    local_corp_tax: Decimal
    enterprise_tax: Decimal
    special_local_corp_tax: Decimal
    rd_credit: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    losses_carried_forward: Decimal
    is_sme: bool


# ── Computations ─────────────────────────────────────────────────────────


def is_sme(inputs: JapaneseTaxInputs) -> bool:
    """SME for capital ≤ ¥100M (per Article 66 CTL)."""
    return inputs.capital <= CAPITAL_SME_THRESHOLD


def apply_loss_cf(taxable: Decimal, losses_bf: Decimal, is_sme_flag: bool) -> tuple[Decimal, Decimal, Decimal]:
    """Apply CF with 50%/100% income limit depending on size."""
    if taxable <= 0:
        return Decimal("0"), taxable, losses_bf + abs(taxable)
    if losses_bf == 0:
        return Decimal("0"), taxable, Decimal("0")

    limit = LOSSES_CF_LIMIT_SME if is_sme_flag else LOSSES_CF_LIMIT_LARGE
    cap = taxable * limit
    used = min(losses_bf, cap)
    return used, taxable - used, losses_bf - used


def compute_national_corp_tax(taxable: Decimal, is_sme_flag: bool) -> Decimal:
    """National Corporation Tax with SME reduced-rate threshold."""
    if taxable <= 0:
        return Decimal("0")
    if is_sme_flag:
        first_tier = min(taxable, SME_INCOME_THRESHOLD) * NCT_SME_REDUCED_RATE
        residual = max(Decimal("0"), taxable - SME_INCOME_THRESHOLD) * NCT_STANDARD_RATE
        return first_tier + residual
    return taxable * NCT_STANDARD_RATE


def compute_enterprise_tax(taxable: Decimal, is_sme_flag: bool) -> Decimal:
    """Enterprise Tax (income-based portion) — simplified Tokyo Metropolitan rate."""
    if taxable <= 0:
        return Decimal("0")
    if is_sme_flag:
        return taxable * ET_INCOME_SME
    # Large enterprise progressive
    a = min(taxable, Decimal("4000000")) * ET_INCOME_LARGE_LOW
    b = max(Decimal("0"), min(taxable, Decimal("8000000")) - Decimal("4000000")) * ET_INCOME_LARGE_MID
    c = max(Decimal("0"), taxable - Decimal("8000000")) * ET_INCOME_LARGE_HIGH
    return a + b + c


def compute_japanese_tax(inputs: JapaneseTaxInputs) -> JapaneseTaxOutput:
    """End-to-end Japanese CT calc for one period."""
    sme_flag = is_sme(inputs)
    taxable_before = inputs.pretax_book_income + inputs.permanent_disallowances

    # Apply loss CF (expired losses dropped)
    if inputs.losses_age_years >= LOSSES_CF_YEARS:
        losses_used = Decimal("0")
        taxable_after = taxable_before
        losses_cf = Decimal("0")  # expired
    else:
        losses_used, taxable_after, losses_cf = apply_loss_cf(taxable_before, inputs.losses_brought_forward, sme_flag)

    nct = compute_national_corp_tax(taxable_after, sme_flag)
    lct = nct * LCT_RATE
    et = compute_enterprise_tax(taxable_after, sme_flag)
    slct = et * SLCT_MULTIPLIER

    # R&D credit (capped at 25% of NCT)
    rd_uncapped = inputs.rd_qualifying_expenditure * RD_BASE_RATE
    rd_cap = nct * RD_TAX_CREDIT_CAP_PCT
    rd_credit = min(rd_uncapped, rd_cap)

    total = max(Decimal("0"), nct - rd_credit) + lct + et + slct
    etr = (total / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")

    return JapaneseTaxOutput(
        taxable_income=taxable_after,
        losses_used=losses_used,
        national_corp_tax=nct,
        local_corp_tax=lct,
        enterprise_tax=et,
        special_local_corp_tax=slct,
        rd_credit=rd_credit,
        total_tax=total,
        effective_rate=etr,
        losses_carried_forward=losses_cf,
        is_sme=sme_flag,
    )

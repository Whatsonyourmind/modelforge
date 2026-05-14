"""French corporate-tax computations: Impôt sur les sociétés (IS), CVAE,
social-contribution surcharge, R&D tax credit (CIR), participation exemption,
group consolidation regime.

Pure Python, deterministic, follows ``italian_tax.py`` pattern.

References:
    - IS standard rate: 25% (Article 219 CGI, post-2022)
    - IS reduced rate: 15% on first €42,500 of profit for SMEs (CA < €10M
      and ≥75% individual ownership)
    - Social-contribution surcharge: 3.3% of IS exceeding €763K
      (Article 235 ter ZC CGI)
    - CVAE (Cotisation sur la Valeur Ajoutée des Entreprises): 0.094% (2026,
      progressively eliminated through 2027) — replacing the prior 0.28%
    - CIR (Crédit d'Impôt Recherche): 30% of R&D expenditure up to €100M,
      then 5% above
    - Participation exemption: 88% exemption on qualifying dividends/disposals
      (Article 145, 216 CGI; quote-part of 12% taxed)
    - Carried-forward losses: unlimited duration; €1M unlimited use, then 50%
      of excess above €1M (Article 209 I CGI)

NOTE: v0 scaffold. Rates are 2026 official; validate against current
Loi de Finances before production use.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


# ── Rates snapshot (2026-05-14, Loi de Finances 2026) ─────────────────────

IS_STANDARD_RATE = Decimal("0.25")
IS_REDUCED_RATE = Decimal("0.15")
IS_REDUCED_RATE_THRESHOLD = Decimal("42500")  # First €42,500 at 15% for SME
IS_REDUCED_RATE_TURNOVER_CAP = Decimal("10000000")  # CA < €10M for SME eligibility

SOCIAL_SURCHARGE_RATE = Decimal("0.033")
SOCIAL_SURCHARGE_THRESHOLD = Decimal("763000")

CVAE_RATE_2026 = Decimal("0.00094")  # 0.094% — being phased out by 2027
CIR_RATE_FIRST_TIER = Decimal("0.30")
CIR_RATE_SECOND_TIER = Decimal("0.05")
CIR_FIRST_TIER_CAP = Decimal("100000000")  # €100M

PARTICIPATION_EXEMPTION_PCT = Decimal("0.88")  # 88% exempt
PARTICIPATION_QUOTE_PART = Decimal("0.12")     # 12% taxed (quote-part)

LOSSES_CF_UNLIMITED_USE = Decimal("1000000")  # €1M
LOSSES_CF_RESIDUAL_PCT = Decimal("0.50")       # 50% of excess above €1M


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FrenchTaxInputs:
    """Single-period inputs for French CT calc."""
    pretax_book_income: Decimal
    annual_turnover: Decimal = Decimal("0")  # For SME eligibility check
    permanent_disallowances: Decimal = Decimal("0")
    cir_qualifying_expenditure: Decimal = Decimal("0")
    losses_brought_forward: Decimal = Decimal("0")
    qualifying_dividends_received: Decimal = Decimal("0")
    individual_ownership_pct: Decimal = Decimal("0")  # for SME test (≥75%)
    value_added_eligible_for_cvae: Decimal = Decimal("0")  # base for CVAE


@dataclass
class FrenchTaxOutput:
    """Computed French CT position."""
    taxable_profits: Decimal
    losses_used: Decimal
    is_at_reduced_rate: Decimal
    is_at_standard_rate: Decimal
    is_total: Decimal
    social_surcharge: Decimal
    cir: Decimal  # research credit (negative tax)
    participation_exemption: Decimal
    cvae: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    losses_carried_forward: Decimal


# ── Computations ──────────────────────────────────────────────────────────


def apply_loss_cf(taxable: Decimal, losses_bf: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Apply loss CF with min-taxation rule: €1M unlimited, then 50% of excess."""
    if taxable <= 0:
        return Decimal("0"), taxable, losses_bf + abs(taxable)
    if losses_bf == 0:
        return Decimal("0"), taxable, Decimal("0")

    cap_unlimited = min(LOSSES_CF_UNLIMITED_USE, taxable)
    if taxable <= LOSSES_CF_UNLIMITED_USE:
        used = min(losses_bf, taxable)
        return used, taxable - used, losses_bf - used

    cap_residual = (taxable - LOSSES_CF_UNLIMITED_USE) * LOSSES_CF_RESIDUAL_PCT
    max_use = cap_unlimited + cap_residual
    used = min(losses_bf, max_use)
    return used, taxable - used, losses_bf - used


def compute_cir(qualifying: Decimal) -> Decimal:
    """R&D tax credit (Crédit d'Impôt Recherche)."""
    if qualifying <= 0:
        return Decimal("0")
    first_tier = min(qualifying, CIR_FIRST_TIER_CAP) * CIR_RATE_FIRST_TIER
    second_tier = max(Decimal("0"), qualifying - CIR_FIRST_TIER_CAP) * CIR_RATE_SECOND_TIER
    return first_tier + second_tier


def is_sme(inputs: FrenchTaxInputs) -> bool:
    """SME eligibility for reduced 15% rate: CA < €10M AND ≥75% individual ownership."""
    return (
        inputs.annual_turnover < IS_REDUCED_RATE_TURNOVER_CAP
        and inputs.individual_ownership_pct >= Decimal("0.75")
    )


def compute_french_tax(inputs: FrenchTaxInputs) -> FrenchTaxOutput:
    """End-to-end French CT position for one period."""
    # Adjust pretax book → taxable
    qualifying_div = inputs.qualifying_dividends_received
    participation_exempt = qualifying_div * PARTICIPATION_EXEMPTION_PCT

    taxable = (
        inputs.pretax_book_income
        + inputs.permanent_disallowances
        - participation_exempt  # 88% exemption on qualifying div
    )

    # Apply losses CF
    losses_used, taxable_after, losses_cf = apply_loss_cf(taxable, inputs.losses_brought_forward)

    # IS: split reduced/standard if SME
    if is_sme(inputs):
        is_reduced_base = min(taxable_after, IS_REDUCED_RATE_THRESHOLD)
        is_standard_base = max(Decimal("0"), taxable_after - IS_REDUCED_RATE_THRESHOLD)
    else:
        is_reduced_base = Decimal("0")
        is_standard_base = max(Decimal("0"), taxable_after)

    is_reduced = is_reduced_base * IS_REDUCED_RATE
    is_standard = is_standard_base * IS_STANDARD_RATE
    is_total_before_credits = is_reduced + is_standard

    # CIR (credit reducing IS)
    cir = compute_cir(inputs.cir_qualifying_expenditure)
    is_after_cir = max(Decimal("0"), is_total_before_credits - cir)

    # Social surcharge: 3.3% of IS above €763K
    surcharge_base = max(Decimal("0"), is_total_before_credits - SOCIAL_SURCHARGE_THRESHOLD)
    surcharge = surcharge_base * SOCIAL_SURCHARGE_RATE

    # CVAE on value-added
    cvae = inputs.value_added_eligible_for_cvae * CVAE_RATE_2026

    total = is_after_cir + surcharge + cvae
    etr = (total / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")

    return FrenchTaxOutput(
        taxable_profits=taxable_after,
        losses_used=losses_used,
        is_at_reduced_rate=is_reduced,
        is_at_standard_rate=is_standard,
        is_total=is_after_cir,
        social_surcharge=surcharge,
        cir=cir,
        participation_exemption=participation_exempt,
        cvae=cvae,
        total_tax=total,
        effective_rate=etr,
        losses_carried_forward=losses_cf,
    )

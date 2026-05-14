"""German corporate-tax computations: Körperschaftsteuer (KSt), Gewerbesteuer
(GewSt), Solidaritätszuschlag (SolZ), trade-tax add-backs (§ 8 GewStG), loss
carryforward minimum-taxation rule, Organschaft (fiscal unity).

Pure Python, deterministic, follows ``italian_tax.py`` pattern.

References:
    - KStG § 23: Körperschaftsteuer rate 15%
    - SolZ: 5.5% surcharge on KSt (since 1991)
    - GewStG § 11: trade-tax baseline rate 3.5% × municipal multiplier
      (Hebesatz). Munich 490%, Berlin 410%, Frankfurt 460%, average ~400%.
    - § 10a EStG: minimum-taxation rule on losses CF — €1M unlimited use,
      then only 60% of excess above €1M can be offset
    - § 8 GewStG: add-backs (interest expense, rents, royalties — 25%
      add-back after €200K free amount)
    - Organschaft (§ 14-19 KStG): fiscal unity allows P&L pooling

NOTE: v0 scaffold. German tax is jurisdiction-sensitive due to Hebesatz
variation; for production use, pass the actual municipal Hebesatz (Hebesatz_pct).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# ── Rates snapshot (2026-05-14) ─────────────────────────────────────────

KST_RATE = Decimal("0.15")                  # 15% Körperschaftsteuer
SOLZ_RATE = Decimal("0.055")                # 5.5% Solidaritätszuschlag (of KSt)
GEWST_BASE_RATE = Decimal("0.035")          # 3.5% Gewerbesteuer Steuermesszahl
DEFAULT_HEBESATZ = Decimal("4.00")          # 400% municipal multiplier (avg)

GEWST_ADDBACK_FRACTION_FINANCING = Decimal("0.25")  # 25% of interest/rent above threshold
GEWST_ADDBACK_FREE_AMOUNT = Decimal("200000")        # €200K free amount

LOSSES_CF_MIN_USE = Decimal("1000000")  # €1M unlimited
LOSSES_CF_RESIDUAL_PCT = Decimal("0.60")  # then 60% of excess above €1M


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GermanTaxInputs:
    """Single-period inputs for German corporate-tax calc."""
    pretax_book_income: Decimal
    permanent_disallowances: Decimal = Decimal("0")
    interest_expense: Decimal = Decimal("0")  # for § 8 GewStG add-back
    rent_royalty_expense: Decimal = Decimal("0")  # for § 8 add-back
    losses_brought_forward: Decimal = Decimal("0")
    hebesatz: Decimal = DEFAULT_HEBESATZ  # municipal multiplier (e.g. 4.00 = 400%)
    organschaft_member: bool = False
    organschaft_attributed_income: Decimal = Decimal("0")  # P&L from subordinate entity


@dataclass
class GermanTaxOutput:
    """Computed German CT position."""
    taxable_kst_base: Decimal
    taxable_gewst_base: Decimal
    gewst_addbacks: Decimal
    losses_used: Decimal
    kst: Decimal
    solz: Decimal
    gewst: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    losses_carried_forward: Decimal
    overall_tax_burden_pct: Decimal  # KSt+SolZ+GewSt as % of pretax book income


# ── Computations ────────────────────────────────────────────────────────


def compute_gewst_addbacks(inputs: GermanTaxInputs) -> Decimal:
    """§ 8 GewStG add-backs for trade tax base.

    25% of (interest + rents + royalties) above €200K free amount.
    """
    total_financing_expense = inputs.interest_expense + inputs.rent_royalty_expense
    above_free = max(Decimal("0"), total_financing_expense - GEWST_ADDBACK_FREE_AMOUNT)
    return above_free * GEWST_ADDBACK_FRACTION_FINANCING


def apply_loss_cf(taxable: Decimal, losses_bf: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Minimum-taxation rule: €1M unlimited use, then 60% of excess.

    Returns (used, taxable_after, losses_remaining).
    """
    if taxable <= 0:
        return Decimal("0"), taxable, losses_bf + abs(taxable)
    if losses_bf == 0:
        return Decimal("0"), taxable, Decimal("0")

    cap_unlimited = min(LOSSES_CF_MIN_USE, taxable)
    if taxable <= LOSSES_CF_MIN_USE:
        used = min(losses_bf, taxable)
        return used, taxable - used, losses_bf - used

    cap_residual = (taxable - LOSSES_CF_MIN_USE) * LOSSES_CF_RESIDUAL_PCT
    max_use = cap_unlimited + cap_residual
    used = min(losses_bf, max_use)
    return used, taxable - used, losses_bf - used


def compute_german_tax(inputs: GermanTaxInputs) -> GermanTaxOutput:
    """End-to-end German CT calc for one period.

    Combined effective burden (KSt + SolZ + GewSt) at default Hebesatz 400%:
    ~30-32% on profitable corp.
    """
    base_book = inputs.pretax_book_income + inputs.permanent_disallowances
    if inputs.organschaft_member:
        base_book += inputs.organschaft_attributed_income

    # KSt base (no add-backs — those are GewSt-specific)
    losses_used_kst, kst_base, losses_cf_kst = apply_loss_cf(base_book, inputs.losses_brought_forward)

    # GewSt base (with § 8 add-backs)
    addbacks = compute_gewst_addbacks(inputs)
    gewst_base_before_losses = base_book + addbacks
    # GewSt uses same losses CF (simplified — they're actually separate pools)
    losses_used_gewst, gewst_base, _ = apply_loss_cf(gewst_base_before_losses, inputs.losses_brought_forward)

    # Compute taxes
    kst = max(Decimal("0"), kst_base) * KST_RATE
    solz = kst * SOLZ_RATE
    gewst = max(Decimal("0"), gewst_base) * GEWST_BASE_RATE * inputs.hebesatz
    total = kst + solz + gewst

    etr = (total / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")
    # Overall burden incl. SolZ
    burden_pct = etr * 100

    return GermanTaxOutput(
        taxable_kst_base=kst_base,
        taxable_gewst_base=gewst_base,
        gewst_addbacks=addbacks,
        losses_used=losses_used_kst,
        kst=kst,
        solz=solz,
        gewst=gewst,
        total_tax=total,
        effective_rate=etr,
        losses_carried_forward=losses_cf_kst,
        overall_tax_burden_pct=burden_pct,
    )

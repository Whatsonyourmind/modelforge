"""Swiss corporate-tax computations: federal direct tax (DBG/LIFD) +
cantonal/communal layers, participation deduction (Beteiligungsabzug),
patent box (Patentbox / IP-Box), R&D super-deduction, capital tax,
loss carry-forward, BEPS 2.0 minimum 15% top-up.

Pure Python, deterministic, follows ``italian_tax.py`` pattern.

References:
    - Federal direct tax (Bundesgesetz über die direkte Bundessteuer / LIFD):
      flat 8.5% on profit after tax → effective ~7.83% pre-tax (because
      the federal tax itself is deductible)
    - Cantonal + communal: vary widely. National average ~14-21% combined
      effective rate including federal. Defaults to Zug (lowest, ~11.85%
      total) and Geneva (high, ~14.0%) as references; user passes their
      canton via `canton_total_rate` to override.
    - Participation deduction (Art. 69-70 LIFD / DBG): proportional
      reduction of tax on participation income. Implemented as effective
      exemption percentage on qualifying dividends/cap gains (typically
      effectively ~95-100% if the participation thresholds are met:
      ≥10% stake or ≥CHF 1M acquisition cost).
    - Patent box (Art. 24a-b StHG, federal frame; cantonal application):
      up to 90% reduction of net profits from qualified IP, capped at
      70% of total taxable profit (cantonal cap, varies). Uses 90% as
      the headline reduction (Zug, Nidwalden) and lets caller scale down.
    - R&D super-deduction (Art. 25a StHG): up to 50% extra deduction on
      qualifying R&D expenses, capped at 70% of pre-special-deduction
      profit. Cantonally enacted; defaults to 50% (Zug, Bern) where
      adopted, 0% otherwise.
    - Loss carry-forward: 7 years, no time-limit at the cantonal level
      in some cantons (Zurich, Vaud, Bern post-2026). 100% offset, no
      Spanish-style 70% cap.
    - BEPS 2.0 OECD Pillar Two minimum 15%: in force from 2024 in CH
      via Qualified Domestic Minimum Top-up Tax (QDMTT). Applies to
      groups with consolidated revenue ≥ EUR 750M.

NOTE: v0 scaffold. Cantonal rates vary widely (Zug 11.85% vs Geneva 14.0%
vs Vaud 14.0% vs Zurich 19.7% pre-2024 reform → 19.65% post). Module
takes the *combined* effective rate as input, leaving cantonal selection
to the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


# ── Rates snapshot (2026, federal LIFD; cantonal varies) ──────────────────

FEDERAL_RATE_ON_PRETAX = Decimal("0.0783")    # Effective when federal tax itself deductible
FEDERAL_RATE_NOMINAL = Decimal("0.085")       # Statutory rate on profit AFTER tax

# Reference cantonal+communal+federal combined rates (illustrative; pass real one).
CANTON_TOTAL_RATES_2026 = {
    "ZG": Decimal("0.1185"),  # Zug — lowest in CH
    "NW": Decimal("0.1197"),  # Nidwalden
    "OW": Decimal("0.1274"),  # Obwalden
    "LU": Decimal("0.1257"),  # Lucerne
    "BS": Decimal("0.1305"),  # Basel-Stadt
    "GE": Decimal("0.1399"),  # Geneva
    "VD": Decimal("0.1400"),  # Vaud
    "BE": Decimal("0.1986"),  # Bern
    "ZH": Decimal("0.1965"),  # Zurich (post-2024 reform)
}
DEFAULT_CANTON_RATE = CANTON_TOTAL_RATES_2026["ZH"]   # safer mid-high default

PARTICIPATION_EXEMPTION_PCT = Decimal("1.00")    # Effective full exemption when thresholds met
PARTICIPATION_THRESHOLD_STAKE = Decimal("0.10")   # ≥10% stake
PARTICIPATION_THRESHOLD_VALUE = Decimal("1000000") # OR ≥CHF 1M acquisition cost

PATENT_BOX_MAX_REDUCTION_PCT = Decimal("0.90")    # 90% reduction on qualifying IP profit
PATENT_BOX_OVERALL_CAP_PCT = Decimal("0.70")      # ≤70% of total profit (cantonal cap)

RD_SUPER_DEDUCTION_PCT = Decimal("0.50")          # 50% extra deduction on R&D
RD_OVERALL_CAP_PCT = Decimal("0.70")              # All special deductions ≤70% of pre-special profit

LOSSES_CF_YEARS = 7   # Standard; some cantons unlimited

# BEPS Pillar 2
BEPS_TURNOVER_THRESHOLD = Decimal("750000000")    # EUR 750M consolidated group revenue
BEPS_MIN_RATE = Decimal("0.15")


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SwissTaxInputs:
    """Single-period inputs for Swiss CT calc."""
    pretax_book_income: Decimal
    canton: str = "ZH"                                  # Used to look up combined rate if not overridden
    canton_total_rate: Decimal | None = None             # Overrides the canton lookup
    permanent_disallowances: Decimal = Decimal("0")
    losses_brought_forward: Decimal = Decimal("0")
    qualifying_participation_income: Decimal = Decimal("0")
    participation_threshold_met: bool = False
    patent_box_qualifying_profit: Decimal = Decimal("0")
    rd_qualifying_expenditure: Decimal = Decimal("0")
    consolidated_group_revenue: Decimal = Decimal("0")   # For BEPS Pillar 2 trigger


@dataclass
class SwissTaxOutput:
    """Computed Swiss CT position."""
    taxable_profits_pre_special: Decimal
    losses_used: Decimal
    participation_deduction: Decimal
    patent_box_deduction: Decimal
    rd_super_deduction: Decimal
    taxable_profits_post_special: Decimal
    cantonal_rate_applied: Decimal
    federal_tax: Decimal
    cantonal_tax: Decimal
    total_tax_pre_topup: Decimal
    beps_topup: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    losses_carried_forward: Decimal


# ── Computations ─────────────────────────────────────────────────────────


def apply_loss_cf(taxable: Decimal, losses_bf: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """100% offset, no Spanish-style cap. Returns (used, remaining_taxable, losses_remaining)."""
    if taxable <= 0:
        return Decimal("0"), taxable, losses_bf + abs(taxable)
    if losses_bf == 0:
        return Decimal("0"), taxable, Decimal("0")
    used = min(losses_bf, taxable)
    return used, taxable - used, losses_bf - used


def applicable_rate(inputs: SwissTaxInputs) -> Decimal:
    """Pick the combined federal+cantonal+communal effective rate."""
    if inputs.canton_total_rate is not None:
        return inputs.canton_total_rate
    return CANTON_TOTAL_RATES_2026.get(inputs.canton, DEFAULT_CANTON_RATE)


def compute_participation_deduction(inputs: SwissTaxInputs) -> Decimal:
    """Participation income exempt when thresholds met (≥10% stake OR ≥CHF 1M)."""
    if not inputs.participation_threshold_met:
        return Decimal("0")
    return inputs.qualifying_participation_income * PARTICIPATION_EXEMPTION_PCT


def compute_patent_box_deduction(qualifying_profit: Decimal,
                                  total_taxable: Decimal) -> Decimal:
    """90% reduction on qualifying IP profit, capped at 70% of total taxable."""
    raw = qualifying_profit * PATENT_BOX_MAX_REDUCTION_PCT
    cap = max(Decimal("0"), total_taxable * PATENT_BOX_OVERALL_CAP_PCT)
    return min(raw, cap)


def compute_rd_super_deduction(rd_expenditure: Decimal,
                               total_taxable: Decimal,
                               other_special_deductions: Decimal) -> Decimal:
    """50% additional deduction on qualifying R&D, capped at 70% of pre-special profit."""
    raw = rd_expenditure * RD_SUPER_DEDUCTION_PCT
    cap = max(Decimal("0"), total_taxable * RD_OVERALL_CAP_PCT - other_special_deductions)
    return min(raw, max(Decimal("0"), cap))


def compute_swiss_tax(inputs: SwissTaxInputs) -> SwissTaxOutput:
    """End-to-end Swiss CT calc for one period."""
    pre_loss = inputs.pretax_book_income + inputs.permanent_disallowances
    losses_used, taxable_after_loss, losses_cf = apply_loss_cf(
        pre_loss, inputs.losses_brought_forward,
    )

    # Special deductions order: participation → patent box → R&D super-deduction
    participation = compute_participation_deduction(inputs)
    base_after_part = max(Decimal("0"), taxable_after_loss - participation)

    patent = compute_patent_box_deduction(
        inputs.patent_box_qualifying_profit, base_after_part,
    )
    base_after_patent = max(Decimal("0"), base_after_part - patent)

    rd = compute_rd_super_deduction(
        inputs.rd_qualifying_expenditure, base_after_part, patent,
    )
    taxable_post_special = max(Decimal("0"), base_after_patent - rd)

    rate = applicable_rate(inputs)
    # We use the combined effective rate (federal + cantonal + communal).
    # Federal is included in the combined rate; we surface the federal
    # component for transparency only.
    federal_tax = taxable_post_special * FEDERAL_RATE_ON_PRETAX
    total_pre_topup = taxable_post_special * rate
    cantonal_tax = max(Decimal("0"), total_pre_topup - federal_tax)

    # BEPS Pillar 2: top up to 15% if effective rate below 15% AND group qualifies
    if (inputs.consolidated_group_revenue >= BEPS_TURNOVER_THRESHOLD
            and inputs.pretax_book_income > 0
            and rate < BEPS_MIN_RATE):
        target = inputs.pretax_book_income * BEPS_MIN_RATE
        beps_topup = max(Decimal("0"), target - total_pre_topup)
    else:
        beps_topup = Decimal("0")

    total = total_pre_topup + beps_topup
    etr = (total / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")

    return SwissTaxOutput(
        taxable_profits_pre_special=base_after_part,
        losses_used=losses_used,
        participation_deduction=participation,
        patent_box_deduction=patent,
        rd_super_deduction=rd,
        taxable_profits_post_special=taxable_post_special,
        cantonal_rate_applied=rate,
        federal_tax=federal_tax,
        cantonal_tax=cantonal_tax,
        total_tax_pre_topup=total_pre_topup,
        beps_topup=beps_topup,
        total_tax=total,
        effective_rate=etr,
        losses_carried_forward=losses_cf,
    )

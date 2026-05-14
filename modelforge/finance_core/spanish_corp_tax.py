"""Spanish corporate-tax computations: Impuesto sobre Sociedades (IS), small
entity reduced rate, R&D tax credit (Deducción I+D+i), participation
exemption, group consolidation regime, ICAC limitation.

Pure Python, deterministic, follows ``italian_tax.py`` pattern.

References:
    - IS standard rate: 25% (Article 29 LIS)
    - IS reduced rates: 23% for SMEs with net turnover < €1M (Article 29.1 LIS);
      15% for newly created entities, first two profitable years
    - R&D / innovation deduction: 25% of basic R&D + 42% of incremental + 17%
      of researcher salary; 12% of innovation activities (Article 35 LIS)
    - Participation exemption: 95% exemption on qualifying dividends/disposals
      (Article 21 LIS — capped at 95% from 2021)
    - Carried-forward losses: unlimited duration; 70% of taxable income limit
      (with €1M minimum unlimited) — Article 26 LIS
    - Minimum tax 15% (introduced 2022) for large taxpayers (CA ≥ €20M):
      Article 30 bis LIS

NOTE: v0 scaffold. Rates are 2026 official; some regional/foral regimes
(Basque Country, Navarre) differ — this module covers the national regime.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


# ── Rates snapshot (2026-05-14, LIS) ─────────────────────────────────────

IS_STANDARD_RATE = Decimal("0.25")
IS_SME_RATE = Decimal("0.23")        # Net turnover < €1M
IS_NEWLY_CREATED_RATE = Decimal("0.15")  # First 2 profitable years
IS_MIN_TAX_RATE = Decimal("0.15")     # Minimum effective rate for CA ≥ €20M
SME_TURNOVER_CAP = Decimal("1000000")
LARGE_TAXPAYER_CAP = Decimal("20000000")

RD_BASIC_DEDUCTION = Decimal("0.25")
RD_INCREMENTAL_DEDUCTION = Decimal("0.42")
RD_RESEARCHER_SALARY_DEDUCTION = Decimal("0.17")
INNOVATION_DEDUCTION = Decimal("0.12")

PARTICIPATION_EXEMPTION_PCT = Decimal("0.95")  # 95% post-2021

LOSSES_CF_LIMIT_PCT = Decimal("0.70")  # 70% of taxable income
LOSSES_CF_MIN_USE = Decimal("1000000")  # €1M unlimited regardless


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SpanishTaxInputs:
    """Single-period inputs for Spanish CT calc."""
    pretax_book_income: Decimal
    net_turnover: Decimal = Decimal("0")
    permanent_disallowances: Decimal = Decimal("0")
    losses_brought_forward: Decimal = Decimal("0")
    qualifying_dividends_received: Decimal = Decimal("0")
    rd_basic_expenditure: Decimal = Decimal("0")
    rd_incremental_expenditure: Decimal = Decimal("0")
    rd_researcher_salary: Decimal = Decimal("0")
    innovation_expenditure: Decimal = Decimal("0")
    is_newly_created: bool = False  # First 2 profitable years
    profitable_years_count: int = 0


@dataclass
class SpanishTaxOutput:
    """Computed Spanish CT position."""
    taxable_profits: Decimal
    losses_used: Decimal
    is_gross: Decimal
    rd_deduction: Decimal
    innovation_deduction: Decimal
    participation_exemption: Decimal
    is_net_pre_min_tax: Decimal
    min_tax_applied: bool
    total_tax: Decimal
    effective_rate: Decimal
    losses_carried_forward: Decimal


# ── Computations ─────────────────────────────────────────────────────────


def apply_loss_cf(taxable: Decimal, losses_bf: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """70% of taxable income limit, with €1M unlimited use."""
    if taxable <= 0:
        return Decimal("0"), taxable, losses_bf + abs(taxable)
    if losses_bf == 0:
        return Decimal("0"), taxable, Decimal("0")

    cap = max(LOSSES_CF_MIN_USE, taxable * LOSSES_CF_LIMIT_PCT)
    used = min(losses_bf, cap, taxable)
    return used, taxable - used, losses_bf - used


def applicable_rate(inputs: SpanishTaxInputs) -> Decimal:
    """Pick the applicable corporate-tax rate."""
    if inputs.is_newly_created and inputs.profitable_years_count <= 2:
        return IS_NEWLY_CREATED_RATE
    if inputs.net_turnover > 0 and inputs.net_turnover < SME_TURNOVER_CAP:
        return IS_SME_RATE
    return IS_STANDARD_RATE


def compute_rd_deductions(inputs: SpanishTaxInputs) -> Decimal:
    """R&D + innovation deductions (Article 35 LIS)."""
    rd = (
        inputs.rd_basic_expenditure * RD_BASIC_DEDUCTION
        + inputs.rd_incremental_expenditure * RD_INCREMENTAL_DEDUCTION
        + inputs.rd_researcher_salary * RD_RESEARCHER_SALARY_DEDUCTION
    )
    innovation = inputs.innovation_expenditure * INNOVATION_DEDUCTION
    return rd + innovation


def compute_spanish_tax(inputs: SpanishTaxInputs) -> SpanishTaxOutput:
    """End-to-end Spanish CT calc for one period."""
    participation = inputs.qualifying_dividends_received * PARTICIPATION_EXEMPTION_PCT

    taxable = (
        inputs.pretax_book_income
        + inputs.permanent_disallowances
        - participation
    )

    losses_used, taxable_after, losses_cf = apply_loss_cf(taxable, inputs.losses_brought_forward)

    rate = applicable_rate(inputs)
    is_gross = max(Decimal("0"), taxable_after) * rate

    rd = inputs.rd_basic_expenditure * RD_BASIC_DEDUCTION + \
         inputs.rd_incremental_expenditure * RD_INCREMENTAL_DEDUCTION + \
         inputs.rd_researcher_salary * RD_RESEARCHER_SALARY_DEDUCTION
    innovation = inputs.innovation_expenditure * INNOVATION_DEDUCTION

    is_net_pre_min = max(Decimal("0"), is_gross - rd - innovation)

    # Minimum 15% rule (large taxpayers, post-2022)
    is_large = inputs.net_turnover >= LARGE_TAXPAYER_CAP
    if is_large and taxable_after > 0:
        min_tax = taxable_after * IS_MIN_TAX_RATE
        if is_net_pre_min < min_tax:
            total = min_tax
            min_applied = True
        else:
            total = is_net_pre_min
            min_applied = False
    else:
        total = is_net_pre_min
        min_applied = False

    etr = (total / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")

    return SpanishTaxOutput(
        taxable_profits=taxable_after,
        losses_used=losses_used,
        is_gross=is_gross,
        rd_deduction=rd,
        innovation_deduction=innovation,
        participation_exemption=participation,
        is_net_pre_min_tax=is_net_pre_min,
        min_tax_applied=min_applied,
        total_tax=total,
        effective_rate=etr,
        losses_carried_forward=losses_cf,
    )

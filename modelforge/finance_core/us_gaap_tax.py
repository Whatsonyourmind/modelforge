"""US corporate-tax computations: federal CIT, state CIT, NOL CF, R&D credit,
GILTI/BEAT high-level, Section 162(m), ASC 740 DTA/DTL methodology.

Pure Python, deterministic, no pydantic side effects. Follows the same pattern
as ``italian_tax.py``.

References:
    - Federal CIT: 26 USC § 11; rate 21% (TCJA, unchanged 2018-2026)
    - NOL carryforward: 26 USC § 172; 80% taxable-income limitation post-2017
    - R&D credit: 26 USC § 41; regular method 20% of QREs above base amount,
      or alternative simplified credit (ASC) 14% of QREs above 50% of prior-3yr avg
    - GILTI: 26 USC § 951A; 50% deduction → effective 10.5-13.125% on tested income
    - BEAT: 26 USC § 59A; 10% (12.5% post-2025) of modified taxable income for
      large taxpayers (gross receipts > $500M, base-erosion ratio ≥ 3%)
    - § 162(m): 26 USC § 162(m); $1M deduction limit on top-5 executive comp
    - ASC 740: temporary differences → DTA/DTL at enacted future rate

NOTE: v0 scaffold. All rates accurate as of 2026-05-14 but state CIT varies
49 ways across US states; this module uses a single blended state rate
(default: 6.0% post-deduction). For state-specific deals (CA, NY, TX, FL),
override the state_rate parameter with the actual jurisdiction's rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal, Optional

# ── Rates snapshot (2026-05-14) ─────────────────────────────────────────

FEDERAL_CIT_RATE = Decimal("0.21")      # 21% (TCJA standard rate)
DEFAULT_STATE_CIT_RATE = Decimal("0.06")  # Blended; varies CA 8.84% / NY 7.25% / TX 0% / FL 5.5%
NOL_LIMITATION = Decimal("0.80")         # 80% of taxable income (post-2017 NOLs)
GILTI_DEDUCTION = Decimal("0.50")        # 50% § 250 deduction
GILTI_EFFECTIVE_LOWER = Decimal("0.105")  # 10.5% effective on GILTI tested income
GILTI_EFFECTIVE_UPPER = Decimal("0.13125")
BEAT_RATE = Decimal("0.125")             # 12.5% post-2025 (was 10% in 2018-2025)
BEAT_THRESHOLD_GROSS_RECEIPTS = Decimal("500000000")  # $500M
BEAT_BASE_EROSION_RATIO_TRIGGER = Decimal("0.03")     # 3%
SECTION_162M_DEDUCTION_LIMIT = Decimal("1000000")     # $1M per covered executive
RD_CREDIT_REGULAR_RATE = Decimal("0.20")               # 20% of QREs above base
RD_CREDIT_ASC_RATE = Decimal("0.14")                   # 14% of QREs above 50% of avg


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class USTaxInputs:
    """Single-period inputs for US corporate-tax calc."""
    pretax_book_income: Decimal
    permanent_differences: Decimal = Decimal("0")  # M-1 perm diffs (entertainment, fines)
    temporary_differences_origin: Decimal = Decimal("0")  # M-1 temp diff originating (creates DTL)
    temporary_differences_reversal: Decimal = Decimal("0")  # M-1 temp diff reversing (uses DTA)
    nol_brought_forward: Decimal = Decimal("0")
    state_rate: Decimal = DEFAULT_STATE_CIT_RATE
    state_deduction_on_federal: bool = True  # state tax deductible federally? (yes, mostly)
    rd_credit_qre: Decimal = Decimal("0")  # qualified research expenses
    rd_credit_base: Decimal = Decimal("0")  # base amount (prior-period avg)
    rd_method: Literal["regular", "asc"] = "asc"
    gilti_tested_income: Decimal = Decimal("0")
    gilti_qbai: Decimal = Decimal("0")  # qualified business asset investment (10% deemed return)
    beat_modified_taxable_income: Decimal = Decimal("0")
    beat_apply: bool = False
    section_162m_disallowed: Decimal = Decimal("0")  # covered exec comp over $1M


@dataclass
class USTaxOutput:
    """Computed per-period US tax position."""
    taxable_income_before_nol: Decimal
    nol_used: Decimal
    taxable_income_after_nol: Decimal
    federal_cit_current: Decimal
    state_cit_current: Decimal
    gilti_inclusion: Decimal
    beat_addition: Decimal
    rd_credit: Decimal
    total_current_tax: Decimal
    effective_tax_rate: Decimal
    # ASC 740 deferred
    dta_origination: Decimal
    dtl_origination: Decimal
    deferred_tax_expense: Decimal
    # NOL roll
    nol_carried_forward: Decimal


# ── Computations ────────────────────────────────────────────────────────


def compute_taxable_income(inputs: USTaxInputs) -> Decimal:
    """Pretax book → taxable income via M-1 reconciliation.

    Taxable income = Book income
        + Permanent differences (non-deductible)
        + Temporary differences originating (creates DTL)
        - Temporary differences reversing (uses DTA)
        + § 162(m) disallowed exec comp
    """
    return (
        inputs.pretax_book_income
        + inputs.permanent_differences
        + inputs.temporary_differences_origin
        - inputs.temporary_differences_reversal
        + inputs.section_162m_disallowed
    )


def apply_nol(taxable_income: Decimal, nol_bf: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Apply NOL CF with 80% limitation. Returns (nol_used, ti_after, nol_remaining)."""
    if taxable_income <= 0:
        # Current-year loss → NOL increases
        return Decimal("0"), taxable_income, nol_bf + abs(taxable_income)
    cap = taxable_income * NOL_LIMITATION
    nol_used = min(cap, nol_bf)
    return nol_used, taxable_income - nol_used, nol_bf - nol_used


def compute_rd_credit(inputs: USTaxInputs) -> Decimal:
    """R&D credit per § 41 — regular method or alternative simplified."""
    if inputs.rd_credit_qre <= 0:
        return Decimal("0")
    excess = max(Decimal("0"), inputs.rd_credit_qre - inputs.rd_credit_base)
    rate = RD_CREDIT_REGULAR_RATE if inputs.rd_method == "regular" else RD_CREDIT_ASC_RATE
    return excess * rate


def compute_gilti(tested_income: Decimal, qbai: Decimal) -> Decimal:
    """GILTI inclusion = tested income - (QBAI × 10%).

    Effective rate after § 250 50% deduction is ~10.5% on GILTI net.
    """
    if tested_income <= 0:
        return Decimal("0")
    deemed_return = qbai * Decimal("0.10")
    return max(Decimal("0"), tested_income - deemed_return)


def compute_beat(inputs: USTaxInputs, regular_tax: Decimal) -> Decimal:
    """BEAT add-on: max(0, BEAT_rate × MTI − regular_tax).

    Only applies if gross receipts ≥ $500M and base-erosion ratio ≥ 3% (caller
    must signal via ``beat_apply=True``).
    """
    if not inputs.beat_apply:
        return Decimal("0")
    beat_liab = BEAT_RATE * inputs.beat_modified_taxable_income
    return max(Decimal("0"), beat_liab - regular_tax)


def compute_us_tax(inputs: USTaxInputs, future_rate: Optional[Decimal] = None) -> USTaxOutput:
    """End-to-end US corporate tax position for one period.

    Returns ``USTaxOutput`` with current tax, deferred tax (ASC 740), and
    NOL carryforward roll.

    ``future_rate`` (for DTA/DTL) defaults to ``FEDERAL_CIT_RATE + state_rate``.
    """
    ti_before = compute_taxable_income(inputs)
    nol_used, ti_after, nol_cf = apply_nol(ti_before, inputs.nol_brought_forward)

    # State CIT first (deductible federally if elected)
    state_cit = ti_after * inputs.state_rate if ti_after > 0 else Decimal("0")

    if inputs.state_deduction_on_federal:
        federal_base = ti_after - state_cit
    else:
        federal_base = ti_after
    federal_cit_base = max(Decimal("0"), federal_base) * FEDERAL_CIT_RATE

    gilti = compute_gilti(inputs.gilti_tested_income, inputs.gilti_qbai)
    gilti_tax = gilti * Decimal("0.5") * FEDERAL_CIT_RATE  # § 250 50% deduction baked in

    regular_tax = federal_cit_base + state_cit + gilti_tax
    rd_credit = compute_rd_credit(inputs)
    regular_after_credit = max(Decimal("0"), regular_tax - rd_credit)

    beat = compute_beat(inputs, regular_after_credit)
    total_current = regular_after_credit + beat

    etr = (total_current / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")

    # ASC 740 deferred (simplified — full pos requires more inputs)
    rate_future = future_rate or (FEDERAL_CIT_RATE + inputs.state_rate)
    dta_origin = inputs.temporary_differences_reversal * rate_future
    dtl_origin = inputs.temporary_differences_origin * rate_future
    deferred_expense = dtl_origin - dta_origin

    return USTaxOutput(
        taxable_income_before_nol=ti_before,
        nol_used=nol_used,
        taxable_income_after_nol=ti_after,
        federal_cit_current=federal_cit_base,
        state_cit_current=state_cit,
        gilti_inclusion=gilti,
        beat_addition=beat,
        rd_credit=rd_credit,
        total_current_tax=total_current,
        effective_tax_rate=etr,
        dta_origination=dta_origin,
        dtl_origination=dtl_origin,
        deferred_tax_expense=deferred_expense,
        nol_carried_forward=nol_cf,
    )

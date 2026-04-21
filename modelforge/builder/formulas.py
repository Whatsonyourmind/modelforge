"""Formula string builders.

No raw Excel strings outside this module — every formula goes through
a helper. Keeps the formula grammar centralized and auditable.

All formulas use named ranges or explicit sheet refs, never magic numbers.
Scenario toggle lives in the named range `scenario_index` (1/2/3 for
WORST/BASE/BEST) and every scenario-dependent read goes through
`scenario_pick()`.
"""

from __future__ import annotations

from typing import Iterable


# ─────────────────────────────────────────────────────────────────────────────
# Cross-sheet references
# ─────────────────────────────────────────────────────────────────────────────


def xref(sheet: str, ref: str) -> str:
    """Return a safe cross-sheet reference string like `='Assumptions'!$B$12`.

    Always quotes sheet name, always absolute.
    """
    return f"'{sheet}'!{ref}"


def abs_ref(col: str, row: int) -> str:
    return f"${col}${row}"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario dispatch
# ─────────────────────────────────────────────────────────────────────────────


def scenario_pick(worst_ref: str, base_ref: str, best_ref: str) -> str:
    """Pick the active scenario value using the toggle named range.

    scenario_index ∈ {1,2,3} for WORST/BASE/BEST.
    """
    return f"=CHOOSE(scenario_index,{worst_ref},{base_ref},{best_ref})"


def scenario_pick_from_row(sheet: str, row: int, worst_col: str, base_col: str, best_col: str) -> str:
    return scenario_pick(
        f"'{sheet}'!${worst_col}${row}",
        f"'{sheet}'!${base_col}${row}",
        f"'{sheet}'!${best_col}${row}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Arithmetic primitives
# ─────────────────────────────────────────────────────────────────────────────


def growth(prior_ref: str, growth_ref: str) -> str:
    """prior * (1 + growth)."""
    return f"={prior_ref}*(1+{growth_ref})"


def margin(base_ref: str, margin_ref: str) -> str:
    """base * margin."""
    return f"={base_ref}*{margin_ref}"


def negated(ref: str) -> str:
    """-ref   (costs-negative sign convention)."""
    return f"=-{ref}"


def sum_range(start: str, end: str) -> str:
    return f"=SUM({start}:{end})"


def sum_list(refs: Iterable[str]) -> str:
    return "=" + "+".join(refs)


def ratio(numer: str, denom: str) -> str:
    """IFERROR(numer/denom, 0)  — safe division."""
    return f"=IFERROR({numer}/{denom},0)"


def mult(a: str, b: str) -> str:
    return f"={a}*{b}"


def diff(a: str, b: str) -> str:
    return f"={a}-{b}"


def add(a: str, b: str) -> str:
    return f"={a}+{b}"


# ─────────────────────────────────────────────────────────────────────────────
# Financial patterns
# ─────────────────────────────────────────────────────────────────────────────


def all_in_rate(reference_rate_ref: str, margin_bps_ref: str, floor_ref: str) -> str:
    """max(reference_rate, floor) + margin_bps/10000.

    Returns a decimal rate.
    """
    return (
        f"=MAX({reference_rate_ref},{floor_ref})+({margin_bps_ref}/10000)"
    )


def interest_expense(avg_debt_ref: str, rate_ref: str) -> str:
    """Average-balance interest: avg_debt * rate."""
    return f"=-{avg_debt_ref}*{rate_ref}"  # costs negative


def average_of(prior_ref: str, current_ref: str) -> str:
    return f"=({prior_ref}+{current_ref})/2"


def ebitda_multiple(debt_ref: str, ebitda_ref: str) -> str:
    return f"=IFERROR({debt_ref}/{ebitda_ref},0)"


def interest_coverage(ebitda_ref: str, interest_ref: str) -> str:
    """EBITDA / |interest|  — returns a coverage multiple."""
    return f"=IFERROR({ebitda_ref}/ABS({interest_ref}),0)"


def headroom(actual_ref: str, threshold_ref: str, direction: str = "max") -> str:
    """Covenant headroom.

    direction='max' for leverage-type covenants (actual must be ≤ threshold):
        headroom = (threshold - actual) / threshold
    direction='min' for coverage-type covenants (actual must be ≥ threshold):
        headroom = (actual - threshold) / threshold
    """
    if direction == "max":
        return f"=IFERROR(({threshold_ref}-{actual_ref})/{threshold_ref},0)"
    return f"=IFERROR(({actual_ref}-{threshold_ref})/{threshold_ref},0)"


# ─────────────────────────────────────────────────────────────────────────────
# IRR / cash flow helpers
# ─────────────────────────────────────────────────────────────────────────────


def irr(range_start: str, range_end: str) -> str:
    return f"=IRR({range_start}:{range_end})"


def xirr(cashflow_range: str, date_range: str) -> str:
    return f"=XIRR({cashflow_range},{date_range})"


def moic(inflows_range: str, outflows_abs_ref: str) -> str:
    """MoIC = sum(positive cashflows) / |initial outflow|."""
    return f"=IFERROR(SUMIF({inflows_range},\">0\")/ABS({outflows_abs_ref}),0)"


def eir(cashflow_range: str, guess: str = "0.08") -> str:
    """IFRS 9 Effective Interest Rate (EIR).

    The rate that exactly discounts estimated future cash payments to the
    gross carrying amount. Under IFRS 9, all fees (arrangement, OID) that
    are an integral part of the instrument feed in — which is the case
    here since our lender CF includes them at t=0.

    For evenly-spaced annual periods, EIR = IRR. Kept as a separate helper
    so the Returns sheet can label it correctly per accounting standard.
    """
    return f"=IRR({cashflow_range},{guess})"


def eir_xirr(cashflow_range: str, date_range: str, guess: str = "0.08") -> str:
    """EIR via XIRR — for uneven periods (not currently used; kept for extensibility)."""
    return f"=XIRR({cashflow_range},{date_range},{guess})"


def cash_sweep(fcf_ref: str, leverage_ref: str, threshold_ref: str, sweep_pct_ref: str) -> str:
    """Cash sweep mechanism (single-tier).

    If leverage > threshold, sweep `sweep_pct` of positive FCF to principal.
    Returns a negative number (reduces debt closing).

        sweep = -IF(leverage > threshold, MAX(fcf, 0) * sweep_pct, 0)
    """
    return (
        f"=-IF({leverage_ref}>{threshold_ref},MAX({fcf_ref},0)*{sweep_pct_ref},0)"
    )


def cash_sweep_tiered(fcf_ref: str, leverage_ref: str, sweep_pct_ref: str) -> str:
    """v0.8.7 US-542: Cash sweep stepping down by leverage tier.

    Bulge-bracket convention (per WSP / Macabacus LBO templates):
      Leverage ≥ 5.0x   → 100% of sweep_pct × FCF
      Leverage 4.0-5.0x →  75% of sweep_pct × FCF
      Leverage 3.0-4.0x →  50% of sweep_pct × FCF
      Leverage < 3.0x   →   0% (deal-dependent covenant carve-out)

    Returns a negative number (reduces debt closing).
    """
    base_sweep = f"MAX({fcf_ref},0)*{sweep_pct_ref}"
    return (
        f"=-IF({leverage_ref}>=5,{base_sweep}*1,"
        f"IF({leverage_ref}>=4,{base_sweep}*0.75,"
        f"IF({leverage_ref}>=3,{base_sweep}*0.5,0)))"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Check-cell builders (for the QC sheet)
# ─────────────────────────────────────────────────────────────────────────────


def check_equals(a_ref: str, b_ref: str, tolerance: float = 1.0) -> str:
    """1 if |a - b| <= tolerance, else 0.

    Tolerance in model units (e.g. EUR 1.0 if unit is actuals, or 0.001 if
    millions). Caller chooses.
    """
    return f"=IF(ABS({a_ref}-{b_ref})<={tolerance},1,0)"


def check_zero(a_ref: str, tolerance: float = 1.0) -> str:
    return f"=IF(ABS({a_ref})<={tolerance},1,0)"


def check_positive(a_ref: str) -> str:
    return f"=IF({a_ref}>0,1,0)"


def check_negative(a_ref: str) -> str:
    """For cost lines under costs-negative convention."""
    return f"=IF({a_ref}<=0,1,0)"


def check_all_true(cell_refs: Iterable[str]) -> str:
    """AND of a set of check cells."""
    return "=AND(" + ",".join(f"{r}=1" for r in cell_refs) + ")*1"

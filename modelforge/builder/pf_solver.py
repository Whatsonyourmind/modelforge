"""Project Finance debt solvers.

Pure-Python numerical helpers for v0.3 PF enhancements. Runs at build time
BEFORE the workbook is emitted; results are baked into the sheet as either
hardcoded constants (blue-styled) or as rescaled references to the
senior_amount named range so scenarios stay live.

Functions
---------
level_debt_service_pct_schedule(rate, amort_years, grace_years, op_years)
    Return a list of length op_years. Each entry is principal_t / original_P
    under a level-debt-service (annuity) curve. Years before grace_end are 0.

level_debt_service_total_debt_service(P, rate, amort_years)
    Return the constant per-year debt service (principal + interest) under
    the annuity. Used to compare debt quantum against CFADS capacity.

solve_dscr_target_debt(cfads, rate, amort_years, grace_years,
                       target_dscr, cap, tol=0.01, max_iter=50)
    Binary-search the maximum senior debt amount P such that the minimum
    DSCR over operating years >= target_dscr. Returns solved P.

precompute_cfads_base(spec)
    Evaluate the Operating-phase math deterministically for BASE scenario:
    Revenue_t × (1 - opex_pct) - tax = CFADS_t. Returns list of length
    operating_years. Used as input to solve_dscr_target_debt.

Design notes
------------
- Sculpted schedules are written into the workbook as *percentages* of the
  senior_amount named range, so if the user subsequently edits the
  Assumptions BASE/Worst/Best, scenario scaling still works.
- Binary search is preferred over Newton: CFADS is effectively independent
  of debt quantum in this model (no interest tax shield implemented yet on
  CFADS), so DSCR is monotone in P. Search always terminates.
- Tolerance is in EUR m (default 0.01 = €10k).
"""

from __future__ import annotations

from typing import List


def level_debt_service_pct_schedule(
    rate: float,
    amort_years: int,
    grace_years: int,
    operating_years: int,
) -> List[float]:
    """Principal repayment as fraction of original P, per operating year.

    Year indices: 0-based. First `grace_years` entries are 0. Next
    `amort_years` entries follow the level-debt-service annuity curve
    (rising principal, falling interest). Any remaining post-amort years
    are 0.

    Returns a list of length `operating_years`.
    """
    if amort_years <= 0:
        raise ValueError("amort_years must be positive")
    if operating_years < grace_years + amort_years:
        raise ValueError(
            f"operating_years ({operating_years}) must cover "
            f"grace ({grace_years}) + amort ({amort_years})"
        )

    # Annuity constant as a fraction of P
    if rate == 0:
        c_pct = 1.0 / amort_years
        schedule_amort: List[float] = [c_pct] * amort_years
    else:
        c_pct = rate / (1.0 - (1.0 + rate) ** (-amort_years))
        balance_pct = 1.0
        schedule_amort = []
        for _ in range(amort_years):
            interest_pct = balance_pct * rate
            principal_pct = c_pct - interest_pct
            schedule_amort.append(principal_pct)
            balance_pct -= principal_pct

    out: List[float] = [0.0] * operating_years
    for i, p in enumerate(schedule_amort):
        out[grace_years + i] = p
    return out


def level_debt_service_constant(P: float, rate: float, amort_years: int) -> float:
    """Constant annuity payment (principal + interest) per period."""
    if amort_years <= 0:
        raise ValueError("amort_years must be positive")
    if rate == 0:
        return P / amort_years
    return P * rate / (1.0 - (1.0 + rate) ** (-amort_years))


def level_debt_service_per_year(
    P: float,
    rate: float,
    amort_years: int,
    grace_years: int,
    operating_years: int,
) -> List[float]:
    """Total debt service (interest + principal) per operating year.

    During grace: interest only on outstanding balance.
    During amort: level annuity payment.
    Post amort: zero.
    """
    out: List[float] = [0.0] * operating_years
    # Grace years: interest only on full balance
    for i in range(grace_years):
        out[i] = P * rate
    # Amort years: level payment
    c = level_debt_service_constant(P, rate, amort_years)
    for i in range(amort_years):
        idx = grace_years + i
        if idx < operating_years:
            out[idx] = c
    return out


def solve_dscr_target_debt(
    cfads: List[float],
    rate: float,
    amort_years: int,
    grace_years: int,
    target_dscr: float,
    cap: float,
    tol: float = 0.01,
    max_iter: int = 50,
) -> float:
    """Binary-search max P such that min(DSCR) over operating years >= target.

    cfads: length = operating_years. Cash Flow Available for Debt Service
           per operating year (BASE scenario).
    rate: all-in annual rate (ref + margin/10000).
    cap: upper bound on P (user's senior_amount.base is a natural choice).
    Returns solved P in EUR m (same unit as cfads).
    """
    if target_dscr <= 0:
        raise ValueError("target_dscr must be positive")
    if cap <= 0:
        return 0.0

    operating_years = len(cfads)
    if operating_years < grace_years + amort_years:
        raise ValueError(
            "cfads length must be >= grace_years + amort_years"
        )

    def min_dscr(P: float) -> float:
        ds = level_debt_service_per_year(P, rate, amort_years, grace_years, operating_years)
        dscrs = []
        for t in range(operating_years):
            if ds[t] == 0:
                continue  # grace with rate=0 or post-amort — skip
            dscrs.append(cfads[t] / ds[t])
        return min(dscrs) if dscrs else float("inf")

    lo, hi = 0.0, cap
    # If cap already clears target comfortably, return cap (no need to shrink)
    if min_dscr(cap) >= target_dscr:
        return cap

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if min_dscr(mid) >= target_dscr:
            lo = mid
        else:
            hi = mid
        if (hi - lo) < tol:
            break
    return lo


def precompute_cfads_base(spec) -> List[float]:
    """Reproduce the Operating-phase Python math for BASE scenario.

    Must stay in lockstep with pf_cashflow.build formulas:
        revenue_1 = availability_payment_eur_m_yr1
        revenue_t = revenue_{t-1} * (1 + revenue_indexation_pct)
        opex_t = -revenue_t * opex_pct_revenue
        ebitda_t = revenue_t + opex_t
        tax_t = -max(ebitda_t, 0) * effective_tax_rate
        cfads_t = ebitda_t + tax_t

    Returns a list of length operating_years. Negative values possible if
    opex > revenue (pathological case — skipped in solver).
    """
    o = spec.horizon.operating_years
    yr1 = spec.operating.availability_payment_eur_m_yr1.base
    idx = spec.operating.revenue_indexation_pct.base
    opex_pct = spec.operating.opex_pct_revenue.base
    tax_rate = spec.equity.effective_tax_rate.base

    cfads = []
    rev = yr1
    for t in range(o):
        if t > 0:
            rev = rev * (1.0 + idx)
        opex = -rev * opex_pct
        ebitda = rev + opex
        tax = -max(ebitda, 0.0) * tax_rate
        cfads.append(ebitda + tax)
    return cfads

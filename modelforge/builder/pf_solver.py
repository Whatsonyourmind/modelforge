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

v0.12 (US-PF-sculpt): genuine CFADS-driven DSCR sculpting.
    sculpt_dscr_target_schedule(spec)
        Solve the FULL coupled debt schedule for amortization_profile=
        sculpted_dscr_target so the realised DSCR (as the workbook actually
        renders it: average-balance interest, EBIT−interest tax shield,
        maintenance capex) is FLAT at the target every amortizing operating
        year, while the balance amortises to exactly 0 and never goes
        negative. The senior amount is *solved* (sum of scheduled principal,
        capped at the user's senior_amount), not assumed. Returns
        (senior_amount, principal_pct_schedule, dscr_binds).

Design notes
------------
- Sculpted schedules are written into the workbook as *percentages* of the
  senior_amount named range, so if the user subsequently edits the
  Assumptions BASE/Worst/Best, scenario scaling still works.
- The legacy ``level_debt_service_*`` helpers + ``solve_dscr_target_debt``
  binary search remain for the level-debt-service profiles and back-compat.
  Their numeric contract is unchanged (CFADS independent of P, monotone DSCR).
- True DSCR sculpting is NOT monotone-in-P and NOT a binary search: the
  schedule, the debt quantum, and the interest tax-shield are mutually
  coupled. ``sculpt_dscr_target_schedule`` resolves the circularity by
  fixed-point iteration on (P, principal-schedule) until it converges — the
  same way a live workbook with iterative calc would settle. The sizing CFADS
  is now reconciled to the rendered-sheet CFADS (EBIT−interest tax, minus
  maintenance capex), removing the prior sizer-vs-sheet tax-base mismatch.
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


# ──────────────────────────────────────────────────────────────────────────
# v0.12 — genuine CFADS-driven DSCR sculpting
# ──────────────────────────────────────────────────────────────────────────
def _render_pf_cashflow_and_debt(spec, P: float, pct_schedule: List[float]) -> dict:
    """Reproduce the EXACT numerics pf_cashflow.build + pf_debt.build emit,
    for a candidate senior amount ``P`` and principal-pct schedule.

    This is the in-Python twin of the rendered workbook used to make the
    sculpt self-consistent with what the sheet actually computes:

      * interest_t = -avg_balance_t * rate         (average-balance convention)
      * tax_t      = -max(EBIT_t + interest_t, 0) * tax_rate   (interest shield)
      * CFADS_t    = EBITDA_t + tax_t + ΔWC_t + maint_t
      * debt_service_t = interest_t + amort_t      (both ≤ 0)
      * DSCR_t     = CFADS_t / |debt_service_t|

    Returns arrays indexed over the full timeline (length c+o). Crucially the
    SIZING CFADS here is the SAME definition the sheet renders (EBIT−interest
    tax, minus maintenance capex), reconciling the prior sizer-vs-sheet
    tax-base mismatch (the old precompute_cfads_base taxed EBITDA directly and
    ignored D&A, the interest shield and maintenance capex).
    """
    c = spec.horizon.construction_years
    o = spec.horizon.operating_years
    n = c + o

    capex = spec.construction.total_capex_eur_m.base
    phasing = [p.base for p in spec.construction.capex_phasing_pct]
    rev1 = spec.operating.availability_payment_eur_m_yr1.base
    rev_idx = spec.operating.revenue_indexation_pct.base
    opex_pct = spec.operating.opex_pct_revenue.base
    maint_pct = spec.operating.maintenance_reserve_pct_revenue.base
    tax_rate = spec.equity.effective_tax_rate.base
    deg = getattr(spec.operating, "panel_degradation_pct_annual", None)
    deg = deg.base if deg is not None else 0.0
    nwc = getattr(spec.operating, "nwc_pct_revenue", None)
    nwc = nwc.base if nwc is not None else 0.0
    rate = spec.debt.reference_rate.base + spec.debt.margin_bps.base / 10000.0

    # Debt roll-forward (mirrors pf_debt: drawdown on phasing, amort = -P*pct)
    opening = [0.0] * n
    drawdown = [0.0] * n
    amort = [0.0] * n
    closing = [0.0] * n
    for i in range(c):
        drawdown[i] = P * phasing[i]
    for i in range(n):
        opening[i] = closing[i - 1] if i > 0 else 0.0
        if i >= c:
            op = i - c
            amort[i] = -P * pct_schedule[op] if op < len(pct_schedule) else 0.0
        closing[i] = opening[i] + drawdown[i] + amort[i]
    avg = [(opening[i] + closing[i]) / 2.0 for i in range(n)]
    interest = [-avg[i] * rate for i in range(n)]
    debt_service = [interest[i] + amort[i] for i in range(n)]

    # Operating walk (mirrors pf_cashflow exactly)
    revenue = [0.0] * n
    cfads = [0.0] * n
    dscr: List[float | None] = [None] * n
    for i in range(c, n):
        t = i - c
        if t == 0:
            rev_t = rev1
        else:
            rev_t = revenue[i - 1] * (1.0 + rev_idx) * (1.0 - deg)
        revenue[i] = rev_t
        opex = -rev_t * opex_pct
        ebitda = rev_t + opex
        da = -capex / o
        ebit = ebitda + da
        taxable = ebit + interest[i]                 # interest negative
        tax = -max(taxable, 0.0) * tax_rate
        maint = -rev_t * maint_pct
        if t == 0:
            d_wc = -rev_t * nwc
        else:
            d_wc = -(rev_t - revenue[i - 1]) * nwc
        cfads[i] = ebitda + tax + d_wc + maint
        ds = abs(debt_service[i])
        dscr[i] = (cfads[i] / ds) if ds > 1e-9 else None

    return dict(
        opening=opening, closing=closing, amort=amort, interest=interest,
        debt_service=debt_service, cfads=cfads, dscr=dscr, rate=rate,
        c=c, o=o, n=n,
    )


def sculpt_dscr_target_schedule(
    spec,
    tol: float = 1e-10,
    max_iter: int = 500,
) -> tuple[float, List[float], bool]:
    """Solve a genuine DSCR-sculpted principal schedule.

    Sizes the senior debt and shapes each operating-year principal so that the
    REALISED DSCR — exactly as pf_cashflow/pf_debt render it — is flat at the
    BASE target every *amortizing* operating year, the balance amortises to 0,
    and the balance never goes negative.

    Mechanics (per amortizing year t):
        |debt_service_t| = CFADS_t / target          (flat-DSCR condition)
        principal_t      = CFADS_t / target − |interest_t|
    Grace years: principal 0 (interest-only → DSCR naturally > target).
    Post-amort years: principal 0.

    CFADS_t and interest_t are mutually coupled (interest shields tax, which
    moves CFADS; the principal schedule moves the balance, which moves
    interest), so the schedule is found by fixed-point iteration on
    (P, principal-$) until P converges. Converges in ~10-15 iterations for
    well-posed PF inputs.

    Sizing is the textbook DSCR-sculpt: P = Σ scheduled principal (so it
    amortises to exactly 0). When that exceeds the user's senior_amount cap,
    the cap binds: principal is rescaled to amortise the capped P to 0 and the
    realised DSCR floats ABOVE target (honest — LTV, not DSCR, is then the
    binding constraint).

    Returns (senior_amount, principal_pct_schedule, dscr_binds) where the pct
    schedule is each year's principal as a fraction of senior_amount (sums to
    1.0) and dscr_binds is True iff the DSCR target is the binding constraint
    (i.e. realised DSCR is flat at target).
    """
    o = spec.horizon.operating_years
    grace = spec.debt.grace_years
    amort_years = spec.debt.tenor_operating_years - spec.debt.grace_years
    if amort_years <= 0:
        raise ValueError("tenor must exceed grace for a sculpted schedule")
    if spec.debt.target_dscr_base is None:
        raise ValueError("sculpted_dscr_target requires debt.target_dscr_base")
    target = spec.debt.target_dscr_base.base
    cap = spec.debt.amount.base
    c = spec.horizon.construction_years
    last_amort = grace + amort_years - 1  # 0-based op index of last amort year

    # Seed: start at the cap with a flat principal guess; iterate to the fixed
    # point where principal_t = CFADS_t/target − |interest_t|.
    P = cap
    principal = [0.0] * o
    binds = True
    for _ in range(max_iter):
        pct = [p / P if P > 0 else 0.0 for p in principal]
        m = _render_pf_cashflow_and_debt(spec, P, pct)
        interest = m["interest"]
        cfads = m["cfads"]
        new_principal = [0.0] * o
        for op in range(o):
            i = c + op
            if op < grace or op > last_amort:
                new_principal[op] = 0.0
            else:
                required_ds = cfads[i] / target          # flat-DSCR condition
                prin = required_ds - abs(interest[i])
                new_principal[op] = max(prin, 0.0)
        new_P = sum(new_principal)
        if new_P > cap + 1e-12:
            # Cap binds — rescale to amortise the capped P to exactly 0.
            scale = cap / new_P if new_P > 0 else 0.0
            new_principal = [p * scale for p in new_principal]
            new_P = cap
            binds = False
        else:
            binds = True
        dP = abs(new_P - P)
        principal = new_principal
        P = new_P
        if dP < tol:
            break

    pct_schedule = [p / P if P > 0 else 0.0 for p in principal]
    return P, pct_schedule, binds

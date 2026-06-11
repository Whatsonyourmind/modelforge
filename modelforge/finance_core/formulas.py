"""Template-agnostic finance formulas used across ModelForge templates.

These are pure-Python implementations of common Excel / financial
formulas so callers can:

- Compute reference values in Python for unit tests (sanity-check the
  Excel-rendered workbook against these — closes the v0.3 PMT-drift
  incident class).
- Let downstream wrappers (vertical composers/services) do
  finance math without taking the whole openpyxl dependency.

All functions are vector-free and work on ``float`` (or Decimal for
money). No NumPy dependency.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Iterable, Sequence, Union

Number = Union[float, Decimal, int]


# ── Time-value helpers ───────────────────────────────────────────────────


def pmt(rate: float, n_periods: int, present_value: float) -> float:
    """Annuity payment matching Excel ``PMT(rate, n, -pv)``.

    Signs follow the finance convention (negative present value → positive
    payment). Zero rate returns PV / n.
    """
    if n_periods <= 0:
        raise ValueError("n_periods must be > 0")
    if rate == 0:
        return present_value / n_periods
    factor = (1 + rate) ** n_periods
    return present_value * rate * factor / (factor - 1)


def present_value(rate: float, cashflows: Sequence[float]) -> float:
    """PV of ``cashflows`` at periodic ``rate`` — discounted to t=0.

    Cashflow at index 0 is NOT discounted (t=0); index 1 discounted by
    (1+r)^1, and so on.
    """
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Excel-compatible NPV where the 1st cashflow is at t=1 (as in Excel).

    For PV-semantics where cashflow 0 is at t=0, use :func:`present_value`.
    """
    return sum(cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cashflows))


def irr(
    cashflows: Sequence[float],
    *,
    guess: float = 0.10,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> float:
    """Periodic IRR solved via Newton-Raphson on PV(cashflows)=0.

    Cashflows follow the PV convention: index 0 is at t=0 (typically the
    initial negative outlay). Raises ValueError when Newton-Raphson
    doesn't converge — caller should fall back to a bracket method.
    """
    if not cashflows:
        raise ValueError("cashflows must be non-empty")
    # IRR exists only if there is at least one positive AND one negative
    # cashflow. Check the SET, not adjacent pairs: a canonical PE/LBO stream
    # like [-equity, 0, 0, 0, 0, exit] has its sign change separated by zeros
    # and must NOT be rejected (the old adjacent-pair guard wrongly did).
    if not (any(cf > 0 for cf in cashflows) and any(cf < 0 for cf in cashflows)):
        raise ValueError(
            "cashflows must contain at least one positive and one negative value"
        )

    rate = guess
    for _ in range(max_iter):
        denom = 0.0
        value = 0.0
        for t, cf in enumerate(cashflows):
            factor = (1 + rate) ** t
            value += cf / factor
            if t > 0:
                denom -= t * cf / factor / (1 + rate)
        if abs(denom) < 1e-14:
            break
        next_rate = rate - value / denom
        if abs(next_rate - rate) < tol:
            return next_rate
        rate = next_rate
    raise ValueError(
        "IRR did not converge; try different guess or bracket method"
    )


# ── Fixed-income analytics (duration / convexity / issuer cost) ─────────


def macaulay_duration(
    cashflows: Sequence[float],
    rate: float,
    times: Sequence[float] | None = None,
) -> float:
    """Macaulay duration — PV-weighted average time to the cash inflows.

    ``cashflows`` are the bond's *inflows* (coupon + principal) ordered by
    period. ``times`` is the matching period for each cashflow; when omitted
    they default to ``1, 2, … len(cashflows)`` (i.e. ``cashflows[0]`` falls at
    t=1, the first coupon date — NOT t=0). Pass an explicit ``times`` to handle
    a t=0 entry or non-annual spacing.

    Returns ``sum(t · PV_t) / sum(PV_t)`` where ``PV_t = CF_t / (1+rate)^t``.
    For a bond priced at par discounted at its coupon, this is the textbook
    Macaulay duration. Raises if the discounted inflows sum to zero.
    """
    cfs = list(cashflows)
    if not cfs:
        raise ValueError("cashflows must be non-empty")
    ts = list(times) if times is not None else [i + 1 for i in range(len(cfs))]
    if len(ts) != len(cfs):
        raise ValueError("times must match cashflows length")
    pv = [cf / (1 + rate) ** t for cf, t in zip(cfs, ts)]
    denom = sum(pv)
    if denom == 0:
        raise ValueError("sum of discounted cashflows is zero; duration undefined")
    return sum(t * p for t, p in zip(ts, pv)) / denom


def modified_duration(macaulay: float, ytm: float, freq: int = 1) -> float:
    """Modified duration = Macaulay / (1 + ytm/freq).

    ``freq`` is the number of coupon periods per year (1 = annual). Modified
    duration is the first-order price sensitivity: ΔP/P ≈ −ModDur · Δytm.
    """
    if freq <= 0:
        raise ValueError("freq must be > 0")
    return macaulay / (1 + ytm / freq)


def convexity(cashflows: Sequence[float], rate: float,
              times: Sequence[float] | None = None) -> float:
    """Convexity — second-order price sensitivity of the inflows.

    ``C = sum(t·(t+1)·PV_t) / (P · (1+rate)^2)`` where ``P = sum(PV_t)`` is the
    PV of the inflows. ``cashflows`` / ``times`` follow :func:`macaulay_duration`
    (default times are 1, 2, …). The full price change is then
    ``ΔP/P ≈ −ModDur·Δy + ½·C·Δy²``.
    """
    cfs = list(cashflows)
    if not cfs:
        raise ValueError("cashflows must be non-empty")
    ts = list(times) if times is not None else [i + 1 for i in range(len(cfs))]
    if len(ts) != len(cfs):
        raise ValueError("times must match cashflows length")
    pv = [cf / (1 + rate) ** t for cf, t in zip(cfs, ts)]
    price = sum(pv)
    if price == 0:
        raise ValueError("PV of inflows is zero; convexity undefined")
    weighted = sum(t * (t + 1) * cf / (1 + rate) ** (t + 2) for cf, t in zip(cfs, ts))
    return weighted / price


def all_in_cost_of_debt(
    ytm: float,
    upfront_fees: float,
    face: float,
) -> float:
    """Issuer all-in cost of funds (annualised), fees amortised over the life.

    A first-order approximation of the issuer's cost of debt: the periodic
    coupon yield (``ytm``) grossed up for upfront fees spread across the face.
    With ``upfront_fees`` (arrangement + legal + listing + rating, as a positive
    money amount) and ``face`` (the notional drawn), the issuer receives only
    ``face − upfront_fees`` but services the full coupon, so its effective cost
    exceeds the coupon. Returns ``ytm · face / (face − upfront_fees)``.

    This closed form is the simple net-proceeds gross-up; the workbook renders
    the *exact* all-in via an IRR of the issuer cashflow (net proceeds in,
    coupon+principal out). Use the IRR for reporting and this for a quick check
    that ``all_in > coupon`` whenever fees are positive. Raises if net proceeds
    are non-positive.
    """
    net_proceeds = face - upfront_fees
    if net_proceeds <= 0:
        raise ValueError("net proceeds (face - upfront_fees) must be > 0")
    return ytm * face / net_proceeds


# ── Returns + multiples ────────────────────────────────────────────────


def moic(invested: Number, returned: Number) -> float:
    """Multiple of invested capital (MOIC)."""
    invested_f = float(invested)
    returned_f = float(returned)
    if invested_f <= 0:
        raise ValueError("invested must be > 0")
    return returned_f / invested_f


def tvpi(drawn: Number, distributions: Number, nav: Number) -> float:
    """Total value to paid-in (TVPI) = (distributions + NAV) / drawn."""
    drawn_f = float(drawn)
    if drawn_f <= 0:
        raise ValueError("drawn (paid-in) must be > 0")
    return (float(distributions) + float(nav)) / drawn_f


def dpi(drawn: Number, distributions: Number) -> float:
    """Distributions to paid-in."""
    drawn_f = float(drawn)
    if drawn_f <= 0:
        raise ValueError("drawn (paid-in) must be > 0")
    return float(distributions) / drawn_f


def rvpi(drawn: Number, nav: Number) -> float:
    """Residual value to paid-in."""
    drawn_f = float(drawn)
    if drawn_f <= 0:
        raise ValueError("drawn (paid-in) must be > 0")
    return float(nav) / drawn_f


# ── Valuation + leverage ───────────────────────────────────────────────


def gordon_terminal_value(
    cashflow_t1: float, discount_rate: float, growth_rate: float
) -> float:
    """Gordon-growth terminal value: CF₁ / (r − g).

    Raises when growth >= discount (mathematically undefined).
    """
    if discount_rate <= growth_rate:
        raise ValueError(
            f"discount_rate ({discount_rate}) must be > growth_rate ({growth_rate})"
        )
    return cashflow_t1 / (discount_rate - growth_rate)


def exit_multiple_terminal_value(
    terminal_ebitda: float, exit_multiple: float
) -> float:
    """Terminal value via exit multiple = EBITDA_exit × multiple."""
    if exit_multiple <= 0:
        raise ValueError("exit_multiple must be > 0")
    return terminal_ebitda * exit_multiple


def dscr(cash_available: float, debt_service: float) -> float:
    """Debt-service coverage ratio."""
    if debt_service <= 0:
        raise ValueError("debt_service must be > 0 to compute DSCR")
    return cash_available / debt_service


def ltv(debt_balance: float, asset_value: float) -> float:
    """Loan-to-value ratio."""
    if asset_value <= 0:
        raise ValueError("asset_value must be > 0 to compute LTV")
    return debt_balance / asset_value


def wacc(
    *,
    equity_market_value: float,
    debt_market_value: float,
    cost_of_equity: float,
    cost_of_debt_after_tax: float,
) -> float:
    """Weighted average cost of capital with after-tax debt cost."""
    total = equity_market_value + debt_market_value
    if total <= 0:
        raise ValueError("equity + debt must be > 0")
    return (
        (equity_market_value / total) * cost_of_equity
        + (debt_market_value / total) * cost_of_debt_after_tax
    )


def levered_beta(
    unlevered_beta: float, debt_to_equity: float, tax_rate: float
) -> float:
    """Hamada levered beta: β_L = β_U × [1 + (1 − t) × D/E]."""
    return unlevered_beta * (1 + (1 - tax_rate) * debt_to_equity)


# ── Growth helpers ──────────────────────────────────────────────────────


def cagr(start_value: float, end_value: float, periods: int) -> float:
    """Compound annual growth rate over ``periods`` years."""
    if start_value <= 0:
        raise ValueError("start_value must be > 0")
    if end_value <= 0:
        raise ValueError("end_value must be > 0")
    if periods <= 0:
        raise ValueError("periods must be > 0")
    return (end_value / start_value) ** (1 / periods) - 1


def apply_growth(base: float, rate: float, periods: int) -> float:
    """Compound a base value by ``rate`` over ``periods``."""
    return base * (1 + rate) ** periods

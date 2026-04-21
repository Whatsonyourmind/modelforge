"""Template-agnostic finance formulas used across ModelForge templates.

These are pure-Python implementations of common Excel / financial
formulas so callers can:

- Compute reference values in Python for unit tests (sanity-check the
  Excel-rendered workbook against these — closes the v0.3 PMT-drift
  incident class).
- Let downstream wrappers (Aither, CreditAI, DeckForge composers) do
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
    has_sign_change = any(
        a * b < 0 for a, b in zip(cashflows, cashflows[1:])
    )
    if not has_sign_change:
        raise ValueError("cashflows must have at least one sign change")

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

"""Utilities shared by shadow engines."""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np


def driver_value(assumption, overrides: dict[str, float]) -> float:
    """Return the BASE value of an assumption, respecting overrides.

    overrides maps Assumption.name → replacement value.
    """
    return overrides.get(assumption.name, assumption.base)


def irr(cashflows: Iterable[float], guess: float = 0.1) -> Optional[float]:
    """Newton-Raphson IRR solver — mirrors Excel IRR(). Returns None
    if it fails to converge in 200 iterations.

    numpy-financial isn't in core deps so we roll our own (60 lines
    beats dragging in another package).
    """
    cf = np.asarray(list(cashflows), dtype=float)
    if cf.size < 2:
        return None
    r = float(guess)
    for _ in range(200):
        t = np.arange(cf.size)
        disc = (1 + r) ** t
        npv = np.sum(cf / disc)
        dnpv = -np.sum(t * cf / disc / (1 + r))
        if abs(dnpv) < 1e-12:
            return None
        new_r = r - npv / dnpv
        if abs(new_r - r) < 1e-8:
            return float(new_r)
        # Clamp to avoid runaway negatives
        if new_r <= -0.99:
            new_r = -0.99
        r = new_r
    return None


def npv(rate: float, cashflows: Iterable[float]) -> float:
    """Discount cash flows at `rate`. Matches Excel NPV semantics when
    t=0 is already included in the series."""
    cf = np.asarray(list(cashflows), dtype=float)
    t = np.arange(cf.size)
    return float(np.sum(cf / (1 + rate) ** t))

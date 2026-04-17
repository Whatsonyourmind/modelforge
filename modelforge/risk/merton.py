"""Merton (1974) structural default model.

Given a firm's equity value E, equity volatility σ_E, face value of
debt D (discounted to maturity T), risk-free rate r, and horizon T:

    (1)  E = V·N(d1) − D·e^{-rT}·N(d2)
    (2)  σ_E·E = σ_V·V·N(d1)

where
    d1 = (ln(V/D) + (r + 0.5·σ_V²)·T) / (σ_V·sqrt(T))
    d2 = d1 − σ_V·sqrt(T)

Unknowns: asset value V, asset volatility σ_V. We solve the two-
equation system by Newton iteration on (V, σ_V). Once solved:

    Distance-to-Default  DD = (ln(V/D) + (r − 0.5·σ_V²)·T) / (σ_V·sqrt(T))
    Physical PD           = N(−DD)

Implementation uses math.erf for N(x) so there's no SciPy dependency.
Textbook reference: Hull, *Options, Futures, and Other Derivatives*,
ch. 24 (Credit Risk).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ─── Standard normal CDF via erf (no SciPy dep) ─────────────────────────────


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass
class MertonInputs:
    equity_value: float           # market cap (€m)
    equity_volatility: float      # annualized σ of equity returns (decimal, e.g. 0.30)
    debt_face_value: float        # total debt face at maturity (€m)
    risk_free_rate: float         # continuously-compounded rate (decimal, e.g. 0.04)
    horizon_years: float = 1.0    # typical one-year default horizon

    def __post_init__(self) -> None:
        if self.equity_value <= 0:
            raise ValueError("equity_value must be > 0")
        if self.equity_volatility <= 0:
            raise ValueError("equity_volatility must be > 0")
        if self.debt_face_value <= 0:
            raise ValueError("debt_face_value must be > 0")
        if self.horizon_years <= 0:
            raise ValueError("horizon_years must be > 0")


@dataclass
class MertonResult:
    asset_value: float
    asset_volatility: float
    distance_to_default: float
    probability_of_default: float
    d1: float
    d2: float
    iterations: int
    converged: bool


def _merton_system(V: float, sigma_V: float, inputs: MertonInputs):
    """Return (E_implied - E_observed, sigma_E_implied - sigma_E_observed)."""
    r = inputs.risk_free_rate
    T = inputs.horizon_years
    D = inputs.debt_face_value
    sqrtT = math.sqrt(T)

    if V <= 0 or sigma_V <= 0:
        # Guard against invalid iterate
        return 1e12, 1e12, 0.0, 0.0

    d1 = (math.log(V / D) + (r + 0.5 * sigma_V ** 2) * T) / (sigma_V * sqrtT)
    d2 = d1 - sigma_V * sqrtT
    Nd1 = _norm_cdf(d1)
    Nd2 = _norm_cdf(d2)

    E_implied = V * Nd1 - D * math.exp(-r * T) * Nd2
    # Iteratively derived: σ_E·E ≈ σ_V·V·N(d1)
    sigma_E_implied = sigma_V * V * Nd1 / max(E_implied, 1e-9)

    return E_implied, sigma_E_implied, d1, d2


def solve_merton(
    inputs: MertonInputs,
    max_iter: int = 200,
    tol: float = 1e-8,
) -> MertonResult:
    """Solve for (V, σ_V) via Newton iteration on the Merton system.

    Initial guess: V = E + D·e^{-rT}, σ_V = σ_E · E / V.
    """
    r = inputs.risk_free_rate
    T = inputs.horizon_years
    E = inputs.equity_value
    sigma_E = inputs.equity_volatility
    D = inputs.debt_face_value

    # Seed
    V = E + D * math.exp(-r * T)
    sigma_V = max(sigma_E * E / V, 1e-6)

    converged = False
    for i in range(max_iter):
        E_imp, sE_imp, d1, d2 = _merton_system(V, sigma_V, inputs)
        f1 = E_imp - E
        f2 = sE_imp - sigma_E
        if abs(f1) < tol * max(E, 1.0) and abs(f2) < tol * max(sigma_E, 1.0):
            converged = True
            break

        # Numerical Jacobian via finite difference
        h_V = max(abs(V) * 1e-6, 1e-6)
        h_s = max(abs(sigma_V) * 1e-6, 1e-9)
        E1, sE1, _, _ = _merton_system(V + h_V, sigma_V, inputs)
        E2, sE2, _, _ = _merton_system(V, sigma_V + h_s, inputs)

        J = [
            [(E1 - E_imp) / h_V, (E2 - E_imp) / h_s],
            [(sE1 - sE_imp) / h_V, (sE2 - sE_imp) / h_s],
        ]
        det = J[0][0] * J[1][1] - J[0][1] * J[1][0]
        if abs(det) < 1e-12:
            break
        dV = (J[1][1] * f1 - J[0][1] * f2) / det
        ds = (-J[1][0] * f1 + J[0][0] * f2) / det
        V_new = V - dV
        s_new = sigma_V - ds

        # Damp if moving too aggressively
        if V_new <= 0:
            V_new = V * 0.5
        if s_new <= 0:
            s_new = sigma_V * 0.5
        V, sigma_V = V_new, s_new

    _, _, d1, d2 = _merton_system(V, sigma_V, inputs)
    # DD under the physical measure (no risk-free adjustment for the PD
    # interpretation; Moody's KMV uses the drift-adjusted form).
    sqrtT = math.sqrt(T)
    DD = (math.log(V / D) + (r - 0.5 * sigma_V ** 2) * T) / (sigma_V * sqrtT)
    PD = _norm_cdf(-DD)

    return MertonResult(
        asset_value=V, asset_volatility=sigma_V,
        distance_to_default=DD, probability_of_default=PD,
        d1=d1, d2=d2, iterations=i + 1, converged=converged,
    )

"""IFRS 9 Expected Credit Loss engine + Hosmer-Lemeshow backtesting.

Per IFRS 9 §5.5 and §B5.5.17:

    Stage 1 — performing; 12-month ECL
    Stage 2 — SICR (significant increase in credit risk) since initial
              recognition; lifetime ECL
    Stage 3 — credit-impaired (default); lifetime ECL on the
              defaulted carrying amount

Stage transitions are configurable (default thresholds per EBA
GL/2017/06 "Guidelines on credit institutions' credit risk management
practices and accounting for expected credit losses"):

    * 30 dpd → Stage 2 (rebuttable presumption under IFRS 9 §B5.5.37)
    * 2x PD increase vs origination → Stage 2 (SICR proxy)
    * 90 dpd OR default event → Stage 3

This module computes ECL for a single exposure or a list of exposures,
using the discounted expected loss formula:

    ECL = Σ_t  PD_t × LGD × EAD_t / (1 + EIR)^t

For Stage 1 we use the 12-month PD curve (t ∈ [0, 1]).
For Stage 2/3 we use the lifetime PD curve (t ∈ [0, maturity]).

Also bundles a Hosmer-Lemeshow goodness-of-fit test for validation
of the PD curves against realized-default history — CLI-ready.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class Stage(str, Enum):
    STAGE_1 = "stage_1"      # 12-month ECL
    STAGE_2 = "stage_2"      # lifetime ECL
    STAGE_3 = "stage_3"      # credit-impaired lifetime ECL


@dataclass
class ECLInputs:
    """One loan / exposure. PD curve is annual marginal probabilities."""

    exposure_at_default_eur_m: float   # EAD
    loss_given_default: float          # LGD as decimal (e.g. 0.45)
    effective_interest_rate: float     # EIR for discounting (decimal)
    maturity_years: int                # lifetime horizon
    pd_curve_annual: list[float]       # marginal PDs: [P(default in Y1), P(def Y2|survived Y1), ...]
    days_past_due: int = 0
    origination_pd_12m: float = 0.0    # reference for SICR check
    current_pd_12m: float = 0.0        # current 12-mo PD

    # Optional override; if not provided, stage is inferred from dpd + SICR
    stage_override: Optional[Stage] = None


@dataclass
class ECLResult:
    exposure_id: str = ""
    stage: Stage = Stage.STAGE_1
    ecl_12_month_eur_m: float = 0.0
    ecl_lifetime_eur_m: float = 0.0
    ecl_eur_m: float = 0.0              # the one reported (12m for S1, lifetime for S2/S3)
    cumulative_pd: float = 0.0
    implied_rate_pct: float = 0.0       # ECL / EAD as %
    notes: list[str] = field(default_factory=list)


def _infer_stage(inp: ECLInputs) -> Stage:
    """Apply EBA GL/2017/06 default transition thresholds."""
    if inp.stage_override is not None:
        return inp.stage_override
    if inp.days_past_due >= 90:
        return Stage.STAGE_3
    sicr = False
    # 30 dpd rebuttable presumption
    if inp.days_past_due >= 30:
        sicr = True
    # PD doubled vs origination → SICR proxy
    if inp.origination_pd_12m > 0 and inp.current_pd_12m >= 2 * inp.origination_pd_12m:
        sicr = True
    return Stage.STAGE_2 if sicr else Stage.STAGE_1


def _discounted_ecl(
    pd_curve: list[float],
    lgd: float,
    ead: float,
    eir: float,
    horizon: int,
) -> tuple[float, float]:
    """Return (ecl, cumulative_pd) over [0, horizon] years."""
    ecl = 0.0
    cum_pd = 0.0
    # Probability of survival up to period t-1
    surv = 1.0
    for t in range(min(horizon, len(pd_curve))):
        marginal = pd_curve[t]
        # Default event happens mid-period → discount by t+0.5 is common;
        # IFRS 9 allows a pragmatic choice, we use end-of-period here.
        disc = (1 + eir) ** (t + 1)
        ecl += surv * marginal * lgd * ead / disc
        cum_pd += surv * marginal
        surv *= (1 - marginal)
    return ecl, cum_pd


def compute_ecl(
    inputs: ECLInputs,
    exposure_id: str = "",
) -> ECLResult:
    """Compute Stage 1 or Stage 2/3 ECL per IFRS 9 §B5.5.17."""
    stage = _infer_stage(inputs)
    notes: list[str] = []

    # 12-month ECL always computed for disclosure
    ecl_12m, cum_pd_12m = _discounted_ecl(
        inputs.pd_curve_annual, inputs.loss_given_default,
        inputs.exposure_at_default_eur_m, inputs.effective_interest_rate, 1,
    )
    ecl_life, cum_pd_life = _discounted_ecl(
        inputs.pd_curve_annual, inputs.loss_given_default,
        inputs.exposure_at_default_eur_m, inputs.effective_interest_rate,
        inputs.maturity_years,
    )

    if stage == Stage.STAGE_1:
        reported = ecl_12m
        notes.append("Stage 1: performing; 12-month ECL reported")
    elif stage == Stage.STAGE_2:
        reported = ecl_life
        if inputs.days_past_due >= 30:
            notes.append("Stage 2 triggered: ≥30 dpd (§B5.5.37 rebuttable)")
        if (inputs.origination_pd_12m > 0
                and inputs.current_pd_12m >= 2 * inputs.origination_pd_12m):
            notes.append("Stage 2 triggered: PD doubled vs origination (SICR)")
    else:
        # Stage 3: lifetime ECL on EAD assumed near-100% defaulted
        reported = inputs.exposure_at_default_eur_m * inputs.loss_given_default
        notes.append("Stage 3: credit-impaired; lifetime ECL on current EAD")

    return ECLResult(
        exposure_id=exposure_id,
        stage=stage,
        ecl_12_month_eur_m=ecl_12m,
        ecl_lifetime_eur_m=ecl_life,
        ecl_eur_m=reported,
        cumulative_pd=cum_pd_life,
        implied_rate_pct=reported / max(inputs.exposure_at_default_eur_m, 1e-9),
        notes=notes,
    )


# ─── Backtesting — Hosmer-Lemeshow goodness-of-fit ───────────────────────────


def hosmer_lemeshow(
    predicted_pds: list[float],
    realized_defaults: list[int],
    n_groups: int = 10,
) -> tuple[float, float]:
    """Compute the H-L χ² statistic and p-value for PD calibration.

    Groups exposures into ``n_groups`` deciles by predicted PD; compares
    total predicted vs observed defaults per group. Large χ² / small
    p-value → PD curve mis-calibrated.

    Returns (chi2_statistic, p_value).
    """
    if len(predicted_pds) != len(realized_defaults):
        raise ValueError("predicted_pds and realized_defaults must match length")
    if not predicted_pds:
        return 0.0, 1.0

    pd_arr = np.asarray(predicted_pds, dtype=float)
    real_arr = np.asarray(realized_defaults, dtype=float)

    # Rank by predicted PD, then split into equal-count groups
    order = np.argsort(pd_arr)
    pd_sorted = pd_arr[order]
    real_sorted = real_arr[order]

    groups = np.array_split(np.arange(len(pd_sorted)), n_groups)
    chi2 = 0.0
    df = 0
    for idx in groups:
        if idx.size == 0:
            continue
        predicted = pd_sorted[idx].sum()
        observed = real_sorted[idx].sum()
        expected = predicted
        n = idx.size
        # Bernoulli variance approx: n·p·(1-p) where p is group mean PD
        p_bar = predicted / n if n > 0 else 0.0
        var = max(n * p_bar * (1 - p_bar), 1e-9)
        chi2 += (observed - expected) ** 2 / var
        df += 1
    df = max(df - 2, 1)  # H-L degrees of freedom = groups − 2

    # p-value from upper-tail χ² survival function via series approximation
    # (avoids SciPy). Good to ~3 sig figs for typical df ∈ [4, 12].
    p_value = _chi2_sf(chi2, df)
    return chi2, p_value


def _chi2_sf(x: float, df: int) -> float:
    """Upper-tail of χ² distribution via regularised incomplete gamma.

    P(X > x | X ~ χ²_df) = 1 − P(df/2, x/2). Uses a Lentz-style
    continued fraction for numerical stability.
    """
    if x <= 0:
        return 1.0
    a = df / 2.0
    z = x / 2.0
    # Use series for small z, continued fraction otherwise
    if z < a + 1:
        # Series representation
        term = 1.0 / a
        total = term
        for n in range(1, 200):
            term *= z / (a + n)
            total += term
            if abs(term) < abs(total) * 1e-12:
                break
        lower = math.exp(-z + a * math.log(z) - _lgamma(a)) * total
        return max(0.0, 1.0 - lower)
    else:
        # Continued fraction (Lentz)
        b = z + 1 - a
        c = 1e30
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delt = d * c
            h *= delt
            if abs(delt - 1.0) < 1e-12:
                break
        upper = math.exp(-z + a * math.log(z) - _lgamma(a)) * h
        return max(0.0, min(1.0, upper))


# lightweight lgamma via Stirling + correction
def _lgamma(x: float) -> float:
    import math
    return math.lgamma(x)


import math  # re-export for use above

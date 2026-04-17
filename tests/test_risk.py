"""Tests for modelforge.risk — Merton, KMV, IFRS 9 ECL, H-L backtest."""

from __future__ import annotations

import math

import numpy as np
import pytest

from modelforge.risk import (
    ECLInputs,
    MertonInputs,
    Stage,
    calibrate_pd_kmv,
    compute_ecl,
    empirical_dd_to_pd_table,
    hosmer_lemeshow,
    solve_merton,
)


# ─── Merton ──────────────────────────────────────────────────────────────────


def test_merton_converges_on_hull_textbook_case():
    """Hull ch 24: firm with E=3, σ_E=0.80, D=10, r=5%, T=1."""
    r = solve_merton(MertonInputs(
        equity_value=3.0, equity_volatility=0.80,
        debt_face_value=10.0, risk_free_rate=0.05, horizon_years=1.0,
    ))
    assert r.converged
    # Textbook: V ≈ 12.40, σ_V ≈ 0.21, DD ≈ 1.14
    assert 12.0 < r.asset_value < 13.0
    assert 0.15 < r.asset_volatility < 0.25
    assert 1.0 < r.distance_to_default < 1.3


def test_merton_asset_value_exceeds_equity():
    """V = E + discounted debt face, so V > E for any positive debt."""
    r = solve_merton(MertonInputs(
        equity_value=100.0, equity_volatility=0.30,
        debt_face_value=50.0, risk_free_rate=0.04, horizon_years=1.0,
    ))
    assert r.asset_value > 100.0


def test_merton_higher_leverage_higher_pd():
    """Same E + σ_E, more debt → higher PD."""
    low_lev = solve_merton(MertonInputs(
        equity_value=100.0, equity_volatility=0.30,
        debt_face_value=30.0, risk_free_rate=0.04, horizon_years=1.0,
    ))
    high_lev = solve_merton(MertonInputs(
        equity_value=100.0, equity_volatility=0.30,
        debt_face_value=200.0, risk_free_rate=0.04, horizon_years=1.0,
    ))
    assert high_lev.probability_of_default > low_lev.probability_of_default


def test_merton_pd_is_between_zero_and_one():
    r = solve_merton(MertonInputs(
        equity_value=100.0, equity_volatility=0.50,
        debt_face_value=150.0, risk_free_rate=0.04, horizon_years=1.0,
    ))
    assert 0.0 < r.probability_of_default < 1.0


def test_merton_rejects_bad_inputs():
    with pytest.raises(ValueError):
        MertonInputs(equity_value=-1.0, equity_volatility=0.3,
                     debt_face_value=50.0, risk_free_rate=0.04)
    with pytest.raises(ValueError):
        MertonInputs(equity_value=100.0, equity_volatility=0.0,
                     debt_face_value=50.0, risk_free_rate=0.04)


# ─── KMV empirical calibration ───────────────────────────────────────────────


def test_kmv_monotonic():
    """Higher DD → lower PD, strictly."""
    dds = [-4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]
    pds = [calibrate_pd_kmv(d) for d in dds]
    for a, b in zip(pds, pds[1:]):
        assert a >= b


def test_kmv_interpolates_between_buckets():
    """DD=2.5 should give PD between DD=2.0 and DD=3.0."""
    pd_2 = calibrate_pd_kmv(2.0)
    pd_25 = calibrate_pd_kmv(2.5)
    pd_3 = calibrate_pd_kmv(3.0)
    assert pd_3 < pd_25 < pd_2


def test_kmv_clamps_beyond_range():
    """DD off the edges returns the edge value, not NaN/extrapolation."""
    far_left = calibrate_pd_kmv(-10.0)
    far_right = calibrate_pd_kmv(20.0)
    assert far_left == calibrate_pd_kmv(-4.0)  # clamped to edge
    assert far_right == calibrate_pd_kmv(8.0)


def test_kmv_table_immutable():
    """Caller can't corrupt the bundled table."""
    t1 = empirical_dd_to_pd_table()
    t1.append((99.0, 0.0))
    t2 = empirical_dd_to_pd_table()
    assert (99.0, 0.0) not in t2


# ─── IFRS 9 ECL ──────────────────────────────────────────────────────────────


def test_stage_1_uses_12_month_ecl():
    inp = ECLInputs(
        exposure_at_default_eur_m=100.0, loss_given_default=0.45,
        effective_interest_rate=0.05, maturity_years=10,
        pd_curve_annual=[0.02] * 10,
        current_pd_12m=0.02, origination_pd_12m=0.02,
        days_past_due=0,
    )
    r = compute_ecl(inp)
    assert r.stage == Stage.STAGE_1
    assert r.ecl_eur_m == pytest.approx(r.ecl_12_month_eur_m, rel=1e-9)
    # 12-mo ECL ≈ PD × LGD × EAD × discount = 0.02 × 0.45 × 100 × (1/1.05) ≈ 0.857
    assert abs(r.ecl_eur_m - 0.857) < 0.01


def test_stage_2_triggered_by_sicr():
    """PD doubled vs origination → Stage 2."""
    inp = ECLInputs(
        exposure_at_default_eur_m=100.0, loss_given_default=0.45,
        effective_interest_rate=0.05, maturity_years=10,
        pd_curve_annual=[0.05] * 10,
        current_pd_12m=0.05, origination_pd_12m=0.02,  # 2.5x → SICR
        days_past_due=0,
    )
    r = compute_ecl(inp)
    assert r.stage == Stage.STAGE_2
    assert r.ecl_eur_m == pytest.approx(r.ecl_lifetime_eur_m, rel=1e-9)
    # Lifetime is much larger than 12-month
    assert r.ecl_lifetime_eur_m > 4 * r.ecl_12_month_eur_m


def test_stage_2_triggered_by_30_dpd():
    inp = ECLInputs(
        exposure_at_default_eur_m=100.0, loss_given_default=0.45,
        effective_interest_rate=0.05, maturity_years=10,
        pd_curve_annual=[0.02] * 10,
        current_pd_12m=0.02, origination_pd_12m=0.02,
        days_past_due=45,
    )
    r = compute_ecl(inp)
    assert r.stage == Stage.STAGE_2


def test_stage_3_triggered_by_90_dpd():
    inp = ECLInputs(
        exposure_at_default_eur_m=100.0, loss_given_default=0.45,
        effective_interest_rate=0.05, maturity_years=10,
        pd_curve_annual=[0.02] * 10,
        days_past_due=100,
    )
    r = compute_ecl(inp)
    assert r.stage == Stage.STAGE_3
    # Stage 3: ECL = EAD × LGD on current carrying amount
    assert r.ecl_eur_m == pytest.approx(100.0 * 0.45, rel=1e-9)


def test_explicit_stage_override():
    inp = ECLInputs(
        exposure_at_default_eur_m=100.0, loss_given_default=0.45,
        effective_interest_rate=0.05, maturity_years=5,
        pd_curve_annual=[0.02] * 5,
        stage_override=Stage.STAGE_3,
    )
    r = compute_ecl(inp)
    assert r.stage == Stage.STAGE_3


# ─── Hosmer-Lemeshow ─────────────────────────────────────────────────────────


def test_hl_well_calibrated_large_p_value():
    """Synthetic well-calibrated PDs should produce large p-value."""
    rng = np.random.default_rng(42)
    n = 1000
    pds = rng.uniform(0.001, 0.20, n)
    defaults = (rng.uniform(0, 1, n) < pds).astype(int)
    chi2, p = hosmer_lemeshow(pds.tolist(), defaults.tolist())
    assert p > 0.05  # can't reject null of good calibration


def test_hl_miscalibrated_small_p_value():
    """If actual default rate is 2× predicted, H-L should flag it."""
    rng = np.random.default_rng(42)
    n = 1000
    pds = rng.uniform(0.001, 0.10, n)
    # Realised defaults at TRUE rate of 2× PD (miscalibration)
    defaults = (rng.uniform(0, 1, n) < (2 * pds)).astype(int)
    chi2, p = hosmer_lemeshow(pds.tolist(), defaults.tolist())
    assert p < 0.01  # strong evidence of miscalibration


def test_hl_length_mismatch_raises():
    with pytest.raises(ValueError):
        hosmer_lemeshow([0.1, 0.2], [0, 0, 1])

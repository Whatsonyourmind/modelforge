"""Tests for modelforge.analytics.monte_carlo (US-002)."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
import yaml
from openpyxl import load_workbook

from modelforge.analytics.factors import SensitivityFactor, default_factors_for
from modelforge.analytics.monte_carlo import (
    MCConfig,
    append_monte_carlo_sheet,
    run_monte_carlo,
)
from modelforge.qc import run_qc
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def built_unitranche(tmp_path_factory):
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("mc") / "u.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    return out


def test_sheet_and_chart_present(built_unitranche):
    wb = load_workbook(built_unitranche)
    assert "MonteCarlo" in wb.sheetnames
    ws = wb["MonteCarlo"]
    assert len(ws._charts) >= 1


def test_distribution_stats_populated(built_unitranche):
    wb = load_workbook(built_unitranche)
    ws = wb["MonteCarlo"]
    # Rows 9..17 hold Mean/Std/P5/P25/P50/P75/P95/Min/Max
    for r in range(9, 18):
        v = ws.cell(row=r, column=2).value
        assert v is not None and isinstance(v, float)


def test_deterministic_with_seed():
    factors = default_factors_for("unitranche")
    r1 = run_monte_carlo(factors, MCConfig(n_runs=500, seed=42))
    r2 = run_monte_carlo(factors, MCConfig(n_runs=500, seed=42))
    np.testing.assert_array_almost_equal(r1.samples, r2.samples)


def test_different_seeds_diverge():
    factors = default_factors_for("unitranche")
    r1 = run_monte_carlo(factors, MCConfig(n_runs=500, seed=1))
    r2 = run_monte_carlo(factors, MCConfig(n_runs=500, seed=2))
    assert not np.allclose(r1.samples, r2.samples)


def test_n_runs_respected():
    factors = default_factors_for("unitranche")
    r = run_monte_carlo(factors, MCConfig(n_runs=2500, seed=0))
    assert len(r.samples) == 2500


def test_triangular_respects_bounds():
    """With triangular(left=-0.2, mode=0, right=0.2), draws should stay in [-0.2, 0.2]."""
    factors = [SensitivityFactor(driver_name="revenue_growth_y1", label="t",
                                 low_shock=-0.2, high_shock=0.2)]
    r = run_monte_carlo(factors, MCConfig(n_runs=2000, distribution="triangular", seed=0))
    contrib = r.factor_contributions["revenue_growth_y1"]
    # elasticity for revenue_growth_y1 is 0.8 → contrib bounded by [-0.16, 0.16]
    assert contrib.min() >= -0.16 - 1e-9
    assert contrib.max() <= 0.16 + 1e-9


def test_normal_distribution_produces_near_symmetric_mean():
    factors = default_factors_for("unitranche")
    r = run_monte_carlo(factors, MCConfig(n_runs=5000, distribution="normal", seed=0))
    assert abs(r.mean) < 0.05  # near zero


def test_percentiles_ordered():
    factors = default_factors_for("unitranche")
    r = run_monte_carlo(factors, MCConfig(n_runs=1000, seed=0))
    assert r.percentile(5) < r.percentile(50) < r.percentile(95)


def test_performance_1000_runs_under_5s():
    """PRD US-002 AC: 1000 runs on a 5-year deal in < 5s."""
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    factors = default_factors_for("unitranche")
    t0 = time.time()
    r = run_monte_carlo(factors, MCConfig(n_runs=1000, seed=0))
    elapsed = time.time() - t0
    assert elapsed < 5.0
    assert len(r.samples) == 1000


def test_mc_sheet_on_all_templates(tmp_path):
    """Every template gets a MonteCarlo sheet after build_model.

    Builds each example into a temp dir (self-contained) rather than reading
    gitignored prebuilt output/*.xlsx, so the test passes from a clean checkout.
    """
    from modelforge.cli import _load_spec_class

    specs = [
        ("unitranche_cdmo.yaml", "unitranche"),
        ("minibond_logistics.yaml", "minibond"),
        ("credit_memo_cdmo.yaml", "credit_memo"),
        ("project_finance_solar.yaml", "project_finance"),
        ("real_estate_pbsa.yaml", "real_estate"),
        ("npl_mixed_portfolio.yaml", "npl"),
        ("structured_credit_pmi.yaml", "structured_credit"),
        ("three_statement_cdmo.yaml", "three_statement"),
    ]
    for fname, mt in specs:
        spec_path = ROOT / "examples" / fname
        raw = yaml.safe_load(spec_path.read_bytes())
        spec = _load_spec_class(raw.get("model_type", mt)).model_validate(raw)
        out = tmp_path / f"{Path(fname).stem}.xlsx"
        build_model(spec, out, spec_source_bytes=spec_path.read_bytes(), spec_source_path=spec_path)
        wb = load_workbook(out)
        assert "MonteCarlo" in wb.sheetnames, f"MC missing on {mt}"


def test_qc_still_passes_with_mc(built_unitranche):
    report = run_qc(built_unitranche)
    assert report.all_pass, [c.name for c in report.checks if not c.passed]

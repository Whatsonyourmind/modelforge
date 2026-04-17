"""Tests for modelforge.drift (US-029)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from modelforge.cli import main
from modelforge.drift import check_drift, render_markdown
from modelforge.drift.watcher import DriftItem, DriftReport
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def unitranche_built(tmp_path_factory):
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("drift") / "u.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    return out


@pytest.fixture(scope="module")
def dcf_built(tmp_path_factory):
    from modelforge.spec.dcf import DCFSpec
    p = ROOT / "examples" / "dcf_enel.yaml"
    spec = DCFSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("drift2") / "d.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    return out


# ── Core behaviour ──────────────────────────────────────────────────────────


def test_unitranche_euribor_flagged_as_stale(unitranche_built):
    """CDMO unitranche spec has EURIBOR 6M at 2.8%; bundled feed shows
    3.95% → drift of 115bps > 50bps threshold → flagged."""
    rep = check_drift(unitranche_built)
    euribor = [i for i in rep.items if i.driver_name == "euribor_6m_rate"]
    assert len(euribor) == 1
    assert euribor[0].flagged


def test_dcf_damodaran_matches(dcf_built):
    """Enel DCF spec carries ERP = 6.7% (matches bundled Damodaran) →
    clean (no drift flagged)."""
    rep = check_drift(dcf_built)
    erp = [i for i in rep.items if i.driver_name == "equity_risk_premium"]
    assert len(erp) == 1
    assert not erp[0].flagged
    assert abs(erp[0].delta_abs) < 1e-6


def test_threshold_respected(unitranche_built):
    """A very loose threshold should hide all flags."""
    rep = check_drift(unitranche_built, threshold_bps=10_000.0,
                      threshold_rel=10.0)
    assert rep.n_flagged == 0


def test_tight_threshold_flags_more(dcf_built):
    """A very tight threshold should flag even the 10bps risk-free drift."""
    rep = check_drift(dcf_built, threshold_bps=5.0)
    rf = [i for i in rep.items if i.driver_name == "risk_free_rate"]
    assert rf and rf[0].flagged


def test_missing_drivers_reported(unitranche_built):
    """Drivers not defined in workbook go to missing_drivers list."""
    rep = check_drift(unitranche_built)
    assert len(rep.missing_drivers) > 0
    assert "equity_risk_premium" in rep.missing_drivers


def test_clean_property(dcf_built):
    """DCF Enel is clean at default thresholds."""
    rep = check_drift(dcf_built, threshold_bps=50.0)
    assert rep.clean is True
    assert rep.n_flagged == 0


def test_markdown_output_well_formed(unitranche_built):
    rep = check_drift(unitranche_built)
    md = render_markdown(rep)
    assert "# Drift report" in md
    # tmp_path_factory names the file deterministically, just check extension
    assert ".xlsx" in md
    assert "euribor" in md.lower()


def test_items_carry_source_info(unitranche_built):
    rep = check_drift(unitranche_built)
    assert all(i.source for i in rep.items)
    # ECB items mention ECB
    ecb_items = [i for i in rep.items if "EURIBOR" in i.driver_name.upper() or "euribor" in i.driver_name]
    if ecb_items:
        assert all("ECB" in i.source for i in ecb_items)


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_drift_cli_exits_1_on_flagged(unitranche_built):
    runner = CliRunner()
    result = runner.invoke(main, ["drift", str(unitranche_built)])
    assert result.exit_code == 1
    assert "FLAG" in result.output


def test_drift_cli_exits_0_on_clean(dcf_built):
    runner = CliRunner()
    result = runner.invoke(main, ["drift", str(dcf_built)])
    assert result.exit_code == 0

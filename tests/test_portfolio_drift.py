"""Tests for portfolio-level drift sweep (US-029 extension)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from modelforge.cli import main
from modelforge.drift import (
    PortfolioDriftReport,
    check_portfolio,
    render_portfolio_markdown,
)
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def mixed_portfolio(tmp_path_factory):
    """Build two workbooks in a single folder: one with stale EURIBOR
    (unitranche) and one clean (DCF Enel)."""
    from modelforge.spec.unitranche import UnitrancheSpec
    from modelforge.spec.dcf import DCFSpec
    folder = tmp_path_factory.mktemp("portfolio")
    p1 = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec1 = UnitrancheSpec.model_validate(yaml.safe_load(p1.read_bytes()))
    build_model(spec1, folder / "unitranche.xlsx",
                spec_source_bytes=p1.read_bytes(), spec_source_path=p1)
    p2 = ROOT / "examples" / "dcf_enel.yaml"
    spec2 = DCFSpec.model_validate(yaml.safe_load(p2.read_bytes()))
    build_model(spec2, folder / "dcf.xlsx",
                spec_source_bytes=p2.read_bytes(), spec_source_path=p2)
    return folder


# ── Core checker ───────────────────────────────────────────────────────────


def test_portfolio_drift_scans_both(mixed_portfolio):
    rep = check_portfolio(mixed_portfolio)
    assert rep.n_workbooks == 2


def test_portfolio_drift_flags_at_least_one(mixed_portfolio):
    """Unitranche has stale EURIBOR → at least one workbook flagged."""
    rep = check_portfolio(mixed_portfolio)
    assert rep.n_flagged_workbooks >= 1
    assert rep.total_flags >= 1


def test_portfolio_drift_not_clean(mixed_portfolio):
    rep = check_portfolio(mixed_portfolio)
    assert not rep.clean


def test_portfolio_drift_raises_on_non_directory(tmp_path):
    with pytest.raises(ValueError):
        check_portfolio(tmp_path / "does_not_exist")


def test_portfolio_markdown_rendering(mixed_portfolio):
    rep = check_portfolio(mixed_portfolio)
    md = render_portfolio_markdown(rep)
    assert "# Portfolio drift report" in md
    assert "unitranche.xlsx" in md
    assert "dcf.xlsx" in md


def test_loose_thresholds_produce_clean_portfolio(mixed_portfolio):
    rep = check_portfolio(mixed_portfolio, threshold_bps=10_000.0,
                          threshold_rel=10.0)
    assert rep.clean


# ── CLI surface ────────────────────────────────────────────────────────────


def test_drift_cli_portfolio_flag(mixed_portfolio):
    runner = CliRunner()
    result = runner.invoke(main, ["drift", "--portfolio",
                                   str(mixed_portfolio)])
    # Exit 1 because at least the unitranche workbook flags
    assert result.exit_code == 1
    assert "Portfolio drift" in result.output
    assert "2" in result.output  # both workbooks scanned


def test_drift_cli_portfolio_non_dir_exits_2(tmp_path):
    runner = CliRunner()
    # Passing a FILE path with --portfolio should error
    f = tmp_path / "not_a_dir.xlsx"
    f.write_text("x")
    result = runner.invoke(main, ["drift", "--portfolio", str(f)])
    assert result.exit_code == 2
    assert "not a directory" in result.output


def test_drift_cli_portfolio_markdown_export(mixed_portfolio, tmp_path):
    runner = CliRunner()
    out = tmp_path / "drift_summary.md"
    result = runner.invoke(main, ["drift", "--portfolio",
                                   str(mixed_portfolio),
                                   "-o", str(out)])
    assert result.exit_code == 1   # has flags
    assert out.exists()
    md = out.read_text(encoding="utf-8")
    assert "# Portfolio drift report" in md

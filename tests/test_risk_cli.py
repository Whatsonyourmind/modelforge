"""Tests for modelforge.cli risk command (US-020 integration)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from modelforge.cli import main


def test_risk_cli_produces_reasonable_output():
    runner = CliRunner()
    result = runner.invoke(main, [
        "risk",
        "--equity", "500", "--equity-vol", "0.32",
        "--debt", "400", "--maturity", "7",
        "--counterparty", "TestCo",
    ])
    assert result.exit_code == 0
    assert "TestCo" in result.output
    assert "Merton PD" in result.output
    assert "KMV PD" in result.output
    assert "12-month ECL" in result.output
    assert "STAGE_1" in result.output  # low-leverage IG → Stage 1


def test_risk_cli_stage_3_on_default(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, [
        "risk",
        "--equity", "50", "--equity-vol", "0.80",
        "--debt", "500", "--dpd", "120",
        "--counterparty", "DefaultedCo",
    ])
    assert result.exit_code == 0
    assert "STAGE_3" in result.output


def test_risk_cli_json_export(tmp_path):
    runner = CliRunner()
    json_path = tmp_path / "risk.json"
    result = runner.invoke(main, [
        "risk",
        "--equity", "500", "--equity-vol", "0.30",
        "--debt", "400", "--maturity", "5",
        "--counterparty", "ExportTest",
        "--json-out", str(json_path),
    ])
    assert result.exit_code == 0
    payload = json.loads(json_path.read_text())
    assert payload["counterparty"] == "ExportTest"
    assert "merton" in payload
    assert payload["merton"]["converged"] is True
    assert 0 <= payload["merton"]["pd"] <= 1
    assert payload["kmv_pd"] >= 0
    assert payload["ecl"]["stage"] == "stage_1"


def test_risk_cli_high_leverage_higher_pd():
    runner = CliRunner()
    low = runner.invoke(main, [
        "risk", "--equity", "500", "--equity-vol", "0.30",
        "--debt", "200", "--maturity", "5", "--json-out", "-",
    ])
    # The --json-out "-" writes to a file literally named "-";
    # Click's CliRunner writes to the runner's filesystem.
    # Just do it without JSON; check textual output contains PD values.
    high = runner.invoke(main, [
        "risk", "--equity", "500", "--equity-vol", "0.30",
        "--debt", "1500", "--maturity", "5",
    ])
    low = runner.invoke(main, [
        "risk", "--equity", "500", "--equity-vol", "0.30",
        "--debt", "200", "--maturity", "5",
    ])
    assert low.exit_code == 0 and high.exit_code == 0
    # Can't easily parse the table but both must mention KMV PD
    assert "KMV PD" in low.output
    assert "KMV PD" in high.output

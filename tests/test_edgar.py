"""Tests for modelforge.ingest.edgar (US-026 SEC adapter)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from modelforge.cli import main
from modelforge.ingest.edgar import (
    EdgarFinancials,
    _BUNDLED_SAMPLE,
    fetch_company_financials,
)


# ── Bundled sample is extractable ───────────────────────────────────────────


def test_bundled_aapl_sample_has_five_fiscal_years():
    fin = fetch_company_financials("AAPL", years=5, prefer_bundled=True)
    assert fin is not None
    assert fin.ticker == "AAPL"
    assert fin.cik == 320193
    assert fin.entity_name == "APPLE INC."
    assert fin.fiscal_years == [2020, 2021, 2022, 2023, 2024]
    # Revenue matches bundled data (in $m)
    assert fin.revenue_usd_m[0] == pytest.approx(274515.0, rel=1e-6)
    assert fin.revenue_usd_m[-1] == pytest.approx(391035.0, rel=1e-6)
    assert fin.fetched_from == "bundled"


def test_bundled_snapshot_has_balance_sheet_items():
    fin = fetch_company_financials("AAPL", prefer_bundled=True)
    assert fin.total_assets_usd_m == pytest.approx(364980.0, rel=1e-6)
    assert fin.long_term_debt_usd_m == pytest.approx(85750.0, rel=1e-6)


def test_years_parameter_truncates():
    fin = fetch_company_financials("AAPL", years=3, prefer_bundled=True)
    assert len(fin.fiscal_years) == 3
    # Should be the MOST RECENT 3 years (2022, 2023, 2024)
    assert fin.fiscal_years == [2022, 2023, 2024]


def test_unknown_ticker_falls_back_gracefully(monkeypatch):
    """Unknown ticker + no live network → returns None (not raises)."""
    # Force live lookups to fail
    with patch("modelforge.ingest.edgar._lookup_cik_live", return_value=None):
        with patch("modelforge.ingest.edgar._fetch_facts_live", return_value=None):
            result = fetch_company_financials("ZZZZZZ", prefer_bundled=False)
    assert result is None


def test_live_network_error_falls_back_to_bundled_if_available():
    """Live call fails but ticker in bundled → use bundled."""
    with patch("modelforge.ingest.edgar._lookup_cik_live", return_value=None):
        with patch("modelforge.ingest.edgar._fetch_facts_live", return_value=None):
            fin = fetch_company_financials("AAPL", prefer_bundled=False)
    assert fin is not None
    assert fin.fetched_from == "bundled"


# ── CLI surface ─────────────────────────────────────────────────────────────


def test_edgar_cli_offline_mode():
    runner = CliRunner()
    result = runner.invoke(main, ["edgar", "AAPL", "--offline"])
    assert result.exit_code == 0
    assert "AAPL" in result.output
    assert "APPLE INC." in result.output
    assert "274,515" in result.output  # FY2020 revenue


def test_edgar_cli_unknown_ticker_exits_2(monkeypatch):
    runner = CliRunner()
    with patch("modelforge.ingest.edgar._lookup_cik_live", return_value=None):
        result = runner.invoke(main, ["edgar", "ZZZZZZ"])
    assert result.exit_code == 2
    assert "Could not fetch" in result.output


def test_edgar_cli_json_export(tmp_path):
    import json
    runner = CliRunner()
    out = tmp_path / "aapl.json"
    result = runner.invoke(main, [
        "edgar", "AAPL", "--offline", "--json-out", str(out),
    ])
    assert result.exit_code == 0
    payload = json.loads(out.read_text())
    assert payload["ticker"] == "AAPL"
    assert payload["cik"] == 320193
    assert len(payload["fiscal_years"]) == 5

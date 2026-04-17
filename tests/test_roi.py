"""Tests for modelforge.roi (US-036)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from modelforge.cli import main
from modelforge.roi import ROIInputs, compute_roi, render_markdown


# ── Math sanity ────────────────────────────────────────────────────────────


def test_defaults_produce_positive_net_savings():
    res = compute_roi(ROIInputs())
    assert res.hours_saved_per_deal == pytest.approx(34.0)
    # At 20 deals × 34 hrs × €180 = €122,400 annual time savings alone
    assert res.annual_time_savings_eur >= 120_000
    assert res.net_savings_eur > 0
    assert res.roi_1y_pct > 1.0  # > 100%


def test_payback_under_3_months_at_defaults():
    res = compute_roi(ROIInputs())
    assert res.payback_months < 3


def test_higher_volume_higher_savings():
    res_low = compute_roi(ROIInputs(deals_per_year=5))
    res_high = compute_roi(ROIInputs(deals_per_year=50))
    assert res_high.total_gross_savings_eur > res_low.total_gross_savings_eur


def test_error_rate_delta_drives_rework_savings():
    base = compute_roi(ROIInputs(legacy_error_rate=0.15,
                                  modelforge_error_rate=0.15))
    big = compute_roi(ROIInputs(legacy_error_rate=0.30,
                                 modelforge_error_rate=0.02))
    assert big.rework_savings_eur > base.rework_savings_eur


def test_flagged_negative_case():
    """Inputs where ModelForge is more expensive than it saves."""
    inputs = ROIInputs(
        deals_per_year=1,
        hours_per_deal_legacy=5,
        hours_per_deal_modelforge=4,
        loaded_analyst_cost_eur_per_hour=50,
        seats=10,
        monthly_price_per_seat_eur=999,
    )
    res = compute_roi(inputs)
    assert res.net_savings_eur < 0
    assert any("ROI < 100%" in n or "No gross savings" in n
               for n in res.notes)


def test_audit_savings_positive_at_defaults():
    res = compute_roi(ROIInputs())
    assert res.audit_savings_eur > 0


def test_zero_delta_audit_still_computes():
    res = compute_roi(ROIInputs(audit_hours_legacy=4.0,
                                 audit_hours_modelforge=4.0))
    assert res.audit_savings_eur == 0


def test_hours_saved_non_negative_even_if_mf_above_legacy():
    """If MF hours > legacy, savings clamped to 0, not negative."""
    res = compute_roi(ROIInputs(hours_per_deal_legacy=10,
                                 hours_per_deal_modelforge=30))
    assert res.hours_saved_per_deal == 0


# ── Markdown rendering ────────────────────────────────────────────────────


def test_markdown_contains_customer_and_assumptions():
    res = compute_roi(ROIInputs(deals_per_year=30))
    md = render_markdown(res, customer="TestFund")
    assert "# ModelForge ROI — TestFund" in md
    assert "Deals per year" in md
    assert "## Headline numbers" in md
    assert "€" in md  # euro sign in rendered numbers


# ── CLI ───────────────────────────────────────────────────────────────────


def test_roi_cli_prints_expected_numbers():
    runner = CliRunner()
    result = runner.invoke(main, [
        "roi", "--deals", "25", "--hours-legacy", "45", "--hours-mf", "6",
        "--customer", "TestCo",
    ])
    assert result.exit_code == 0
    assert "TestCo" in result.output
    assert "1-year ROI" in result.output
    assert "Payback period" in result.output


def test_roi_cli_markdown_export(tmp_path):
    runner = CliRunner()
    md = tmp_path / "roi.md"
    result = runner.invoke(main, [
        "roi", "--customer", "ExportCo", "-o", str(md),
    ])
    assert result.exit_code == 0
    assert md.exists()
    txt = md.read_text(encoding="utf-8")
    assert "ExportCo" in txt
    assert "Payback period" in txt

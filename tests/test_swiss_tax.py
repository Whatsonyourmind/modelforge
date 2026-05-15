"""Tests for the Swiss corporate-tax module (federal LIFD + cantonal,
participation deduction, patent box, R&D super-deduction, BEPS Pillar 2)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from modelforge.finance_core.swiss_corp_tax import (
    BEPS_MIN_RATE,
    CANTON_TOTAL_RATES_2026,
    DEFAULT_CANTON_RATE,
    PARTICIPATION_EXEMPTION_PCT,
    PATENT_BOX_MAX_REDUCTION_PCT,
    RD_SUPER_DEDUCTION_PCT,
    SwissTaxInputs,
    apply_loss_cf,
    applicable_rate,
    compute_participation_deduction,
    compute_patent_box_deduction,
    compute_rd_super_deduction,
    compute_swiss_tax,
)


# ── basic rate selection ─────────────────────────────────────────────────


def test_zug_is_lowest_canton():
    """Zug should be the lowest combined rate in the canton snapshot."""
    assert min(CANTON_TOTAL_RATES_2026.values()) == CANTON_TOTAL_RATES_2026["ZG"]


def test_zurich_is_default_canton_rate():
    assert DEFAULT_CANTON_RATE == CANTON_TOTAL_RATES_2026["ZH"]


def test_canton_lookup_falls_back_to_default():
    inputs = SwissTaxInputs(pretax_book_income=Decimal("1_000_000"), canton="XX")
    assert applicable_rate(inputs) == DEFAULT_CANTON_RATE


def test_canton_total_rate_override_wins():
    custom = Decimal("0.10")
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("1_000_000"),
        canton="ZH",
        canton_total_rate=custom,
    )
    assert applicable_rate(inputs) == custom


# ── participation deduction ──────────────────────────────────────────────


def test_participation_deduction_zero_when_threshold_not_met():
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("0"),
        qualifying_participation_income=Decimal("500_000"),
        participation_threshold_met=False,
    )
    assert compute_participation_deduction(inputs) == Decimal("0")


def test_participation_deduction_full_when_threshold_met():
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("0"),
        qualifying_participation_income=Decimal("500_000"),
        participation_threshold_met=True,
    )
    assert (
        compute_participation_deduction(inputs)
        == Decimal("500_000") * PARTICIPATION_EXEMPTION_PCT
    )


# ── patent box ────────────────────────────────────────────────────────────


def test_patent_box_deduction_max_90_pct_of_qualifying_profit():
    """Without the cap kicking in, deduction = 90% of IP profit."""
    qualifying = Decimal("100_000")
    total = Decimal("10_000_000")  # very large → cap doesn't bind
    deduction = compute_patent_box_deduction(qualifying, total)
    assert deduction == qualifying * PATENT_BOX_MAX_REDUCTION_PCT


def test_patent_box_deduction_capped_at_70_pct_of_total():
    """Deduction can't exceed 70% of total taxable profit."""
    qualifying = Decimal("1_000_000")  # would imply 900K deduction
    total = Decimal("100_000")          # cap = 70K
    deduction = compute_patent_box_deduction(qualifying, total)
    assert deduction == Decimal("70_000")


# ── R&D super-deduction ──────────────────────────────────────────────────


def test_rd_super_deduction_50_pct_of_expenditure():
    rd = Decimal("200_000")
    total = Decimal("10_000_000")
    deduction = compute_rd_super_deduction(rd, total, Decimal("0"))
    assert deduction == rd * RD_SUPER_DEDUCTION_PCT


def test_rd_super_deduction_capped_by_overall_70_pct_minus_other_specials():
    rd = Decimal("100_000")
    total = Decimal("100_000")          # 70% cap = 70K
    other = Decimal("60_000")           # used by patent box
    deduction = compute_rd_super_deduction(rd, total, other)
    # cap_remaining = 70K - 60K = 10K → deduction limited to 10K
    assert deduction == Decimal("10_000")


def test_rd_super_deduction_zero_when_cap_already_consumed():
    rd = Decimal("100_000")
    total = Decimal("100_000")
    other = Decimal("80_000")  # exceeds 70K cap → no room
    deduction = compute_rd_super_deduction(rd, total, other)
    assert deduction == Decimal("0")


# ── loss carry-forward (100% offset, no Spanish cap) ─────────────────────


def test_loss_cf_full_offset_when_losses_cover_taxable():
    used, after, remaining = apply_loss_cf(
        Decimal("500_000"), Decimal("1_000_000"),
    )
    assert used == Decimal("500_000")
    assert after == Decimal("0")
    assert remaining == Decimal("500_000")


def test_loss_cf_partial_when_losses_smaller_than_taxable():
    used, after, remaining = apply_loss_cf(
        Decimal("1_000_000"), Decimal("300_000"),
    )
    assert used == Decimal("300_000")
    assert after == Decimal("700_000")
    assert remaining == Decimal("0")


def test_loss_cf_negative_taxable_grows_carryforward():
    used, after, remaining = apply_loss_cf(
        Decimal("-200_000"), Decimal("100_000"),
    )
    assert used == Decimal("0")
    assert after == Decimal("-200_000")
    assert remaining == Decimal("300_000")


# ── end-to-end ────────────────────────────────────────────────────────────


def test_compute_swiss_tax_zurich_baseline():
    """Plain Zurich-domiciled co with no special deductions."""
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("10_000_000"),
        canton="ZH",
    )
    out = compute_swiss_tax(inputs)
    expected_total = Decimal("10_000_000") * CANTON_TOTAL_RATES_2026["ZH"]
    assert out.total_tax == expected_total
    # Effective rate equals headline since no special deductions
    assert out.effective_rate == CANTON_TOTAL_RATES_2026["ZH"]


def test_compute_swiss_tax_zug_advantage():
    """Same income in Zug should produce ~40% less tax than Zurich."""
    inputs_zug = SwissTaxInputs(
        pretax_book_income=Decimal("10_000_000"),
        canton="ZG",
    )
    inputs_zh = SwissTaxInputs(
        pretax_book_income=Decimal("10_000_000"),
        canton="ZH",
    )
    out_zug = compute_swiss_tax(inputs_zug)
    out_zh = compute_swiss_tax(inputs_zh)
    assert out_zug.total_tax < out_zh.total_tax
    # Zurich/Zug ratio matches headline ratio
    ratio = out_zug.total_tax / out_zh.total_tax
    expected = CANTON_TOTAL_RATES_2026["ZG"] / CANTON_TOTAL_RATES_2026["ZH"]
    assert abs(ratio - expected) < Decimal("0.001")


def test_beps_topup_fires_when_below_15pct_and_large_group():
    """Big-Group + Zug rate (11.85%) → BEPS adds top-up to 15%."""
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("100_000_000"),
        canton="ZG",
        consolidated_group_revenue=Decimal("1_000_000_000"),  # > €750M
    )
    out = compute_swiss_tax(inputs)
    # Total ETR should land at exactly the 15% BEPS minimum
    assert out.beps_topup > Decimal("0")
    assert abs(out.effective_rate - BEPS_MIN_RATE) < Decimal("0.001")


def test_beps_topup_does_not_fire_for_small_group():
    """Small-group co at Zug rate stays at canton rate (no top-up)."""
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("10_000_000"),
        canton="ZG",
        consolidated_group_revenue=Decimal("100_000_000"),  # < €750M
    )
    out = compute_swiss_tax(inputs)
    assert out.beps_topup == Decimal("0")
    assert out.effective_rate == CANTON_TOTAL_RATES_2026["ZG"]


def test_beps_topup_does_not_fire_when_canton_already_above_15():
    """Bern (19.86%) is already > 15% → no top-up regardless of group size."""
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("100_000_000"),
        canton="BE",
        consolidated_group_revenue=Decimal("10_000_000_000"),
    )
    out = compute_swiss_tax(inputs)
    assert out.beps_topup == Decimal("0")


def test_full_stack_with_participation_patent_rd():
    """Mid-sized Zurich co with €1M IP profit + €500K R&D + €2M qualifying dividends."""
    inputs = SwissTaxInputs(
        pretax_book_income=Decimal("10_000_000"),
        canton="ZH",
        qualifying_participation_income=Decimal("2_000_000"),
        participation_threshold_met=True,
        patent_box_qualifying_profit=Decimal("1_000_000"),
        rd_qualifying_expenditure=Decimal("500_000"),
    )
    out = compute_swiss_tax(inputs)
    assert out.participation_deduction == Decimal("2_000_000")
    assert out.patent_box_deduction > Decimal("0")
    assert out.rd_super_deduction > Decimal("0")
    # Effective rate should be materially below headline
    assert out.effective_rate < CANTON_TOTAL_RATES_2026["ZH"]

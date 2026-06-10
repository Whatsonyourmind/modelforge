"""Tests for modelforge.finance_core formulas, currency, and ID helpers."""
from __future__ import annotations

from decimal import Decimal

import pytest

from modelforge.finance_core import (
    IdAllocationError,
    IdAllocator,
    apply_growth,
    assert_unique_ids,
    cagr,
    dpi,
    dscr,
    eur_k_to_eur,
    eur_m_to_eur,
    eur_to_eur_m,
    exit_multiple_terminal_value,
    format_bps,
    format_eur,
    format_eur_m,
    format_id,
    format_multiple,
    format_pct,
    format_smart,
    gordon_terminal_value,
    irr,
    levered_beta,
    ltv,
    moic,
    npv,
    pmt,
    present_value,
    rvpi,
    tvpi,
    validate_id,
    wacc,
)


# ── Formulas · time value ───────────────────────────────────────────────


def test_pmt_matches_excel():
    # Excel: =PMT(0.05, 10, -100) returns 12.95046
    assert pmt(0.05, 10, 100) == pytest.approx(12.9504574, abs=1e-4)


def test_pmt_zero_rate_is_straight_line():
    assert pmt(0.0, 10, 100) == pytest.approx(10.0, abs=1e-9)


def test_pmt_rejects_zero_periods():
    with pytest.raises(ValueError):
        pmt(0.05, 0, 100)


def test_npv_sums_discounted_cashflows_starting_at_t1():
    # Excel NPV: =NPV(0.1, 50, 50, 50) → 124.3426
    result = npv(0.10, [50, 50, 50])
    assert result == pytest.approx(124.34259, abs=1e-3)


def test_present_value_does_not_discount_t0():
    # PV semantics: first CF at t=0 is not discounted
    result = present_value(0.10, [-100, 50, 50, 60])
    # -100 + 50/1.1 + 50/1.21 + 60/1.331 ≈ 31.856
    assert result == pytest.approx(31.8557, abs=1e-3)


def test_irr_finds_10_pct_for_known_stream():
    # -100 at t=0, then +55, +55, +55 → IRR ~29%? Easier: -100, +110 → 10%
    result = irr([-100, 110])
    assert result == pytest.approx(0.10, abs=1e-6)


def test_irr_requires_sign_change():
    # all-positive stream has no negative cashflow → IRR undefined
    with pytest.raises(ValueError, match="positive and one negative"):
        irr([100, 110, 120])


def test_irr_handles_sign_change_separated_by_zeros():
    # canonical PE/LBO stream: invest at t0, no interim flows, exit at tN.
    # Regression guard for the adjacent-pair sign-change bug (2026-06-10).
    result = irr([-100, 0, 0, 0, 260])
    assert result == pytest.approx(0.269823, abs=1e-5)


def test_irr_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        irr([])


def test_irr_three_period_project():
    # Classic: -1000 + 400+400+400 → IRR ≈ 9.701%
    result = irr([-1000, 400, 400, 400])
    assert result == pytest.approx(0.09701, abs=1e-4)


# ── Formulas · returns ─────────────────────────────────────────────────


def test_moic_basic():
    assert moic(100, 250) == pytest.approx(2.5, abs=1e-9)


def test_moic_rejects_zero_invested():
    with pytest.raises(ValueError):
        moic(0, 100)


def test_tvpi_dpi_rvpi_consistency():
    drawn = 100
    distributions = 80
    nav = 50
    assert dpi(drawn, distributions) == pytest.approx(0.8)
    assert rvpi(drawn, nav) == pytest.approx(0.5)
    assert tvpi(drawn, distributions, nav) == pytest.approx(1.3)
    assert tvpi(drawn, distributions, nav) == pytest.approx(
        dpi(drawn, distributions) + rvpi(drawn, nav)
    )


# ── Formulas · valuation ───────────────────────────────────────────────


def test_gordon_terminal_value():
    # CF1=10, r=10%, g=3% → 10 / 0.07 = 142.857
    assert gordon_terminal_value(10.0, 0.10, 0.03) == pytest.approx(
        142.857142857, abs=1e-6
    )


def test_gordon_rejects_growth_above_discount():
    with pytest.raises(ValueError, match="growth_rate"):
        gordon_terminal_value(10.0, 0.05, 0.06)


def test_exit_multiple_terminal_value():
    assert exit_multiple_terminal_value(25.0, 12.0) == 300.0


def test_exit_multiple_rejects_zero_multiple():
    with pytest.raises(ValueError):
        exit_multiple_terminal_value(25.0, 0.0)


def test_dscr_basic():
    assert dscr(1_200_000, 1_000_000) == pytest.approx(1.20, abs=1e-9)


def test_ltv_basic():
    assert ltv(6_500_000, 10_000_000) == pytest.approx(0.65, abs=1e-9)


def test_wacc_blended():
    # 50/50 leverage, ke=12%, kd after-tax=4% → wacc 8%
    result = wacc(
        equity_market_value=50,
        debt_market_value=50,
        cost_of_equity=0.12,
        cost_of_debt_after_tax=0.04,
    )
    assert result == pytest.approx(0.08, abs=1e-9)


def test_levered_beta_hamada():
    # β_U=1.0, D/E=0.5, tax=0.25 → β_L = 1.0 * (1 + 0.75*0.5) = 1.375
    assert levered_beta(1.0, 0.5, 0.25) == pytest.approx(1.375, abs=1e-9)


def test_cagr_basic():
    assert cagr(100, 200, 10) == pytest.approx(0.071773, abs=1e-4)


def test_cagr_rejects_zero_start():
    with pytest.raises(ValueError):
        cagr(0, 100, 5)


def test_apply_growth_compounds():
    assert apply_growth(100, 0.05, 3) == pytest.approx(115.7625, abs=1e-4)


# ── Currency converters ────────────────────────────────────────────────


def test_eur_m_to_eur_roundtrip():
    assert eur_m_to_eur(1.25) == Decimal("1250000")
    assert eur_to_eur_m(Decimal("1250000")) == Decimal("1.25")


def test_eur_k_to_eur_basic():
    assert eur_k_to_eur(250) == Decimal("250000")


def test_format_eur_m_default_1dp():
    assert format_eur_m(1.2499) == "€1.2M"


def test_format_eur_m_custom_decimals():
    assert format_eur_m(1.2499, decimals=2) == "€1.25M"


def test_format_eur_grouping():
    assert format_eur(1_234_567.89) == "€1,234,567.89"


def test_format_pct_handles_decimal():
    assert format_pct(0.17555) == "17.6%"


def test_format_bps_handles_float():
    assert format_bps(0.0250) == "250 bps"


def test_format_multiple_basic():
    assert format_multiple(2.345) == "2.3x"


def test_format_smart_picks_best_unit():
    assert format_smart(5_400_000) == "€5.4M"
    assert format_smart(7_500) == "€8k"
    assert format_smart(85) == "€85"


def test_format_smart_handles_negatives():
    assert format_smart(-2_500_000) == "€-2.5M"


# ── ID allocator ───────────────────────────────────────────────────────


def test_validate_id_basic():
    assert validate_id("A-007", "A") == 7
    assert validate_id("S-042", "S") == 42


def test_validate_id_rejects_wrong_prefix():
    with pytest.raises(IdAllocationError):
        validate_id("A-007", "S")


def test_validate_id_rejects_too_short():
    with pytest.raises(IdAllocationError):
        validate_id("A-7", "A")


def test_format_id_left_pads():
    assert format_id("A", 1) == "A-001"
    assert format_id("S", 42) == "S-042"


def test_format_id_rejects_zero():
    with pytest.raises(IdAllocationError):
        format_id("A", 0)


def test_allocator_produces_monotonic_ids():
    allocator = IdAllocator()
    assert allocator.next_assumption() == "A-001"
    assert allocator.next_assumption() == "A-002"
    assert allocator.next_source() == "S-001"
    assert allocator.next_source() == "S-002"


def test_allocator_register_claim_and_keeps_counter_ahead():
    allocator = IdAllocator()
    allocator.register("A-050")
    # Next auto-allocation must be past A-050
    nxt = allocator.next_assumption()
    assert nxt == "A-051"


def test_allocator_register_rejects_duplicate():
    allocator = IdAllocator()
    allocator.next_assumption()
    with pytest.raises(IdAllocationError):
        allocator.register("A-001")


def test_allocator_register_rejects_malformed():
    allocator = IdAllocator()
    with pytest.raises(IdAllocationError):
        allocator.register("bogus")


def test_allocator_separates_A_and_S_counters():
    allocator = IdAllocator()
    allocator.register("A-100")
    # S-counter is independent of A-counter
    assert allocator.next_source() == "S-001"


def test_allocator_all_ids_listed():
    allocator = IdAllocator()
    allocator.next_assumption()
    allocator.next_assumption()
    allocator.register("A-099")
    allocator.next_source()
    assert allocator.all_assumption_ids() == ["A-001", "A-002", "A-099"]
    assert allocator.all_source_ids() == ["S-001"]


def test_assert_unique_ids_passes_when_all_unique():
    assert_unique_ids(["A-001", "A-002", "A-003"], kind="A")


def test_assert_unique_ids_raises_on_duplicate():
    with pytest.raises(IdAllocationError, match="Duplicate"):
        assert_unique_ids(["A-001", "A-002", "A-001"], kind="A")


def test_assert_unique_ids_raises_on_malformed():
    with pytest.raises(IdAllocationError, match="Invalid"):
        assert_unique_ids(["A-001", "A-02"], kind="A")

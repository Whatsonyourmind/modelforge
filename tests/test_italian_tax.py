"""Tests for the Italian corporate-tax module (IRES / IRAP / SIIQ / PEX)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from modelforge.finance_core.italian_tax import (
    ITALIAN_TAX_RATES_2026,
    IRAPInputs,
    IRESInputs,
    PEXCheckInputs,
    SIIQCheckInputs,
    apply_pex_to_capital_gain,
    apply_siiq_regime,
    check_pex_eligibility,
    check_siiq_eligibility,
    combined_corporate_tax,
    compute_irap,
    compute_ires,
)


# ── IRES ────────────────────────────────────────────────────────────────


def test_ires_basic_2026_rate_is_24_pct():
    result = compute_ires(IRESInputs(pretax_income_eur=Decimal("1000000")))
    assert result.ires_tax_eur == Decimal("240000.00")
    assert result.effective_rate == Decimal("0.24")
    assert result.nol_consumed_eur == Decimal("0")


def test_ires_with_non_deductible_items_increases_base():
    result = compute_ires(
        IRESInputs(
            pretax_income_eur=Decimal("1000000"),
            non_deductible_items_eur=Decimal("200000"),
        )
    )
    # Base = 1.0M + 0.2M = 1.2M  → tax = 288k
    assert result.ires_base_eur == Decimal("1200000")
    assert result.ires_tax_eur == Decimal("288000.00")


def test_ires_nol_offset_capped_at_80_pct_of_base():
    result = compute_ires(
        IRESInputs(
            pretax_income_eur=Decimal("1000000"),
            carried_forward_nol_eur=Decimal("2000000"),  # huge NOL
        )
    )
    # 80% cap => NOL used = 0.8M, base = 0.2M, tax = 48k, NOL remaining = 1.2M
    assert result.nol_consumed_eur == Decimal("800000.00")
    assert result.ires_base_eur == Decimal("200000.00")
    assert result.ires_tax_eur == Decimal("48000.00")
    assert result.nol_remaining_eur == Decimal("1200000.00")


def test_ires_nol_smaller_than_cap_consumed_in_full():
    result = compute_ires(
        IRESInputs(
            pretax_income_eur=Decimal("1000000"),
            carried_forward_nol_eur=Decimal("300000"),
        )
    )
    # Cap = 800k, NOL = 300k → consume all 300k
    assert result.nol_consumed_eur == Decimal("300000")
    assert result.ires_base_eur == Decimal("700000")
    assert result.ires_tax_eur == Decimal("168000.00")
    assert result.nol_remaining_eur == Decimal("0")


def test_ires_negative_pretax_income_floors_base_at_zero():
    result = compute_ires(IRESInputs(pretax_income_eur=Decimal("-500000")))
    assert result.ires_base_eur == Decimal("0")
    assert result.ires_tax_eur == Decimal("0")


# ── IRAP ────────────────────────────────────────────────────────────────


def test_irap_basic_2026_rate_is_3_9_pct():
    result = compute_irap(
        IRAPInputs(
            production_value_eur=Decimal("5000000"),
            production_costs_eur=Decimal("3000000"),
            deductible_personnel_eur=Decimal("1500000"),
        )
    )
    # Base = 5.0 - 3.0 - 1.5 = 0.5M * 3.9% = 19,500
    assert result.irap_base_eur == Decimal("500000")
    assert result.irap_tax_eur == Decimal("19500.00")


def test_irap_financial_entity_rate_is_6_65_pct():
    result = compute_irap(
        IRAPInputs(
            production_value_eur=Decimal("5000000"),
            production_costs_eur=Decimal("2000000"),
            deductible_personnel_eur=Decimal("0"),
            is_financial_entity=True,
        )
    )
    # Base = 3.0M * 6.65% = 199,500
    assert result.irap_base_eur == Decimal("3000000")
    assert result.irap_tax_eur == Decimal("199500.00")


def test_irap_regional_surcharge_added_on_top_of_national():
    result = compute_irap(
        IRAPInputs(
            production_value_eur=Decimal("1000000"),
            production_costs_eur=Decimal("500000"),
            regional_surcharge_pct=Decimal("0.005"),  # +0.5pp
        )
    )
    # Rate = 3.9% + 0.5% = 4.4% on base 500k
    assert result.irap_tax_eur == Decimal("22000.00")


def test_irap_base_cannot_be_negative():
    result = compute_irap(
        IRAPInputs(
            production_value_eur=Decimal("1000000"),
            production_costs_eur=Decimal("1500000"),
        )
    )
    assert result.irap_base_eur == Decimal("0")
    assert result.irap_tax_eur == Decimal("0")


def test_irap_regional_surcharge_floor_at_zero():
    """Regional surcharge that goes negative (theoretical) cannot go below 0."""
    result = compute_irap(
        IRAPInputs(
            production_value_eur=Decimal("1000000"),
            production_costs_eur=Decimal("0"),
            regional_surcharge_pct=Decimal("-0.05"),  # absurdly negative
        )
    )
    # Effective rate floored at 0 → no tax.
    assert result.irap_tax_eur == Decimal("0")


# ── Combined ────────────────────────────────────────────────────────────


def test_combined_tax_sums_ires_and_irap():
    ires_inputs = IRESInputs(pretax_income_eur=Decimal("1000000"))
    irap_inputs = IRAPInputs(
        production_value_eur=Decimal("5000000"),
        production_costs_eur=Decimal("3000000"),
        deductible_personnel_eur=Decimal("1500000"),
    )
    combined = combined_corporate_tax(ires_inputs, irap_inputs)
    assert combined.ires.ires_tax_eur == Decimal("240000.00")
    assert combined.irap.irap_tax_eur == Decimal("19500.00")
    assert combined.total_tax_eur == Decimal("259500.00")
    # Blended effective rate = 259500 / 1000000 = 25.95%
    assert combined.blended_effective_rate == Decimal("0.25950")


# ── SIIQ ────────────────────────────────────────────────────────────────


def _siiq_happy() -> SIIQCheckInputs:
    return SIIQCheckInputs(
        is_italian_spa=True,
        is_listed_eu_regulated_market=True,
        rental_revenue_pct_of_total=Decimal("0.85"),
        largest_shareholder_pct=Decimal("0.35"),
        free_float_pct=Decimal("0.40"),
        distribution_pct_of_exempt_income=Decimal("0.90"),
    )


def test_siiq_eligible_when_all_criteria_met():
    result = check_siiq_eligibility(_siiq_happy())
    assert result.eligible is True
    assert result.failures == []


def test_siiq_warns_when_distribution_within_5pp_of_floor():
    facts = _siiq_happy()
    facts.distribution_pct_of_exempt_income = Decimal("0.86")
    result = check_siiq_eligibility(facts)
    assert result.eligible is True
    assert any("85% floor" in w for w in result.warnings)


def test_siiq_fails_when_not_italian_spa():
    facts = _siiq_happy()
    facts.is_italian_spa = False
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert any("S.p.A." in f for f in result.failures)


def test_siiq_fails_when_not_listed():
    facts = _siiq_happy()
    facts.is_listed_eu_regulated_market = False
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert any("listed" in f.lower() for f in result.failures)


def test_siiq_fails_when_rental_pct_below_80():
    facts = _siiq_happy()
    facts.rental_revenue_pct_of_total = Decimal("0.70")
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert any("Rental revenue" in f for f in result.failures)


def test_siiq_fails_when_largest_shareholder_exceeds_60_pct():
    facts = _siiq_happy()
    facts.largest_shareholder_pct = Decimal("0.65")
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert any("Largest shareholder" in f for f in result.failures)


def test_siiq_fails_when_free_float_below_25_pct():
    facts = _siiq_happy()
    facts.free_float_pct = Decimal("0.20")
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert any("Free float" in f for f in result.failures)


def test_siiq_fails_when_distribution_below_85_pct():
    facts = _siiq_happy()
    facts.distribution_pct_of_exempt_income = Decimal("0.75")
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert any("Distribution" in f for f in result.failures)


def test_siiq_multiple_failures_collected():
    facts = _siiq_happy()
    facts.is_italian_spa = False
    facts.rental_revenue_pct_of_total = Decimal("0.50")
    result = check_siiq_eligibility(facts)
    assert result.eligible is False
    assert len(result.failures) == 2


def test_apply_siiq_regime_exempts_rental_when_eligible():
    eligibility = check_siiq_eligibility(_siiq_happy())
    impact = apply_siiq_regime(
        rental_income_eur=Decimal("5000000"),
        non_core_taxable_income_eur=Decimal("500000"),
        eligibility=eligibility,
    )
    assert impact.rental_income_exempt_eur == Decimal("5000000")
    assert impact.rental_income_taxed_eur == Decimal("0")
    # Only non-core taxed
    assert impact.ordinary_tax_due_eur == Decimal("500000") * (
        Decimal("0.24") + Decimal("0.039")
    )


def test_apply_siiq_regime_falls_back_to_ordinary_when_ineligible():
    facts = _siiq_happy()
    facts.rental_revenue_pct_of_total = Decimal("0.50")
    eligibility = check_siiq_eligibility(facts)
    impact = apply_siiq_regime(
        rental_income_eur=Decimal("5000000"),
        non_core_taxable_income_eur=Decimal("500000"),
        eligibility=eligibility,
    )
    assert impact.rental_income_taxed_eur == Decimal("5000000")
    assert impact.rental_income_exempt_eur == Decimal("0")
    # Full 5.5M taxed at 27.9% blended
    expected = Decimal("5500000") * (Decimal("0.24") + Decimal("0.039"))
    assert impact.ordinary_tax_due_eur == expected


# ── PEX ────────────────────────────────────────────────────────────────


def _pex_happy() -> PEXCheckInputs:
    return PEXCheckInputs(
        holding_period_months=24,
        classified_as_financial_asset_since_first_fy=True,
        subsidiary_not_tax_haven_resident=True,
        subsidiary_exercises_commercial_activity=True,
    )


def test_pex_eligible_when_all_tests_pass():
    result = check_pex_eligibility(_pex_happy())
    assert result.eligible is True
    assert result.failures == []


def test_pex_fails_when_holding_short():
    facts = _pex_happy()
    facts.holding_period_months = 6
    result = check_pex_eligibility(facts)
    assert result.eligible is False
    assert any("Holding period" in f for f in result.failures)


def test_pex_fails_when_classified_as_current_asset():
    facts = _pex_happy()
    facts.classified_as_financial_asset_since_first_fy = False
    result = check_pex_eligibility(facts)
    assert result.eligible is False
    assert any("immobilizzazioni" in f for f in result.failures)


def test_pex_fails_when_subsidiary_in_tax_haven():
    facts = _pex_happy()
    facts.subsidiary_not_tax_haven_resident = False
    result = check_pex_eligibility(facts)
    assert result.eligible is False
    assert any("tax-haven" in f for f in result.failures)


def test_pex_fails_when_subsidiary_is_pure_holding():
    facts = _pex_happy()
    facts.subsidiary_exercises_commercial_activity = False
    result = check_pex_eligibility(facts)
    assert result.eligible is False
    assert any("commercial-activity" in f for f in result.failures)


def test_apply_pex_exempts_95_pct_when_eligible():
    eligibility = check_pex_eligibility(_pex_happy())
    impact = apply_pex_to_capital_gain(
        gross_capital_gain_eur=Decimal("10000000"),
        eligibility=eligibility,
    )
    # Exempt = 9.5M, taxable = 0.5M, tax = 0.5M * 24% = 120k
    assert impact.exempt_gain_eur == Decimal("9500000.00")
    assert impact.taxable_gain_eur == Decimal("500000.00")
    assert impact.ires_tax_on_gain_eur == Decimal("120000.00")
    # Effective 1.2% on gross
    assert impact.effective_rate_on_gain == Decimal("0.012")


def test_apply_pex_full_tax_when_ineligible():
    facts = _pex_happy()
    facts.holding_period_months = 6
    eligibility = check_pex_eligibility(facts)
    impact = apply_pex_to_capital_gain(
        gross_capital_gain_eur=Decimal("10000000"),
        eligibility=eligibility,
    )
    assert impact.exempt_gain_eur == Decimal("0")
    assert impact.taxable_gain_eur == Decimal("10000000")
    assert impact.ires_tax_on_gain_eur == Decimal("2400000.00")
    assert impact.effective_rate_on_gain == Decimal("0.24")


def test_apply_pex_with_capital_loss_returns_zero_tax():
    eligibility = check_pex_eligibility(_pex_happy())
    impact = apply_pex_to_capital_gain(
        gross_capital_gain_eur=Decimal("-1000000"),
        eligibility=eligibility,
    )
    assert impact.ires_tax_on_gain_eur == Decimal("0")
    assert impact.exempt_gain_eur == Decimal("0")


# ── Rates snapshot ─────────────────────────────────────────────────────


def test_rates_snapshot_matches_2026_italian_tax_code():
    rates = ITALIAN_TAX_RATES_2026
    assert rates.ires_rate == Decimal("0.24")
    assert rates.irap_rate_default == Decimal("0.039")
    assert rates.pex_exempt_pct == Decimal("0.95")
    assert rates.pex_min_holding_months == 12
    assert rates.siiq_min_distribution_pct == Decimal("0.85")
    assert rates.siiq_min_rental_pct == Decimal("0.80")
    assert rates.nol_offset_pct_cap == Decimal("0.80")


def test_rates_snapshot_is_frozen():
    """Consumer mutation attempt should raise — frozen dataclass."""
    with pytest.raises(Exception):  # FrozenInstanceError in stdlib
        ITALIAN_TAX_RATES_2026.ires_rate = Decimal("0.30")  # type: ignore[misc]

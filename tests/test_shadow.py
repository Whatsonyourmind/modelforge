"""Tests for modelforge.shadow — per-template exact primary_output engines."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from modelforge.shadow import compute_primary_output, has_shadow_engine
from modelforge.shadow._util import irr, npv

ROOT = Path(__file__).resolve().parent.parent


# ─── Basic coverage ──────────────────────────────────────────────────────────


def test_registry_covers_expected_templates():
    # v0.4.12: all 10 scalar-output templates must have shadow engines
    # (fairness is the only template without — football field is the output)
    expected = ("dcf", "unitranche", "credit_memo", "project_finance", "merger",
                "three_statement", "minibond", "real_estate", "npl",
                "structured_credit")
    for mt in expected:
        assert has_shadow_engine(mt), f"{mt} should have a shadow engine"


def test_fairness_has_no_shadow_engine():
    """Fairness is a valuation-range aggregator — no scalar primary output."""
    assert not has_shadow_engine("fairness")


def test_unknown_template_has_no_engine():
    assert not has_shadow_engine("this_does_not_exist")


def test_compute_returns_none_for_unknown_template():
    class FakeSpec:
        model_type = "this_does_not_exist"

        def all_assumptions(self):
            return []
    assert compute_primary_output(FakeSpec(), {}) is None


# ─── Numeric correctness — DCF (math most transparent) ───────────────────────


def _load(fname, cls_import):
    mod, name = cls_import
    SC = getattr(__import__(mod, fromlist=[name]), name)
    p = ROOT / "examples" / fname
    return SC.model_validate(yaml.safe_load(p.read_bytes()))


def test_dcf_enel_base_ev_reasonable():
    spec = _load("dcf_enel.yaml", ("modelforge.spec.dcf", "DCFSpec"))
    ev = compute_primary_output(spec, {})
    # Enel illustrative: EV should be in the €100B-€300B range
    assert 100_000 < ev < 300_000


def test_dcf_shocks_move_ev_in_right_direction():
    spec = _load("dcf_enel.yaml", ("modelforge.spec.dcf", "DCFSpec"))
    base = compute_primary_output(spec, {})
    # Higher beta → higher WACC → lower EV
    higher_beta = compute_primary_output(spec, {"beta_levered": 1.10})
    lower_beta = compute_primary_output(spec, {"beta_levered": 0.60})
    assert higher_beta < base < lower_beta
    # Higher exit multiple → higher EV
    higher_mult = compute_primary_output(spec, {"exit_ev_ebitda_x": 9.0})
    assert higher_mult > base


def test_dcf_capex_is_inverse():
    spec = _load("dcf_enel.yaml", ("modelforge.spec.dcf", "DCFSpec"))
    base = compute_primary_output(spec, {})
    # Higher capex → lower FCF → lower EV
    higher_capex = compute_primary_output(spec, {"capex_pct_revenue": 0.15})
    assert higher_capex < base


# ─── Unitranche lender IRR ───────────────────────────────────────────────────


def test_unitranche_irr_matches_expected_range():
    spec = _load("unitranche_cdmo.yaml",
                 ("modelforge.spec.unitranche", "UnitrancheSpec"))
    r = compute_primary_output(spec, {})
    # CDMO unitranche: EURIBOR ~3.8% + ~550bps margin + arrangement fee
    # Should produce ~8-11% blended IRR
    assert 0.07 < r < 0.12


def test_unitranche_margin_shock_lifts_irr():
    spec = _load("unitranche_cdmo.yaml",
                 ("modelforge.spec.unitranche", "UnitrancheSpec"))
    base = compute_primary_output(spec, {})
    # Find the margin driver base value and shock it +50%
    margin_base = None
    for a in spec.all_assumptions():
        if a.name == "senior_unitranche_margin_bps":
            margin_base = a.base
            break
    assert margin_base is not None
    shocked = compute_primary_output(
        spec, {"senior_unitranche_margin_bps": margin_base * 1.5}
    )
    assert shocked > base  # higher margin → higher lender IRR


# ─── Project Finance equity IRR ──────────────────────────────────────────────


def test_pf_irr_in_reasonable_range():
    spec = _load("project_finance_solar.yaml",
                 ("modelforge.spec.project_finance", "ProjectFinanceSpec"))
    r = compute_primary_output(spec, {})
    # Italian solar FER X equity IRR typically 4-12%
    assert 0.0 < r < 0.15


def test_pf_revenue_shock_lifts_equity_irr():
    spec = _load("project_finance_solar.yaml",
                 ("modelforge.spec.project_finance", "ProjectFinanceSpec"))
    base = compute_primary_output(spec, {})
    rev_base = next(a.base for a in spec.all_assumptions() if a.name == "revenue_yr1")
    higher = compute_primary_output(spec, {"revenue_yr1": rev_base * 1.15})
    assert higher > base


# ─── Merger accretion/dilution ───────────────────────────────────────────────


def test_merger_synergies_drive_accretion():
    spec = _load("merger_tim_iliad.yaml",
                 ("modelforge.spec.merger", "MergerSpec"))
    base = compute_primary_output(spec, {})
    # More cost synergies → higher accretion %
    cost_base = next(a.base for a in spec.all_assumptions()
                     if a.name == "cost_synergies_eur_m")
    higher = compute_primary_output(
        spec, {"cost_synergies_eur_m": cost_base * 1.5}
    )
    assert higher > base


def test_merger_higher_premium_drives_dilution():
    spec = _load("merger_tim_iliad.yaml",
                 ("modelforge.spec.merger", "MergerSpec"))
    base = compute_primary_output(spec, {})
    premium_base = next(a.base for a in spec.all_assumptions()
                        if a.name == "offer_premium_pct")
    # Much higher premium → more cash financing → more interest → dilution
    higher_premium = compute_primary_output(
        spec, {"offer_premium_pct": premium_base * 1.6}
    )
    assert higher_premium < base


# ─── Utility math ────────────────────────────────────────────────────────────


def test_irr_textbook_case():
    # Classic textbook: -100 at t=0, +10 for 10 years → ~0% IRR
    # (sums to zero; IRR is zero)
    cf = [-100] + [10] * 10
    r = irr(cf, guess=0.0)
    assert abs(r) < 0.001


def test_irr_positive_yield():
    # -100 at t=0, +120 at t=1 → 20% IRR
    r = irr([-100, 120])
    assert abs(r - 0.20) < 1e-4


def test_npv_at_zero_rate_is_sum():
    cf = [-100, 50, 50, 50]
    assert abs(npv(0.0, cf) - sum(cf)) < 1e-9


# ─── New v0.4.12 shadow engines ──────────────────────────────────────────────


def test_three_statement_ni_y1_reasonable():
    spec = _load("three_statement_cdmo.yaml",
                 ("modelforge.spec.three_statement", "ThreeStatementSpec"))
    ni = compute_primary_output(spec, {})
    # CDMO illustrative: positive NI in reasonable €m range
    assert -50 < ni < 200


def test_three_statement_ebitda_margin_shock_lifts_ni():
    spec = _load("three_statement_cdmo.yaml",
                 ("modelforge.spec.three_statement", "ThreeStatementSpec"))
    base = compute_primary_output(spec, {})
    m_base = next(a.base for a in spec.all_assumptions()
                  if a.name == "ebitda_margin_y1")
    higher = compute_primary_output(spec, {"ebitda_margin_y1": m_base * 1.20})
    assert higher > base


def test_minibond_net_ytm_matches_expected_range():
    spec = _load("minibond_logistics.yaml",
                 ("modelforge.spec.minibond", "MinibondSpec"))
    ytm = compute_primary_output(spec, {})
    # After 26% Italian WHT on a ~6.5% coupon minus 1.5% upfront fee
    # → ~3.5-5.5% net YTM
    assert 0.02 < ytm < 0.07


def test_minibond_withholding_shock_reduces_ytm():
    spec = _load("minibond_logistics.yaml",
                 ("modelforge.spec.minibond", "MinibondSpec"))
    base = compute_primary_output(spec, {})
    wht_base = next(a.base for a in spec.all_assumptions()
                    if a.name == "withholding_tax_pct")
    higher_wht = compute_primary_output(
        spec, {"withholding_tax_pct": wht_base * 1.50}
    )
    assert higher_wht < base


def test_real_estate_irr_reasonable():
    spec = _load("real_estate_pbsa.yaml",
                 ("modelforge.spec.real_estate", "RealEstateSpec"))
    irr = compute_primary_output(spec, {})
    # Milan PBSA unlevered returns 5-10%; levered equity IRR 10-18%
    assert 0.05 < irr < 0.25


def test_real_estate_cap_rate_shock_inverse():
    spec = _load("real_estate_pbsa.yaml",
                 ("modelforge.spec.real_estate", "RealEstateSpec"))
    base = compute_primary_output(spec, {})
    cap_base = next(a.base for a in spec.all_assumptions()
                    if a.name == "exit_cap_rate")
    higher_cap = compute_primary_output(spec, {"exit_cap_rate": cap_base * 1.20})
    # Higher exit cap → lower exit value → lower equity IRR
    assert higher_cap < base


def test_npl_irr_reasonable():
    spec = _load("npl_mixed_portfolio.yaml",
                 ("modelforge.spec.npl", "NPLSpec"))
    irr = compute_primary_output(spec, {})
    # Italian NPL mixed equity IRR targets 15-30% (risk-adjusted)
    assert 0.05 < irr < 0.50


def test_npl_higher_purchase_price_reduces_irr():
    spec = _load("npl_mixed_portfolio.yaml",
                 ("modelforge.spec.npl", "NPLSpec"))
    base = compute_primary_output(spec, {})
    pp_base = next(a.base for a in spec.all_assumptions()
                   if a.name == "purchase_price_pct_gbv")
    # Paying more → lower IRR
    higher = compute_primary_output(spec, {"purchase_price_pct_gbv": pp_base * 1.25})
    assert higher < base


def test_structured_credit_senior_irr_near_coupon():
    spec = _load("structured_credit_pmi.yaml",
                 ("modelforge.spec.structured_credit", "StructuredCreditSpec"))
    irr = compute_primary_output(spec, {})
    # Well-structured senior with subordination protection → IRR ≈ coupon
    coupon = next(a.base for a in spec.all_assumptions()
                  if a.name == "senior_coupon")
    assert abs(irr - coupon) < 0.02  # within 200bps

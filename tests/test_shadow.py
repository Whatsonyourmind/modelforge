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
    # These five must have shadow engines in v0.4.x
    for mt in ("dcf", "unitranche", "credit_memo", "project_finance", "merger"):
        assert has_shadow_engine(mt), f"{mt} should have a shadow engine"


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

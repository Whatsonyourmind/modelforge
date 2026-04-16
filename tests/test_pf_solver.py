"""Tests for PF sculpted-amort + DSCR-target solver (v0.3)."""

from __future__ import annotations

import math

import pytest

from modelforge.builder.pf_solver import (
    level_debt_service_constant,
    level_debt_service_pct_schedule,
    level_debt_service_per_year,
    solve_dscr_target_debt,
)


# ──────────────────────────────────────────────────────────────────
# 1. Annuity math agrees with Excel PMT() to 4 decimals
# ──────────────────────────────────────────────────────────────────
def test_annuity_constant_matches_excel_pmt():
    """PMT(5%, 10, -100) in Excel returns 12.9504..."""
    P, rate, n = 100.0, 0.05, 10
    c = level_debt_service_constant(P, rate, n)
    assert c == pytest.approx(12.9504574, abs=1e-4)


def test_annuity_constant_zero_rate():
    """At 0% rate, annuity = P / n."""
    c = level_debt_service_constant(100.0, 0.0, 10)
    assert c == pytest.approx(10.0, abs=1e-9)


def test_pct_schedule_sums_to_one():
    """Principal pcts across amort years should sum to exactly 1.0."""
    schedule = level_debt_service_pct_schedule(
        rate=0.05, amort_years=10, grace_years=2, operating_years=15,
    )
    assert sum(schedule) == pytest.approx(1.0, abs=1e-9)
    # First 2 entries (grace) are zero
    assert schedule[0] == 0.0
    assert schedule[1] == 0.0
    # Amort years 2-11 are non-zero
    for i in range(2, 12):
        assert schedule[i] > 0
    # Post-amort years are zero
    for i in range(12, 15):
        assert schedule[i] == 0.0


def test_pct_schedule_principal_grows():
    """Under level-debt-service, principal portion rises each period as
    interest portion falls."""
    schedule = level_debt_service_pct_schedule(
        rate=0.05, amort_years=10, grace_years=0, operating_years=10,
    )
    for i in range(len(schedule) - 1):
        assert schedule[i + 1] > schedule[i], f"year {i+1} principal not > year {i}"


# ──────────────────────────────────────────────────────────────────
# 2. DSCR solver convergence on synthetic CFADS
# ──────────────────────────────────────────────────────────────────
def test_dscr_solver_converges_on_flat_cfads():
    """Flat CFADS of 20, target 1.5, rate 5%, 10y amort, 2y grace.
    Expected: min DSCR == 1.5 at converged P."""
    cfads = [20.0] * 12
    solved = solve_dscr_target_debt(
        cfads=cfads, rate=0.05, amort_years=10, grace_years=2,
        target_dscr=1.5, cap=500.0, tol=1e-4,
    )
    # Verify resulting min DSCR is very close to 1.5
    ds = level_debt_service_per_year(solved, 0.05, 10, 2, 12)
    dscrs = [cfads[t] / ds[t] for t in range(12) if ds[t] > 0]
    min_dscr = min(dscrs)
    assert min_dscr == pytest.approx(1.5, abs=0.01)


def test_dscr_solver_respects_cap():
    """If the cap already clears target comfortably, solver returns cap."""
    cfads = [100.0] * 12
    cap = 50.0
    solved = solve_dscr_target_debt(
        cfads=cfads, rate=0.05, amort_years=10, grace_years=2,
        target_dscr=1.2, cap=cap,
    )
    # At P=50, min DSCR >> 1.2 → solver should stop at cap
    assert solved == pytest.approx(cap, abs=0.01)


def test_dscr_solver_zero_cap():
    """cap = 0 → returns 0."""
    solved = solve_dscr_target_debt(
        cfads=[10.0] * 12, rate=0.05, amort_years=10, grace_years=2,
        target_dscr=1.5, cap=0.0,
    )
    assert solved == 0.0


def test_dscr_solver_low_cfads():
    """CFADS too low to support any debt at target → solver returns near 0."""
    solved = solve_dscr_target_debt(
        cfads=[0.01] * 12, rate=0.05, amort_years=10, grace_years=2,
        target_dscr=2.0, cap=500.0,
    )
    assert solved < 0.5  # essentially zero


# ──────────────────────────────────────────────────────────────────
# 3. per_year debt service shape
# ──────────────────────────────────────────────────────────────────
def test_level_debt_service_per_year_shape():
    """Grace years: interest only. Amort years: annuity constant. Post-amort: 0."""
    P, rate = 100.0, 0.05
    ds = level_debt_service_per_year(P, rate, amort_years=10, grace_years=2, operating_years=15)
    # Grace years: interest only = P * rate = 5.0
    assert ds[0] == pytest.approx(5.0, abs=1e-9)
    assert ds[1] == pytest.approx(5.0, abs=1e-9)
    # Amort years (2..11): constant annuity
    c = level_debt_service_constant(P, rate, 10)
    for i in range(2, 12):
        assert ds[i] == pytest.approx(c, abs=1e-9)
    # Post-amort years (12..14): zero
    for i in range(12, 15):
        assert ds[i] == 0.0


# ──────────────────────────────────────────────────────────────────
# 4. Back-compat: default PF spec still builds (v0.2 behaviour)
# ──────────────────────────────────────────────────────────────────
def test_pf_spec_backcompat_defaults():
    """A PF YAML without any v0.3 fields still parses with v0.2 defaults."""
    from modelforge.spec.project_finance import ProjectFinanceSpec
    import yaml
    with open("examples/minibond_logistics.yaml") as _:  # existence check
        pass
    # Load a PF YAML — they all have v0.3 fields now, so build a minimal
    # inline spec dict instead.
    spec_dict = {
        "model_type": "project_finance",
        "meta": {
            "project_code": "TEST-PF",
            "deliverable": {"en": "t", "it": "t"},
            "analyst": "t",
            "valuation_date": "2026-01-01",
            "revision_log": [],
        },
        "target": {
            "name": "t",
            "sector": {"en": "t", "it": "t"},
            "revenue_last_fy_eur_m": 0,
            "revenue_source_id": "S-001",
            "ebitda_last_fy_eur_m": 0,
            "ebitda_source_id": "S-001",
            "last_fy_end": "2025-12-31",
        },
        "horizon": {"construction_years": 1, "operating_years": 10},
        "sources": [{"id": "S-001", "doc": "t", "publisher": "t", "date": "2026-01-01"}],
        "construction": {
            "total_capex_eur_m": {"id": "A-001", "name": "tc", "label": {"en": "t", "it": "t"}, "base": 10.0, "rationale": "t"},
            "capex_phasing_pct": [
                {"id": "A-002", "name": "ph1", "label": {"en": "t", "it": "t"}, "base": 1.0, "rationale": "t", "unit": "pct"},
            ],
            "commitment_fee_bps": {"id": "A-003", "name": "cf", "label": {"en": "t", "it": "t"}, "base": 75, "rationale": "t", "unit": "bps"},
        },
        "operating": {
            "availability_payment_eur_m_yr1": {"id": "A-010", "name": "r", "label": {"en": "t", "it": "t"}, "base": 2.0, "rationale": "t"},
            "revenue_indexation_pct": {"id": "A-011", "name": "ri", "label": {"en": "t", "it": "t"}, "base": 0.02, "rationale": "t", "unit": "pct"},
            "opex_pct_revenue": {"id": "A-012", "name": "op", "label": {"en": "t", "it": "t"}, "base": 0.2, "rationale": "t", "unit": "pct"},
            "opex_indexation_pct": {"id": "A-013", "name": "oi", "label": {"en": "t", "it": "t"}, "base": 0.02, "rationale": "t", "unit": "pct"},
            "maintenance_reserve_pct_revenue": {"id": "A-014", "name": "mm", "label": {"en": "t", "it": "t"}, "base": 0.01, "rationale": "t", "unit": "pct"},
        },
        "debt": {
            "name": {"en": "s", "it": "s"},
            "amount": {"id": "A-020", "name": "sa", "label": {"en": "t", "it": "t"}, "base": 5.0, "rationale": "t"},
            "tenor_operating_years": 8,
            "grace_years": 1,
            "reference_rate": {"id": "A-021", "name": "rr", "label": {"en": "t", "it": "t"}, "base": 0.03, "rationale": "t", "unit": "pct"},
            "margin_bps": {"id": "A-022", "name": "mb", "label": {"en": "t", "it": "t"}, "base": 200, "rationale": "t", "unit": "bps"},
            "arrangement_fee_pct": {"id": "A-023", "name": "ap", "label": {"en": "t", "it": "t"}, "base": 0.01, "rationale": "t", "unit": "pct"},
        },
        "covenant": {
            "threshold_by_year": [
                {"id": f"A-{30+i:03d}", "name": f"d{i}", "label": {"en": "t", "it": "t"}, "base": 1.25, "rationale": "t", "unit": "x"}
                for i in range(10)
            ],
            "lock_up_threshold": {"id": "A-060", "name": "lu", "label": {"en": "t", "it": "t"}, "base": 1.15, "rationale": "t", "unit": "x"},
        },
        "equity": {
            "target_irr": {"id": "A-070", "name": "ti", "label": {"en": "t", "it": "t"}, "base": 0.1, "rationale": "t", "unit": "pct"},
            "effective_tax_rate": {"id": "A-071", "name": "etr", "label": {"en": "t", "it": "t"}, "base": 0.28, "rationale": "t", "unit": "pct"},
        },
    }
    spec = ProjectFinanceSpec(**spec_dict)
    assert spec.debt.amortization_profile == "linear"
    assert spec.debt.debt_sizing_mode == "fixed_amount"
    assert spec.debt.dsra_months == 6
    assert spec.debt.target_dscr_base is None


def test_pf_spec_dscr_target_requires_target():
    """debt_sizing_mode=dscr_target without target_dscr_base → ValidationError."""
    from pydantic import ValidationError
    from modelforge.spec.project_finance import ProjectFinanceSpec
    spec_dict = {
        "model_type": "project_finance",
        "meta": {"project_code": "T", "deliverable": {"en": "t", "it": "t"}, "analyst": "t", "valuation_date": "2026-01-01", "revision_log": []},
        "target": {"name": "t", "sector": {"en": "t", "it": "t"}, "revenue_last_fy_eur_m": 0, "revenue_source_id": "S-001", "ebitda_last_fy_eur_m": 0, "ebitda_source_id": "S-001", "last_fy_end": "2025-12-31"},
        "horizon": {"construction_years": 1, "operating_years": 10},
        "sources": [{"id": "S-001", "doc": "t", "publisher": "t", "date": "2026-01-01"}],
        "construction": {
            "total_capex_eur_m": {"id": "A-001", "name": "tc", "label": {"en": "t", "it": "t"}, "base": 10.0, "rationale": "t"},
            "capex_phasing_pct": [{"id": "A-002", "name": "ph1", "label": {"en": "t", "it": "t"}, "base": 1.0, "rationale": "t", "unit": "pct"}],
            "commitment_fee_bps": {"id": "A-003", "name": "cf", "label": {"en": "t", "it": "t"}, "base": 75, "rationale": "t", "unit": "bps"},
        },
        "operating": {
            "availability_payment_eur_m_yr1": {"id": "A-010", "name": "r", "label": {"en": "t", "it": "t"}, "base": 2.0, "rationale": "t"},
            "revenue_indexation_pct": {"id": "A-011", "name": "ri", "label": {"en": "t", "it": "t"}, "base": 0.02, "rationale": "t", "unit": "pct"},
            "opex_pct_revenue": {"id": "A-012", "name": "op", "label": {"en": "t", "it": "t"}, "base": 0.2, "rationale": "t", "unit": "pct"},
            "opex_indexation_pct": {"id": "A-013", "name": "oi", "label": {"en": "t", "it": "t"}, "base": 0.02, "rationale": "t", "unit": "pct"},
            "maintenance_reserve_pct_revenue": {"id": "A-014", "name": "mm", "label": {"en": "t", "it": "t"}, "base": 0.01, "rationale": "t", "unit": "pct"},
        },
        "debt": {
            "name": {"en": "s", "it": "s"},
            "amount": {"id": "A-020", "name": "sa", "label": {"en": "t", "it": "t"}, "base": 5.0, "rationale": "t"},
            "tenor_operating_years": 8, "grace_years": 1,
            "reference_rate": {"id": "A-021", "name": "rr", "label": {"en": "t", "it": "t"}, "base": 0.03, "rationale": "t", "unit": "pct"},
            "margin_bps": {"id": "A-022", "name": "mb", "label": {"en": "t", "it": "t"}, "base": 200, "rationale": "t", "unit": "bps"},
            "arrangement_fee_pct": {"id": "A-023", "name": "ap", "label": {"en": "t", "it": "t"}, "base": 0.01, "rationale": "t", "unit": "pct"},
            "debt_sizing_mode": "dscr_target",  # but target_dscr_base missing!
        },
        "covenant": {
            "threshold_by_year": [{"id": f"A-{30+i:03d}", "name": f"d{i}", "label": {"en": "t", "it": "t"}, "base": 1.25, "rationale": "t", "unit": "x"} for i in range(10)],
            "lock_up_threshold": {"id": "A-060", "name": "lu", "label": {"en": "t", "it": "t"}, "base": 1.15, "rationale": "t", "unit": "x"},
        },
        "equity": {
            "target_irr": {"id": "A-070", "name": "ti", "label": {"en": "t", "it": "t"}, "base": 0.1, "rationale": "t", "unit": "pct"},
            "effective_tax_rate": {"id": "A-071", "name": "etr", "label": {"en": "t", "it": "t"}, "base": 0.28, "rationale": "t", "unit": "pct"},
        },
    }
    with pytest.raises(ValidationError, match="target_dscr_base"):
        ProjectFinanceSpec(**spec_dict)


def test_solver_terminates_within_iter_cap():
    """Solver must not hang. Pathological inputs should still return in ≤ max_iter."""
    import time
    start = time.perf_counter()
    solved = solve_dscr_target_debt(
        cfads=[50.0] * 20, rate=0.055, amort_years=17, grace_years=1,
        target_dscr=1.30, cap=1000.0, max_iter=50,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"solver took {elapsed:.3f}s, expected < 100ms"
    assert solved > 0

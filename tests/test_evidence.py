"""Evidence-binding gate (tier 1).

The regression that motivated it: the shipped Enfinity spec filed the €316M
*financing package* as `total_capex_eur_m` with confidence H, and fifteen
gates (QC, Trust, Moat) passed it. These tests pin that the gate blocks that
binding, and exercise every deterministic check against the synthetic
Enfinity data room in tests/fixtures/dataroom_enfinity_synth/.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from modelforge.cli import _load_spec_class, main
from modelforge.evidence import Verdict, parse_overrides, run_gate
from modelforge.evidence.corpus import Corpus
from modelforge.evidence.derive import ExprError, evaluate, rationale_arithmetic
from modelforge.evidence.gate import LeafResult, _value_in_quote
from modelforge.evidence.numbers import find_mentions, normalize_text, to_field_unit
from modelforge.evidence.roles import conflicts, field_role

ROOT = Path(__file__).resolve().parents[1]
ENFINITY = ROOT / "examples" / "real_enfinity_solar_pf.yaml"
DATAROOM = ROOT / "tests" / "fixtures" / "dataroom_enfinity_synth"

# The leaf exactly as it shipped before the gate existed.
DEFECTIVE_CAPEX = {
    "id": "A-001", "name": "total_capex",
    "label": {"en": "Total project capex", "it": "Capex progetto totale"},
    "unit": "eur_m", "base": 316.0,
    "rationale": "Total Enfinity financing package €316M (incl. VAT + PPA + decommissioning facilities).",
    "confidence": "H", "source_id": "S-001",
}


def _raw() -> dict:
    return yaml.safe_load(ENFINITY.read_bytes())


def _spec(raw: dict):
    return _load_spec_class(raw["model_type"]).model_validate(raw)


def _leaf(result, aid):
    return next(lf for lf in result.leaves if lf.id == aid)


def _dataroom_raw() -> dict:
    """Enfinity spec with its sources repointed at the synthetic data room."""
    raw = _raw()
    docs = {
        "S-001": "01_enfinity_press_release.pdf",
        "S-002": "02_enfinity_IM_extract.pdf",
        "S-003": "03_terna_irradiation_report_2025.pdf",
        "S-004": "04_gse_fer_x_results.pdf",
        "S-005": "05_ecb_euro_swap_10y.pdf",
        "S-006": "07_senior_green_loan_term_sheet.pdf",
        "S-008": "06_pwc_italy_tax.pdf",
    }
    for s in raw["sources"]:
        if s["id"] in docs:
            s["doc"] = docs[s["id"]]
            s["page"] = 1
    return raw


@pytest.fixture(scope="module")
def corpus():
    pytest.importorskip("pdfplumber")  # the `test` extra; PDFs read as empty without it
    return Corpus.load(DATAROOM)


# ─────────────────────────────────────────────────────────────────────────────
# Building blocks
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,unit,expected", [
    ("EUR 316 million financing package", "eur_m", 316.0),
    ("Facility amount: EUR 214,000,000.", "eur_m", 214.0),
    ("€316M (incl. VAT", "eur_m", 316.0),
    ("Arrangement fee: 1.25% of facility amount", "pct", 0.0125),
    ("EUR Swap 10Y + 175 bps margin", "bps", 175.0),
    ("totaling 27.9 percent", "pct", 0.279),
    ("DSCR minimum 1.20x year 1", "x", 1.20),
])
def test_number_normalisation(text, unit, expected):
    vals = [to_field_unit(m, unit) for m in find_mentions(normalize_text(text))]
    assert any(v is not None and abs(v - expected) < 1e-9 for v in vals), vals


def test_physical_quantities_are_not_money():
    vals = [to_field_unit(m, "eur_m") for m in find_mentions(normalize_text("276 MW of solar"))]
    assert vals == [None]


def test_field_roles():
    assert field_role("Total project capex", "total_capex", "total_capex_eur_m") == "capex"
    assert field_role("Senior debt amount (cap)", "senior_amount", "amount") == "debt_amount"
    assert field_role("Commitment fee (bps)", "commitment_fee_bps") == "commitment_fee"
    assert field_role("Senior margin (bps)", "senior_margin_bps") == "margin"
    assert field_role("Lock-up something", "foo_bar") is None


def test_conflicts_only_within_a_family():
    assert conflicts("capex", "financing_package")
    assert conflicts("enterprise_value", "equity_value")
    assert not conflicts("capex", "margin")
    assert not conflicts("capex", "capex")


def test_rationale_arithmetic():
    ok = rationale_arithmetic("276 MW × 1,550 kWh/kWp/yr × €75/MWh = €32.1M/yr")[0]
    assert ok.consistent and abs(ok.scaled_to(32.1) - 32.085) < 1e-9
    assert rationale_arithmetic("IRES 24.0% + IRAP 3.9% = 27.9%")[0].consistent
    assert not rationale_arithmetic("276 × 1,550 × 70 = €32.1M")[0].consistent


def test_expr_is_not_eval():
    assert evaluate("a * b / 1e6", {"a": 276, "b": 1550}) == pytest.approx(0.4278)
    for bad in ("__import__('os').system('x')", "a.real", "[a]", "a if a else b"):
        with pytest.raises(ExprError):
            evaluate(bad, {"a": 1.0, "b": 2.0})


def test_unit_mismatch_is_told_apart_from_absence():
    leaf = LeafResult(id="A-999", name="x", path="x", value=0.75, unit="pct",
                      claim="fact", declared=True, source_id="S-001", field_role=None)
    assert not _value_in_quote(leaf, normalize_text("Commitment fee: 75 bps p.a."), allow_range=False)
    assert leaf.checks[-1].name == "unit_consistent"
    assert "basis points" in leaf.reasons[-1]


# ─────────────────────────────────────────────────────────────────────────────
# The Enfinity regression (no data room needed)
# ─────────────────────────────────────────────────────────────────────────────

def test_shipped_defect_is_broken():
    raw = _raw()
    raw["construction"]["total_capex_eur_m"] = copy.deepcopy(DEFECTIVE_CAPEX)
    result = run_gate(_spec(raw))
    leaf = _leaf(result, "A-001")
    assert leaf.verdict == Verdict.BROKEN
    assert "financing package" in leaf.reasons[0] and "capex" in leaf.reasons[0]
    assert not result.passed


def test_fixed_example_passes_default_but_not_strict():
    result = run_gate(_spec(_raw()))
    assert result.passed
    assert _leaf(result, "A-001").verdict == Verdict.ASSUMPTION
    assert _leaf(result, "A-010").verdict == Verdict.UNVERIFIED  # derived; inputs lack quotes
    assert not run_gate(_spec(_raw()), strict=True).passed


def test_undeclared_derivation_is_named():
    raw = _raw()
    raw["operating"]["availability_payment_eur_m_yr1"].pop("evidence")
    leaf = _leaf(run_gate(_spec(raw)), "A-010")
    assert leaf.verdict == Verdict.UNVERIFIED
    assert any("derived in the rationale" in r for r in leaf.reasons)


def test_every_shipped_example_passes_default_gate():
    """Zero false positives on the shipped corpus (the gate must not cry wolf)."""
    for p in sorted((ROOT / "examples").glob("*.yaml")):
        raw = yaml.safe_load(p.read_bytes())
        spec = _load_spec_class(raw.get("model_type", "unitranche")).model_validate(raw)
        result = run_gate(spec)
        assert result.passed, (p.name, [(lf.id, lf.reasons) for lf in result.blocking])


# ─────────────────────────────────────────────────────────────────────────────
# Against the synthetic data room
# ─────────────────────────────────────────────────────────────────────────────

def _with_evidence(raw, path, ev, **leaf_updates):
    node = raw
    *parents, last = path
    for k in parents:
        node = node[k]
    node[last] = {**node[last], **leaf_updates, "evidence": ev}
    return raw


def test_bound_fact(corpus):
    raw = _with_evidence(_dataroom_raw(), ["debt", "amount"], {
        "kind": "fact", "source_id": "S-006", "page": 1,
        "quote": "Facility amount: EUR 214,000,000."})
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-020")
    assert leaf.verdict == Verdict.BOUND, leaf.reasons


def test_contradiction_between_documents_is_contested(corpus):
    # The IM calls 316 "project capex"; the press release calls the same 316 a
    # financing package that includes €101M of non-capex facilities.
    raw = _with_evidence(_dataroom_raw(), ["construction", "total_capex_eur_m"], {
        "kind": "fact", "source_id": "S-002",
        "quote": "Total project capex of EUR 316 million is phased 35 percent in Year 1"},
        source_id="S-002", confidence="H")
    result = run_gate(_spec(raw), corpus=corpus)
    leaf = _leaf(result, "A-001")
    assert leaf.verdict == Verdict.CONTESTED, leaf.reasons
    assert any("01_enfinity_press_release.pdf" in r and "financing package" in r for r in leaf.reasons)
    assert not result.passed


def test_quote_naming_another_quantity_is_broken(corpus):
    raw = _with_evidence(_dataroom_raw(), ["construction", "total_capex_eur_m"], {
        "kind": "fact", "source_id": "S-001",
        "quote": "the closing of a EUR 316 million financing package for 276 MW"},
        source_id="S-001")
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-001")
    assert leaf.verdict == Verdict.BROKEN
    assert any(c.name == "role_quote" and c.ok is False for c in leaf.checks)


def test_invented_quote_is_broken(corpus):
    raw = _with_evidence(_dataroom_raw(), ["debt", "margin_bps"], {
        "kind": "fact", "source_id": "S-006", "quote": "The senior margin is 175 bps."})
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-022")
    assert leaf.verdict == Verdict.BROKEN
    assert any(c.name == "quote_present" and c.ok is False for c in leaf.checks)


def test_value_missing_from_quote_is_broken(corpus):
    raw = _with_evidence(_dataroom_raw(), ["debt", "reference_rate"], {
        "kind": "fact", "source_id": "S-006",
        "quote": "Arrangement fee: 1.25% of facility amount, payable upfront."})
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-021")
    assert leaf.verdict == Verdict.BROKEN
    assert any(c.name == "value_in_quote" and c.ok is False for c in leaf.checks)


def test_wrong_page_is_broken(corpus):
    raw = _with_evidence(_dataroom_raw(), ["debt", "amount"], {
        "kind": "fact", "source_id": "S-006", "page": 2,
        "quote": "Facility amount: EUR 214,000,000."})
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-020")
    assert leaf.verdict == Verdict.BROKEN and "page 1" in leaf.reasons[0]


def test_benchmark_value_inside_quoted_range(corpus):
    raw = _with_evidence(_dataroom_raw(), ["operating", "opex_pct_revenue"], {
        "kind": "benchmark", "source_id": "S-002", "peer_set": "Sponsor IM, Italian utility-scale solar",
        "quote": "O&M, land lease, insurance and grid fees aggregate to approximately 22 percent of revenue"})
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-012")
    assert leaf.verdict == Verdict.BOUND, leaf.reasons


def _derived(price_value: float, with_quotes: bool = True) -> dict:
    def t(v, s, q):
        return {"value": v, "source_id": s, **({"quote": q} if with_quotes else {})}

    return {"kind": "derived", "expr": "capacity_mw * yield_kwh_per_kwp * price_eur_per_mwh / 1e6",
            "terms": {
                "capacity_mw": t(276, "S-001", "EUR 316 million financing package for 276 MW of utility-scale solar"),
                "yield_kwh_per_kwp": t(1550, "S-003", "Blended national average for utility-scale assets across southern and central Italy is 1,550 kWh/kWp/year."),
                "price_eur_per_mwh": t(price_value, "S-004", "the blended effective revenue per MWh for solar portfolios structured with a 60/40 FER X / merchant mix is approximately EUR 75/MWh"),
            }}


def test_derived_recomputes_and_binds_inputs(corpus):
    raw = _with_evidence(_dataroom_raw(), ["operating", "availability_payment_eur_m_yr1"], _derived(75))
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-010")
    assert leaf.verdict == Verdict.DERIVED, leaf.reasons


def test_derived_arithmetic_mismatch_is_broken(corpus):
    raw = _with_evidence(_dataroom_raw(), ["operating", "availability_payment_eur_m_yr1"], _derived(70))
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-010")
    assert leaf.verdict == Verdict.BROKEN
    assert any(c.name == "derived_recompute" and c.ok is False for c in leaf.checks)


def test_derived_input_with_invented_quote_is_broken_and_says_why(corpus):
    ev = _derived(75)
    ev["terms"]["price_eur_per_mwh"]["quote"] = "The blended tariff is EUR 75/MWh."
    raw = _with_evidence(_dataroom_raw(), ["operating", "availability_payment_eur_m_yr1"], ev)
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-010")
    assert leaf.verdict == Verdict.BROKEN
    assert any("quote not found in 04_gse_fer_x_results.pdf" in r for r in leaf.reasons)


def test_derived_inputs_unverified_without_dataroom():
    raw = _with_evidence(_dataroom_raw(), ["operating", "availability_payment_eur_m_yr1"], _derived(75))
    leaf = _leaf(run_gate(_spec(raw)), "A-010")
    assert leaf.verdict == Verdict.UNVERIFIED
    assert any(r.startswith("input 'capacity_mw'") for r in leaf.reasons)


def test_legacy_citation_gets_a_suggested_quote(corpus):
    raw = _dataroom_raw()  # A-020 cites S-001 (press release) with no quote
    leaf = _leaf(run_gate(_spec(raw), corpus=corpus), "A-020")
    assert leaf.verdict == Verdict.UNVERIFIED
    assert leaf.suggestion and "214 million" in leaf.suggestion["quote"]


# ─────────────────────────────────────────────────────────────────────────────
# Overrides and strictness
# ─────────────────────────────────────────────────────────────────────────────

def test_signed_override_is_honoured_and_recorded(corpus):
    raw = _with_evidence(_dataroom_raw(), ["construction", "total_capex_eur_m"], {
        "kind": "fact", "source_id": "S-002",
        "quote": "Total project capex of EUR 316 million is phased 35 percent in Year 1"},
        source_id="S-002")
    overrides, errors = parse_overrides([
        {"id": "A-001", "verdict": "contested", "signed_by": "L. Analyst", "date": "2026-10-11",
         "reason": "IM capex confirmed by EPC contract; press release figure is the financing package."},
        {"id": "A-002", "verdict": "broken", "signed_by": "L. Analyst", "date": "2026-10-11",
         "reason": "stale"},
    ])
    assert not errors
    result = run_gate(_spec(raw), corpus=corpus, overrides=overrides)
    leaf = _leaf(result, "A-001")
    assert leaf.verdict == Verdict.OVERRIDDEN and leaf.original_verdict == Verdict.CONTESTED
    assert result.passed
    d = result.to_dict()
    assert d["overrides"][0]["signed_by"] == "L. Analyst"
    assert d["unused_overrides"][0]["id"] == "A-002"


def test_unsigned_override_is_rejected():
    _, errors = parse_overrides([{"id": "A-001", "verdict": "contested", "reason": "x",
                                  "signed_by": "", "date": "2026-10-11"}])
    assert errors


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def test_build_refuses_a_broken_binding(tmp_path):
    raw = _raw()
    raw["construction"]["total_capex_eur_m"] = copy.deepcopy(DEFECTIVE_CAPEX)
    spec_path = tmp_path / "enfinity_defect.yaml"
    spec_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    out = tmp_path / "out.xlsx"
    res = CliRunner().invoke(main, ["build", str(spec_path), "--out", str(out)])
    assert res.exit_code == 1, res.output
    assert "refused" in res.output and not out.exists()


def test_evidence_check_cli_json(tmp_path):
    report = tmp_path / "ev.json"
    res = CliRunner().invoke(main, ["evidence", "check", str(ENFINITY), "--json", str(report)])
    assert res.exit_code == 0, res.output
    d = json.loads(report.read_text(encoding="utf-8"))
    assert d["passed"] and d["counts"]["broken"] == 0 and d["lexicon_version"]
    res = CliRunner().invoke(main, ["evidence", "check", str(ENFINITY), "--strict"])
    assert res.exit_code == 1


# ─────────────────────────────────────────────────────────────────────────────
# Every path that builds from a spec runs the gate — no side door
# ─────────────────────────────────────────────────────────────────────────────

def _write_defective(tmp_path) -> Path:
    raw = _raw()
    raw["construction"]["total_capex_eur_m"] = copy.deepcopy(DEFECTIVE_CAPEX)
    spec_path = tmp_path / "enfinity_defect.yaml"
    spec_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return spec_path


def test_certify_refuses_a_broken_binding(tmp_path):
    spec_path = _write_defective(tmp_path)
    out = tmp_path / "out.xlsx"
    res = CliRunner().invoke(main, ["certify", str(spec_path), "--out", str(out)])
    assert res.exit_code == 1, res.output
    assert "Certification refused" in res.output and not out.exists()


def test_deck_refuses_a_broken_binding(tmp_path):
    pytest.importorskip("modelforge.deck.pipeline")
    spec_path = _write_defective(tmp_path)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        res = runner.invoke(main, ["deck", str(spec_path)])
        assert res.exit_code == 1, res.output
        assert "Deck refused" in res.output
        assert not (Path(cwd) / "output" / "enfinity_defect.xlsx").exists()


def test_audit_all_reports_and_skips_a_refused_spec(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    _write_defective(specs)
    (specs / "real_enfinity_solar_pf.yaml").write_bytes(ENFINITY.read_bytes())
    out_dir, report = tmp_path / "built", tmp_path / "AUDIT.md"
    res = CliRunner().invoke(main, ["audit-all", "--examples-dir", str(specs),
                                    "--out-dir", str(out_dir), "--report", str(report)])
    assert res.exit_code == 0, res.output
    text = report.read_text(encoding="utf-8")
    assert "Evidence-binding gate PASS: **1/2**" in text
    assert "refused by evidence gate: A-001" in text
    assert not (out_dir / "enfinity_defect.xlsx").exists()
    assert (out_dir / "real_enfinity_solar_pf.xlsx").exists()
    assert (out_dir / "real_enfinity_solar_pf.evidence.json").exists()


def test_mcp_tools_refuse_a_broken_binding(tmp_path):
    pytest.importorskip("mcp.server.fastmcp", reason="requires the [mcp] extra")
    from modelforge.mcp_server import build_model, certify

    spec_path = _write_defective(tmp_path)
    out_dir = tmp_path / "mcp_out"
    for res in (build_model(str(spec_path), output_dir=str(out_dir)),
                certify(spec_yaml=str(spec_path), output_dir=str(out_dir))):
        assert res["verdict"] == "EVIDENCE_BLOCKED", res
        assert [b["id"] for b in res["blocking"]] == ["A-001"]
        assert res["blocking"][0]["reasons"]
    assert not list(out_dir.glob("*.xlsx")) if out_dir.exists() else True

    ok = build_model(str(ENFINITY), output_dir=str(out_dir))
    assert ok["ok"], ok
    assert json.loads(Path(ok["evidence"]).read_text(encoding="utf-8"))["passed"]


def test_mcp_strict_and_invalid_override(tmp_path):
    pytest.importorskip("mcp.server.fastmcp", reason="requires the [mcp] extra")
    from modelforge.mcp_server import build_model

    out_dir = tmp_path / "mcp_out"
    strict = build_model(str(ENFINITY), output_dir=str(out_dir), evidence_strict=True)
    assert strict["verdict"] == "EVIDENCE_BLOCKED"
    assert all(b["verdict"] == "unverified" for b in strict["blocking"])

    raw = _raw()
    raw["evidence_overrides"] = [{"id": "A-001", "verdict": "broken", "reason": "",
                                  "signed_by": "", "date": "2026-10-12"}]
    bad = tmp_path / "bad_override.yaml"
    bad.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    res = build_model(str(bad), output_dir=str(out_dir))
    assert res["verdict"] == "EVIDENCE_BLOCKED" and res["errors"], res
    assert not list(out_dir.glob("*.xlsx"))

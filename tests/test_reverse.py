"""Tests for modelforge.reverse (US-016 — competitor reverse-engineer)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from modelforge.reverse import (
    analyze_workbook,
    classify_sheet,
    detect_template_type,
    render_markdown,
    render_spec_skeleton,
)
from modelforge.reverse.engine import SheetProfile
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


# ─── Classification accuracy — round-trips on all 11 templates ──────────────


ROUND_TRIP_CASES = [
    ("unitranche_cdmo.yaml", "unitranche", "UnitrancheSpec"),
    ("minibond_logistics.yaml", "minibond", "MinibondSpec"),
    ("credit_memo_cdmo.yaml", "credit_memo", "CreditMemoSpec"),
    ("project_finance_solar.yaml", "project_finance", "ProjectFinanceSpec"),
    ("real_estate_pbsa.yaml", "real_estate", "RealEstateSpec"),
    ("npl_mixed_portfolio.yaml", "npl", "NPLSpec"),
    ("structured_credit_pmi.yaml", "structured_credit", "StructuredCreditSpec"),
    ("three_statement_cdmo.yaml", "three_statement", "ThreeStatementSpec"),
    ("dcf_enel.yaml", "dcf", "DCFSpec"),
    ("merger_tim_iliad.yaml", "merger", "MergerSpec"),
    ("fairness_amplifon.yaml", "fairness", "FairnessSpec"),
]


@pytest.mark.parametrize("yaml_file,expected_type,cls_name", ROUND_TRIP_CASES)
def test_round_trip_classification(yaml_file, expected_type, cls_name,
                                    tmp_path_factory):
    """A ModelForge-built workbook should round-trip to its own type."""
    spec_module = f"modelforge.spec.{expected_type}"
    # credit_memo nests in unitranche-style
    SC = getattr(__import__(spec_module, fromlist=[cls_name]), cls_name)
    p = ROOT / "examples" / yaml_file
    spec = SC.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("rev") / f"{expected_type}.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)

    rep = analyze_workbook(out)
    assert rep.detected_template == expected_type, (
        f"Expected {expected_type}, got {rep.detected_template} "
        f"with confidence {rep.template_confidence:.0%}. "
        f"Top scores: {sorted(rep.template_scores.items(), key=lambda x: -x[1])[:3]}"
    )


# ─── Sheet classifier smoke ──────────────────────────────────────────────────


@pytest.mark.parametrize("name,kind", [
    ("Cover", "cover"),
    ("Sources", "sources"),
    ("Assumptions", "assumptions"),
    ("OperatingModel", "operating"),
    ("FCFForecast", "operating"),
    ("DebtSchedule", "debt"),
    ("Tranches", "debt"),
    ("Covenants", "covenants"),
    ("Returns", "returns"),
    ("AccretionDilution", "returns"),
    ("Valuation", "valuation"),
    ("WACCBuild", "valuation"),
    ("FootballField", "valuation"),
    ("CollectionWaterfall", "waterfall"),
    ("QC", "qc"),
    ("SensitivityAnalysis", "sensitivity"),
    ("MonteCarlo", "monte_carlo"),
    ("Reproducibility", "metadata"),
    ("SomeRandomTab", "other"),
])
def test_classify_sheet_canonical_names(name, kind):
    assert classify_sheet(name) == kind


# ─── Input extraction ────────────────────────────────────────────────────────


def test_inputs_extracted_from_unitranche(tmp_path_factory):
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("rev2") / "u.xlsx"
    build_model(spec, out)
    rep = analyze_workbook(out)
    # A real unitranche workbook should surface 30+ inputs (assumptions +
    # historical drivers + covenant thresholds etc.)
    assert rep.n_inputs >= 30
    # Input labels should include at least one intuitive driver word
    labels = " ".join(i.label.lower() for i in rep.inputs)
    assert any(w in labels for w in ("revenue", "ebitda", "margin", "rate",
                                      "growth", "capex"))


# ─── Spec skeleton ───────────────────────────────────────────────────────────


def test_spec_skeleton_is_valid_yaml(tmp_path_factory):
    from modelforge.spec.dcf import DCFSpec
    p = ROOT / "examples" / "dcf_enel.yaml"
    spec = DCFSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("rev3") / "d.xlsx"
    build_model(spec, out)
    rep = analyze_workbook(out)
    skeleton_yaml = render_spec_skeleton(rep)
    parsed = yaml.safe_load(skeleton_yaml)
    assert parsed["model_type"] == "dcf"
    assert "_reverse_engineering_notes" in parsed
    assert "_extracted_assumptions" in parsed
    assert parsed["_reverse_engineering_notes"]["detected_template"] == "dcf"


# ─── Markdown rendering ──────────────────────────────────────────────────────


def test_markdown_report_well_formed(tmp_path_factory):
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("rev4") / "u.xlsx"
    build_model(spec, out)
    rep = analyze_workbook(out)
    md = render_markdown(rep)
    assert "# Reverse-engineering report" in md
    assert "Template-match scores" in md
    assert "Sheet analysis" in md
    assert "unitranche" in md


# ─── Detection primitive ────────────────────────────────────────────────────


def test_detect_template_type_empty_sheets():
    best, conf, scores = detect_template_type([])
    # Every signature has base 0 — tied. Any template could come back;
    # but confidence should be 0.
    assert conf == 0.0


def test_detect_template_type_score_monotonicity():
    """More matching kinds → higher score."""
    partial = [SheetProfile(name="Cover", kind="cover", rows=1, cols=1,
                            formula_cells=0, hardcoded_cells=1)]
    more = partial + [
        SheetProfile(name="Sources", kind="sources", rows=1, cols=1,
                     formula_cells=0, hardcoded_cells=1),
        SheetProfile(name="Assumptions", kind="assumptions", rows=1, cols=1,
                     formula_cells=0, hardcoded_cells=1),
    ]
    _, c1, _ = detect_template_type(partial)
    _, c2, _ = detect_template_type(more)
    assert c2 >= c1

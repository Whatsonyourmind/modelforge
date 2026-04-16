"""End-to-end pipeline test — fully mocked Claude, real readers + YAML + validation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from modelforge.ingest.pipeline import ingest


FIXTURES = Path(__file__).parent / "fixtures" / "dataroom_enfinity_synth"


def _mk_response(tool_name: str, payload: dict, cache: int = 0):
    tool_block = SimpleNamespace(type="tool_use", name=tool_name, input=payload)
    usage = SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=cache)
    return SimpleNamespace(content=[tool_block], usage=usage)


# A complete, valid PF spec payload. We'll split it across the mocked responses
# in the order pipeline calls the tools.
_CLASSIFY = {
    "doc_type": "press_release",
    "publisher": "Enfinity Global",
    "date": "2025-08-15",
    "verified": True,
    "relevance_hint": "EUR 316M financing; 276MW solar portfolio.",
    "confidence": "H",
}

_TARGET = {
    "name": "Enfinity Solar Italy SPV",
    "sector": {"en": "Utility-scale solar PV", "it": "Solare PV utility-scale"},
    "country": "IT", "currency": "EUR",
    "revenue_last_fy_eur_m": 0, "revenue_source_id": "S-001",
    "ebitda_last_fy_eur_m": 0, "ebitda_source_id": "S-001",
    "last_fy_end": "2025-12-31",
}

_CONSTRUCTION = {
    "total_capex_eur_m": {
        "id": "A-001", "name": "total_capex",
        "label": {"en": "Total capex", "it": "Capex totale"},
        "unit": "eur_m", "base": 316.0,
        "rationale": "EUR 316M per Enfinity press release.",
        "confidence": "H", "source_id": "S-001",
    },
    "capex_phasing_pct": [
        {"id": "A-002", "name": "capex_phasing_y1",
         "label": {"en": "Capex phasing Y1", "it": "Capex Y1"},
         "unit": "pct", "base": 0.35, "rationale": "Per IM phasing.", "confidence": "M"},
        {"id": "A-003", "name": "capex_phasing_y2",
         "label": {"en": "Capex phasing Y2", "it": "Capex Y2"},
         "unit": "pct", "base": 0.65, "rationale": "Per IM phasing.", "confidence": "M"},
    ],
    "interest_during_construction_capitalized": True,
    "commitment_fee_bps": {
        "id": "A-004", "name": "commitment_fee_bps",
        "label": {"en": "Commitment fee", "it": "Commitment"},
        "unit": "bps", "base": 75.0,
        "rationale": "Per term sheet.", "confidence": "H", "source_id": "S-007",
    },
}

_OPERATING = {
    "availability_payment_eur_m_yr1": {
        "id": "A-010", "name": "revenue_yr1",
        "label": {"en": "Revenue Y1", "it": "Ricavi Y1"},
        "unit": "eur_m", "base": 32.1,
        "rationale": "276MW x 1550 kWh/kWp x 75 EUR/MWh.", "confidence": "H", "source_id": "S-003",
    },
    "revenue_indexation_pct": {
        "id": "A-011", "name": "revenue_indexation",
        "label": {"en": "Revenue CPI escalation", "it": "Indicizzazione"},
        "unit": "pct", "base": 0.015,
        "rationale": "1.5% per IM.", "confidence": "M", "source_id": "S-002",
    },
    "opex_pct_revenue": {
        "id": "A-012", "name": "opex_pct_revenue",
        "label": {"en": "Opex % revenue", "it": "Opex % ricavi"},
        "unit": "pct", "base": 0.22,
        "rationale": "22% per IM.", "confidence": "M", "source_id": "S-002",
    },
    "opex_indexation_pct": {
        "id": "A-013", "name": "opex_indexation",
        "label": {"en": "Opex CPI escalation", "it": "Indicizzazione opex"},
        "unit": "pct", "base": 0.02,
        "rationale": "2% per IM.", "confidence": "M", "source_id": "S-002",
    },
    "maintenance_reserve_pct_revenue": {
        "id": "A-014", "name": "maintenance_reserve_pct",
        "label": {"en": "Maintenance reserve % rev", "it": "Riserva manutenzione"},
        "unit": "pct", "base": 0.02,
        "rationale": "2% MMRA per IM.", "confidence": "M", "source_id": "S-002",
    },
}

_DEBT = {
    "name": {"en": "Senior Green Loan", "it": "Green Loan Senior"},
    "amount": {
        "id": "A-020", "name": "senior_amount",
        "label": {"en": "Senior amount (cap)", "it": "Debito senior (cap)"},
        "unit": "eur_m", "base": 214.0,
        "rationale": "EUR 214M per press + term sheet.", "confidence": "H", "source_id": "S-001",
    },
    "tenor_operating_years": 18, "grace_years": 1,
    "reference_rate": {
        "id": "A-021", "name": "eur_swap_10y",
        "label": {"en": "EUR swap 10Y", "it": "EUR swap 10Y"},
        "unit": "pct", "base": 0.0285,
        "rationale": "ECB SDW April 2026.", "confidence": "H", "source_id": "S-005",
    },
    "margin_bps": {
        "id": "A-022", "name": "senior_margin_bps",
        "label": {"en": "Senior margin", "it": "Margine senior"},
        "unit": "bps", "base": 175.0,
        "rationale": "Per term sheet.", "confidence": "H", "source_id": "S-007",
    },
    "arrangement_fee_pct": {
        "id": "A-023", "name": "senior_arrangement_pct",
        "label": {"en": "Arrangement fee", "it": "Strutturazione"},
        "unit": "pct", "base": 0.0125,
        "rationale": "Per term sheet.", "confidence": "H", "source_id": "S-007",
    },
    "amortization_profile": "sculpted_dscr_target",
    "debt_sizing_mode": "dscr_target",
    "dsra_months": 6,
    "target_dscr_base": {
        "id": "A-080", "name": "target_dscr_base",
        "label": {"en": "Target DSCR base", "it": "DSCR target"},
        "unit": "x", "base": 1.30,
        "rationale": "Term sheet min DSCR.", "confidence": "H", "source_id": "S-007",
    },
}

_COVENANT = {
    "threshold_by_year": [
        {"id": f"A-{30+i:03d}", "name": f"dscr_op{i+1}",
         "label": {"en": f"DSCR O{i+1}", "it": f"DSCR O{i+1}"},
         "unit": "x", "base": 1.20 if i == 0 else (1.25 if i < 3 else 1.30),
         "rationale": "Per term sheet schedule.",
         "confidence": "H", "source_id": "S-007"}
        for i in range(20)
    ],
    "lock_up_threshold": {
        "id": "A-060", "name": "lock_up_dscr",
        "label": {"en": "Lock-up DSCR", "it": "DSCR lock-up"},
        "unit": "x", "base": 1.15,
        "rationale": "Per term sheet.", "confidence": "H", "source_id": "S-007",
    },
}

_EQUITY = {
    "target_irr": {
        "id": "A-070", "name": "target_irr",
        "label": {"en": "Target IRR", "it": "IRR target"},
        "unit": "pct", "base": 0.10,
        "rationale": "European utility solar target 9-11%.", "confidence": "H",
    },
    "effective_tax_rate": {
        "id": "A-071", "name": "effective_tax_rate",
        "label": {"en": "Effective tax rate", "it": "Aliquota effettiva"},
        "unit": "pct", "base": 0.279,
        "rationale": "IRES+IRAP per PwC.", "confidence": "H", "source_id": "S-006",
    },
}


def test_pipeline_end_to_end_offline(tmp_path):
    """Full pipeline with mocked Claude — verifies readers, pipeline plumbing,
    YAML emission, and Pydantic validation all wire together."""
    # One mock response per call. Order:
    #   9 classifier calls (one per doc)
    #   6 extractor calls (target, construction, operating, debt, covenant, equity)
    mock_client = MagicMock()
    responses = []
    for _ in range(9):
        responses.append(_mk_response("classify_document", _CLASSIFY, cache=500))
    responses.append(_mk_response("emit_target", _TARGET))
    responses.append(_mk_response("emit_construction", _CONSTRUCTION, cache=800))
    responses.append(_mk_response("emit_operating", _OPERATING, cache=800))
    responses.append(_mk_response("emit_debt", _DEBT, cache=800))
    responses.append(_mk_response("emit_covenant", _COVENANT, cache=800))
    responses.append(_mk_response("emit_equity", _EQUITY, cache=800))
    mock_client.messages.create.side_effect = responses

    out_yaml = tmp_path / "enfinity_test.yaml"
    result = ingest(
        dataroom_dir=FIXTURES,
        template="project_finance",
        output_yaml=out_yaml,
        model="claude-opus-4-6",
        client=mock_client,
    )

    # Contract checks
    assert result.yaml_path.exists()
    assert result.report_path.exists()
    assert result.spec_valid is True, result.validation_errors
    assert result.cache_hit_rate > 0.8, f"Got {result.cache_hit_rate}"
    assert len(result.classifier_results) == 9
    assert len(result.extraction_results) == 6

    # YAML round-trip
    spec_dict = yaml.safe_load(out_yaml.read_text(encoding="utf-8"))
    from modelforge.spec.project_finance import ProjectFinanceSpec
    spec = ProjectFinanceSpec.model_validate(spec_dict)
    assert spec.debt.amortization_profile == "sculpted_dscr_target"
    assert spec.debt.debt_sizing_mode == "dscr_target"
    assert spec.debt.target_dscr_base is not None
    assert spec.debt.target_dscr_base.base == 1.30
    # Covenant thresholds match the 20-year horizon
    assert len(spec.covenant.threshold_by_year) == 20

    # Report contains doc table + extraction table
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "Ingestion Report" in report_text
    assert "S-001" in report_text
    assert "construction" in report_text.lower()
    assert "operating" in report_text.lower()


def test_pipeline_end_to_end_builds_valid_workbook(tmp_path):
    """Ingested YAML must round-trip through modelforge build cleanly
    (inherits v0.3.0-pf PF pipeline)."""
    mock_client = MagicMock()
    responses = []
    for _ in range(9):
        responses.append(_mk_response("classify_document", _CLASSIFY, cache=500))
    responses.append(_mk_response("emit_target", _TARGET))
    responses.append(_mk_response("emit_construction", _CONSTRUCTION))
    responses.append(_mk_response("emit_operating", _OPERATING))
    responses.append(_mk_response("emit_debt", _DEBT))
    responses.append(_mk_response("emit_covenant", _COVENANT))
    responses.append(_mk_response("emit_equity", _EQUITY))
    mock_client.messages.create.side_effect = responses

    out_yaml = tmp_path / "enfinity_build.yaml"
    result = ingest(
        dataroom_dir=FIXTURES, template="project_finance",
        output_yaml=out_yaml, client=mock_client,
    )
    assert result.spec_valid

    # Build the workbook
    from modelforge.templates import build_model
    from modelforge.spec.project_finance import ProjectFinanceSpec
    spec = ProjectFinanceSpec.model_validate(yaml.safe_load(out_yaml.read_text("utf-8")))
    xlsx_path = tmp_path / "enfinity_build.xlsx"
    build_model(spec, xlsx_path)
    assert xlsx_path.exists()

    # External QC
    from modelforge.qc import run_qc
    report = run_qc(xlsx_path)
    assert report.all_pass, f"QC failed: {[c.name for c in report.checks if not c.passed]}"


def test_pipeline_rejects_unknown_template(tmp_path):
    with pytest.raises(ValueError, match="not supported"):
        ingest(dataroom_dir=FIXTURES, template="ETFpricing",
               output_yaml=tmp_path / "x.yaml")

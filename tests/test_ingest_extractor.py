"""Tests for the extractor — schema derivation + mocked extraction."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modelforge.ingest.extractor import _build_tool, _inline_refs, extract_section
from modelforge.ingest.readers.base import DocChunk


def test_inline_refs_resolves_pydantic_defs():
    schema = {
        "$defs": {
            "Label": {"type": "object", "properties": {
                "en": {"type": "string"}, "it": {"type": "string"}}},
        },
        "type": "object",
        "properties": {
            "field": {"$ref": "#/$defs/Label"},
        },
    }
    inlined = _inline_refs(schema)
    assert "$defs" not in inlined
    assert inlined["properties"]["field"]["type"] == "object"
    assert "en" in inlined["properties"]["field"]["properties"]


def test_build_tool_from_pf_construction():
    from modelforge.spec.project_finance import ConstructionPhase
    tool = _build_tool("construction", ConstructionPhase)
    assert tool["name"] == "emit_construction"
    assert tool["input_schema"]["type"] == "object"
    assert "$defs" not in tool["input_schema"]  # should be inlined
    assert "total_capex_eur_m" in tool["input_schema"]["properties"]


def test_build_tool_from_pf_debt_includes_v03_fields():
    """PFDebt should expose v0.3 fields (amortization_profile, dsra_months)."""
    from modelforge.spec.project_finance import PFDebt
    tool = _build_tool("debt", PFDebt)
    props = tool["input_schema"]["properties"]
    assert "amortization_profile" in props
    assert "debt_sizing_mode" in props
    assert "dsra_months" in props


def _mock_extractor_response(payload: dict, cache_read: int = 0):
    tool_block = SimpleNamespace(
        type="tool_use",
        name="emit_operating",
        input=payload,
    )
    usage = SimpleNamespace(
        input_tokens=2000,
        output_tokens=400,
        cache_read_input_tokens=cache_read,
    )
    return SimpleNamespace(content=[tool_block], usage=usage)


def test_extract_section_returns_valid_payload():
    from modelforge.spec.project_finance import OperatingPhase
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_extractor_response({
        "availability_payment_eur_m_yr1": {
            "id": "A-010", "name": "revenue_yr1",
            "label": {"en": "Revenue Y1", "it": "Ricavi Y1"},
            "unit": "eur_m", "base": 32.1,
            "rationale": "276MW x 1550 kWh/kWp x 75 EUR/MWh per Terna + GSE.",
            "confidence": "H", "source_id": "S-003",
        },
        "revenue_indexation_pct": {
            "id": "A-011", "name": "revenue_indexation",
            "label": {"en": "Revenue CPI escalation", "it": "Indicizzazione ricavi"},
            "unit": "pct", "base": 0.015,
            "rationale": "1.5% per IM section 7.",
            "confidence": "M", "source_id": "S-002",
        },
        "opex_pct_revenue": {
            "id": "A-012", "name": "opex_pct_revenue",
            "label": {"en": "Opex % revenue", "it": "Opex % ricavi"},
            "unit": "pct", "base": 0.22,
            "rationale": "22% per IM operating cost section.",
            "confidence": "M", "source_id": "S-002",
        },
        "opex_indexation_pct": {
            "id": "A-013", "name": "opex_indexation",
            "label": {"en": "Opex CPI escalation", "it": "Indicizzazione opex"},
            "unit": "pct", "base": 0.02,
            "rationale": "2% per IM operating cost section.",
            "confidence": "M", "source_id": "S-002",
        },
        "maintenance_reserve_pct_revenue": {
            "id": "A-014", "name": "maintenance_reserve_pct",
            "label": {"en": "Maintenance reserve % rev", "it": "Riserva manutenzione"},
            "unit": "pct", "base": 0.02,
            "rationale": "2% MMRA per IM.",
            "confidence": "M", "source_id": "S-002",
        },
    })

    sources = [{"id": f"S-{i:03d}", "doc": f"doc_{i}.pdf", "publisher": "t",
                "date": "2026-01-01", "verified": True, "note": "t"}
               for i in range(1, 10)]
    chunks = [DocChunk(doc_filename="doc_1.pdf", page=1, text="Sample text.")]
    result = extract_section(
        "project_finance", "operating", OperatingPhase,
        available_sources=sources, context_chunks=chunks, client=mock_client,
    )
    assert result.validation_ok is True
    assert "availability_payment_eur_m_yr1" in result.payload


def test_extract_section_retries_on_validation_error():
    from modelforge.spec.project_finance import OperatingPhase
    mock_client = MagicMock()
    # First call: invalid (missing required fields)
    bad_resp = _mock_extractor_response({"availability_payment_eur_m_yr1": {}})
    # Second call: still invalid — simulates failure after retry
    mock_client.messages.create.side_effect = [bad_resp, bad_resp]

    sources = [{"id": "S-001", "doc": "d.pdf", "publisher": "t",
                "date": "2026-01-01", "verified": True, "note": ""}]
    chunks = [DocChunk(doc_filename="d.pdf", page=1, text="x")]
    result = extract_section(
        "project_finance", "operating", OperatingPhase,
        available_sources=sources, context_chunks=chunks, client=mock_client,
    )
    assert result.validation_ok is False
    assert result.validation_error
    # Should have been called twice (original + retry)
    assert mock_client.messages.create.call_count == 2

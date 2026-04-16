"""Tests for the classifier (mocked Claude client)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modelforge.ingest.classifier import CLASSIFY_TOOL, classify_all, classify_one
from modelforge.ingest.readers.discovery import read_any


FIXTURES = Path(__file__).parent / "fixtures" / "dataroom_enfinity_synth"


def _mock_response(payload: dict, cache_read_tokens: int = 0):
    """Build a fake Anthropic SDK response object."""
    tool_block = SimpleNamespace(
        type="tool_use",
        name="classify_document",
        input=payload,
    )
    usage = SimpleNamespace(
        input_tokens=500,
        output_tokens=100,
        cache_read_input_tokens=cache_read_tokens,
    )
    return SimpleNamespace(content=[tool_block], usage=usage)


def test_classify_one_returns_structured_result():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response({
        "doc_type": "press_release",
        "publisher": "Enfinity Global",
        "date": "2025-08-15",
        "verified": True,
        "relevance_hint": "EUR 316M financing; 276MW portfolio.",
        "confidence": "H",
    })

    idx = read_any(FIXTURES / "01_enfinity_press_release.pdf")
    result = classify_one(idx, client=mock_client)

    assert result.doc_type == "press_release"
    assert result.publisher == "Enfinity Global"
    assert result.date == date(2025, 8, 15)
    assert result.verified is True
    assert result.confidence == "H"
    # Verify the client was called with cache_control on system + tool
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["system"][0].get("cache_control") == {"type": "ephemeral"}
    assert call_args.kwargs["tools"][0].get("cache_control") == {"type": "ephemeral"}


def test_classify_one_detects_cache_hit():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(
        {
            "doc_type": "market_benchmark",
            "publisher": "Terna",
            "verified": True,
            "relevance_hint": "Solar irradiation benchmark.",
            "confidence": "H",
        },
        cache_read_tokens=800,
    )
    idx = read_any(FIXTURES / "03_terna_irradiation_report_2025.pdf")
    result = classify_one(idx, client=mock_client)
    assert result.cache_hit is True


def test_classify_all_attaches_metadata_to_indexes():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response({
        "doc_type": "press_release",
        "publisher": "Test Publisher",
        "verified": False,
        "relevance_hint": "test",
        "confidence": "M",
    })
    # Use 2 small fixture docs
    from modelforge.ingest.readers.discovery import discover
    indexes = [read_any(p) for p in discover(FIXTURES, max_docs=2)]
    results = classify_all(indexes, client=mock_client)

    assert len(results) == 2
    for idx in indexes:
        assert idx.doc_type == "press_release"
        assert idx.publisher_hint == "Test Publisher"


def test_classify_tool_schema_has_doc_types():
    """Smoke check: the tool schema exposed to Claude includes the enum."""
    enum = CLASSIFY_TOOL["input_schema"]["properties"]["doc_type"]["enum"]
    assert "press_release" in enum
    assert "audited_financials" in enum
    assert "contract_loan" in enum


def test_classify_rejects_missing_api_key(monkeypatch):
    from modelforge.ingest import classifier
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    idx = read_any(FIXTURES / "01_enfinity_press_release.pdf")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        classify_one(idx)

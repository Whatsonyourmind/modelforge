"""Tests for the classifier (mocked LLM backend)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from modelforge.ingest.classifier import CLASSIFY_TOOL_SCHEMA, classify_all, classify_one
from modelforge.ingest.llm import LLMResponse
from modelforge.ingest.readers.discovery import read_any


FIXTURES = Path(__file__).parent / "fixtures" / "dataroom_enfinity_synth"


class MockBackend:
    """Minimal LLM backend that returns a fixed payload."""
    def __init__(self, payload: dict, cache_hit: bool = False):
        self._payload = payload
        self._cache_hit = cache_hit
        self.calls: list[dict] = []

    def call_json(self, system_prompt, user_prompt, tool_name=None, tool_schema=None):
        self.calls.append({"system": system_prompt, "user": user_prompt,
                           "tool_name": tool_name, "tool_schema": tool_schema})
        return LLMResponse(payload=self._payload, cache_hit=self._cache_hit,
                           input_tokens=500, output_tokens=100)


def test_classify_one_returns_structured_result():
    backend = MockBackend({
        "doc_type": "press_release",
        "publisher": "Enfinity Global",
        "date": "2025-08-15",
        "verified": True,
        "relevance_hint": "EUR 316M financing; 276MW portfolio.",
        "confidence": "H",
    })
    idx = read_any(FIXTURES / "01_enfinity_press_release.pdf")
    result = classify_one(idx, backend=backend)

    assert result.doc_type == "press_release"
    assert result.publisher == "Enfinity Global"
    assert result.date == date(2025, 8, 15)
    assert result.verified is True
    assert result.confidence == "H"
    assert len(backend.calls) == 1
    assert backend.calls[0]["tool_name"] == "classify_document"


def test_classify_one_detects_cache_hit():
    backend = MockBackend(
        {"doc_type": "market_benchmark", "publisher": "Terna",
         "verified": True, "relevance_hint": "Solar irradiation benchmark.",
         "confidence": "H"},
        cache_hit=True,
    )
    idx = read_any(FIXTURES / "03_terna_irradiation_report_2025.pdf")
    result = classify_one(idx, backend=backend)
    assert result.cache_hit is True


def test_classify_all_attaches_metadata_to_indexes():
    backend = MockBackend({
        "doc_type": "press_release",
        "publisher": "Test Publisher",
        "verified": False,
        "relevance_hint": "test",
        "confidence": "M",
    })
    from modelforge.ingest.readers.discovery import discover
    indexes = [read_any(p) for p in discover(FIXTURES, max_docs=2)]
    results = classify_all(indexes, backend=backend)

    assert len(results) == 2
    for idx in indexes:
        assert idx.doc_type == "press_release"
        assert idx.publisher_hint == "Test Publisher"


def test_classify_tool_schema_has_doc_types():
    enum = CLASSIFY_TOOL_SCHEMA["properties"]["doc_type"]["enum"]
    assert "press_release" in enum
    assert "audited_financials" in enum
    assert "contract_loan" in enum


def test_classify_rejects_missing_api_key(monkeypatch):
    """Only relevant for API backend — CLI backend doesn't need a key."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from modelforge.ingest.llm import AnthropicAPIBackend
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicAPIBackend()

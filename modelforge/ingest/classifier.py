"""Classify every document in the data room.

Uses the LLM backend abstraction (CLI or API). System prompt + tool schema
are passed to the backend; caching is handled by the backend if supported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

from modelforge.ingest.llm import LLMBackend, LLMResponse
from modelforge.ingest.readers.base import DocIndex

_PROMPT_DIR = Path(__file__).parent / "prompts"
_CLASSIFIER_SYSTEM = (_PROMPT_DIR / "classifier_system.md").read_text(encoding="utf-8")


DOC_TYPES = [
    "press_release",
    "information_memorandum",
    "audited_financials",
    "unaudited_financials",
    "contract_ppa",
    "contract_loan",
    "market_benchmark",
    "regulatory_filing",
    "rating_report",
    "legal_opinion",
    "operational_report",
    "other",
]


CLASSIFY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": DOC_TYPES,
            "description": "One of the known document types.",
        },
        "publisher": {
            "type": "string",
            "description": "Entity that authored/published the document.",
        },
        "date": {
            "type": ["string", "null"],
            "description": "Publication date in YYYY-MM-DD format, or null if not present.",
        },
        "verified": {
            "type": "boolean",
            "description": "True if signed/audited/regulatory/rating/third-party.",
        },
        "relevance_hint": {
            "type": "string",
            "description": "One sentence naming the specific facts this doc provides.",
        },
        "confidence": {
            "type": "string",
            "enum": ["H", "M", "L"],
            "description": "Classifier self-rated confidence.",
        },
    },
    "required": ["doc_type", "publisher", "verified", "relevance_hint", "confidence"],
}


@dataclass
class ClassifierResult:
    doc_filename: str
    doc_type: str
    publisher: str
    date: Optional[date]
    verified: bool
    relevance_hint: str
    confidence: str  # "H" / "M" / "L"
    cache_hit: bool = False


def classify_one(
    index: DocIndex,
    backend: LLMBackend | None = None,
    **kwargs,
) -> ClassifierResult:
    """Classify a single document via one LLM call."""
    if backend is None:
        from modelforge.ingest.llm import get_backend
        backend = get_backend(**kwargs)

    head = index.head_text(3000)
    user_prompt = (
        f"# Document: {index.doc_filename}\n"
        f"Total pages: {index.total_pages}\n\n"
        f"## First pages:\n\n{head}"
    )

    resp: LLMResponse = backend.call_json(
        system_prompt=_CLASSIFIER_SYSTEM,
        user_prompt=user_prompt,
        tool_name="classify_document",
        tool_schema=CLASSIFY_TOOL_SCHEMA,
    )
    payload = resp.payload

    parsed_date: Optional[date] = None
    d = payload.get("date")
    if d:
        try:
            parsed_date = date.fromisoformat(d)
        except ValueError:
            parsed_date = None

    return ClassifierResult(
        doc_filename=index.doc_filename,
        doc_type=payload.get("doc_type", "other"),
        publisher=payload.get("publisher", "Unknown"),
        date=parsed_date,
        verified=bool(payload.get("verified", False)),
        relevance_hint=payload.get("relevance_hint", ""),
        confidence=payload.get("confidence", "M"),
        cache_hit=resp.cache_hit,
    )


def classify_all(
    indexes: list[DocIndex],
    backend: LLMBackend | None = None,
    **kwargs,
) -> list[ClassifierResult]:
    """Classify every document; in-place attaches type/publisher/date to DocIndex."""
    if backend is None:
        from modelforge.ingest.llm import get_backend
        backend = get_backend(**kwargs)
    results: list[ClassifierResult] = []
    for idx in indexes:
        r = classify_one(idx, backend=backend)
        idx.doc_type = r.doc_type
        idx.publisher_hint = r.publisher
        idx.date_hint = r.date
        idx.verified = r.verified
        idx.relevance_hint = r.relevance_hint
        idx.classifier_confidence = r.confidence
        results.append(r)
    return results

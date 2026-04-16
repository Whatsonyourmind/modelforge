"""Classify every document in the data room with a cached Claude call.

Uses the Anthropic SDK with prompt caching. System prompt + tool schema
are cached (`cache_control: ephemeral`), so for an N-doc data room we
pay the full prompt cost once and get N-1 cache hits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

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


CLASSIFY_TOOL = {
    "name": "classify_document",
    "description": "Classify a data-room document and extract light metadata.",
    "input_schema": {
        "type": "object",
        "properties": {
            "doc_type": {
                "type": "string",
                "enum": DOC_TYPES,
                "description": "One of the known document types.",
            },
            "publisher": {
                "type": "string",
                "description": "Entity that authored/published the document (e.g. 'Enfinity Global', 'Terna').",
            },
            "date": {
                "type": ["string", "null"],
                "description": "Publication date in YYYY-MM-DD format, or null if not present.",
            },
            "verified": {
                "type": "boolean",
                "description": "True if signed/audited/regulatory/rating/third-party. Sponsor-authored = false.",
            },
            "relevance_hint": {
                "type": "string",
                "description": "One sentence (≤ 25 words) naming the specific facts this doc provides.",
            },
            "confidence": {
                "type": "string",
                "enum": ["H", "M", "L"],
                "description": "Classifier self-rated confidence in this classification.",
            },
        },
        "required": ["doc_type", "publisher", "verified", "relevance_hint", "confidence"],
    },
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


def _get_client():
    """Lazy anthropic client init — lets tests mock at import time."""
    from anthropic import Anthropic
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. `modelforge ingest` requires a "
            "valid Anthropic API key. See https://console.anthropic.com/."
        )
    return Anthropic()


def classify_one(
    index: DocIndex,
    model: str = "claude-opus-4-6",
    client: Any = None,
    use_cache: bool = True,
) -> ClassifierResult:
    """Classify a single document via one Claude call."""
    client = client or _get_client()
    head = index.head_text(3000)
    user_prompt = (
        f"# Document: {index.doc_filename}\n"
        f"Total pages: {index.total_pages}\n\n"
        f"## First pages:\n\n{head}"
    )

    system_block = {"type": "text", "text": _CLASSIFIER_SYSTEM}
    tool_block: dict[str, Any] = dict(CLASSIFY_TOOL)
    if use_cache:
        system_block["cache_control"] = {"type": "ephemeral"}
        tool_block = {**tool_block, "cache_control": {"type": "ephemeral"}}

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=[system_block],
        tools=[tool_block],
        tool_choice={"type": "tool", "name": "classify_document"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract the tool-use block
    payload = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "classify_document":
            payload = block.input
            break
    if payload is None:
        raise RuntimeError(
            f"Classifier returned no tool_use block for {index.doc_filename}"
        )

    parsed_date: Optional[date] = None
    d = payload.get("date")
    if d:
        try:
            parsed_date = date.fromisoformat(d)
        except ValueError:
            parsed_date = None

    # Detect cache hit from usage block (Anthropic SDK exposes
    # cache_read_input_tokens when cache served)
    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    cache_hit = cache_read > 0

    return ClassifierResult(
        doc_filename=index.doc_filename,
        doc_type=payload["doc_type"],
        publisher=payload["publisher"],
        date=parsed_date,
        verified=bool(payload.get("verified", False)),
        relevance_hint=payload.get("relevance_hint", ""),
        confidence=payload.get("confidence", "M"),
        cache_hit=cache_hit,
    )


def classify_all(
    indexes: list[DocIndex],
    model: str = "claude-opus-4-6",
    client: Any = None,
    use_cache: bool = True,
) -> list[ClassifierResult]:
    """Classify every document; in-place attaches type/publisher/date to DocIndex."""
    client = client or _get_client()
    results: list[ClassifierResult] = []
    for idx in indexes:
        r = classify_one(idx, model=model, client=client, use_cache=use_cache)
        idx.doc_type = r.doc_type
        idx.publisher_hint = r.publisher
        idx.date_hint = r.date
        idx.verified = r.verified
        idx.relevance_hint = r.relevance_hint
        idx.classifier_confidence = r.confidence
        results.append(r)
    return results

"""Confidence scoring for ingested fields.

Two inputs are blended:
    source_quality  — derived from the source doc's verified/kind
    llm_self_rated  — the extractor's own H/M/L on the field

The weaker of the two wins (floor discipline). Output is H/M/L.
"""

from __future__ import annotations


_ORDER = {"H": 3, "M": 2, "L": 1}


def combine(llm_confidence: str | None, source_verified: bool | None) -> str:
    """Return combined H/M/L.

    Rules:
        llm None → "L"
        source verified=True  → cap at least M (cannot be L)
        source verified=False → cap at most M (cannot be H)
        source None (no source_id) → cap at most L
    """
    lc = (llm_confidence or "L").upper()
    if lc not in _ORDER:
        lc = "L"

    if source_verified is None:
        return "L"
    if source_verified is True:
        # Can be H or M (never L)
        return lc if lc in ("H", "M") else "M"
    # source_verified False
    if lc == "H":
        return "M"
    return lc


def bucket_weight(c: str) -> float:
    return {"H": 1.0, "M": 0.6, "L": 0.2}.get(c.upper(), 0.0)


def overall_score(per_field: list[str]) -> float:
    """Mean weighted confidence across all fields. Returns 0..1."""
    if not per_field:
        return 0.0
    return sum(bucket_weight(c) for c in per_field) / len(per_field)

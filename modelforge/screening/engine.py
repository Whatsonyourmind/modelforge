"""Deal-screening engine — filter + rank a deal directory.

Operates on spec YAMLs (in pre-build form), so screening 1,000 deals doesn't
require building 1,000 workbooks.

Design:
    1. Walk a directory tree for *.yaml files
    2. For each, load YAML, extract a "screening summary" via convention
       (looks at well-known keys: sector, geography, deal_size, irr_base, etc.)
    3. Apply filter predicates (eq, lt, gt, in)
    4. Rank by weighted sum of normalized metrics
    5. Return top-N as ScreenResult objects

Convention for spec YAMLs to be screenable (optional `screening:` block):

    screening:
      sector: "industrials"
      geography: "EU/IT"
      deal_size_eur_m: 250
      vintage: 2026
      irr_base: 0.182
      irr_worst: 0.094
      leverage_x: 4.2
      ebitda_margin: 0.21
      dscr_base: 1.35
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


@dataclass
class ScreenCriteria:
    """Filters + ranking weights for a screen."""
    filters: dict[str, Any] = field(default_factory=dict)
    # Filter conventions:
    #   sector="industrials"                # eq
    #   ebitda_margin_min=0.20              # gte (suffix _min)
    #   leverage_x_max=5.0                  # lte (suffix _max)
    #   geography_in=["EU/IT", "EU/ES"]     # in (suffix _in)
    rank_by: dict[str, float] = field(default_factory=dict)
    # Weights: positive means "higher is better", negative means "lower is better"
    top_n: int = 25


@dataclass
class ScreenResult:
    """One deal that passes the screen."""
    spec_path: Path
    deal_id: str
    summary: dict[str, Any]
    score: float
    passes_all: bool


def _load_spec(path: Path) -> Optional[dict]:
    """Load a YAML spec; return None on parse error."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def _extract_screening_block(spec: dict) -> dict[str, Any]:
    """Extract a normalized screening summary from a spec dict.

    Looks in `spec.screening` first, then walks well-known top-level keys
    as fallback (sector, geography, etc.).
    """
    if not isinstance(spec, dict):
        return {}
    if "screening" in spec and isinstance(spec["screening"], dict):
        return dict(spec["screening"])

    # Fallback: try to construct from known top-level fields
    summary: dict[str, Any] = {}
    for key in ("sector", "geography", "vintage", "deal_size_eur_m", "deal_size_usd_m"):
        if key in spec:
            summary[key] = spec[key]
    return summary


def _apply_filter(summary: dict, key: str, value: Any) -> bool:
    """Apply a single filter predicate."""
    if key.endswith("_min"):
        base = key[:-4]
        v = summary.get(base)
        return v is not None and float(v) >= float(value)
    if key.endswith("_max"):
        base = key[:-4]
        v = summary.get(base)
        return v is not None and float(v) <= float(value)
    if key.endswith("_in"):
        base = key[:-3]
        v = summary.get(base)
        return v is not None and v in value
    # Default: equality
    return summary.get(key) == value


def _passes_all(summary: dict, filters: dict) -> bool:
    return all(_apply_filter(summary, k, v) for k, v in filters.items())


def _normalize(values: list[float]) -> dict[float, float]:
    """Min-max normalize a list to [0, 1]."""
    if not values:
        return {}
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return {v: 0.5 for v in values}
    return {v: (v - lo) / (hi - lo) for v in values}


def _score(summary: dict, rank_by: dict[str, float], norm_tables: dict) -> float:
    """Compute weighted normalized score for one deal."""
    score = 0.0
    for metric, weight in rank_by.items():
        v = summary.get(metric)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        # Use normalized value
        norm = norm_tables.get(metric, {}).get(fv, 0.5)
        # Negative weight inverts: lower-is-better
        if weight < 0:
            norm = 1.0 - norm
        score += abs(weight) * norm
    return score


def screen(
    spec_dir: str | Path,
    *,
    filters: Optional[dict[str, Any]] = None,
    rank_by: Optional[dict[str, float]] = None,
    top_n: int = 25,
    glob_pattern: str = "**/*.yaml",
) -> list[ScreenResult]:
    """Screen a directory tree of YAML specs.

    Args:
        spec_dir: Root directory to walk.
        filters: Filter predicates (see ScreenCriteria docs).
        rank_by: Ranking weights (positive = higher-better, negative = lower-better).
        top_n: Max results returned.
        glob_pattern: Glob for matching spec files.

    Returns:
        List of ScreenResult sorted by score descending.
    """
    filters = filters or {}
    rank_by = rank_by or {}
    spec_dir = Path(spec_dir)
    if not spec_dir.exists():
        return []

    # Pass 1: load all candidates that pass filters
    candidates: list[tuple[Path, dict]] = []
    for spec_path in spec_dir.glob(glob_pattern):
        spec = _load_spec(spec_path)
        if spec is None:
            continue
        summary = _extract_screening_block(spec)
        if not summary:
            continue
        if _passes_all(summary, filters):
            candidates.append((spec_path, summary))

    if not candidates:
        return []

    # Pass 2: build normalization tables per ranking metric
    norm_tables: dict[str, dict[float, float]] = {}
    if rank_by:
        for metric in rank_by:
            values: list[float] = []
            for _, summary in candidates:
                v = summary.get(metric)
                if v is None:
                    continue
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    continue
            norm_tables[metric] = _normalize(values)

    # Pass 3: score + sort
    results: list[ScreenResult] = []
    for spec_path, summary in candidates:
        score = _score(summary, rank_by, norm_tables)
        deal_id = summary.get("deal_id") or spec_path.stem
        results.append(ScreenResult(
            spec_path=spec_path,
            deal_id=str(deal_id),
            summary=summary,
            score=score,
            passes_all=True,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]

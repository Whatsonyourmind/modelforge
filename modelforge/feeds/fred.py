"""FRED — Federal Reserve Economic Data adapter (free, no API key required).

Free public data feed. Used for US macro inputs (Treasury rates, SOFR,
inflation, unemployment, GDP). API docs: https://fred.stlouisfed.org/docs/api

Common series IDs:
    DGS10  — 10-year Treasury constant maturity
    DGS2   — 2-year Treasury
    SOFR   — Secured Overnight Financing Rate
    CPIAUCSL — Consumer Price Index for All Urban Consumers
    UNRATE — Civilian Unemployment Rate
    GDP    — Gross Domestic Product
    DFEDTARU — Federal Funds Target Upper Bound

Usage::

    from modelforge.feeds.fred import fetch_series
    latest_10y = fetch_series("DGS10", limit=1)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from modelforge.feeds.cache import get_cache

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(
    series_id: str,
    *,
    api_key: Optional[str] = None,
    limit: int = 100,
    sort_order: str = "desc",
    cache_ttl_seconds: int = 86400,
) -> list[dict]:
    """Fetch a FRED economic series.

    Args:
        series_id: FRED series ID (e.g. "DGS10", "SOFR", "CPIAUCSL").
        api_key: FRED API key. Free at https://fred.stlouisfed.org/docs/api/api_key.html.
                 If None, uses the free public endpoint (rate-limited).
        limit: Max observations to return.
        sort_order: "desc" (newest first) or "asc".
        cache_ttl_seconds: Cache TTL (default 24h — FRED updates infrequently).

    Returns:
        List of dicts with keys: date, value, realtime_start, realtime_end.
    """
    cache = get_cache()
    cache_key = f"fred:{series_id}:{limit}:{sort_order}"
    cached = cache.get(cache_key, ttl_seconds=cache_ttl_seconds)
    if cached is not None:
        return cached

    params = {
        "series_id": series_id,
        "file_type": "json",
        "limit": str(limit),
        "sort_order": sort_order,
    }
    if api_key:
        params["api_key"] = api_key

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"FRED HTTP {e.code} on {series_id}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"FRED network error: {e.reason}") from e

    obs = data.get("observations", [])
    # Filter out missing values (FRED uses "." for missing)
    clean = [
        {
            "date": o["date"],
            "value": float(o["value"]) if o["value"] != "." else None,
            "realtime_start": o.get("realtime_start"),
            "realtime_end": o.get("realtime_end"),
        }
        for o in obs
        if o.get("value") not in (None, ".")
    ]
    cache.set(cache_key, clean)
    return clean


def latest_value(series_id: str, *, api_key: Optional[str] = None) -> tuple[str, float]:
    """Convenience: return the single most recent (date, value) for a series."""
    series = fetch_series(series_id, api_key=api_key, limit=1)
    if not series:
        raise RuntimeError(f"FRED series {series_id} has no observations")
    o = series[0]
    return o["date"], o["value"]


# Common series convenience accessors (cached)
def us_10y_treasury(*, api_key: Optional[str] = None) -> tuple[str, float]:
    """Latest 10-year Treasury constant maturity yield (% annual)."""
    return latest_value("DGS10", api_key=api_key)


def us_2y_treasury(*, api_key: Optional[str] = None) -> tuple[str, float]:
    """Latest 2-year Treasury yield (% annual)."""
    return latest_value("DGS2", api_key=api_key)


def sofr(*, api_key: Optional[str] = None) -> tuple[str, float]:
    """Latest SOFR (Secured Overnight Financing Rate, % annual)."""
    return latest_value("SOFR", api_key=api_key)


def fed_funds_upper(*, api_key: Optional[str] = None) -> tuple[str, float]:
    """Latest Federal Funds Target Upper Bound (% annual)."""
    return latest_value("DFEDTARU", api_key=api_key)


def us_cpi_yoy(*, api_key: Optional[str] = None) -> float:
    """US CPI YoY % change (latest)."""
    series = fetch_series("CPIAUCSL", api_key=api_key, limit=13)
    if len(series) < 13:
        raise RuntimeError("CPI series too short to compute YoY")
    latest = series[0]["value"]
    yago = series[12]["value"]
    if yago is None or yago == 0:
        raise RuntimeError("CPI YoY undefined")
    return (latest / yago - 1) * 100

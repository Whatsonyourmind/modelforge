"""Yahoo Finance adapter — free public quotes + historical (no API key).

Uses Yahoo's public v8 chart endpoint. Not officially supported by Yahoo,
so brittle for production — but ubiquitous for prototyping and free.

For production use cases, prefer Bloomberg / FactSet / Refinitiv (Phase B).

Usage::

    from modelforge.feeds.yahoo import quote, history
    px = quote("AAPL")  # current price
    h = history("AAPL", interval="1d", range="1y")
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Literal, Optional

from modelforge.feeds.cache import get_cache

USER_AGENT = "Mozilla/5.0 (compatible; modelforge/0.9)"
BASE_URL = "https://query2.finance.yahoo.com/v8/finance/chart"

Interval = Literal["1d", "5d", "1wk", "1mo", "3mo"]
Range = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]


def _fetch_chart(symbol: str, interval: Interval, range_: Range) -> dict:
    params = {"interval": interval, "range": range_}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/{symbol}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Yahoo HTTP {e.code} on {symbol}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Yahoo network error: {e.reason}") from e


def quote(symbol: str, *, cache_ttl_seconds: int = 60) -> dict:
    """Latest quote: price, currency, exchange, day-change.

    Args:
        symbol: Yahoo ticker (e.g. "AAPL", "GOOG", "BNP.PA" for Paris-listed).
        cache_ttl_seconds: Cache TTL (default 60s for live quotes).
    """
    cache = get_cache()
    cache_key = f"yahoo:quote:{symbol}"
    cached = cache.get(cache_key, ttl_seconds=cache_ttl_seconds)
    if cached is not None:
        return cached

    data = _fetch_chart(symbol, "1d", "1d")
    result = data.get("chart", {}).get("result", [])
    if not result:
        raise RuntimeError(f"No quote for {symbol}")
    meta = result[0].get("meta", {})

    out = {
        "symbol": meta.get("symbol"),
        "price": meta.get("regularMarketPrice"),
        "previous_close": meta.get("chartPreviousClose"),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "timezone": meta.get("exchangeTimezoneName"),
    }
    if out["price"] and out["previous_close"]:
        out["change_pct"] = (out["price"] / out["previous_close"] - 1) * 100
    cache.set(cache_key, out)
    return out


def history(
    symbol: str,
    *,
    interval: Interval = "1d",
    range_: Range = "1y",
    cache_ttl_seconds: int = 3600,
) -> list[dict]:
    """Historical OHLCV for a symbol.

    Returns:
        List of {date, open, high, low, close, volume}.
    """
    cache = get_cache()
    cache_key = f"yahoo:hist:{symbol}:{interval}:{range_}"
    cached = cache.get(cache_key, ttl_seconds=cache_ttl_seconds)
    if cached is not None:
        return cached

    data = _fetch_chart(symbol, interval, range_)
    result = data.get("chart", {}).get("result", [])
    if not result:
        return []
    r = result[0]
    timestamps = r.get("timestamp", [])
    quote_data = (r.get("indicators", {}).get("quote") or [{}])[0]

    from datetime import datetime, timezone
    rows = []
    for i, ts in enumerate(timestamps):
        rows.append({
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
            "open": (quote_data.get("open") or [None] * len(timestamps))[i],
            "high": (quote_data.get("high") or [None] * len(timestamps))[i],
            "low": (quote_data.get("low") or [None] * len(timestamps))[i],
            "close": (quote_data.get("close") or [None] * len(timestamps))[i],
            "volume": (quote_data.get("volume") or [None] * len(timestamps))[i],
        })
    cache.set(cache_key, rows)
    return rows

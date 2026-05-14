"""Alpha Vantage adapter — free tier 25 calls/day, paid tiers up to 600/min.

API key required (free signup at https://www.alphavantage.co/support/#api-key).
Set ``ALPHAVANTAGE_API_KEY`` env var or pass ``api_key=`` to functions.

Useful endpoints we wrap:
    TIME_SERIES_DAILY_ADJUSTED — daily OHLCV w/ split + dividend adjustments
    FX_DAILY                    — daily FX rates
    REAL_GDP                    — US quarterly real GDP
    TREASURY_YIELD              — US Treasury yields (2yr/10yr/30yr)
    CPI                         — US CPI
    OVERVIEW                    — company fundamentals (FCF, margins, etc.)

For Bloomberg/FactSet/Capital IQ-equivalent data (real-time prices, options
chains, corporate actions), AlphaVantage is NOT the answer — Phase-B
partnerships are.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Literal, Optional

from modelforge.feeds.cache import get_cache

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://www.alphavantage.co/query"


def _api_key(provided: Optional[str]) -> str:
    if provided:
        return provided
    key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not key:
        raise RuntimeError(
            "Alpha Vantage requires an API key. "
            "Set ALPHAVANTAGE_API_KEY or pass api_key= explicitly. "
            "Free key at https://www.alphavantage.co/support/#api-key"
        )
    return key


def _get(params: dict, cache_ttl: int) -> dict:
    cache = get_cache()
    cache_key = "av:" + json.dumps(params, sort_keys=True)
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"AlphaVantage HTTP {e.code}: {e.reason}") from e

    # Alpha Vantage returns errors as JSON payloads with "Error Message" or "Note" keys
    if "Error Message" in data:
        raise RuntimeError(f"AlphaVantage error: {data['Error Message']}")
    if "Note" in data:
        raise RuntimeError(f"AlphaVantage rate limit: {data['Note']}")

    cache.set(cache_key, data)
    return data


def daily_prices(symbol: str, *, api_key: Optional[str] = None, full: bool = False) -> list[dict]:
    """Daily OHLCV w/ split + dividend adjustments.

    Returns list of {date, open, high, low, close, adjusted_close, volume, dividend, split_coeff}.
    """
    key = _api_key(api_key)
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full" if full else "compact",
        "apikey": key,
    }
    data = _get(params, cache_ttl=3600)
    series = data.get("Time Series (Daily)", {})
    rows = []
    for date, row in sorted(series.items(), reverse=True):
        rows.append({
            "date": date,
            "open": float(row.get("1. open", 0)),
            "high": float(row.get("2. high", 0)),
            "low": float(row.get("3. low", 0)),
            "close": float(row.get("4. close", 0)),
            "adjusted_close": float(row.get("5. adjusted close", 0)),
            "volume": int(row.get("6. volume", 0)),
            "dividend": float(row.get("7. dividend amount", 0)),
            "split_coeff": float(row.get("8. split coefficient", 1)),
        })
    return rows


def fx_daily(from_ccy: str, to_ccy: str, *, api_key: Optional[str] = None) -> list[dict]:
    """Daily FX rates."""
    key = _api_key(api_key)
    params = {
        "function": "FX_DAILY",
        "from_symbol": from_ccy,
        "to_symbol": to_ccy,
        "apikey": key,
    }
    data = _get(params, cache_ttl=3600)
    series = data.get("Time Series FX (Daily)", {})
    return [
        {"date": d, "open": float(r["1. open"]), "high": float(r["2. high"]),
         "low": float(r["3. low"]), "close": float(r["4. close"])}
        for d, r in sorted(series.items(), reverse=True)
    ]


def treasury_yield(
    maturity: Literal["3month", "2year", "5year", "7year", "10year", "30year"],
    *,
    interval: Literal["daily", "weekly", "monthly"] = "monthly",
    api_key: Optional[str] = None,
) -> list[dict]:
    """US Treasury yield history."""
    key = _api_key(api_key)
    params = {"function": "TREASURY_YIELD", "interval": interval, "maturity": maturity, "apikey": key}
    data = _get(params, cache_ttl=86400)
    return data.get("data", [])


def company_overview(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Fundamentals snapshot — margins, growth, valuation ratios."""
    key = _api_key(api_key)
    params = {"function": "OVERVIEW", "symbol": symbol, "apikey": key}
    return _get(params, cache_ttl=86400)

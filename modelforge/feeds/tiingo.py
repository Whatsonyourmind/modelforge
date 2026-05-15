"""Tiingo adapter — institutional-grade EOD + IEX live + crypto + news.

Why ship this: Tiingo is what quant shops use when they outgrow Yahoo
but can't justify Polygon's $200/mo for live data. EOD coverage extends
to 1962 with corporate-action adjustments validated against CRSP. The
fundamentals product is reconciled against SEC EDGAR, not scraped.

Free tier: 50 req/hr, 1000 req/day. Power $10/mo unlocks unlimited
EOD + 8 yrs intraday history.

API docs: https://www.tiingo.com/documentation/general/overview

Auth: ``TIINGO_API_KEY`` env var or ``api_key=`` arg.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from modelforge.feeds.cache import get_cache
from modelforge.feeds.provider import (
    AuthRequired,
    Bar,
    Provider,
    ProviderError,
    Quote,
)

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://api.tiingo.com"


def _api_key(provided: Optional[str]) -> str:
    if provided:
        return provided
    key = os.environ.get("TIINGO_API_KEY")
    if not key:
        raise AuthRequired(
            "Tiingo requires TIINGO_API_KEY env var or api_key=. "
            "Free key: https://www.tiingo.com/account/api/token"
        )
    return key


def _get(path: str, params: dict, *, api_key: Optional[str], cache_ttl: int) -> Any:
    key = _api_key(api_key)
    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": f"Token {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    cache = get_cache()
    cache_key = f"tiingo:{path}:" + json.dumps(params, sort_keys=True)
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}{path}?{query}" if params else f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise AuthRequired(f"Tiingo auth rejected ({e.code})") from e
        raise ProviderError(f"Tiingo HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Tiingo network error: {e.reason}") from e

    if isinstance(data, dict) and data.get("detail") and "error" in str(data.get("detail", "")).lower():
        raise ProviderError(f"Tiingo: {data['detail']}")
    cache.set(cache_key, data)
    return data


# ─── direct helpers ─────────────────────────────────────────────────────────


def metadata(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Ticker metadata: name, exchange, start/end dates of coverage."""
    return _get(f"/tiingo/daily/{symbol.lower()}", {}, api_key=api_key, cache_ttl=86400)


def end_of_day(
    symbol: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    """EOD OHLCV with split + dividend adjustments."""
    params: dict[str, Any] = {"format": "json"}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    data = _get(
        f"/tiingo/daily/{symbol.lower()}/prices",
        params,
        api_key=api_key,
        cache_ttl=3600,
    )
    return data if isinstance(data, list) else []


def iex_last(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Last IEX quote (free tier delayed; paid tier real-time)."""
    rows = _get(f"/iex/{symbol.lower()}", {}, api_key=api_key, cache_ttl=60)
    if isinstance(rows, list) and rows:
        return rows[0]
    return rows if isinstance(rows, dict) else {}


def fundamentals_meta(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Fundamentals metadata — coverage start, statementType."""
    return _get(f"/tiingo/fundamentals/{symbol.lower()}/meta", {}, api_key=api_key, cache_ttl=86400)


def fundamentals_daily(symbol: str, *, api_key: Optional[str] = None) -> list[dict]:
    """Daily-frequency derived ratios (P/E, EV/EBITDA TTM)."""
    data = _get(
        f"/tiingo/fundamentals/{symbol.lower()}/daily",
        {},
        api_key=api_key,
        cache_ttl=86400,
    )
    return data if isinstance(data, list) else []


def crypto_top(*, tickers: Optional[list[str]] = None, api_key: Optional[str] = None) -> list[dict]:
    """Live crypto top-of-book (BTCUSD, ETHUSD, …)."""
    params: dict[str, Any] = {}
    if tickers:
        params["tickers"] = ",".join(tickers)
    data = _get("/tiingo/crypto/top", params, api_key=api_key, cache_ttl=60)
    return data if isinstance(data, list) else []


def fx_rate(pair: str, *, api_key: Optional[str] = None) -> dict:
    """Latest FX rate for a pair like 'eurusd' or 'gbpjpy'."""
    rows = _get(f"/tiingo/fx/{pair.lower()}/top", {}, api_key=api_key, cache_ttl=60)
    if isinstance(rows, list) and rows:
        return rows[0]
    return {}


def news(
    *,
    tickers: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    limit: int = 20,
    api_key: Optional[str] = None,
) -> list[dict]:
    params: dict[str, Any] = {"limit": limit}
    if tickers:
        params["tickers"] = ",".join(tickers)
    if tags:
        params["tags"] = ",".join(tags)
    data = _get("/tiingo/news", params, api_key=api_key, cache_ttl=600)
    return data if isinstance(data, list) else []


# ─── Provider adapter ───────────────────────────────────────────────────────


class TiingoProvider(Provider):
    name = "tiingo"
    tier = "institutional"
    requires_auth = True

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key

    def is_available(self) -> bool:
        try:
            _api_key(self._api_key)
            return True
        except AuthRequired:
            return False

    def quote(self, symbol: str) -> Quote:
        d = iex_last(symbol, api_key=self._api_key)
        last = d.get("last") or d.get("tngoLast") or d.get("close")
        prev = d.get("prevClose")
        return Quote(
            symbol=symbol.upper(),
            price=float(last) if last is not None else 0.0,
            previous_close=prev,
            bid=d.get("bidPrice"),
            ask=d.get("askPrice"),
            change_pct=(last / prev - 1) * 100 if last and prev else None,
            volume=d.get("volume"),
            source="tiingo",
        )

    def history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 250,
    ) -> list[Bar]:
        rows = end_of_day(
            symbol, start_date=start, end_date=end, api_key=self._api_key
        )[:limit]
        return [
            Bar(
                date=str(r.get("date", ""))[:10],
                open=r.get("adjOpen") or r.get("open"),
                high=r.get("adjHigh") or r.get("high"),
                low=r.get("adjLow") or r.get("low"),
                close=r.get("adjClose") or r.get("close"),
                volume=r.get("adjVolume") or r.get("volume"),
            )
            for r in rows
        ]

"""Finnhub adapter — fundamentals, estimates, insider trading, news sentiment.

Why ship this: Finnhub is the go-to for analyst-estimate consensus and
insider-transaction filings. Hedge funds use it as the cheap signal
layer over Bloomberg. Free tier 60 calls/min covers individual analysts.

Strongest endpoints we expose:
* /quote — real-time quote (free)
* /stock/financials-reported — as-reported fundamentals (free)
* /stock/recommendation — analyst buy/hold/sell consensus
* /stock/insider-transactions — Form 4 (US) + equivalents
* /news-sentiment — proprietary NLP sentiment per ticker
* /calendar/earnings — earnings calendar
* /forex/rates — FX cross rates

API docs: https://finnhub.io/docs/api

Auth: ``FINNHUB_API_KEY`` env var or ``api_key=`` arg.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Literal, Optional

from modelforge.feeds.cache import get_cache
from modelforge.feeds.provider import (
    AuthRequired,
    Bar,
    Fundamentals,
    Provider,
    ProviderError,
    Quote,
)

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://finnhub.io/api/v1"


def _api_key(provided: Optional[str]) -> str:
    if provided:
        return provided
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        raise AuthRequired(
            "Finnhub requires FINNHUB_API_KEY env var or api_key=. "
            "Free key: https://finnhub.io/register"
        )
    return key


def _get(path: str, params: dict, *, api_key: Optional[str], cache_ttl: int) -> Any:
    key = _api_key(api_key)
    headers = {"User-Agent": USER_AGENT, "X-Finnhub-Token": key}
    cache = get_cache()
    cache_key = f"finnhub:{path}:" + json.dumps(params, sort_keys=True)
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
            raise AuthRequired(f"Finnhub auth rejected ({e.code})") from e
        raise ProviderError(f"Finnhub HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Finnhub network error: {e.reason}") from e

    cache.set(cache_key, data)
    return data


# ─── direct helpers ─────────────────────────────────────────────────────────


def quote_raw(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Real-time quote: c=current, h=high, l=low, o=open, pc=prev close."""
    return _get("/quote", {"symbol": symbol.upper()}, api_key=api_key, cache_ttl=60)


def company_profile(symbol: str, *, api_key: Optional[str] = None) -> dict:
    return _get("/stock/profile2", {"symbol": symbol.upper()}, api_key=api_key, cache_ttl=86400)


def basic_financials(
    symbol: str,
    *,
    metric: str = "all",
    api_key: Optional[str] = None,
) -> dict:
    """Latest TTM ratios — P/E, ROE, debt/equity, etc."""
    return _get(
        "/stock/metric",
        {"symbol": symbol.upper(), "metric": metric},
        api_key=api_key,
        cache_ttl=86400,
    )


def financials_reported(
    symbol: str,
    *,
    freq: Literal["annual", "quarterly"] = "annual",
    api_key: Optional[str] = None,
) -> dict:
    """As-reported financial statements (free tier)."""
    return _get(
        "/stock/financials-reported",
        {"symbol": symbol.upper(), "freq": freq},
        api_key=api_key,
        cache_ttl=86400,
    )


def recommendation_trends(symbol: str, *, api_key: Optional[str] = None) -> list[dict]:
    """Buy/hold/sell consensus over time."""
    data = _get(
        "/stock/recommendation",
        {"symbol": symbol.upper()},
        api_key=api_key,
        cache_ttl=86400,
    )
    return data if isinstance(data, list) else []


def insider_transactions(
    symbol: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    """SEC Form 4 / equivalent insider trading filings."""
    params: dict[str, Any] = {"symbol": symbol.upper()}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    data = _get("/stock/insider-transactions", params, api_key=api_key, cache_ttl=3600)
    return (data or {}).get("data", []) if isinstance(data, dict) else []


def news_sentiment(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Finnhub's NLP sentiment score per ticker."""
    return _get(
        "/news-sentiment",
        {"symbol": symbol.upper()},
        api_key=api_key,
        cache_ttl=3600,
    )


def earnings_calendar(
    *,
    from_date: str,
    to_date: str,
    symbol: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    params: dict[str, Any] = {"from": from_date, "to": to_date}
    if symbol:
        params["symbol"] = symbol.upper()
    data = _get("/calendar/earnings", params, api_key=api_key, cache_ttl=3600)
    return (data or {}).get("earningsCalendar", []) if isinstance(data, dict) else []


def forex_rates(*, base: str = "USD", api_key: Optional[str] = None) -> dict:
    """Latest FX cross rates from a base currency."""
    return _get("/forex/rates", {"base": base.upper()}, api_key=api_key, cache_ttl=300)


def candles(
    symbol: str,
    *,
    resolution: Literal["1", "5", "15", "30", "60", "D", "W", "M"] = "D",
    from_ts: int,
    to_ts: int,
    api_key: Optional[str] = None,
) -> dict:
    """OHLCV candles. Note: `from`/`to` are unix epoch seconds."""
    return _get(
        "/stock/candle",
        {"symbol": symbol.upper(), "resolution": resolution, "from": from_ts, "to": to_ts},
        api_key=api_key,
        cache_ttl=3600,
    )


# ─── Provider adapter ───────────────────────────────────────────────────────


class FinnhubProvider(Provider):
    name = "finnhub"
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
        d = quote_raw(symbol, api_key=self._api_key)
        price = d.get("c") or 0.0
        prev = d.get("pc")
        return Quote(
            symbol=symbol.upper(),
            price=float(price),
            previous_close=prev,
            change_pct=(price / prev - 1) * 100 if prev else None,
            source="finnhub",
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
        from datetime import date, datetime, timedelta, timezone
        end_d = date.fromisoformat(end) if end else date.today()
        start_d = date.fromisoformat(start) if start else end_d - timedelta(days=int(limit * 1.5))
        from_ts = int(datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        to_ts = int(datetime.combine(end_d, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        res_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D", "1wk": "W", "1mo": "M"}
        d = candles(
            symbol,
            resolution=res_map.get(interval, "D"),  # type: ignore[arg-type]
            from_ts=from_ts,
            to_ts=to_ts,
            api_key=self._api_key,
        )
        if d.get("s") != "ok":
            return []
        out: list[Bar] = []
        ts = d.get("t") or []
        opens = d.get("o") or []
        highs = d.get("h") or []
        lows = d.get("l") or []
        closes = d.get("c") or []
        vols = d.get("v") or []
        for i, t in enumerate(ts):
            out.append(Bar(
                date=datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"),
                open=opens[i] if i < len(opens) else None,
                high=highs[i] if i < len(highs) else None,
                low=lows[i] if i < len(lows) else None,
                close=closes[i] if i < len(closes) else None,
                volume=vols[i] if i < len(vols) else None,
            ))
        return out

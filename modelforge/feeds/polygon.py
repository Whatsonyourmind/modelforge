"""Polygon.io adapter — institutional-tier US equities, options, FX, crypto.

Why ship this: Polygon is the most-used Bloomberg substitute for quant
shops priced out of a Terminal seat ($24k/yr) but who need real (not
Yahoo-scraped) consolidated tape data. Same WebSockets that power
Robinhood and Webull underneath.

Free tier: 5 requests/min, EOD only. Paid starts $29/mo for 15-min
delayed and goes up to $2k/mo for full real-time consolidated tape.

API docs: https://polygon.io/docs/stocks/getting-started

Auth: ``POLYGON_API_KEY`` env var or ``api_key=`` arg.
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
BASE_URL = "https://api.polygon.io"


def _api_key(provided: Optional[str]) -> str:
    if provided:
        return provided
    key = os.environ.get("POLYGON_API_KEY")
    if not key:
        raise AuthRequired(
            "Polygon requires POLYGON_API_KEY env var or api_key=. "
            "Free key: https://polygon.io/dashboard/api-keys"
        )
    return key


def _get(path: str, params: dict, *, api_key: Optional[str], cache_ttl: int) -> dict:
    key = _api_key(api_key)
    params = {**params, "apiKey": key}
    cache = get_cache()
    # Strip apiKey from cache key so cache survives key rotation
    cache_params = {k: v for k, v in params.items() if k != "apiKey"}
    cache_key = f"polygon:{path}:" + json.dumps(cache_params, sort_keys=True)
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}{path}?{query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            raise AuthRequired(f"Polygon auth rejected ({e.code})") from e
        raise ProviderError(f"Polygon HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Polygon network error: {e.reason}") from e

    status = data.get("status")
    if status not in ("OK", "DELAYED", None):
        raise ProviderError(f"Polygon error: {data.get('error') or status}")
    cache.set(cache_key, data)
    return data


# ─── direct helpers ─────────────────────────────────────────────────────────


def previous_close(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Previous-day OHLCV for a ticker.

    Endpoint: /v2/aggs/ticker/{ticker}/prev
    """
    data = _get(
        f"/v2/aggs/ticker/{symbol.upper()}/prev",
        {"adjusted": "true"},
        api_key=api_key,
        cache_ttl=300,
    )
    results = data.get("results") or []
    if not results:
        raise ProviderError(f"Polygon: no previous close for {symbol}")
    r = results[0]
    return {
        "symbol": symbol.upper(),
        "open": r.get("o"),
        "high": r.get("h"),
        "low": r.get("l"),
        "close": r.get("c"),
        "volume": r.get("v"),
        "vwap": r.get("vw"),
        "as_of_ms": r.get("t"),
    }


def aggregates(
    symbol: str,
    *,
    multiplier: int = 1,
    timespan: Literal["minute", "hour", "day", "week", "month"] = "day",
    from_date: str,
    to_date: str,
    api_key: Optional[str] = None,
    limit: int = 5000,
) -> list[dict]:
    """Aggregate (OHLCV) bars for a ticker over a date range.

    Endpoint: /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
    """
    path = f"/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
    data = _get(
        path,
        {"adjusted": "true", "sort": "asc", "limit": limit},
        api_key=api_key,
        cache_ttl=3600,
    )
    from datetime import datetime, timezone
    out = []
    for r in data.get("results") or []:
        ts = r.get("t")
        date = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d") if ts else None
        out.append({
            "date": date,
            "open": r.get("o"),
            "high": r.get("h"),
            "low": r.get("l"),
            "close": r.get("c"),
            "volume": r.get("v"),
            "vwap": r.get("vw"),
            "transactions": r.get("n"),
        })
    return out


def ticker_details(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Reference data for a ticker — sector, market cap, share count, etc.

    Endpoint: /v3/reference/tickers/{ticker}
    """
    data = _get(
        f"/v3/reference/tickers/{symbol.upper()}",
        {},
        api_key=api_key,
        cache_ttl=86400,
    )
    return data.get("results") or {}


def financials(
    symbol: str,
    *,
    api_key: Optional[str] = None,
    timeframe: Literal["annual", "quarterly", "ttm"] = "annual",
    limit: int = 5,
) -> list[dict]:
    """Financial statements (Polygon's StockFinancials v2 vX endpoint).

    Endpoint: /vX/reference/financials
    """
    data = _get(
        "/vX/reference/financials",
        {"ticker": symbol.upper(), "timeframe": timeframe, "limit": limit},
        api_key=api_key,
        cache_ttl=86400,
    )
    return data.get("results") or []


# ─── Provider adapter ───────────────────────────────────────────────────────


class PolygonProvider(Provider):
    name = "polygon"
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
        d = previous_close(symbol, api_key=self._api_key)
        return Quote(
            symbol=d["symbol"],
            price=d["close"],
            previous_close=d.get("open"),
            volume=d.get("volume"),
            change_pct=(
                (d["close"] / d["open"] - 1) * 100
                if d.get("close") and d.get("open") else None
            ),
            source="polygon",
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
        # Map our generic interval to polygon (multiplier, timespan)
        mapping = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "1h": (1, "hour"),
            "1d": (1, "day"),
            "1wk": (1, "week"),
            "1mo": (1, "month"),
        }
        mult, span = mapping.get(interval, (1, "day"))
        from datetime import date, timedelta
        end = end or date.today().isoformat()
        if not start:
            # ~limit business days back
            start = (date.fromisoformat(end) - timedelta(days=int(limit * 1.5))).isoformat()
        rows = aggregates(
            symbol,
            multiplier=mult,
            timespan=span,
            from_date=start,
            to_date=end,
            api_key=self._api_key,
            limit=limit,
        )
        return [
            Bar(date=r["date"], open=r["open"], high=r["high"],
                low=r["low"], close=r["close"], volume=r["volume"])
            for r in rows
        ]

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        tf: Literal["annual", "quarterly", "ttm"] = "annual" if period == "annual" else "quarterly"
        records = financials(symbol, timeframe=tf, limit=limit, api_key=self._api_key)
        out: list[Fundamentals] = []
        for r in records:
            fin = r.get("financials") or {}
            inc = fin.get("income_statement") or {}
            bs = fin.get("balance_sheet") or {}
            cf = fin.get("cash_flow_statement") or {}
            period_end = r.get("end_date")
            year = (period_end or "")[:4]
            label = f"FY{year}" if period == "annual" else f"{period_end}"
            out.append(Fundamentals(
                symbol=symbol.upper(),
                period=label,
                period_end=period_end,
                currency=(inc.get("revenues") or {}).get("unit"),
                revenue=_v(inc, "revenues"),
                ebit=_v(inc, "operating_income_loss"),
                net_income=_v(inc, "net_income_loss"),
                eps=_v(inc, "basic_earnings_per_share"),
                total_assets=_v(bs, "assets"),
                total_debt=_v(bs, "long_term_debt"),
                cash=_v(bs, "cash"),
                operating_cash_flow=_v(cf, "net_cash_flow_from_operating_activities"),
                source="polygon",
            ))
        return out


def _v(section: dict, key: str) -> Optional[float]:
    item = section.get(key)
    if isinstance(item, dict) and "value" in item:
        try:
            return float(item["value"])
        except (TypeError, ValueError):
            return None
    return None

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


# ─── Provider class (registry-routable, free key required) ──────────────────


from modelforge.feeds.provider import (  # noqa: E402
    AuthRequired,
    Bar,
    Fundamentals,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
)


class AlphaVantageProvider(Provider):
    """Alpha Vantage — free key (25 calls/day) → quote, history, fundamentals.

    Free key signup: https://www.alphavantage.co/support/#api-key
    Set ALPHAVANTAGE_API_KEY env var (or pass via constructor).

    Free tier rate limit (25 req/day) makes this best-suited as a
    *fallback* provider when Yahoo's anti-bot is acting up. For
    production-grade equity data, prefer Polygon/FMP (paid) or
    Bloomberg/FactSet/Refinitiv (Phase-B).

    Capability map:
        - ``quote(symbol)``        → most-recent close from daily series
        - ``history(symbol)``      → daily OHLCV bars (full or compact)
        - ``fundamentals(symbol)`` → company overview snapshot (1 row)
    """

    name = "alphavantage"
    tier = "institutional"  # free-tier, but quant-grade reliability with key
    requires_auth = True

    def is_available(self) -> bool:
        return bool(os.environ.get("ALPHAVANTAGE_API_KEY"))

    def quote(self, symbol: str) -> Quote:
        if not self.is_available():
            raise AuthRequired(
                "AlphaVantageProvider needs ALPHAVANTAGE_API_KEY (free at "
                "https://www.alphavantage.co/support/#api-key)"
            )
        try:
            rows = daily_prices(symbol)
        except RuntimeError as e:
            raise ProviderError(str(e)) from e
        if not rows:
            raise ProviderError(f"AlphaVantage: no daily data for {symbol}")
        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        change_pct = None
        if prev and prev.get("close"):
            change_pct = (latest["close"] / prev["close"] - 1) * 100
        return Quote(
            symbol=symbol,
            price=float(latest["close"]),
            previous_close=float(prev["close"]) if prev else None,
            change_pct=change_pct,
            volume=latest.get("volume"),
            as_of=latest.get("date"),
            source="alphavantage",
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
        if not self.is_available():
            raise AuthRequired("AlphaVantageProvider needs ALPHAVANTAGE_API_KEY")
        try:
            full = limit > 100
            rows = daily_prices(symbol, full=full)
        except RuntimeError as e:
            raise ProviderError(str(e)) from e
        bars = [
            Bar(
                date=r["date"],
                open=r["open"], high=r["high"], low=r["low"],
                close=r.get("adjusted_close") or r["close"],
                volume=r.get("volume"),
            )
            for r in rows
        ]
        bars.reverse()  # chronological
        if start:
            bars = [b for b in bars if b.date >= start]
        if end:
            bars = [b for b in bars if b.date <= end]
        return bars[-limit:]

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        if not self.is_available():
            raise AuthRequired("AlphaVantageProvider needs ALPHAVANTAGE_API_KEY")
        try:
            ov = company_overview(symbol)
        except RuntimeError as e:
            raise ProviderError(str(e)) from e
        if not ov or "Symbol" not in ov:
            raise ProviderError(f"AlphaVantage OVERVIEW empty for {symbol}")

        def _f(k: str) -> Optional[float]:
            v = ov.get(k)
            if v in (None, "", "None", "-"):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        # AlphaVantage OVERVIEW gives company-level TTM snapshot — one Fundamentals row
        return [
            Fundamentals(
                symbol=symbol,
                period=ov.get("LatestQuarter", "TTM"),
                period_end=ov.get("LatestQuarter"),
                currency=ov.get("Currency"),
                revenue=_f("RevenueTTM"),
                ebit=_f("OperatingIncomeTTM") or _f("EBIT"),
                ebitda=_f("EBITDA"),
                net_income=_f("NetIncomeTTM"),
                eps=_f("EPS"),
                total_assets=None,  # OVERVIEW doesn't include
                total_debt=None,
                cash=None,
                operating_cash_flow=_f("OperatingCashflowTTM"),
                capex=None,
                free_cash_flow=_f("FreeCashflowTTM"),
                shares_diluted=_f("SharesOutstanding"),
                source="alphavantage",
            )
        ][:limit]

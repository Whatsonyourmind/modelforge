"""Yahoo Finance adapter — free public quotes + historical + fundamentals (no API key).

Uses Yahoo's public v8 chart endpoint and v10 quoteSummary endpoint.
Not officially supported by Yahoo, so brittle for production — but
ubiquitous for prototyping, screening, and free.

For production use cases, prefer Bloomberg / FactSet / Refinitiv (Phase B).

Usage (low-level)::

    from modelforge.feeds.yahoo import quote, history
    px = quote("AAPL")
    h = history("AAPL", interval="1d", range="1y")

Usage (Provider interface, registry-routable)::

    from modelforge.feeds import registry
    q = registry.quote("AAPL", prefer="yahoo")        # Quote dataclass
    fs = registry.fundamentals("AAPL", prefer="yahoo", limit=4)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Literal, Optional

from modelforge.feeds.cache import get_cache
from modelforge.feeds.provider import (
    Bar,
    Entity,
    Fundamentals,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
)

USER_AGENT = "Mozilla/5.0 (compatible; modelforge/0.9)"
BASE_URL = "https://query2.finance.yahoo.com/v8/finance/chart"
SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"

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


_CRUMB_CACHE: dict[str, Any] = {"cookie": None, "crumb": None}


def _yahoo_crumb() -> tuple[Optional[str], Optional[str]]:
    """Fetch (cookie, crumb) pair required by Yahoo's quoteSummary endpoint.

    Yahoo's anti-bot requires a one-time cookie set via fc.yahoo.com
    plus a per-cookie crumb token from getcrumb. Cached process-lifetime.
    Returns (None, None) on failure — caller should then surface the
    underlying ProviderError without crumb (will likely 401).
    """
    if _CRUMB_CACHE["cookie"] and _CRUMB_CACHE["crumb"]:
        return _CRUMB_CACHE["cookie"], _CRUMB_CACHE["crumb"]
    try:
        # Step 1: trigger cookie issuance
        req = urllib.request.Request(
            "https://fc.yahoo.com/",
            headers={"User-Agent": USER_AGENT},
        )
        cookie_value: Optional[str] = None
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                set_cookie = resp.headers.get("set-cookie") or resp.headers.get("Set-Cookie")
                if set_cookie:
                    # Take only the cookie name=value, drop attrs
                    cookie_value = set_cookie.split(";")[0]
        except urllib.error.HTTPError as e:
            # 404 still sets cookie
            sc = e.headers.get("set-cookie") or e.headers.get("Set-Cookie") or ""
            if sc:
                cookie_value = sc.split(";")[0]
        if not cookie_value:
            return None, None
        # Step 2: fetch crumb using the cookie
        req2 = urllib.request.Request(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers={"User-Agent": USER_AGENT, "Cookie": cookie_value},
        )
        with urllib.request.urlopen(req2, timeout=10) as resp:
            crumb = resp.read().decode("utf-8").strip()
        if not crumb or len(crumb) > 64:
            return None, None
        _CRUMB_CACHE["cookie"] = cookie_value
        _CRUMB_CACHE["crumb"] = crumb
        return cookie_value, crumb
    except Exception:
        return None, None


def _fetch_summary(symbol: str, modules: list[str]) -> dict:
    """Hit Yahoo's quoteSummary endpoint for fundamentals modules.

    Includes the cookie/crumb anti-bot dance Yahoo enforces since 2023.
    """
    mods = ",".join(modules)
    cookie, crumb = _yahoo_crumb()
    crumb_q = f"&crumb={urllib.parse.quote(crumb)}" if crumb else ""
    url = f"{SUMMARY_URL}/{symbol}?modules={mods}{crumb_q}"
    headers = {"User-Agent": USER_AGENT}
    if cookie:
        headers["Cookie"] = cookie
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Surface 401 with hint to caller
        if e.code in (401, 403):
            raise ProviderError(
                f"Yahoo summary HTTP {e.code} on {symbol} (anti-bot crumb may need refresh; "
                f"prefer EDGAR for US fundamentals)"
            ) from e
        raise ProviderError(f"Yahoo summary HTTP {e.code} on {symbol}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Yahoo summary network error: {e.reason}") from e


def _market_cap(symbol: str, *, cache_ttl_seconds: int = 3600) -> Optional[float]:
    """Convenience: fetch current market cap via summary endpoint (used by Trust Layer)."""
    cache = get_cache()
    cache_key = f"yahoo:mcap:{symbol}"
    cached = cache.get(cache_key, ttl_seconds=cache_ttl_seconds)
    if cached is not None:
        return cached
    data = _fetch_summary(symbol, ["price", "summaryDetail"])
    blocks = data.get("quoteSummary", {}).get("result", [])
    if not blocks:
        return None
    price_block = blocks[0].get("price", {}) or {}
    summary_block = blocks[0].get("summaryDetail", {}) or {}
    mcap = (price_block.get("marketCap") or summary_block.get("marketCap") or {}).get("raw")
    cache.set(cache_key, mcap)
    return mcap


# ─── Provider class (registry-routable, free / public) ──────────────────────


class YahooProvider(Provider):
    """Yahoo Finance — free public quote, history, fundamentals, market cap.

    No API key required. Rate-limited by Yahoo (informally ~2 req/sec
    sustained). Brittle for production but excellent for screening,
    plausibility checks, and free-tier model builds.
    """

    name = "yahoo"
    tier = "free"
    requires_auth = False

    def is_available(self) -> bool:  # noqa: D401
        # Pure-stdlib client, always installable. We treat it as always
        # available; calls fall through to ProviderError on network issues.
        return True

    # ─── capabilities ──────────────────────────────────────────────────────

    def quote(self, symbol: str) -> Quote:
        try:
            payload = quote(symbol)
        except RuntimeError as e:
            raise ProviderError(str(e)) from e
        if payload.get("price") is None:
            raise ProviderError(f"Yahoo returned no price for {symbol}")
        return Quote(
            symbol=payload.get("symbol") or symbol,
            price=float(payload["price"]),
            currency=payload.get("currency"),
            previous_close=payload.get("previous_close"),
            change_pct=payload.get("change_pct"),
            exchange=payload.get("exchange"),
            source="yahoo",
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
        # Map provider-agnostic interval → Yahoo enum; pick range from limit.
        yahoo_interval: Interval = (
            interval if interval in ("1d", "5d", "1wk", "1mo", "3mo") else "1d"  # type: ignore[assignment]
        )
        # If caller asks for >1y of daily bars, use range="5y"; default 1y.
        rng: Range = "5y" if (limit > 365 and yahoo_interval == "1d") else "1y"  # type: ignore[assignment]
        try:
            rows = history(symbol, interval=yahoo_interval, range_=rng)
        except RuntimeError as e:
            raise ProviderError(str(e)) from e
        bars = [
            Bar(
                date=r["date"],
                open=r.get("open"),
                high=r.get("high"),
                low=r.get("low"),
                close=r.get("close"),
                volume=r.get("volume"),
            )
            for r in rows
            if r.get("close") is not None
        ]
        # Apply start/end filtering if provided
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
        # Yahoo's quoteSummary modules cover the most useful FY snapshots.
        # We pull the *Statement modules + earnings + key stats and squash
        # into Fundamentals rows (one per fiscal year, newest first).
        cache = get_cache()
        cache_key = f"yahoo:fund:{symbol}:{statement}:{period}"
        cached = cache.get(cache_key, ttl_seconds=86_400)  # 1 day
        if cached is not None:
            return [Fundamentals(**row) for row in cached][:limit]

        modules = [
            "incomeStatementHistory",
            "balanceSheetHistory",
            "cashflowStatementHistory",
            "defaultKeyStatistics",
            "summaryDetail",
            "price",
        ]
        try:
            data = _fetch_summary(symbol, modules)
        except ProviderError:
            raise
        blocks = data.get("quoteSummary", {}).get("result") or []
        if not blocks:
            raise ProviderError(f"Yahoo summary empty for {symbol}")
        block = blocks[0]
        currency = (
            (block.get("price", {}) or {}).get("financialCurrency")
            or (block.get("summaryDetail", {}) or {}).get("currency")
        )
        income = (
            (block.get("incomeStatementHistory", {}) or {})
            .get("incomeStatementHistory", [])
            or []
        )
        balance = (
            (block.get("balanceSheetHistory", {}) or {})
            .get("balanceSheetStatements", [])
            or []
        )
        cashflow = (
            (block.get("cashflowStatementHistory", {}) or {})
            .get("cashflowStatements", [])
            or []
        )
        out: list[Fundamentals] = []
        for i, inc in enumerate(income[:limit]):
            end_date = (inc.get("endDate") or {}).get("fmt")
            bal = balance[i] if i < len(balance) else {}
            cf = cashflow[i] if i < len(cashflow) else {}

            def _raw(d: dict, k: str) -> Optional[float]:
                v = (d or {}).get(k) or {}
                if isinstance(v, dict):
                    val = v.get("raw")
                    return float(val) if val is not None else None
                return None

            revenue = _raw(inc, "totalRevenue")
            ebit = _raw(inc, "ebit") or _raw(inc, "operatingIncome")
            ebitda = _raw(inc, "ebitda")
            net_income = _raw(inc, "netIncome")
            eps = _raw(inc, "dilutedEPS") or _raw(
                block.get("defaultKeyStatistics", {}) or {},
                "trailingEps",
            )
            total_assets = _raw(bal, "totalAssets")
            total_debt = _raw(bal, "shortLongTermDebt") or _raw(bal, "longTermDebt")
            cash = _raw(bal, "cash") or _raw(bal, "cashAndShortTermInvestments")
            ocf = _raw(cf, "totalCashFromOperatingActivities")
            capex = _raw(cf, "capitalExpenditures")
            fcf = (ocf - abs(capex)) if (ocf is not None and capex is not None) else None
            shares = _raw(
                block.get("defaultKeyStatistics", {}) or {},
                "sharesOutstanding",
            )
            out.append(
                Fundamentals(
                    symbol=symbol,
                    period=f"FY{end_date[:4]}" if end_date else f"FY{i}",
                    period_end=end_date,
                    currency=currency,
                    revenue=revenue,
                    ebit=ebit,
                    ebitda=ebitda,
                    net_income=net_income,
                    eps=eps,
                    total_assets=total_assets,
                    total_debt=total_debt,
                    cash=cash,
                    operating_cash_flow=ocf,
                    capex=capex,
                    free_cash_flow=fcf,
                    shares_diluted=shares,
                    source="yahoo",
                )
            )
        # Cache the dict form so we can rehydrate dataclasses from JSON.
        cache.set(
            cache_key,
            [
                {
                    "symbol": f.symbol,
                    "period": f.period,
                    "period_end": f.period_end,
                    "currency": f.currency,
                    "revenue": f.revenue,
                    "ebit": f.ebit,
                    "ebitda": f.ebitda,
                    "net_income": f.net_income,
                    "eps": f.eps,
                    "total_assets": f.total_assets,
                    "total_debt": f.total_debt,
                    "cash": f.cash,
                    "operating_cash_flow": f.operating_cash_flow,
                    "capex": f.capex,
                    "free_cash_flow": f.free_cash_flow,
                    "shares_diluted": f.shares_diluted,
                    "source": f.source,
                }
                for f in out
            ],
        )
        return out

    def entity_lookup(
        self,
        *,
        lei: Optional[str] = None,
        figi: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> Entity:
        if not ticker:
            raise NotSupported("yahoo entity_lookup requires a ticker")
        try:
            payload = quote(ticker)
        except RuntimeError as e:
            raise ProviderError(str(e)) from e
        return Entity(
            name=payload.get("symbol") or ticker,
            ticker=payload.get("symbol") or ticker,
            exchange=payload.get("exchange"),
        )

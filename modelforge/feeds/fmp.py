"""Financial Modeling Prep (FMP) adapter.

The de-facto budget-tier institutional fundamentals provider. 100K+
analysts use it because the data shape mirrors what Bloomberg / FactSet
return — same line items, same period conventions, same FX rules.

For ModelForge specifically, FMP is the natural partner: it gives us
the full income statement / balance sheet / cash flow / ratios / DCF
inputs that drive the bulge-tier templates without requiring a Phase-B
Bloomberg deal.

Free tier: 250 calls/day, 5 yrs of history. Starter $19/mo lifts to
unlimited daily calls + 30 yrs history.

API docs: https://site.financialmodelingprep.com/developer/docs

Auth: ``FMP_API_KEY`` env var or ``api_key=`` arg.
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
BASE_URL = "https://financialmodelingprep.com/api"


def _api_key(provided: Optional[str]) -> str:
    if provided:
        return provided
    key = os.environ.get("FMP_API_KEY")
    if not key:
        raise AuthRequired(
            "FMP requires FMP_API_KEY env var or api_key=. "
            "Free key: https://site.financialmodelingprep.com/developer"
        )
    return key


def _get(path: str, params: dict, *, api_key: Optional[str], cache_ttl: int) -> Any:
    key = _api_key(api_key)
    params = {**params, "apikey": key}
    cache = get_cache()
    cache_params = {k: v for k, v in params.items() if k != "apikey"}
    cache_key = f"fmp:{path}:" + json.dumps(cache_params, sort_keys=True)
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
        if e.code in (401, 403):
            raise AuthRequired(f"FMP auth rejected ({e.code})") from e
        raise ProviderError(f"FMP HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"FMP network error: {e.reason}") from e

    # FMP returns {"Error Message": "..."} for invalid tickers
    if isinstance(data, dict) and data.get("Error Message"):
        raise ProviderError(f"FMP: {data['Error Message']}")
    cache.set(cache_key, data)
    return data


# ─── direct helpers ─────────────────────────────────────────────────────────


def quote_raw(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """Real-time-ish quote (free tier: EOD)."""
    rows = _get(f"/v3/quote/{symbol.upper()}", {}, api_key=api_key, cache_ttl=60)
    if not rows:
        raise ProviderError(f"FMP: no quote for {symbol}")
    return rows[0]


def income_statement(
    symbol: str,
    *,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 5,
    api_key: Optional[str] = None,
) -> list[dict]:
    return _get(
        f"/v3/income-statement/{symbol.upper()}",
        {"period": period, "limit": limit},
        api_key=api_key,
        cache_ttl=86400,
    ) or []


def balance_sheet(
    symbol: str,
    *,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 5,
    api_key: Optional[str] = None,
) -> list[dict]:
    return _get(
        f"/v3/balance-sheet-statement/{symbol.upper()}",
        {"period": period, "limit": limit},
        api_key=api_key,
        cache_ttl=86400,
    ) or []


def cash_flow(
    symbol: str,
    *,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 5,
    api_key: Optional[str] = None,
) -> list[dict]:
    return _get(
        f"/v3/cash-flow-statement/{symbol.upper()}",
        {"period": period, "limit": limit},
        api_key=api_key,
        cache_ttl=86400,
    ) or []


def ratios(
    symbol: str,
    *,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 5,
    api_key: Optional[str] = None,
) -> list[dict]:
    """Pre-computed ratios — current ratio, P/E, ROE, gearing, etc."""
    return _get(
        f"/v3/ratios/{symbol.upper()}",
        {"period": period, "limit": limit},
        api_key=api_key,
        cache_ttl=86400,
    ) or []


def discounted_cash_flow(symbol: str, *, api_key: Optional[str] = None) -> dict:
    """FMP's bundled DCF intrinsic-value estimate. Useful as sanity check
    against ModelForge's own DCF output."""
    rows = _get(f"/v3/discounted-cash-flow/{symbol.upper()}", {}, api_key=api_key, cache_ttl=86400)
    return (rows or [{}])[0]


def historical_price(
    symbol: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    params: dict[str, Any] = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    data = _get(
        f"/v3/historical-price-full/{symbol.upper()}",
        params,
        api_key=api_key,
        cache_ttl=3600,
    )
    return (data or {}).get("historical", []) if isinstance(data, dict) else []


def company_profile(symbol: str, *, api_key: Optional[str] = None) -> dict:
    rows = _get(f"/v3/profile/{symbol.upper()}", {}, api_key=api_key, cache_ttl=86400)
    return (rows or [{}])[0]


def search_ticker(query: str, *, limit: int = 10, api_key: Optional[str] = None) -> list[dict]:
    return _get("/v3/search", {"query": query, "limit": limit}, api_key=api_key, cache_ttl=86400) or []


# ─── Provider adapter ───────────────────────────────────────────────────────


class FMPProvider(Provider):
    name = "fmp"
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
        return Quote(
            symbol=d.get("symbol", symbol.upper()),
            price=float(d["price"]) if d.get("price") is not None else 0.0,
            previous_close=d.get("previousClose"),
            change_pct=d.get("changesPercentage"),
            volume=d.get("volume"),
            exchange=d.get("exchange"),
            source="fmp",
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
        rows = historical_price(
            symbol, from_date=start, to_date=end, api_key=self._api_key
        )[:limit]
        return [
            Bar(date=r["date"], open=r.get("open"), high=r.get("high"),
                low=r.get("low"), close=r.get("close"), volume=r.get("volume"))
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
        # FMP gives us each statement separately — we merge by period
        income = income_statement(symbol, period=period, limit=limit, api_key=self._api_key)
        bs = balance_sheet(symbol, period=period, limit=limit, api_key=self._api_key)
        cf = cash_flow(symbol, period=period, limit=limit, api_key=self._api_key)

        bs_by = {b["date"]: b for b in bs}
        cf_by = {c["date"]: c for c in cf}

        out: list[Fundamentals] = []
        for inc in income:
            d = inc["date"]
            b = bs_by.get(d, {})
            c = cf_by.get(d, {})
            year = d[:4] if d else "?"
            label = f"FY{year}" if period == "annual" else d
            ebit = inc.get("operatingIncome")
            depr = inc.get("depreciationAndAmortization") or 0
            ebitda = (ebit + depr) if ebit is not None else None
            cash = b.get("cashAndCashEquivalents")
            ocf = c.get("operatingCashFlow")
            capex = c.get("capitalExpenditure")
            fcf = (ocf + capex) if ocf is not None and capex is not None else None
            out.append(Fundamentals(
                symbol=symbol.upper(),
                period=label,
                period_end=d,
                currency=inc.get("reportedCurrency"),
                revenue=inc.get("revenue"),
                ebit=ebit,
                ebitda=ebitda,
                net_income=inc.get("netIncome"),
                eps=inc.get("eps"),
                total_assets=b.get("totalAssets"),
                total_debt=b.get("totalDebt"),
                cash=cash,
                operating_cash_flow=ocf,
                capex=capex,
                free_cash_flow=fcf,
                shares_diluted=inc.get("weightedAverageShsOutDil"),
                source="fmp",
            ))
        return out

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return search_ticker(query, limit=limit, api_key=self._api_key)

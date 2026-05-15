"""S&P Capital IQ / S&P Global Marketplace adapter.

S&P Capital IQ is the canonical M&A database — every IB and PE deal
team uses it. The S&P Global Marketplace API provides programmatic
access to the same dataset (fundamentals, transactions, ratings,
ownership, key developments).

Two flavors of access:

* **Capital IQ Pro Office Plug-in** — Excel-based, used by IB analysts.
  No public Python SDK.
* **S&P Global Marketplace API** — REST, OAuth2. Modern path. Requires
  a Marketplace subscription contract (paid).

This adapter targets the REST flavor. Without a contract it raises
:class:`AuthRequired` with an actionable message.

Activation:
    Set ``SPGLOBAL_API_KEY`` and ``SPGLOBAL_API_SECRET`` provided by
    S&P after contract.

API docs:
* https://www.marketplace.spglobal.com/
* https://www.spglobal.com/marketintelligence/en/solutions/sp-capital-iq-pro

Identifier conventions: S&P uses GVKey (compustat) internally and
accepts ticker, ISIN, CIK, or LEI on the inbound side.
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
    Entity,
    Fundamentals,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
)

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
TOKEN_URL = "https://api.marketintelligence.spglobal.com/oauth2/token"
BASE_URL = "https://api.marketintelligence.spglobal.com"


def _credentials() -> tuple[str, str]:
    key = os.environ.get("SPGLOBAL_API_KEY")
    secret = os.environ.get("SPGLOBAL_API_SECRET")
    if not key or not secret:
        raise AuthRequired(
            "S&P Capital IQ requires SPGLOBAL_API_KEY + SPGLOBAL_API_SECRET. "
            "Provision via https://www.marketplace.spglobal.com/ subscription."
        )
    return key, secret


def _get_token() -> str:
    """OAuth2 client_credentials flow."""
    cache = get_cache()
    cached = cache.get("spglobal:token", ttl_seconds=3300)  # token is 1h, refresh at 55m
    if cached:
        return cached
    key, secret = _credentials()
    body = (
        f"grant_type=client_credentials&client_id={key}&client_secret={secret}"
    ).encode("utf-8")
    try:
        req = urllib.request.Request(
            TOKEN_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise AuthRequired(f"S&P token rejected ({e.code})") from e
        raise ProviderError(f"S&P token HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"S&P token network error: {e.reason}") from e
    token = data.get("access_token")
    if not token:
        raise ProviderError("S&P: token missing from response")
    cache.set("spglobal:token", token)
    return token


def _get(path: str, params: Optional[dict] = None, *, cache_ttl: int = 86400) -> Any:
    cache = get_cache()
    cache_key = f"spglobal:{path}:" + json.dumps(params or {}, sort_keys=True)
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    token = _get_token()
    query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    url = f"{BASE_URL}{path}?{query}" if query else f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise AuthRequired(f"S&P request rejected ({e.code})") from e
        raise ProviderError(f"S&P HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"S&P network error: {e.reason}") from e

    cache.set(cache_key, data)
    return data


# ─── direct helpers ─────────────────────────────────────────────────────────


def gvkey_from_ticker(ticker: str) -> Optional[str]:
    """Resolve ticker → S&P GVKey via the Marketplace identifier service."""
    data = _get("/v1/cross-reference/identifiers", {"ticker": ticker.upper()}, cache_ttl=86400)
    rows = (data or {}).get("identifiers") or []
    return rows[0]["gvkey"] if rows else None


def fundamentals_raw(
    gvkey: str,
    *,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 5,
) -> list[dict]:
    """Compustat-derived fundamentals via Marketplace."""
    data = _get(
        f"/v1/financials/fundamentals/{gvkey}",
        {"frequency": period, "limit": limit},
    )
    return (data or {}).get("data", [])


def transactions(
    *,
    target_gvkey: Optional[str] = None,
    target_ticker: Optional[str] = None,
    sector: Optional[str] = None,
    min_value_usd_m: Optional[float] = None,
    limit: int = 50,
) -> list[dict]:
    """Search M&A transactions in the Capital IQ deal database.

    This is the killer feature — every Capital IQ user is here for
    transaction comps and precedent.
    """
    params: dict[str, Any] = {"limit": limit}
    if target_gvkey:
        params["target_gvkey"] = target_gvkey
    if target_ticker:
        params["target_ticker"] = target_ticker.upper()
    if sector:
        params["sector"] = sector
    if min_value_usd_m is not None:
        params["min_deal_value_usd_m"] = min_value_usd_m
    data = _get("/v1/transactions/search", params, cache_ttl=86400)
    return (data or {}).get("data", [])


def credit_ratings(entity: str) -> list[dict]:
    """Active S&P credit ratings for an entity (long-term issuer rating)."""
    data = _get(f"/v1/ratings/{entity}", cache_ttl=86400)
    return (data or {}).get("ratings", [])


# ─── Provider adapter ───────────────────────────────────────────────────────


class SPCapitalIQProvider(Provider):
    name = "spcapiq"
    tier = "bulge"
    requires_auth = True

    def is_available(self) -> bool:
        try:
            _credentials()
            return True
        except AuthRequired:
            return False

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        gvkey = gvkey_from_ticker(symbol)
        if not gvkey:
            raise ProviderError(f"S&P: no GVKey for {symbol}")
        rows = fundamentals_raw(gvkey, period=period, limit=limit)
        out: list[Fundamentals] = []
        for r in rows:
            ocf = r.get("operating_cash_flow")
            capex = r.get("capex")
            fcf = (ocf + capex) if ocf is not None and capex is not None else None
            out.append(Fundamentals(
                symbol=symbol.upper(),
                period=f"FY{r.get('fiscal_year')}" if period == "annual" else str(r.get("fiscal_period")),
                period_end=r.get("period_end"),
                currency=r.get("currency"),
                revenue=r.get("revenue"),
                ebit=r.get("ebit"),
                ebitda=r.get("ebitda"),
                net_income=r.get("net_income"),
                eps=r.get("eps_diluted"),
                total_assets=r.get("total_assets"),
                total_debt=r.get("long_term_debt"),
                cash=r.get("cash"),
                operating_cash_flow=ocf,
                capex=capex,
                free_cash_flow=fcf,
                source="spcapiq",
            ))
        return out

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search M&A transactions matching the query (target ticker/sector)."""
        return transactions(target_ticker=query, limit=limit)

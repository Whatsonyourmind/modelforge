"""OpenFIGI adapter — Bloomberg's free FIGI cross-reference.

The Financial Instrument Global Identifier (FIGI) is the open ISO 17442
asset-class identifier maintained by Bloomberg's Open Symbology
Initiative. It is the only globally-unique identifier that doesn't
re-use codes when a security is delisted (unlike CUSIP / ISIN, which
recycle).

Why it matters for ModelForge: the moment a model spans more than one
country, ticker collisions (BNP listed in Paris vs BNP in another
exchange) bite. FIGI removes the ambiguity. ICE, S&P, MSCI, FactSet
all reference FIGI internally now.

Free tier: 25 requests/min unauthenticated, 250 req/min with key.
``OPENFIGI_API_KEY`` env var optional (just for the higher rate limit).

API docs: https://www.openfigi.com/api
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from modelforge.feeds.cache import get_cache
from modelforge.feeds.provider import Entity, Provider, ProviderError

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://api.openfigi.com/v3"


def _post(path: str, body: list[dict] | dict, *, api_key: Optional[str], cache_ttl: int) -> Any:
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    key = api_key or os.environ.get("OPENFIGI_API_KEY")
    if key:
        headers["X-OPENFIGI-APIKEY"] = key

    cache = get_cache()
    cache_key = f"openfigi:{path}:" + json.dumps(body, sort_keys=True)
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    payload = json.dumps(body).encode("utf-8")
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ProviderError(f"OpenFIGI HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"OpenFIGI network error: {e.reason}") from e

    cache.set(cache_key, data)
    return data


def map_identifier(
    id_type: str,
    id_value: str,
    *,
    exch_code: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    """Map any identifier (TICKER, ISIN, CUSIP, SEDOL, BASE_TICKER, …) to FIGI.

    Args:
        id_type: One of ``ID_ISIN``, ``ID_CUSIP``, ``ID_SEDOL``, ``ID_BB``,
                 ``TICKER``, ``BASE_TICKER``, ``COMPOSITE_ID_BB_GLOBAL``.
        id_value: The identifier value.
        exch_code: Optional ISO MIC exchange filter (e.g. ``XPAR`` for Paris).
    """
    job: dict[str, Any] = {"idType": id_type, "idValue": id_value}
    if exch_code:
        job["exchCode"] = exch_code
    rows = _post("/mapping", [job], api_key=api_key, cache_ttl=86400)
    if not isinstance(rows, list) or not rows:
        return []
    block = rows[0]
    if "data" in block and isinstance(block["data"], list):
        return block["data"]
    return []


def isin_to_figi(isin: str, *, api_key: Optional[str] = None) -> Optional[str]:
    rows = map_identifier("ID_ISIN", isin, api_key=api_key)
    return rows[0]["figi"] if rows else None


def ticker_to_figi(
    ticker: str,
    *,
    exch_code: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[str]:
    rows = map_identifier("TICKER", ticker, exch_code=exch_code, api_key=api_key)
    return rows[0]["figi"] if rows else None


def search_securities(query: str, *, limit: int = 25, api_key: Optional[str] = None) -> list[dict]:
    """Free-text search across the OpenFIGI universe."""
    body = {"query": query}
    data = _post("/search", body, api_key=api_key, cache_ttl=86400)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"][:limit]
    return []


# ─── Provider adapter ───────────────────────────────────────────────────────


class OpenFIGIProvider(Provider):
    name = "openfigi"
    tier = "free"
    requires_auth = False

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key

    def is_available(self) -> bool:
        return True  # works without key, just rate-limited

    def entity_lookup(
        self,
        *,
        lei: Optional[str] = None,
        figi: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> Entity:
        if figi:
            rows = map_identifier("ID_BB_GLOBAL", figi, api_key=self._api_key)
        elif ticker:
            rows = map_identifier("TICKER", ticker, api_key=self._api_key)
        else:
            raise ProviderError("OpenFIGI entity_lookup needs figi or ticker")
        if not rows:
            raise ProviderError("OpenFIGI: no match")
        r = rows[0]
        return Entity(
            name=r.get("name", ""),
            figi=r.get("figi"),
            ticker=r.get("ticker"),
            exchange=r.get("exchCode"),
        )

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return search_securities(query, limit=limit, api_key=self._api_key)

"""GLEIF adapter — Global Legal Entity Identifier (LEI) registry.

The LEI is the ISO 17442 standard for legally-identifying any entity
that participates in financial transactions worldwide. Mandated by
EMIR, MiFID II, Dodd-Frank, SFTR — every counterparty in any swap,
bond issuance, repo, or derivative trade must have one.

GLEIF (Global Legal Entity Identifier Foundation) is the not-for-profit
that maintains the open registry. ModelForge ships this adapter so any
counterparty in a model can be unambiguously named.

100% free, no API key, governed by ISO 17442. Updated daily.

API docs: https://api.gleif.org/api/v1
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from modelforge.feeds.cache import get_cache
from modelforge.feeds.provider import Entity, Provider, ProviderError

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://api.gleif.org/api/v1"


def _get(path: str, params: dict, *, cache_ttl: int) -> Any:
    cache = get_cache()
    cache_key = f"gleif:{path}:" + json.dumps(params, sort_keys=True)
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{BASE_URL}{path}?{query}" if params else f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.api+json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise ProviderError(f"GLEIF HTTP {e.code} on {path}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"GLEIF network error: {e.reason}") from e

    cache.set(cache_key, data)
    return data


def lei_record(lei: str) -> Optional[dict]:
    """Fetch the full record for a 20-char LEI."""
    data = _get(f"/lei-records/{lei.upper()}", {}, cache_ttl=86400)
    if not isinstance(data, dict):
        return None
    return data.get("data")


def search_entities(query: str, *, limit: int = 10) -> list[dict]:
    """Fuzzy-search LEI records by entity name."""
    data = _get(
        "/lei-records",
        {"filter[entity.legalName]": query, "page[size]": limit},
        cache_ttl=86400,
    )
    if not isinstance(data, dict):
        return []
    return data.get("data") or []


def entity_to_lei(name: str, *, country: Optional[str] = None) -> Optional[str]:
    """Best-match LEI for an entity name (optionally filtered by ISO country)."""
    params: dict[str, Any] = {"filter[entity.legalName]": name, "page[size]": 1}
    if country:
        params["filter[entity.legalAddress.country]"] = country.upper()
    data = _get("/lei-records", params, cache_ttl=86400)
    if not isinstance(data, dict):
        return None
    rows = data.get("data") or []
    if not rows:
        return None
    return rows[0].get("attributes", {}).get("lei")


def parent_relationship(lei: str) -> Optional[dict]:
    """Direct parent (Level 1) relationship per GLEIF Level 2 data."""
    data = _get(f"/lei-records/{lei.upper()}/direct-parent", {}, cache_ttl=86400)
    if not isinstance(data, dict):
        return None
    return data.get("data")


def ultimate_parent(lei: str) -> Optional[dict]:
    """Ultimate consolidating parent."""
    data = _get(f"/lei-records/{lei.upper()}/ultimate-parent", {}, cache_ttl=86400)
    if not isinstance(data, dict):
        return None
    return data.get("data")


# ─── Provider adapter ───────────────────────────────────────────────────────


class GLEIFProvider(Provider):
    name = "gleif"
    tier = "free"
    requires_auth = False

    def is_available(self) -> bool:
        return True

    def entity_lookup(
        self,
        *,
        lei: Optional[str] = None,
        figi: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> Entity:
        if not lei:
            raise ProviderError("GLEIF entity_lookup requires lei=")
        rec = lei_record(lei)
        if rec is None:
            raise ProviderError(f"GLEIF: no record for LEI {lei}")
        attrs = rec.get("attributes", {}) if isinstance(rec, dict) else {}
        entity = (attrs.get("entity") or {}) if isinstance(attrs, dict) else {}
        addr = entity.get("legalAddress", {}) if isinstance(entity, dict) else {}
        return Entity(
            name=entity.get("legalName", {}).get("name", "") if isinstance(entity.get("legalName"), dict) else entity.get("legalName", ""),
            lei=attrs.get("lei"),
            country=addr.get("country") if isinstance(addr, dict) else None,
        )

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = search_entities(query, limit=limit)
        out: list[dict[str, Any]] = []
        for r in rows:
            attrs = r.get("attributes", {}) if isinstance(r, dict) else {}
            entity = (attrs.get("entity") or {}) if isinstance(attrs, dict) else {}
            name_field = entity.get("legalName")
            name = name_field.get("name") if isinstance(name_field, dict) else name_field
            out.append({
                "lei": attrs.get("lei"),
                "name": name,
                "status": attrs.get("registration", {}).get("status") if isinstance(attrs.get("registration"), dict) else None,
                "country": entity.get("legalAddress", {}).get("country") if isinstance(entity.get("legalAddress"), dict) else None,
            })
        return out

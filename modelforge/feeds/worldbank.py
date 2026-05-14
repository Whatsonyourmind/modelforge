"""World Bank Open Data adapter (free, no API key).

API docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392

Useful for cross-country macro: GDP, inflation, sovereign-rating analogs,
demographic forecasts, country risk premia inputs.

Common indicators:
    NY.GDP.MKTP.KD.ZG — GDP growth (annual %)
    FP.CPI.TOTL.ZG   — Inflation (consumer prices, annual %)
    GC.DOD.TOTL.GD.ZS — General government gross debt (% of GDP)
    NY.GNP.PCAP.CD   — GNI per capita (current US$)
    SP.POP.TOTL      — Population, total

Country codes are ISO 3-letter (ITA, USA, DEU, GBR, JPN, BRA...).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from modelforge.feeds.cache import get_cache

USER_AGENT = "modelforge/0.9 (+https://github.com/Whatsonyourmind/modelforge)"
BASE_URL = "https://api.worldbank.org/v2"


def fetch_indicator(
    country: str,
    indicator: str,
    *,
    date_range: Optional[str] = None,
    cache_ttl_seconds: int = 86400 * 7,  # 7d (World Bank updates infrequently)
) -> list[dict]:
    """Fetch an indicator for a country.

    Args:
        country: ISO-3 country code (ITA, USA, DEU, GBR...) or "all".
        indicator: World Bank indicator code (e.g. "NY.GDP.MKTP.KD.ZG").
        date_range: Optional date filter, e.g. "2010:2025".
        cache_ttl_seconds: Cache TTL.

    Returns:
        List of observations: {date, value, country, indicator_name}.
    """
    cache = get_cache()
    cache_key = f"worldbank:{country}:{indicator}:{date_range or 'all'}"
    cached = cache.get(cache_key, ttl_seconds=cache_ttl_seconds)
    if cached is not None:
        return cached

    params = {"format": "json", "per_page": "100"}
    if date_range:
        params["date"] = date_range

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/country/{country}/indicator/{indicator}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"WB HTTP {e.code} on {country}/{indicator}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"WB network error: {e.reason}") from e

    # WB API returns [metadata, observations]
    if not isinstance(raw, list) or len(raw) < 2:
        return []
    observations = raw[1] or []

    clean = [
        {
            "date": o.get("date"),
            "value": o.get("value"),
            "country": (o.get("country") or {}).get("value"),
            "indicator_name": (o.get("indicator") or {}).get("value"),
        }
        for o in observations
        if o.get("value") is not None
    ]
    cache.set(cache_key, clean)
    return clean


def gdp_growth(country: str, year: Optional[str] = None) -> Optional[float]:
    """Latest (or specific year) GDP growth % for a country (ISO-3)."""
    series = fetch_indicator(country, "NY.GDP.MKTP.KD.ZG")
    if year:
        for o in series:
            if o["date"] == year:
                return o["value"]
        return None
    return series[0]["value"] if series else None


def inflation_cpi(country: str, year: Optional[str] = None) -> Optional[float]:
    """Latest (or specific year) CPI inflation % for a country (ISO-3)."""
    series = fetch_indicator(country, "FP.CPI.TOTL.ZG")
    if year:
        for o in series:
            if o["date"] == year:
                return o["value"]
        return None
    return series[0]["value"] if series else None


def government_debt_pct_gdp(country: str, year: Optional[str] = None) -> Optional[float]:
    """General government gross debt as % of GDP."""
    series = fetch_indicator(country, "GC.DOD.TOTL.GD.ZS")
    if year:
        for o in series:
            if o["date"] == year:
                return o["value"]
        return None
    return series[0]["value"] if series else None

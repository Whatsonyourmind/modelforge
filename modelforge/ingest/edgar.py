"""SEC EDGAR company-facts adapter — v0.5 US-026 MVP.

Pulls XBRL-tagged historical financials from the SEC's free public API
(no key required) and resolves US tickers to CIKs.

Key endpoints:

    GET https://www.sec.gov/files/company_tickers.json
        — ticker ↔ CIK lookup (tiny ~500 KB JSON)

    GET https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json
        — all XBRL facts ever reported by a company
        — requires User-Agent header per SEC fair-use policy

Ships a minimal bundled sample (AAPL abbreviated) for offline tests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


_USER_AGENT = ("ModelForge/0.5 (contact: redacted@example.com) "
               "Python/urllib")
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


# ── Bundled sample for offline tests (AAPL FY2020-2024 abbreviated) ─────────

_BUNDLED_SAMPLE = {
    "AAPL": {
        "cik": 320193,
        "entityName": "APPLE INC.",
        "facts": {
            "us-gaap": {
                "Revenues": [
                    {"fy": 2020, "fp": "FY", "val": 274515000000, "form": "10-K"},
                    {"fy": 2021, "fp": "FY", "val": 365817000000, "form": "10-K"},
                    {"fy": 2022, "fp": "FY", "val": 394328000000, "form": "10-K"},
                    {"fy": 2023, "fp": "FY", "val": 383285000000, "form": "10-K"},
                    {"fy": 2024, "fp": "FY", "val": 391035000000, "form": "10-K"},
                ],
                "OperatingIncomeLoss": [
                    {"fy": 2020, "fp": "FY", "val": 66288000000, "form": "10-K"},
                    {"fy": 2021, "fp": "FY", "val": 108949000000, "form": "10-K"},
                    {"fy": 2022, "fp": "FY", "val": 119437000000, "form": "10-K"},
                    {"fy": 2023, "fp": "FY", "val": 114301000000, "form": "10-K"},
                    {"fy": 2024, "fp": "FY", "val": 123216000000, "form": "10-K"},
                ],
                "NetIncomeLoss": [
                    {"fy": 2020, "fp": "FY", "val": 57411000000, "form": "10-K"},
                    {"fy": 2021, "fp": "FY", "val": 94680000000, "form": "10-K"},
                    {"fy": 2022, "fp": "FY", "val": 99803000000, "form": "10-K"},
                    {"fy": 2023, "fp": "FY", "val": 96995000000, "form": "10-K"},
                    {"fy": 2024, "fp": "FY", "val": 93736000000, "form": "10-K"},
                ],
                "Assets": [
                    {"fy": 2024, "fp": "FY", "val": 364980000000, "form": "10-K"},
                ],
                "LongTermDebtNoncurrent": [
                    {"fy": 2024, "fp": "FY", "val": 85750000000, "form": "10-K"},
                ],
            },
        },
    },
}


# ── Data classes ────────────────────────────────────────────────────────────


@dataclass
class EdgarFinancials:
    ticker: str
    cik: int
    entity_name: str
    fiscal_years: list[int]
    revenue_usd_m: list[float]            # millions USD
    operating_income_usd_m: list[float]
    net_income_usd_m: list[float]
    total_assets_usd_m: Optional[float] = None
    long_term_debt_usd_m: Optional[float] = None
    source_url: str = ""
    fetched_from: str = "live"            # "live" or "bundled"
    notes: list[str] = field(default_factory=list)


# ── Ticker → CIK ────────────────────────────────────────────────────────────


def _lookup_cik_live(ticker: str, timeout: float = 10.0) -> Optional[int]:
    req = urllib.request.Request(
        _TICKERS_URL,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    wanted = ticker.upper()
    for _, entry in payload.items():
        if entry.get("ticker", "").upper() == wanted:
            return int(entry["cik_str"])
    return None


# ── Live facts fetch ────────────────────────────────────────────────────────


def _fetch_facts_live(cik: int, timeout: float = 15.0) -> Optional[dict]:
    url = _FACTS_URL.format(cik=cik)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


# ── XBRL fact extraction ─────────────────────────────────────────────────────


# Order matters: later tags win when same FY is present in multiple
# (used by _first_available merge). Newer post-ASC-606 tag last.
_REVENUE_TAGS = (
    "SalesRevenueNet",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
)
_OPINCOME_TAGS = ("OperatingIncomeLoss",)
_NETINCOME_TAGS = ("NetIncomeLoss",)
_ASSETS_TAGS = ("Assets",)
_LTDEBT_TAGS = (
    "LongTermDebtNoncurrent",
    "LongTermDebt",
)


def _fact_series(facts: dict, concept: str) -> list[dict]:
    """Extract the USD FY series for a concept. Returns list of
    {'fy', 'fp', 'val', 'form'} dicts ordered by fiscal year."""
    raw = facts.get("us-gaap", {}).get(concept)
    if not raw:
        return []
    # Live EDGAR shape: raw["units"]["USD"] = [{fy, fp, val, form, ...}]
    if isinstance(raw, dict):
        usd = raw.get("units", {}).get("USD", [])
    else:
        usd = raw
    fy_only = [x for x in usd
               if x.get("fp") == "FY" and x.get("form", "").startswith("10-K")]
    fy_only.sort(key=lambda x: x.get("fy", 0))
    # Keep last one per fiscal year (avoids duplicate amended filings)
    seen: dict[int, dict] = {}
    for row in fy_only:
        seen[row["fy"]] = row
    return [seen[k] for k in sorted(seen)]


def _first_available(facts: dict, tags: tuple) -> list[dict]:
    """Merge FY series across synonymous XBRL tags; later tags win.

    US-GAAP concepts evolved over time — e.g. revenue reported as
    `SalesRevenueNet` pre-ASC 606 then as
    `RevenueFromContractWithCustomerExcludingAssessedTax` after 2018.
    We concatenate series across all provided tags and dedupe by
    fiscal year, preferring the row from the LAST tag in the tuple
    (most-specific / most-recent convention).
    """
    merged: dict[int, dict] = {}
    for t in tags:
        for row in _fact_series(facts, t):
            fy = row.get("fy")
            if fy is not None:
                merged[fy] = row
    return [merged[k] for k in sorted(merged)]


# ── Public API ──────────────────────────────────────────────────────────────


def fetch_company_financials(
    ticker: str,
    years: int = 5,
    prefer_bundled: bool = False,
    timeout: float = 15.0,
) -> Optional[EdgarFinancials]:
    """Fetch N years of XBRL financials for a US-listed ticker.

    Order: bundled sample (if prefer_bundled or if live fails) → live
    EDGAR. Returns None only if neither path produces data.
    """
    ticker_u = ticker.upper()

    # Try bundled first if asked
    if prefer_bundled and ticker_u in _BUNDLED_SAMPLE:
        return _extract_from_payload(
            ticker_u, _BUNDLED_SAMPLE[ticker_u],
            source_url="bundled:modelforge.ingest.edgar._BUNDLED_SAMPLE",
            fetched_from="bundled", years=years,
        )

    # Live path
    cik = _lookup_cik_live(ticker_u, timeout=timeout)
    if cik is not None:
        payload = _fetch_facts_live(cik, timeout=timeout)
        if payload is not None:
            return _extract_from_payload(
                ticker_u, payload,
                source_url=_FACTS_URL.format(cik=cik),
                fetched_from="live", years=years,
            )

    # Fall back to bundled
    if ticker_u in _BUNDLED_SAMPLE:
        return _extract_from_payload(
            ticker_u, _BUNDLED_SAMPLE[ticker_u],
            source_url="bundled:modelforge.ingest.edgar._BUNDLED_SAMPLE",
            fetched_from="bundled",
            years=years,
        )
    return None


def _extract_from_payload(
    ticker: str, payload: dict, source_url: str,
    fetched_from: str, years: int,
) -> EdgarFinancials:
    facts = payload.get("facts", {}) or payload  # live vs bundled shape
    revenue = _first_available(facts, _REVENUE_TAGS)
    opincome = _first_available(facts, _OPINCOME_TAGS)
    netincome = _first_available(facts, _NETINCOME_TAGS)

    fys = sorted({r.get("fy") for r in revenue if r.get("fy")})[-years:]

    def _lookup(series: list[dict], fy: int) -> Optional[float]:
        for r in series:
            if r.get("fy") == fy:
                return float(r.get("val", 0)) / 1_000_000.0  # → millions
        return None

    rev_m = [_lookup(revenue, fy) or 0.0 for fy in fys]
    opinc_m = [_lookup(opincome, fy) or 0.0 for fy in fys]
    ni_m = [_lookup(netincome, fy) or 0.0 for fy in fys]

    # Snapshot values (most recent FY)
    assets_series = _first_available(facts, _ASSETS_TAGS)
    assets_m = (float(assets_series[-1]["val"]) / 1_000_000.0
                if assets_series else None)
    ltdebt_series = _first_available(facts, _LTDEBT_TAGS)
    ltdebt_m = (float(ltdebt_series[-1]["val"]) / 1_000_000.0
                if ltdebt_series else None)

    notes: list[str] = []
    if fetched_from == "bundled":
        notes.append("Using bundled sample; live EDGAR unreachable or "
                     "prefer_bundled=True.")
    if len(fys) < years:
        notes.append(f"Only {len(fys)} FYs available (requested {years}).")

    return EdgarFinancials(
        ticker=ticker,
        cik=int(payload.get("cik", 0)),
        entity_name=str(payload.get("entityName", ticker)),
        fiscal_years=list(fys),
        revenue_usd_m=rev_m,
        operating_income_usd_m=opinc_m,
        net_income_usd_m=ni_m,
        total_assets_usd_m=assets_m,
        long_term_debt_usd_m=ltdebt_m,
        source_url=source_url,
        fetched_from=fetched_from,
        notes=notes,
    )

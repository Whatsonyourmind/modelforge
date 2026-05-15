"""SEC EDGAR filings adapter — US regulatory source-of-truth.

Provider-interface wrapper around EDGAR. The richer XBRL company-facts
loader lives in ``modelforge.ingest.edgar`` (used by templates that
seed historicals). This module focuses on:

* **Submissions** — every 10-K / 10-Q / 8-K / S-1 a registrant filed.
* **CIK lookup** — ticker ↔ 10-digit Central Index Key.
* **Insider holdings** — Form 4 / Form 13F summaries.

Why ship this: every US M&A / equity research / credit team starts the
day at EDGAR. It is the regulator-blessed source — anything else is a
mirror. 100% free, no API key, but the SEC requires a contact User-Agent
under their fair-use policy.

API docs:
* https://www.sec.gov/edgar/sec-api-documentation
* https://data.sec.gov/

Rate limits: SEC asks for ≤10 req/sec. We rely on cache to stay polite.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from modelforge.feeds.cache import get_cache
from modelforge.feeds.provider import Filing, Provider, ProviderError

_USER_AGENT = (
    "ModelForge/0.9 (contact: luka.stanisljevic@gmail.com) Python/urllib"
)
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_BASE_ARCHIVE = "https://www.sec.gov/Archives/edgar/data"


def _get(url: str, *, cache_ttl: int) -> Any:
    cache = get_cache()
    cache_key = f"edgar:{url}"
    cached = cache.get(cache_key, ttl_seconds=cache_ttl)
    if cached is not None:
        return cached

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ProviderError(f"EDGAR HTTP {e.code} on {url}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"EDGAR network error: {e.reason}") from e

    cache.set(cache_key, data)
    return data


# ─── helpers ────────────────────────────────────────────────────────────────


def lookup_cik(ticker: str) -> Optional[int]:
    """Resolve a US ticker to a 10-digit CIK."""
    data = _get(_TICKERS_URL, cache_ttl=86400)
    if not isinstance(data, dict):
        return None
    target = ticker.upper()
    for entry in data.values():
        if str(entry.get("ticker", "")).upper() == target:
            return int(entry["cik_str"])
    return None


def submissions(cik: int | str) -> dict:
    """Fetch the submissions index for a CIK."""
    cik_int = int(str(cik).lstrip("0") or "0")
    return _get(_SUBMISSIONS_URL.format(cik=cik_int), cache_ttl=3600)


def list_filings(
    cik_or_ticker: str | int,
    *,
    form: Optional[str] = None,
    limit: int = 20,
) -> list[Filing]:
    """List a registrant's recent filings, newest first.

    Args:
        cik_or_ticker: e.g. ``"AAPL"`` or ``320193`` or ``"0000320193"``.
        form: optional form filter, e.g. ``"10-K"``, ``"10-Q"``, ``"8-K"``.
        limit: max number of filings returned.
    """
    if isinstance(cik_or_ticker, str) and not cik_or_ticker.isdigit():
        cik = lookup_cik(cik_or_ticker)
        if cik is None:
            raise ProviderError(f"EDGAR: ticker not found: {cik_or_ticker}")
    else:
        cik = int(str(cik_or_ticker).lstrip("0") or "0")

    sub = submissions(cik)
    recent = (sub.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    accs = recent.get("accessionNumber") or []
    dates = recent.get("filingDate") or []
    primary = recent.get("primaryDocument") or []

    out: list[Filing] = []
    for i, frm in enumerate(forms):
        if form and frm != form:
            continue
        acc = accs[i] if i < len(accs) else ""
        date = dates[i] if i < len(dates) else ""
        doc = primary[i] if i < len(primary) else None
        # URL convention: archives/edgar/data/{cik_int}/{acc_no_dashes}/{doc}
        acc_clean = acc.replace("-", "")
        url = f"{_BASE_ARCHIVE}/{cik}/{acc_clean}/{doc}" if doc else None
        out.append(Filing(
            cik=str(cik).zfill(10),
            accession_number=acc,
            form=frm,
            filed_date=date,
            primary_document=doc,
            url=url,
        ))
        if len(out) >= limit:
            break
    return out


def latest_10k(ticker: str) -> Optional[Filing]:
    rows = list_filings(ticker, form="10-K", limit=1)
    return rows[0] if rows else None


def latest_10q(ticker: str) -> Optional[Filing]:
    rows = list_filings(ticker, form="10-Q", limit=1)
    return rows[0] if rows else None


def recent_8ks(ticker: str, *, limit: int = 10) -> list[Filing]:
    return list_filings(ticker, form="8-K", limit=limit)


# ─── Provider adapter ───────────────────────────────────────────────────────


class EdgarProvider(Provider):
    name = "edgar"
    tier = "free"
    requires_auth = False

    def is_available(self) -> bool:
        return True  # public API, no auth

    def filings(
        self,
        cik: str,
        *,
        form: Optional[str] = None,
        limit: int = 20,
    ) -> list[Filing]:
        return list_filings(cik, form=form, limit=limit)

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search the global ticker index by ticker or company name."""
        data = _get(_TICKERS_URL, cache_ttl=86400)
        if not isinstance(data, dict):
            return []
        q = query.upper()
        out: list[dict[str, Any]] = []
        for entry in data.values():
            ticker = str(entry.get("ticker", "")).upper()
            name = str(entry.get("title", "")).upper()
            if q in ticker or q in name:
                out.append({
                    "ticker": entry.get("ticker"),
                    "cik": int(entry.get("cik_str", 0)),
                    "name": entry.get("title"),
                })
                if len(out) >= limit:
                    break
        return out

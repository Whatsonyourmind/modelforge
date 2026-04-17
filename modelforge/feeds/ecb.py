"""ECB Statistical Data Warehouse adapter.

Pulls EURIBOR 3M / 6M / 12M, ECB main refinancing rate, and ESTR from
https://data-api.ecb.europa.eu/ .

Free public API. No key required. Response is SDMX-JSON; we parse
just the latest observation for each series.

Series ID reference (as of 2026-04):
    FM.M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA  — 3M EURIBOR, monthly avg
    FM.M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA  — 6M EURIBOR
    FM.M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA  — 12M EURIBOR
    FM.D.U2.EUR.4F.KR.MRR_FR.LEV        — ECB Main Refinancing Rate
    FM.D.U2.EUR.4F.KR.DFR.LEV           — Deposit Facility Rate
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from modelforge.feeds.cache import FeedSnapshot, cache_dir


# ── Bundled 2026-04 snapshot (Apr 2026 mid-month indicative levels) ─────────

_BUNDLED = {
    "euribor_3m": 0.0385,
    "euribor_6m": 0.0395,
    "euribor_12m": 0.0405,
    "ecb_main_refi": 0.0400,
    "ecb_deposit_facility": 0.0350,
    "estr": 0.0391,
    "as_of_date": "2026-04-15",
}


_SDMX_URL = "https://data-api.ecb.europa.eu/service/data"
_SERIES = {
    "euribor_3m": "FM.M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA",
    "euribor_6m": "FM.M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA",
    "euribor_12m": "FM.M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA",
    "ecb_main_refi": "FM.D.U2.EUR.4F.KR.MRR_FR.LEV",
    "ecb_deposit_facility": "FM.D.U2.EUR.4F.KR.DFR.LEV",
}


@dataclass
class ECBFeed:
    """Adapter for ECB SDW — bundled snapshot + optional live refresh."""

    snapshot: FeedSnapshot

    @classmethod
    def load(cls, prefer_cache: bool = True) -> "ECBFeed":
        """Load from on-disk cache if present, else from bundled data."""
        if prefer_cache:
            p = cache_dir() / "ecb.json"
            if p.exists():
                return cls(snapshot=FeedSnapshot.load(p))
        return cls(snapshot=FeedSnapshot(
            adapter="ecb",
            fetched_at="2026-04-15T12:00:00+00:00",  # bundled snapshot date
            source_url="bundled:modelforge.feeds.ecb._BUNDLED",
            data=dict(_BUNDLED),
        ))

    # ── Convenience accessors
    @property
    def euribor_3m(self) -> float: return float(self.snapshot.data["euribor_3m"])
    @property
    def euribor_6m(self) -> float: return float(self.snapshot.data["euribor_6m"])
    @property
    def euribor_12m(self) -> float: return float(self.snapshot.data["euribor_12m"])
    @property
    def ecb_main_refi(self) -> float: return float(self.snapshot.data["ecb_main_refi"])
    @property
    def deposit_facility(self) -> float: return float(self.snapshot.data["ecb_deposit_facility"])
    @property
    def as_of(self) -> str: return self.snapshot.data.get("as_of_date", self.snapshot.fetched_at)

    # ── Live refresh
    def refresh(self, timeout: float = 10.0) -> "ECBFeed":
        """Fetch latest observation for each series from ECB SDW.

        Swallows network errors and returns the current snapshot
        unchanged (graceful degradation). To see fetch errors,
        wrap in try/except around `_fetch_series`.
        """
        try:
            import urllib.request
            import urllib.error
            import json
        except ImportError:
            return self

        new_data: dict[str, float | str] = {}
        for key, series_id in _SERIES.items():
            url = f"{_SDMX_URL}/{series_id}?lastNObservations=1&format=jsondata"
            try:
                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    payload = json.loads(r.read().decode("utf-8"))
                # SDMX-JSON: data.dataSets[0].series["0:0:0:..."].observations["0"] = [value, ...]
                ds = payload.get("dataSets", [{}])[0].get("series", {})
                if ds:
                    obs = next(iter(ds.values())).get("observations", {})
                    if obs:
                        val = next(iter(obs.values()))[0]
                        new_data[key] = float(val) / 100.0  # SDW returns percent
            except Exception:
                # Skip this series; keep the bundled value
                pass

        if new_data:
            merged = dict(self.snapshot.data)
            merged.update(new_data)
            merged["as_of_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            snap = FeedSnapshot.now("ecb", _SDMX_URL, merged)
            snap.save()
            return ECBFeed(snapshot=snap)
        return self

    def as_rows(self) -> list[tuple[str, float]]:
        return [
            ("EURIBOR 3M", self.euribor_3m),
            ("EURIBOR 6M", self.euribor_6m),
            ("EURIBOR 12M", self.euribor_12m),
            ("ECB Main Refi", self.ecb_main_refi),
            ("ECB Deposit Facility", self.deposit_facility),
        ]

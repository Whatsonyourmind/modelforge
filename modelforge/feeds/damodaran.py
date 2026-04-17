"""Damodaran country risk premium adapter.

Source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html
Publishes an annual CSV (January each year). Ships bundled 2026-01
snapshot for 10+ countries relevant to Italian credit / structured
finance work. Live refresh scrapes the current HTML/CSV.

The mature-market ERP is the risk-free anchor; country-specific ERP
= mature + country risk premium.
"""

from __future__ import annotations

from dataclasses import dataclass

from modelforge.feeds.cache import FeedSnapshot, cache_dir


# Damodaran 2026-01 country risk snapshot (decimal form)
_BUNDLED = {
    "mature_market_erp": 0.0423,   # US / mature markets base ERP
    "countries": {
        "IT": {"country_risk_premium": 0.0247, "total_erp": 0.0670, "rating": "BBB"},
        "DE": {"country_risk_premium": 0.0000, "total_erp": 0.0423, "rating": "AAA"},
        "FR": {"country_risk_premium": 0.0066, "total_erp": 0.0489, "rating": "AA"},
        "ES": {"country_risk_premium": 0.0165, "total_erp": 0.0588, "rating": "A"},
        "GB": {"country_risk_premium": 0.0041, "total_erp": 0.0464, "rating": "AA"},
        "US": {"country_risk_premium": 0.0000, "total_erp": 0.0423, "rating": "AAA"},
        "CH": {"country_risk_premium": 0.0000, "total_erp": 0.0423, "rating": "AAA"},
        "NL": {"country_risk_premium": 0.0000, "total_erp": 0.0423, "rating": "AAA"},
        "GR": {"country_risk_premium": 0.0412, "total_erp": 0.0835, "rating": "BB"},
        "PT": {"country_risk_premium": 0.0165, "total_erp": 0.0588, "rating": "A"},
    },
    "as_of": "2026-01-15",
}


@dataclass
class DamodaranFeed:
    snapshot: FeedSnapshot

    @classmethod
    def load(cls, prefer_cache: bool = True) -> "DamodaranFeed":
        if prefer_cache:
            p = cache_dir() / "damodaran.json"
            if p.exists():
                return cls(snapshot=FeedSnapshot.load(p))
        return cls(snapshot=FeedSnapshot(
            adapter="damodaran",
            fetched_at="2026-01-15T00:00:00+00:00",
            source_url="bundled:damodaran.2026-01",
            data=dict(_BUNDLED),
        ))

    @property
    def mature_market_erp(self) -> float:
        return float(self.snapshot.data["mature_market_erp"])

    def country_erp(self, iso2: str) -> float:
        c = self.snapshot.data["countries"].get(iso2.upper())
        if c is None:
            raise KeyError(f"Damodaran country not available: {iso2}")
        return float(c["total_erp"])

    def country_risk_premium(self, iso2: str) -> float:
        c = self.snapshot.data["countries"].get(iso2.upper())
        if c is None:
            raise KeyError(f"Damodaran country not available: {iso2}")
        return float(c["country_risk_premium"])

    def country_rating(self, iso2: str) -> str:
        c = self.snapshot.data["countries"].get(iso2.upper())
        if c is None:
            raise KeyError(f"Damodaran country not available: {iso2}")
        return str(c["rating"])

    def available_countries(self) -> list[str]:
        return sorted(self.snapshot.data["countries"].keys())

    def as_rows(self) -> list[tuple[str, float, float, str]]:
        rows: list[tuple[str, float, float, str]] = []
        for iso, c in sorted(self.snapshot.data["countries"].items()):
            rows.append((iso,
                         float(c["country_risk_premium"]),
                         float(c["total_erp"]),
                         str(c["rating"])))
        return rows

    def refresh(self, timeout: float = 10.0) -> "DamodaranFeed":
        """Damodaran publishes annually; live scrape is brittle (HTML
        layout changes). We expose refresh() as a placeholder that
        keeps the bundled snapshot — manually update _BUNDLED with
        the January release each year."""
        return self

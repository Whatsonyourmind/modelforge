"""Tests for modelforge.feeds (US-019 — ECB + Damodaran)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modelforge.feeds import DamodaranFeed, ECBFeed, FeedSnapshot


# ─── Bundled-snapshot behaviour ──────────────────────────────────────────────


def test_ecb_loads_bundled_snapshot_by_default():
    # Don't prefer cache so we always hit bundled
    ecb = ECBFeed.load(prefer_cache=False)
    assert 0.02 < ecb.euribor_3m < 0.05
    assert 0.02 < ecb.euribor_6m < 0.06
    assert 0.02 < ecb.euribor_12m < 0.06
    assert 0.02 < ecb.ecb_main_refi < 0.06


def test_ecb_euribor_term_structure_non_negative():
    """Longer tenors should carry at least the short-end rate."""
    ecb = ECBFeed.load(prefer_cache=False)
    assert ecb.euribor_6m >= ecb.euribor_3m - 1e-6
    assert ecb.euribor_12m >= ecb.euribor_6m - 1e-6


def test_damodaran_italy_erp_matches_2026_reference():
    """Italy total ERP should be ~6.7% per Damodaran Jan 2026 table."""
    dam = DamodaranFeed.load(prefer_cache=False)
    assert abs(dam.country_erp("IT") - 0.067) < 0.005


def test_damodaran_mature_erp_reasonable():
    dam = DamodaranFeed.load(prefer_cache=False)
    assert 0.03 < dam.mature_market_erp < 0.06


def test_damodaran_country_lookup_by_iso2():
    dam = DamodaranFeed.load(prefer_cache=False)
    # Italy ERP should exceed Germany (more country risk)
    assert dam.country_erp("IT") > dam.country_erp("DE")
    # Greece should exceed Italy (higher country risk)
    assert dam.country_erp("GR") > dam.country_erp("IT")


def test_damodaran_country_risk_ordering():
    dam = DamodaranFeed.load(prefer_cache=False)
    # Mature markets (DE, US, NL) should have 0 CRP
    for iso in ("DE", "US", "NL", "CH"):
        assert dam.country_risk_premium(iso) == pytest.approx(0.0)


def test_damodaran_unknown_country_raises():
    dam = DamodaranFeed.load(prefer_cache=False)
    with pytest.raises(KeyError):
        dam.country_erp("XX")


def test_damodaran_rating_returned():
    dam = DamodaranFeed.load(prefer_cache=False)
    assert dam.country_rating("DE") == "AAA"
    assert dam.country_rating("IT") == "BBB"


def test_damodaran_available_countries_is_sorted():
    dam = DamodaranFeed.load(prefer_cache=False)
    countries = dam.available_countries()
    assert countries == sorted(countries)
    assert "IT" in countries


# ─── Refresh degrades gracefully ─────────────────────────────────────────────


def test_ecb_refresh_network_error_returns_existing():
    """If ECB network call fails, refresh returns the existing feed."""
    ecb = ECBFeed.load(prefer_cache=False)
    with patch("urllib.request.urlopen", side_effect=ConnectionError("test")):
        ecb2 = ecb.refresh(timeout=0.1)
    # Values unchanged
    assert ecb2.euribor_3m == ecb.euribor_3m


def test_damodaran_refresh_is_noop():
    """Damodaran is annual — refresh is intentionally a no-op."""
    dam = DamodaranFeed.load(prefer_cache=False)
    dam2 = dam.refresh()
    assert dam2.country_erp("IT") == dam.country_erp("IT")


# ─── Snapshot cache round-trip ───────────────────────────────────────────────


def test_snapshot_save_and_load_roundtrip(tmp_path):
    snap = FeedSnapshot.now("test", "http://example", {"x": 1, "y": [1, 2]})
    path = tmp_path / "snap.json"
    snap.save(path)
    loaded = FeedSnapshot.load(path)
    assert loaded.adapter == "test"
    assert loaded.source_url == "http://example"
    assert loaded.data["x"] == 1
    assert loaded.data["y"] == [1, 2]

"""Tests for the v0.9.7 provider stack — Polygon, FMP, Finnhub, Tiingo,
EDGAR, OpenFIGI, GLEIF, Bloomberg, Refinitiv, FactSet, S&P Capital IQ,
the registry, and the cache layer.

All HTTP is mocked. We never reach the network — tests must run in CI
without any API keys present.
"""

from __future__ import annotations

import io
import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from modelforge.feeds import (
    AuthRequired,
    Bar,
    Entity,
    Filing,
    Fundamentals,
    NoProviderAvailable,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
    Registry,
    TTLCache,
    cache_dir,
    get_cache,
    registry,
    status,
)
from modelforge.feeds.bloomberg import BloombergProvider
from modelforge.feeds.edgar import EdgarProvider
from modelforge.feeds.factset import FactSetProvider
from modelforge.feeds.finnhub import FinnhubProvider
from modelforge.feeds.fmp import FMPProvider
from modelforge.feeds.gleif import GLEIFProvider
from modelforge.feeds.openfigi import OpenFIGIProvider
from modelforge.feeds.polygon import PolygonProvider
from modelforge.feeds.refinitiv import RefinitivProvider
from modelforge.feeds.spcapiq import SPCapitalIQProvider
from modelforge.feeds.tiingo import TiingoProvider


# ─── helpers ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_creds(monkeypatch):
    """Strip any provider creds inherited from the dev box."""
    for k in (
        "POLYGON_API_KEY", "FMP_API_KEY", "FINNHUB_API_KEY", "TIINGO_API_KEY",
        "ALPHAVANTAGE_API_KEY", "OPENFIGI_API_KEY",
        "REFINITIV_APP_KEY", "EIKON_APP_KEY",
        "FACTSET_USERNAME_SERIAL", "FACTSET_API_KEY",
        "SPGLOBAL_API_KEY", "SPGLOBAL_API_SECRET",
        "BLOOMBERG_HOST", "BLOOMBERG_PORT",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")


def _http_mock(payload: dict | list | bytes, status_code: int = 200):
    """Build a fake urlopen context manager returning ``payload``."""
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body
    cm.__enter__.return_value.headers = {}
    return cm


# ─── cache layer ────────────────────────────────────────────────────────────


def test_ttl_cache_roundtrips_with_ttl(tmp_path, monkeypatch):
    monkeypatch.delenv("MODELFORGE_FEEDS_NOCACHE", raising=False)
    c = TTLCache(root=tmp_path)
    c.set("k", {"a": 1})
    assert c.get("k", ttl_seconds=60) == {"a": 1}


def test_ttl_cache_expires_when_stale(tmp_path, monkeypatch):
    monkeypatch.delenv("MODELFORGE_FEEDS_NOCACHE", raising=False)
    c = TTLCache(root=tmp_path)
    c.set("k", "v")
    # Force ttl 0 → must be considered stale
    assert c.get("k", ttl_seconds=0) is None


def test_ttl_cache_disable_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    c = TTLCache(root=tmp_path)
    c.set("k", "v")
    assert c.get("k", ttl_seconds=999999) is None


def test_ttl_cache_clear(tmp_path, monkeypatch):
    monkeypatch.delenv("MODELFORGE_FEEDS_NOCACHE", raising=False)
    c = TTLCache(root=tmp_path)
    c.set("a", 1); c.set("b", 2); c.set("c", 3)
    assert c.clear() == 3


def test_get_cache_returns_singleton():
    a = get_cache()
    b = get_cache()
    assert a is b


# ─── provider base ──────────────────────────────────────────────────────────


def test_provider_default_methods_raise_not_supported():
    class Stub(Provider):
        name = "stub"
        def is_available(self): return True
    p = Stub()
    with pytest.raises(NotSupported):
        p.quote("AAPL")
    with pytest.raises(NotSupported):
        p.history("AAPL")
    with pytest.raises(NotSupported):
        p.fundamentals("AAPL")
    with pytest.raises(NotSupported):
        p.filings("0000320193")
    with pytest.raises(NotSupported):
        p.entity_lookup(ticker="AAPL")
    with pytest.raises(NotSupported):
        p.search("apple")


def test_provider_supports_introspection():
    class Stub(Provider):
        name = "stub"
        def is_available(self): return True
        def quote(self, symbol):
            return Quote(symbol=symbol, price=1.0)
    p = Stub()
    assert p.supports("quote") is True
    assert p.supports("history") is False


# ─── Polygon ────────────────────────────────────────────────────────────────


def test_polygon_unavailable_without_key():
    p = PolygonProvider()
    assert p.is_available() is False


def test_polygon_quote_routes_through_previous_close(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = {"status": "OK", "results": [
        {"o": 100.0, "h": 105.0, "l": 99.0, "c": 104.0, "v": 1_000_000, "t": 1_700_000_000_000}
    ]}
    p = PolygonProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        q = p.quote("AAPL")
    assert q.symbol == "AAPL"
    assert q.price == 104.0
    assert q.previous_close == 100.0
    assert q.source == "polygon"


def test_polygon_aggregates_returns_normalized_bars(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = {"status": "OK", "results": [
        {"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100, "t": 1_700_000_000_000},
        {"o": 1.5, "h": 3, "l": 1.4, "c": 2.5, "v": 200, "t": 1_700_086_400_000},
    ]}
    p = PolygonProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        bars = p.history("AAPL", interval="1d", start="2025-01-01", end="2025-01-02", limit=10)
    assert len(bars) == 2
    assert bars[0].close == 1.5
    assert bars[1].close == 2.5


def test_polygon_auth_error_translates(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    import urllib.error
    err = urllib.error.HTTPError("u", 401, "Unauthorized", None, io.BytesIO(b""))
    p = PolygonProvider()
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(AuthRequired):
            p.quote("AAPL")


# ─── FMP ────────────────────────────────────────────────────────────────────


def test_fmp_unavailable_without_key():
    assert FMPProvider().is_available() is False


def test_fmp_quote_normalizes(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = [{"symbol": "AAPL", "price": 200.0, "previousClose": 195.0,
                "changesPercentage": 2.56, "volume": 50_000_000, "exchange": "NASDAQ"}]
    p = FMPProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        q = p.quote("AAPL")
    assert q.symbol == "AAPL"
    assert q.price == 200.0
    assert q.exchange == "NASDAQ"
    assert q.source == "fmp"


def test_fmp_fundamentals_merges_three_statements(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    income = [{"date": "2024-12-31", "reportedCurrency": "USD",
               "revenue": 1000.0, "operatingIncome": 200.0,
               "depreciationAndAmortization": 50.0, "netIncome": 150.0,
               "eps": 1.5, "weightedAverageShsOutDil": 100.0}]
    bs = [{"date": "2024-12-31", "totalAssets": 5000.0,
           "totalDebt": 1500.0, "cashAndCashEquivalents": 800.0}]
    cf = [{"date": "2024-12-31", "operatingCashFlow": 300.0, "capitalExpenditure": -80.0}]

    payloads = [income, bs, cf]
    call_count = {"i": 0}

    def fake(req, **_):
        body = json.dumps(payloads[call_count["i"]]).encode()
        call_count["i"] += 1
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = body
        return cm

    p = FMPProvider()
    with patch("urllib.request.urlopen", side_effect=fake):
        rows = p.fundamentals("AAPL", period="annual", limit=1)
    assert len(rows) == 1
    f = rows[0]
    assert f.revenue == 1000.0
    assert f.ebit == 200.0
    assert f.ebitda == 250.0  # 200 + 50
    assert f.free_cash_flow == 220.0  # 300 + (-80)
    assert f.source == "fmp"


# ─── Finnhub ────────────────────────────────────────────────────────────────


def test_finnhub_unavailable_without_key():
    assert FinnhubProvider().is_available() is False


def test_finnhub_quote_computes_change_pct(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = {"c": 105.0, "h": 106.0, "l": 100.0, "o": 101.0, "pc": 100.0}
    p = FinnhubProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        q = p.quote("AAPL")
    assert q.price == 105.0
    assert q.previous_close == 100.0
    assert abs(q.change_pct - 5.0) < 1e-6


def test_finnhub_history_decodes_candles(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = {
        "s": "ok",
        "t": [1_700_000_000, 1_700_086_400],
        "o": [1, 2], "h": [3, 4], "l": [0.5, 1.5], "c": [2, 3], "v": [100, 200],
    }
    p = FinnhubProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        bars = p.history("AAPL", interval="1d", start="2025-01-01", end="2025-01-02")
    assert len(bars) == 2
    assert bars[0].close == 2
    assert bars[1].volume == 200


# ─── Tiingo ─────────────────────────────────────────────────────────────────


def test_tiingo_unavailable_without_key():
    assert TiingoProvider().is_available() is False


def test_tiingo_history_uses_adjusted_prices(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "X")
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = [
        {"date": "2025-01-02T00:00:00.000Z",
         "adjOpen": 1.1, "adjHigh": 1.2, "adjLow": 1.0, "adjClose": 1.15,
         "adjVolume": 1000},
    ]
    p = TiingoProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        bars = p.history("AAPL", start="2025-01-01", end="2025-01-02")
    assert len(bars) == 1
    assert bars[0].close == 1.15
    assert bars[0].date == "2025-01-02"


# ─── EDGAR (free, real only on integration days) ────────────────────────────


def test_edgar_provider_always_available():
    assert EdgarProvider().is_available() is True


def test_edgar_filings_parses_submissions(monkeypatch):
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    submissions_payload = {"filings": {"recent": {
        "form": ["10-K", "10-Q", "8-K"],
        "accessionNumber": ["0000320193-25-000079", "0000320193-25-000050", "0000320193-25-000040"],
        "filingDate": ["2025-10-31", "2025-08-01", "2025-06-12"],
        "primaryDocument": ["aapl-20250927.htm", "aapl-q3.htm", "aapl-8k.htm"],
    }}}

    call_count = {"i": 0}
    payloads = [tickers, submissions_payload]

    def fake(req, **_):
        body = json.dumps(payloads[call_count["i"]]).encode()
        call_count["i"] += 1
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = body
        return cm

    p = EdgarProvider()
    with patch("urllib.request.urlopen", side_effect=fake):
        rows = p.filings("AAPL", form="10-K", limit=5)
    assert len(rows) == 1
    f = rows[0]
    assert f.cik == "0000320193"
    assert f.form == "10-K"
    assert "320193" in f.url and "10-K" not in f.url


def test_edgar_search_filters_by_query(monkeypatch):
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    tickers = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
    }
    p = EdgarProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(tickers)):
        rows = p.search("AAPL", limit=5)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"


# ─── OpenFIGI ───────────────────────────────────────────────────────────────


def test_openfigi_always_available():
    assert OpenFIGIProvider().is_available() is True


def test_openfigi_entity_lookup_by_ticker(monkeypatch):
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = [{"data": [{
        "figi": "BBG000B9XRY4", "name": "APPLE INC", "ticker": "AAPL",
        "exchCode": "US", "marketSector": "Equity",
    }]}]
    p = OpenFIGIProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        e = p.entity_lookup(ticker="AAPL")
    assert e.figi == "BBG000B9XRY4"
    assert e.name == "APPLE INC"


def test_openfigi_entity_lookup_requires_id():
    p = OpenFIGIProvider()
    with pytest.raises(ProviderError):
        p.entity_lookup()


# ─── GLEIF ──────────────────────────────────────────────────────────────────


def test_gleif_always_available():
    assert GLEIFProvider().is_available() is True


def test_gleif_entity_lookup_parses_record(monkeypatch):
    monkeypatch.setenv("MODELFORGE_FEEDS_NOCACHE", "1")
    payload = {"data": {
        "attributes": {
            "lei": "HWUPKR0MPOU8FGXBT394",
            "entity": {
                "legalName": {"name": "Apple Inc."},
                "legalAddress": {"country": "US"},
            },
        },
    }}
    p = GLEIFProvider()
    with patch("urllib.request.urlopen", return_value=_http_mock(payload)):
        e = p.entity_lookup(lei="HWUPKR0MPOU8FGXBT394")
    assert e.name == "Apple Inc."
    assert e.lei == "HWUPKR0MPOU8FGXBT394"
    assert e.country == "US"


def test_gleif_entity_lookup_requires_lei():
    p = GLEIFProvider()
    with pytest.raises(ProviderError):
        p.entity_lookup(ticker="AAPL")  # GLEIF only takes LEI


# ─── Bloomberg / Refinitiv / FactSet / S&P — graceful degradation ───────────


def test_bloomberg_unavailable_without_sdk():
    p = BloombergProvider()
    # blpapi is highly unlikely to be installed in CI
    if p.is_available():
        pytest.skip("blpapi installed; integration test required")
    assert p.is_available() is False


def test_bloomberg_quote_raises_actionable_when_no_sdk(monkeypatch):
    p = BloombergProvider()
    if p.is_available():
        pytest.skip("blpapi installed; integration test required")
    with pytest.raises(AuthRequired) as exc:
        p.quote("IBM US Equity")
    assert "blpapi" in str(exc.value)


def test_refinitiv_unavailable_without_sdk():
    assert RefinitivProvider().is_available() is False


def test_factset_unavailable_without_sdk():
    assert FactSetProvider().is_available() is False


def test_spcapiq_unavailable_without_creds():
    assert SPCapitalIQProvider().is_available() is False


# ─── Registry + routing ─────────────────────────────────────────────────────


def test_registry_lists_full_default_stack():
    r = Registry()
    names = [p.name for p in r.list()]
    for expected in (
        "bloomberg", "refinitiv", "factset", "spcapiq",
        "polygon", "fmp", "finnhub", "tiingo",
        "edgar", "openfigi", "gleif",
    ):
        assert expected in names, f"missing {expected}"


def test_registry_status_reports_tier_and_caps():
    rows = Registry().status()
    edgar = next(r for r in rows if r["name"] == "edgar")
    assert edgar["tier"] == "free"
    assert "filings" in edgar["supports"]
    bloomberg = next(r for r in rows if r["name"] == "bloomberg")
    assert bloomberg["tier"] == "bulge"


def test_registry_quote_raises_when_nothing_available():
    r = Registry()
    with pytest.raises(NoProviderAvailable):
        r.quote("AAPL")


def test_registry_routes_to_preferred(monkeypatch):
    """`prefer=` jumps an institutional provider ahead of bulge."""
    class FakeFmp(Provider):
        name = "fmp"
        tier = "institutional"
        def is_available(self): return True
        def quote(self, symbol):
            return Quote(symbol=symbol, price=999.0, source="fmp")

    class FakeBloomberg(Provider):
        name = "bloomberg"
        tier = "bulge"
        def is_available(self): return True
        def quote(self, symbol):
            return Quote(symbol=symbol, price=111.0, source="bloomberg")

    r = Registry(providers=[FakeFmp(), FakeBloomberg()])
    # Default tier order picks bulge first
    assert r.quote("AAPL").source == "bloomberg"
    # prefer flips it
    assert r.quote("AAPL", prefer="fmp").source == "fmp"


def test_registry_falls_back_when_preferred_fails():
    class Broken(Provider):
        name = "broken"
        tier = "bulge"
        def is_available(self): return True
        def quote(self, symbol):
            raise ProviderError("boom")

    class Good(Provider):
        name = "good"
        tier = "institutional"
        def is_available(self): return True
        def quote(self, symbol):
            return Quote(symbol=symbol, price=42.0, source="good")

    r = Registry(providers=[Broken(), Good()])
    q = r.quote("AAPL")
    assert q.source == "good"
    assert q.price == 42.0


def test_registry_skips_unavailable_providers():
    class Authd(Provider):
        name = "auth_needed"
        tier = "bulge"
        requires_auth = True
        def is_available(self): return False
        def quote(self, symbol): raise AuthRequired("nope")

    class Free(Provider):
        name = "free_one"
        tier = "free"
        def is_available(self): return True
        def quote(self, symbol):
            return Quote(symbol=symbol, price=1.0, source="free_one")

    r = Registry(providers=[Authd(), Free()])
    q = r.quote("AAPL")
    assert q.source == "free_one"


def test_registry_register_replaces_by_name():
    class V1(Provider):
        name = "x"; tier = "free"
        def is_available(self): return True
    class V2(Provider):
        name = "x"; tier = "free"
        def is_available(self): return True
    r = Registry(providers=[V1()])
    r.register(V2())
    matches = [p for p in r.list() if p.name == "x"]
    assert len(matches) == 1
    assert isinstance(matches[0], V2)


# ─── module-level facade ────────────────────────────────────────────────────


def test_module_facade_status_returns_rows():
    rows = status()
    assert isinstance(rows, list)
    assert len(rows) >= 5
    assert all("name" in r and "tier" in r for r in rows)


def test_module_facade_registry_singleton():
    assert registry() is registry()

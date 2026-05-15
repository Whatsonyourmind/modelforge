"""Live data feeds — bulge-tier through free.

Three tiers of providers:

* **bulge** — Bloomberg, Refinitiv (LSEG), FactSet, S&P Capital IQ.
              Real-time institutional. Optional dependency on vendor SDK.
* **institutional** — Polygon, Tiingo, Finnhub, FMP. Quant-grade at
              retail price. HTTP API + token.
* **free** — ECB, FRED, Yahoo, World Bank, Damodaran, EDGAR, OpenFIGI,
              GLEIF, AlphaVantage. Public-data adapters, bundled snapshots.

Every adapter implements the unified :class:`Provider` interface so the
registry can route ``quote``, ``history``, ``fundamentals``, ``filings``,
``entity_lookup``, and ``search`` to the best available source.

Quick start::

    from modelforge.feeds import quote, fundamentals
    q = quote("AAPL")                          # auto-routed
    fs = fundamentals("AAPL", limit=5)         # 5y annual
    q = quote("AAPL", prefer="bloomberg")      # explicit

The package never reaches the network on import — adapters fetch lazily
and cache responses to ``~/.modelforge/feeds/``.
"""

from modelforge.feeds.cache import (
    FeedSnapshot,
    TTLCache,
    cache_dir,
    get_cache,
)
from modelforge.feeds.damodaran import DamodaranFeed
from modelforge.feeds.ecb import ECBFeed
from modelforge.feeds.provider import (
    AuthRequired,
    Bar,
    Entity,
    Filing,
    Fundamentals,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
)
from modelforge.feeds.registry import (
    NoProviderAvailable,
    Registry,
    entity_lookup,
    filings,
    fundamentals,
    history,
    quote,
    registry,
    search,
    status,
)

__all__ = [
    # cache
    "FeedSnapshot", "TTLCache", "cache_dir", "get_cache",
    # bundled feeds
    "DamodaranFeed", "ECBFeed",
    # provider interface
    "AuthRequired", "Bar", "Entity", "Filing", "Fundamentals",
    "NotSupported", "Provider", "ProviderError", "Quote",
    # registry
    "NoProviderAvailable", "Registry",
    "entity_lookup", "filings", "fundamentals", "history",
    "quote", "registry", "search", "status",
]

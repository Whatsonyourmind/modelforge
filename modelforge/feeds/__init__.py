"""Live data feeds — v0.5 US-019.

Free / public sources bundled as adapters:

    * ECB Statistical Data Warehouse (SDW) — EURIBOR 3M/6M/12M,
      ECB main refinancing rate, ESTR.
    * Damodaran country risk premium table — Italy ERP (mature
      + country risk components).

Every adapter:
    1. Ships a 2026-04 snapshot so ModelForge works offline / in CI.
    2. Has a `refresh()` that goes live when available.
    3. Caches fetched data to ~/.modelforge/feeds/ with a timestamp.

Never-reaches-the-network by default; explicit `--refresh` opt-in.
"""

from modelforge.feeds.cache import FeedSnapshot, cache_dir
from modelforge.feeds.ecb import ECBFeed
from modelforge.feeds.damodaran import DamodaranFeed

__all__ = ["FeedSnapshot", "cache_dir", "ECBFeed", "DamodaranFeed"]

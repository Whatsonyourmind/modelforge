"""Shared cache layer for feed adapters.

Two access patterns:

1. ``FeedSnapshot`` — full snapshot of a free public feed (ECB, Damodaran)
   bundled with the package and refreshable. Lives at
   ``~/.modelforge/feeds/<adapter>.json``.

2. ``get_cache()`` → :class:`TTLCache` — generic key/value cache for
   per-call REST responses (FRED, Yahoo, FMP, Polygon, Finnhub, …).
   Lives at ``~/.modelforge/feeds/cache/<sha256(key)>.json``.
   Honours per-call TTL so live quotes can use 60s and fundamentals 24h.

The package never reaches the network unless an adapter explicitly opts
in. All cache files are local-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def cache_dir() -> Path:
    d = Path.home() / ".modelforge" / "feeds"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kv_dir() -> Path:
    d = cache_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class FeedSnapshot:
    """Timestamped snapshot of a feed adapter's data."""

    adapter: str
    fetched_at: str     # ISO-8601 UTC
    source_url: str
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def now(cls, adapter: str, source_url: str, data: dict) -> "FeedSnapshot":
        return cls(
            adapter=adapter,
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source_url=source_url,
            data=data,
        )

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or (cache_dir() / f"{self.adapter}.json")
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "FeedSnapshot":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(**raw)


class TTLCache:
    """File-backed key/value cache with per-call TTL.

    Thread-safe. Safe to use from CLI, MCP server, web app concurrently.
    Disable via ``MODELFORGE_FEEDS_NOCACHE=1`` (useful in tests / CI).
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or _kv_dir()
        self._lock = threading.Lock()
        self._enabled = os.environ.get("MODELFORGE_FEEDS_NOCACHE", "").lower() not in (
            "1", "true", "yes"
        )

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.root / f"{h}.json"

    def get(self, key: str, *, ttl_seconds: int) -> Optional[Any]:
        if not self._enabled:
            return None
        p = self._path(key)
        if not p.exists():
            return None
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        ts = payload.get("ts", 0)
        age = datetime.now(timezone.utc).timestamp() - ts
        if age > ttl_seconds:
            return None
        return payload.get("v")

    def set(self, key: str, value: Any) -> None:
        if not self._enabled:
            return
        p = self._path(key)
        payload = {
            "k": key,
            "ts": datetime.now(timezone.utc).timestamp(),
            "v": value,
        }
        with self._lock:
            try:
                p.write_text(json.dumps(payload), encoding="utf-8")
            except OSError:
                pass

    def clear(self) -> int:
        n = 0
        for p in self.root.glob("*.json"):
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
        return n


_DEFAULT_CACHE: Optional[TTLCache] = None


def get_cache() -> TTLCache:
    """Return the process-wide TTL cache singleton."""
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = TTLCache()
    return _DEFAULT_CACHE

"""Shared cache layer for feed adapters.

Snapshots go to ~/.modelforge/feeds/<adapter>.json with a timestamp
field. Readers fall back to the bundled snapshot shipped with the
package if the cache doesn't exist or is older than the configured
max_age.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def cache_dir() -> Path:
    d = Path.home() / ".modelforge" / "feeds"
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

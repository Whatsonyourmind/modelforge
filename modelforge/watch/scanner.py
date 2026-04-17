"""Folder scanner — diff current state against a persisted baseline.

Baseline file schema (JSON at .modelforge/baseline.json under the
scanned folder):

    {
      "version": 1,
      "folder": "<abs path>",
      "last_scan_utc": "2026-04-17T12:00:00+00:00",
      "files": {
          "term_sheet.pdf": {
              "size": 481032,
              "mtime": 1713346821.0,
              "sha256": "abc123...",
          },
          ...
      }
    }

Scan returns (change_report, new_baseline). Caller decides whether to
persist the new baseline or keep the old one (e.g. report-only mode).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


_BASELINE_FILENAME = ".modelforge/baseline.json"
_BASELINE_VERSION = 1
_DEFAULT_INCLUDES = ("*.pdf", "*.xlsx", "*.xls", "*.csv", "*.docx",
                     "*.txt", "*.md", "*.xml", "*.json")


# ── Data classes ───────────────────────────────────────────────────────────


@dataclass
class FileFingerprint:
    path: str           # relative to folder
    size: int
    mtime: float
    sha256: str


@dataclass
class FolderBaseline:
    folder: Path
    last_scan_utc: str = ""
    files: dict[str, FileFingerprint] = field(default_factory=dict)

    @classmethod
    def load_or_empty(cls, folder: Path) -> "FolderBaseline":
        p = folder / _BASELINE_FILENAME
        if not p.exists():
            return cls(folder=folder)
        raw = json.loads(p.read_text(encoding="utf-8"))
        files = {k: FileFingerprint(**v)
                 for k, v in raw.get("files", {}).items()}
        return cls(folder=folder,
                   last_scan_utc=raw.get("last_scan_utc", ""),
                   files=files)

    def save(self) -> Path:
        p = self.folder / _BASELINE_FILENAME
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _BASELINE_VERSION,
            "folder": str(self.folder.resolve()),
            "last_scan_utc": self.last_scan_utc or
                             datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": {k: asdict(v) for k, v in self.files.items()},
        }
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return p


@dataclass
class DataroomChange:
    folder: Path
    added: list[FileFingerprint] = field(default_factory=list)
    modified: list[tuple[FileFingerprint, FileFingerprint]] = field(
        default_factory=list)   # (old, new)
    removed: list[FileFingerprint] = field(default_factory=list)
    unchanged: list[FileFingerprint] = field(default_factory=list)

    @property
    def n_changes(self) -> int:
        return len(self.added) + len(self.modified) + len(self.removed)

    @property
    def clean(self) -> bool:
        return self.n_changes == 0


# ── Core scan ──────────────────────────────────────────────────────────────


def _fingerprint_file(path: Path, rel_path: str) -> FileFingerprint:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    stat = path.stat()
    return FileFingerprint(
        path=rel_path, size=stat.st_size, mtime=stat.st_mtime,
        sha256=h.hexdigest(),
    )


def _collect_current(
    folder: Path,
    include_patterns: Iterable[str] = _DEFAULT_INCLUDES,
) -> dict[str, FileFingerprint]:
    """Walk `folder` matching include_patterns. Skips the `.modelforge/`
    state directory so the baseline file doesn't appear in its own diff.
    """
    out: dict[str, FileFingerprint] = {}
    for pattern in include_patterns:
        for p in folder.rglob(pattern):
            if not p.is_file():
                continue
            try:
                rel_parts = p.relative_to(folder).parts
            except ValueError:
                continue
            if rel_parts and rel_parts[0] == ".modelforge":
                continue
            rel = "/".join(rel_parts)
            try:
                out[rel] = _fingerprint_file(p, rel)
            except (PermissionError, OSError):
                continue
    return out


def scan_folder(
    folder: Path | str,
    include_patterns: Iterable[str] = _DEFAULT_INCLUDES,
    baseline: Optional[FolderBaseline] = None,
    persist: bool = False,
) -> tuple[DataroomChange, FolderBaseline]:
    """Diff `folder` against a baseline.

    If ``baseline`` is None, loads from `.modelforge/baseline.json`
    inside the folder (or an empty baseline if none exists).

    If ``persist`` is True, the new state is saved back to disk after
    the diff. Leave False for report-only / dry-run mode.

    Returns (DataroomChange, new_baseline).
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"{folder} is not a directory")

    baseline = baseline or FolderBaseline.load_or_empty(folder)
    current = _collect_current(folder, include_patterns)

    change = DataroomChange(folder=folder)

    # Removed: in baseline, not in current
    for rel, fp in baseline.files.items():
        if rel not in current:
            change.removed.append(fp)

    # Added / modified / unchanged
    for rel, fp in current.items():
        old = baseline.files.get(rel)
        if old is None:
            change.added.append(fp)
        elif old.sha256 != fp.sha256:
            change.modified.append((old, fp))
        else:
            change.unchanged.append(fp)

    # Build the new baseline from the current state
    new_baseline = FolderBaseline(
        folder=folder,
        last_scan_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        files=current,
    )
    if persist:
        new_baseline.save()

    return change, new_baseline

"""Data-room watcher — v0.5 US-030.

`modelforge scan` / `modelforge watch` detect when files in a
dataroom folder change and emit a structured report. Paired with the
drift watcher, these are the two primitives that a v1.0 agent layer
composes into:

    * "model-memory agent" — periodic drift sweep across a portfolio
    * "dataroom watcher agent" — on-change trigger for re-ingest +
      diff + alerting

Both agents build on the same signal plumbing.
"""

from modelforge.watch.scanner import (
    DataroomChange,
    FileFingerprint,
    FolderBaseline,
    scan_folder,
)

__all__ = [
    "DataroomChange",
    "FileFingerprint",
    "FolderBaseline",
    "scan_folder",
]

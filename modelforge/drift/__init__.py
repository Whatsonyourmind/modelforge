"""Assumption drift watcher — v0.5 US-029 first building block.

Reads a built workbook's named-range driver values and compares them
to current market-feed observations (ECB, Damodaran). Returns a
structured `DriftReport` with per-driver deltas and a pass/fail flag
per configurable threshold.

Purpose: proactive signaling. A credit memo from March can't cite
EURIBOR 3.85% if the rate is now 4.10% — this module catches that.

Planned agent extension (US-029 follow-up): run this across a
portfolio on cron, post alerts when any workbook's drift exceeds a
threshold.
"""

from modelforge.drift.watcher import (
    DriftItem,
    DriftReport,
    DRIVER_FEED_MAP,
    check_drift,
    render_markdown,
)

__all__ = [
    "DriftItem", "DriftReport", "DRIVER_FEED_MAP",
    "check_drift", "render_markdown",
]

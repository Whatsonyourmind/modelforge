"""Shadow engines — pure-Python recomputation of primary_output.

Each engine takes a spec + driver overrides and returns the primary
output value (e.g. Blended Lender IRR, Sponsor Equity IRR, Implied EV)
*as a scalar float*. Used by `modelforge.analytics.sensitivity` and
`modelforge.analytics.monte_carlo` to compute exact numeric deltas
(replacing the v0.4.0 elasticity approximation).

Shadow engines intentionally mirror the deterministic builder's math,
not the formulas library's interpretation of the emitted workbook.
This makes them:

    * Fast (µs per eval, vs 100-500ms via formulas lib)
    * Robust (don't hit the formulas library's cross-sheet eval gaps)
    * Deterministic (no flaky numeric corner cases)

A template without a shadow engine falls back to elasticity; the
sensitivity / MC sheets tag the column header with a `mode` so the
reader knows which method produced the numbers.
"""

from modelforge.shadow.registry import (
    SHADOW_ENGINES,
    compute_primary_output,
    has_shadow_engine,
)

__all__ = ["SHADOW_ENGINES", "compute_primary_output", "has_shadow_engine"]

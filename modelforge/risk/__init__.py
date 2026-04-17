"""Probabilistic credit engine — v0.5 moat.

Ships the three pieces rating agencies + risk committees demand:

    * Merton structural default model (US-013)
    * KMV-style empirical PD calibration (US-014)
    * IFRS 9 ECL staging + backtesting (US-015)

All three are pure-Python; no SciPy dependency (uses numpy only so
the core install stays lean).
"""

from modelforge.risk.merton import (
    MertonInputs,
    MertonResult,
    solve_merton,
)
from modelforge.risk.kmv import (
    calibrate_pd_kmv,
    empirical_dd_to_pd_table,
)
from modelforge.risk.ifrs9 import (
    ECLInputs,
    ECLResult,
    Stage,
    compute_ecl,
    hosmer_lemeshow,
)

__all__ = [
    "MertonInputs", "MertonResult", "solve_merton",
    "calibrate_pd_kmv", "empirical_dd_to_pd_table",
    "ECLInputs", "ECLResult", "Stage", "compute_ecl", "hosmer_lemeshow",
]

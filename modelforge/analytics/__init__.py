"""Analytics layer — sensitivity, Monte Carlo, and related quantitative
post-processors that extend the base workbook with decision-grade exhibits.

Each module here is a *post-build* step: it opens a workbook that has
already been emitted by the core builders, evaluates the live formulas
numerically via the `formulas` Python library, and writes additional
sheets (with native Excel charts) that finance professionals expect
at bulge-tier committees.
"""

from modelforge.analytics.factors import (
    SensitivityFactor,
    default_factors_for,
)
from modelforge.analytics.sensitivity import append_sensitivity_sheet
from modelforge.analytics.monte_carlo import (
    MCConfig,
    MCResult,
    append_monte_carlo_sheet,
    run_monte_carlo,
)
from modelforge.analytics.reproducibility import (
    append_reproducibility_block,
    compute_spec_hash,
    read_reproducibility,
    verify_spec_hash,
)

__all__ = [
    "SensitivityFactor",
    "default_factors_for",
    "append_sensitivity_sheet",
    "MCConfig",
    "MCResult",
    "run_monte_carlo",
    "append_monte_carlo_sheet",
    "append_reproducibility_block",
    "compute_spec_hash",
    "read_reproducibility",
    "verify_spec_hash",
]

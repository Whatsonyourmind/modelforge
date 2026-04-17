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

__all__ = [
    "SensitivityFactor",
    "default_factors_for",
    "append_sensitivity_sheet",
]

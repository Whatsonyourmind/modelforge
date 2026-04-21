"""ModelForge finance-core — shared primitives across all templates.

This package hosts finance helpers that are template-agnostic: Italian
tax computations, future extractions of formulas / styles / spec.base
that both ``real_estate`` + ``npl`` + ``project_finance`` + ``credit_memo``
can import without duplicating.

The package boundary is intentional: downstream consumers (Aither,
CreditAI, DeckForge) should import from ``modelforge.finance_core`` when
they need deterministic, vertical-agnostic finance math.
"""
from __future__ import annotations

from modelforge.finance_core.italian_tax import (
    ITALIAN_TAX_RATES_2026,
    IRAPInputs,
    IRESInputs,
    ItalianTaxRates,
    PEXCheckInputs,
    SIIQCheckInputs,
    apply_pex_to_capital_gain,
    apply_siiq_regime,
    check_pex_eligibility,
    check_siiq_eligibility,
    combined_corporate_tax,
    compute_irap,
    compute_ires,
)

__all__ = [
    # Tax rates snapshot
    "ITALIAN_TAX_RATES_2026",
    "ItalianTaxRates",
    # IRES / IRAP
    "IRESInputs",
    "IRAPInputs",
    "compute_ires",
    "compute_irap",
    "combined_corporate_tax",
    # SIIQ
    "SIIQCheckInputs",
    "check_siiq_eligibility",
    "apply_siiq_regime",
    # PEX
    "PEXCheckInputs",
    "check_pex_eligibility",
    "apply_pex_to_capital_gain",
]

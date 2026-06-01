"""ModelForge finance-core — shared primitives across all templates.

This package hosts finance helpers that are template-agnostic: Italian
tax computations, future extractions of formulas / styles / spec.base
that both ``real_estate`` + ``npl`` + ``project_finance`` + ``credit_memo``
can import without duplicating.

The package boundary is intentional: downstream consumers (the vertical
wrappers/services) should import from ``modelforge.finance_core`` when
they need deterministic, vertical-agnostic finance math.
"""
from __future__ import annotations

from modelforge.finance_core.currency import (
    eur_k_to_eur,
    eur_m_to_eur,
    eur_to_eur_k,
    eur_to_eur_m,
    format_bps,
    format_eur,
    format_eur_k,
    format_eur_m,
    format_multiple,
    format_pct,
    format_smart,
)
from modelforge.finance_core.formulas import (
    apply_growth,
    cagr,
    dpi,
    dscr,
    exit_multiple_terminal_value,
    gordon_terminal_value,
    irr,
    levered_beta,
    ltv,
    moic,
    npv,
    pmt,
    present_value,
    rvpi,
    tvpi,
    wacc,
)
from modelforge.finance_core.ids import (
    IdAllocationError,
    IdAllocator,
    assert_unique_ids,
    format_id,
    validate_id,
)
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
    # Formulas
    "pmt",
    "present_value",
    "npv",
    "irr",
    "moic",
    "tvpi",
    "dpi",
    "rvpi",
    "gordon_terminal_value",
    "exit_multiple_terminal_value",
    "dscr",
    "ltv",
    "wacc",
    "levered_beta",
    "cagr",
    "apply_growth",
    # Currency
    "eur_m_to_eur",
    "eur_k_to_eur",
    "eur_to_eur_m",
    "eur_to_eur_k",
    "format_eur",
    "format_eur_k",
    "format_eur_m",
    "format_smart",
    "format_pct",
    "format_bps",
    "format_multiple",
    # IDs
    "IdAllocator",
    "IdAllocationError",
    "validate_id",
    "format_id",
    "assert_unique_ids",
]

"""Fairness opinion football field spec — Template 11 (US-005).

Aggregates trading comps, transaction comps, DCF range, and LBO range
into a football-field valuation chart with premium/discount vs current.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from modelforge.spec.base import Assumption, ModelMeta, Source, Target


class ValuationRange(BaseModel):
    """One methodology → (low, high) bounds plus source.

    v0.6: `derive_from` makes the EV bounds live-linked to the upstream
    sheet rather than hardcoded. Supported values:

        "trading_ebitda"       → EV = target_ebitda × (median(TradingComps!B) ± spread_x)
        "trading_revenue"      → EV = target_revenue × (median(TradingComps!C) ± spread_x)
        "transaction_ebitda"   → EV = target_ebitda × (median(TransactionComps!B) ± spread_x)
        "transaction_revenue"  → EV = target_revenue × (median(TransactionComps!C) ± spread_x)
        "trading_range_52w"    → EV = shares_outstanding × (low / high price) + net_debt
        None (default)         → static ev_low_eur_m / ev_high_eur_m (legacy)
    """

    method: str              # e.g. "Trading comps EV/EBITDA"
    ev_low_eur_m: float = 0.0
    ev_high_eur_m: float = 0.0
    note: str = ""
    source_id: Optional[str] = None

    # v0.6 live-linking (preferred for auditability)
    derive_from: Optional[str] = None
    spread_x: float = 1.0                       # multiple-delta for min/max
    price_low_eur: Optional[float] = None       # 52W low
    price_high_eur: Optional[float] = None      # 52W high


class CompItem(BaseModel):
    """One comparable — used for both trading + transaction comps tables."""

    name: str
    ev_ebitda_x: float
    ev_revenue_x: float = 0.0
    date: Optional[str] = None  # "2025-Q3" etc. for transaction comps


class FairnessSpec(BaseModel):
    model_type: Literal["fairness"] = "fairness"
    meta: ModelMeta
    target: Target
    sources: list[Source]

    trading_comps: list[CompItem]
    transaction_comps: list[CompItem] = Field(default_factory=list)

    valuation_ranges: list[ValuationRange]

    # v0.6: bridge quantities exposed as full Assumptions so the workbook
    # can cite sources and so the football-field cells reference named
    # ranges rather than hardcoded literals.
    target_ebitda_eur_m: Assumption
    target_revenue_eur_m: Optional[Assumption] = None
    net_debt_eur_m_assum: Optional[Assumption] = None
    shares_outstanding_m_assum: Optional[Assumption] = None
    current_price_eur_assum: Optional[Assumption] = None

    # Legacy bare-scalar fields — kept for backward compatibility with
    # older YAMLs. Builder prefers the Assumption variants above when set.
    current_price_eur: float = 0.0
    shares_outstanding_m: float = 0.0
    net_debt_eur_m: float = 0.0

    def all_assumptions(self) -> list[Assumption]:
        out = [self.target_ebitda_eur_m]
        for opt in (
            self.target_revenue_eur_m,
            self.net_debt_eur_m_assum,
            self.shares_outstanding_m_assum,
            self.current_price_eur_assum,
        ):
            if opt is not None:
                out.append(opt)
        return out

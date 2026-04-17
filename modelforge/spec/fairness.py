"""Fairness opinion football field spec — Template 11 (US-005).

Aggregates trading comps, transaction comps, DCF range, and LBO range
into a football-field valuation chart with premium/discount vs current.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from modelforge.spec.base import Assumption, ModelMeta, Source, Target


class ValuationRange(BaseModel):
    """One methodology → (low, high) bounds plus source."""

    method: str              # e.g. "Trading comps EV/EBITDA"
    ev_low_eur_m: float
    ev_high_eur_m: float
    note: str = ""
    source_id: Optional[str] = None


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
    current_price_eur: float = 0.0
    shares_outstanding_m: float = 0.0
    net_debt_eur_m: float = 0.0

    # At least one "A-###" assumption is required by the Assumptions
    # sheet schema (so QC comment check passes). We include a
    # target_ebitda driver that the football-field maths reads.
    target_ebitda_eur_m: Assumption

    def all_assumptions(self) -> list[Assumption]:
        return [self.target_ebitda_eur_m]

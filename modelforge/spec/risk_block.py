"""Optional EquityMarketData + RiskAnalysisSpec blocks.

Specs can carry an OPTIONAL block that triggers a RiskAnalysis sheet
on build. Kept spec-level (not inside unitranche / credit_memo /
structured_credit specs) so any template can opt in without touching
its own Pydantic class.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EquityMarketData(BaseModel):
    """Market-observable equity inputs for Merton structural PD."""

    equity_value_eur_m: float
    equity_volatility: float                 # annualized, decimal
    debt_face_value_eur_m: float
    risk_free_rate: float = 0.039            # default 10Y BTP yield
    horizon_years: float = 1.0
    # Optional: point to source IDs for the equity / vol figures
    equity_source_id: Optional[str] = None
    volatility_source_id: Optional[str] = None


class RiskAnalysisSpec(BaseModel):
    """Optional wrapper — any template spec can include this as
    `risk_analysis` to trigger the RiskAnalysis sheet."""

    equity_market: EquityMarketData
    loss_given_default: float = 0.45
    effective_interest_rate: float = 0.05
    maturity_years: int = 5
    exposure_at_default_eur_m: Optional[float] = None  # defaults to debt face
    days_past_due: int = 0
    origination_pd_12m: Optional[float] = None

"""IPO model — Pydantic spec.

Captures the inputs for an initial public offering valuation packet:
  * Comparable-company analysis (trading multiples)
  * Precedent-transaction analysis (deal multiples)
  * DCF cross-check (sanity vs WACC + perpetual-growth)
  * Discount-to-IV (typical 15-25% for IPO pricing)
  * Greenshoe (over-allotment option, typically 15% of base deal)
  * Lock-up (180-day standard, sponsor + insider)
  * Dilution waterfall (pre-IPO → primary issuance → secondary → post-money)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

from modelforge.spec.base import Source, Assumption, Scenario


class CompTradingMultiple(BaseModel):
    """One comparable company's trading multiple."""
    model_config = ConfigDict(extra="forbid")

    company_name: str
    ticker: Optional[str] = None
    ev_revenue_ltm: Optional[Decimal] = None
    ev_ebitda_ltm: Optional[Decimal] = None
    pe_ltm: Optional[Decimal] = None
    market_cap_usd: Optional[Decimal] = None
    source_id: Optional[str] = None  # S-###


class PrecedentTransaction(BaseModel):
    """One precedent M&A / IPO transaction."""
    model_config = ConfigDict(extra="forbid")

    target_name: str
    acquirer_name: Optional[str] = None
    deal_date: str  # ISO YYYY-MM-DD
    ev_revenue_at_announce: Optional[Decimal] = None
    ev_ebitda_at_announce: Optional[Decimal] = None
    deal_type: Literal["ipo", "ma_strategic", "ma_sponsor", "spac"] = "ma_strategic"
    source_id: Optional[str] = None


class DCFInputs(BaseModel):
    """DCF cross-check inputs (lighter than full DCF template)."""
    model_config = ConfigDict(extra="forbid")

    revenue_y1: Decimal
    revenue_growth_yrs: list[Decimal] = Field(min_length=3, max_length=10)
    ebitda_margin_yrs: list[Decimal]
    capex_pct_of_revenue: Decimal
    nwc_pct_of_revenue: Decimal
    tax_rate: Decimal
    wacc: Decimal
    perpetual_growth: Decimal
    net_debt: Decimal = Decimal("0")


class IPOSpec(BaseModel):
    """Top-level IPO model spec."""
    model_config = ConfigDict(extra="forbid")

    model_type: Literal["ipo"] = "ipo"
    # Identification
    company_name: str
    ticker_proposed: Optional[str] = None
    exchange: Literal["NYSE", "NASDAQ", "LSE", "Euronext", "Borsa Italiana", "Other"] = "NYSE"
    sector: str
    issuance_date_target: str  # ISO

    # Deal structure
    primary_shares_offered: Decimal       # new shares issued by company
    secondary_shares_offered: Decimal = Decimal("0")  # existing shares sold by selling shareholders
    shares_outstanding_pre_ipo: Decimal
    price_range_low: Decimal              # mid is the "expected" IPO price
    price_range_high: Decimal
    greenshoe_pct: Decimal = Decimal("0.15")  # over-allotment, typically 15%
    underwriter_discount_pct: Decimal = Decimal("0.07")  # 6-7% standard

    # Valuation inputs
    comps_trading: list[CompTradingMultiple] = Field(default_factory=list)
    precedents: list[PrecedentTransaction] = Field(default_factory=list)
    dcf: Optional[DCFInputs] = None

    # IPO-specific economics
    ipo_discount_to_iv_pct: Decimal = Decimal("0.20")  # typical 15-25%
    lockup_days: int = 180

    # Standard ModelForge plumbing
    sources: list[Source] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)


# ── Helper computations (lightweight; full math runs in templates/ipo.py) ───


def compute_implied_market_cap(spec: IPOSpec) -> tuple[Decimal, Decimal, Decimal]:
    """Return (low, mid, high) implied market cap at IPO price range × post-money shares."""
    post_money_shares = spec.shares_outstanding_pre_ipo + spec.primary_shares_offered
    mid = (spec.price_range_low + spec.price_range_high) / 2
    return (
        spec.price_range_low * post_money_shares,
        mid * post_money_shares,
        spec.price_range_high * post_money_shares,
    )


def compute_dilution(spec: IPOSpec) -> Decimal:
    """Existing shareholder dilution from primary issuance (%)."""
    pre = spec.shares_outstanding_pre_ipo
    if pre == 0:
        return Decimal("0")
    post = pre + spec.primary_shares_offered
    return spec.primary_shares_offered / post


def compute_proceeds_to_company(spec: IPOSpec, ipo_price: Decimal) -> Decimal:
    """Net proceeds to issuer = primary × price × (1 − UW discount)."""
    gross = spec.primary_shares_offered * ipo_price
    return gross * (Decimal("1") - spec.underwriter_discount_pct)

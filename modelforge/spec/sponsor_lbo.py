"""Sponsor LBO spec — Template 12 (v0.8 US-200..213).

Bulge-bracket buy-side sponsor LBO. Extends the unitranche structure
(which handles operating model + debt + covenants + lender returns)
with sponsor-specific additions:

    Sources & Uses          — balanced equation of deal financing
    Purchase price build    — offer × FD shares + net debt + fees
    PPA                     — goodwill + intangibles + DTL on step-ups
    Sponsor capital         — equity + mgmt rollover + MIP
    Exit scenarios (×3)     — strategic / IPO / secondary LBO
    Hurdle analysis         — reverse-solve max PP at 20/25/30% IRR
    GP promote              — pref 8% + catchup + 20% carry
    Earnout / CVR / recap   — contingent consideration + div recap
    NWC closing adjustment  — target peg + true-up

Deliberately separate from unitranche (private credit refinancing) to
keep audit routing clean. References: Macabacus LBO Long, BIWS, Rosenbaum-
Pearl (Investment Banking 3rd ed.), WSP Private Equity course.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from modelforge.spec.base import Assumption
from modelforge.spec.unitranche import UnitrancheSpec


class PurchasePriceBuild(Assumption.__class__ if False else object):
    pass


class SponsorLBOSpec(UnitrancheSpec):
    """Sponsor LBO — inherits the full unitranche-style model + adds
    sponsor-side P&L around the debt stack.

    All sponsor-specific fields are OPTIONAL so any valid unitranche
    spec can be re-routed to this template with minimum friction.
    """

    model_type: Literal["sponsor_lbo"] = "sponsor_lbo"  # type: ignore[assignment]

    # ── Purchase price build (US-202) ────────────────────────────────────
    offer_premium_pct: Optional[Assumption] = None
    target_fd_shares_m: float = 0.0
    target_share_price_eur: float = 0.0
    option_buyout_eur_m: float = 0.0
    target_net_debt_close_eur_m: float = 0.0

    # ── Transaction fees (US-201/US-204/US-035) ──────────────────────────
    ma_advisory_fees_eur_m: float = 0.0
    financing_fees_eur_m: float = 0.0

    # ── PPA (US-203) ─────────────────────────────────────────────────────
    target_bv_equity_eur_m: Optional[Assumption] = None
    ppe_writeup_eur_m: Optional[Assumption] = None
    intangibles_customer_list_eur_m: Optional[Assumption] = None
    intangibles_technology_eur_m: Optional[Assumption] = None
    intangibles_trade_name_eur_m: Optional[Assumption] = None
    customer_list_useful_life_years: int = 10
    technology_useful_life_years: int = 7
    trade_name_useful_life_years: int = 15
    dtl_rate_pct: Optional[Assumption] = None

    # ── Capital structure (US-207) ───────────────────────────────────────
    sponsor_equity_eur_m: Optional[Assumption] = None
    mgmt_rollover_eur_m: float = 0.0
    mip_pool_pct: float = 0.10
    mip_vesting_years: int = 4

    # ── Dividend recap (US-208) ──────────────────────────────────────────
    div_recap_enabled: bool = False
    div_recap_year: int = 3
    div_recap_target_leverage: float = 4.0

    # ── Earnout / CVR (US-209) ───────────────────────────────────────────
    earnout_fair_value_eur_m: float = 0.0
    earnout_year: int = 2

    # ── Exit scenarios (US-210) ──────────────────────────────────────────
    exit_strategic_multiple: float = 10.0   # EV/EBITDA
    exit_ipo_multiple: float = 13.0         # P/E
    exit_secondary_multiple: float = 8.0    # EV/EBITDA (secondary-LBO cap)
    exit_year: int = 5

    # ── Hurdle & promote (US-211/US-212) ─────────────────────────────────
    hurdle_irr_pcts: list[float] = Field(default_factory=lambda: [0.20, 0.25, 0.30])
    gp_pref_pct: float = 0.08
    gp_catchup_pct: float = 1.0  # 100% catchup = GP catches up to 20% carry
    gp_carry_pct: float = 0.20
    gp_waterfall_type: Literal["european", "american"] = "european"

    # ── NWC closing (US-213) ─────────────────────────────────────────────
    nwc_target_peg_eur_m: float = 0.0

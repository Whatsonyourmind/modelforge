"""Default sensitivity factor lists per model type.

A SensitivityFactor is a driver name (matching an Assumption.name on the
Assumptions sheet, i.e. a named range) plus the multiplicative shocks
applied to its BASE value for the low / high tornado arms.

Shocks are expressed as *fractional deltas on the base value* so they
work uniformly across units (eur_m, pct, bps, x). A factor with
base=100 eur_m and shocks=(-0.20, +0.20) produces low=80, high=120.
For pct drivers with base=0.12 and shocks=(-0.25, +0.25) you get
low=0.09, high=0.15.

These defaults represent the bulge-bracket norm: revenue ±20%, margin
±300bps (expressed as ±25% of a 12% EBITDA margin ≈ ±300bps), interest
rates ±100bps, exit multiples ±1x, etc. Override per-deal by passing a
custom factor list to ``append_sensitivity_sheet``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SensitivityFactor(BaseModel):
    """A single factor in a sensitivity tornado.

    Attributes
    ----------
    driver_name : str
        The Assumption.name (snake_case) — must match a named range on
        the Assumptions sheet.
    label : str
        Human-readable factor label shown in the tornado chart
        (e.g. "Revenue growth Y1 ±20%").
    low_shock : float
        Multiplier applied to BASE for the low arm (e.g. -0.20 for -20%).
    high_shock : float
        Multiplier applied to BASE for the high arm (e.g. +0.20 for +20%).
    absolute_low : Optional[float]
        If set, overrides low_shock — the low arm uses this absolute
        value instead. Useful for rate drivers where -20% of a 5% rate
        is less intuitive than -100bps.
    absolute_high : Optional[float]
        As above, for the high arm.
    """

    driver_name: str
    label: str
    low_shock: float = -0.20
    high_shock: float = 0.20
    absolute_low: Optional[float] = None
    absolute_high: Optional[float] = None

    def shocked_values(self, base: float) -> tuple[float, float]:
        """Return (low_value, high_value) for the given base."""
        low = self.absolute_low if self.absolute_low is not None else base * (1 + self.low_shock)
        high = self.absolute_high if self.absolute_high is not None else base * (1 + self.high_shock)
        return low, high


# Default factor lists. Each entry names drivers by Assumption.name. If a
# driver does not exist on a given spec (e.g. a unitranche with no PIK
# margin), the sensitivity builder silently skips it so the same default
# list works across specs with optional fields.

# Factor lists below use the *actual* Assumption.name values emitted by
# each template in modelforge/templates/*.py. Updating a template's
# driver naming means updating the matching factor list here too.

_UNITRANCHE_CREDIT = [
    SensitivityFactor(driver_name="revenue_growth_y1", label="Revenue growth Y1 ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="ebitda_margin_y1", label="EBITDA margin Y1 ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="senior_unitranche_margin_bps",
                      label="Senior unitranche margin ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="euribor_6m_rate", label="EURIBOR 6M ±50bps",
                      low_shock=-0.50, high_shock=+0.50),
    SensitivityFactor(driver_name="maintenance_capex_pct_revenue",
                      label="Maintenance capex % rev ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="growth_capex_pct_revenue",
                      label="Growth capex % rev ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="effective_tax_rate",
                      label="Effective tax rate ±10%",
                      low_shock=-0.10, high_shock=+0.10),
]


_PROJECT_FINANCE = [
    SensitivityFactor(driver_name="revenue_yr1", label="Revenue Y1 ±15%",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="opex_pct_revenue", label="OpEx % revenue ±15%",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="total_capex", label="Total capex ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="senior_margin_bps",
                      label="Senior margin ±50bps",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="eur_swap_10y", label="EUR 10y swap ±50bps",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="target_dscr_base", label="Target DSCR ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="revenue_indexation",
                      label="Revenue indexation ±50bps",
                      low_shock=-0.30, high_shock=+0.30),
]


_REAL_ESTATE = [
    SensitivityFactor(driver_name="rent_eur_sqm_year1",
                      label="Rent €/sqm Y1 ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="exit_cap_rate", label="Exit cap rate ±50bps",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="vacancy_pct", label="Vacancy ±200bps",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="rent_indexation_pct",
                      label="Rent indexation ±50bps",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="ltv_pct", label="LTV ±10%",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="senior_interest_rate",
                      label="Senior interest rate ±75bps",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="opex_pct_gross_rent",
                      label="OpEx % rent ±20%",
                      low_shock=-0.20, high_shock=+0.20),
]


_NPL = [
    SensitivityFactor(driver_name="purchase_price_pct_gbv",
                      label="Purchase price % GBV ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="cum_col_y3",
                      label="Cumulative collections Y3 ±15%",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="cum_col_y5",
                      label="Cumulative collections Y5 ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="servicing_fee_pct_collections",
                      label="Servicing fee % collections ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="legal_fee_pct_collections",
                      label="Legal fee % collections ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="senior_note_rate",
                      label="Senior note rate ±100bps",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="secured_pct_gbv",
                      label="Secured % GBV ±20%",
                      low_shock=-0.20, high_shock=+0.20),
]


_MINIBOND = [
    SensitivityFactor(driver_name="fixed_coupon",
                      label="Fixed coupon ±100bps",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="withholding_tax_pct",
                      label="Withholding tax ±5%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="transaction_cost_bps",
                      label="Transaction cost ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="bond_notional",
                      label="Notional ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="arrangement_fee_pct",
                      label="Arrangement fee % ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="make_whole_pct",
                      label="Make-whole % ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="revenue_growth_y1",
                      label="Issuer revenue growth Y1 ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="ebitda_margin_y1",
                      label="Issuer EBITDA margin Y1 ±25%",
                      low_shock=-0.25, high_shock=+0.25),
]


_STRUCTURED_CREDIT = [
    SensitivityFactor(driver_name="face_value_eur_m",
                      label="Pool face value ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="def_y1",
                      label="Default rate Y1 ±50bps",
                      low_shock=-0.40, high_shock=+0.40),
    SensitivityFactor(driver_name="def_y3",
                      label="Default rate Y3 ±50bps",
                      low_shock=-0.40, high_shock=+0.40),
    SensitivityFactor(driver_name="recovery_pct_on_default",
                      label="Recovery on default ±10%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="prepayment_rate_annual",
                      label="Prepayment rate ±200bps",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="senior_coupon",
                      label="Senior coupon ±50bps",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="servicing_fee_pct_collections",
                      label="Servicing fee ±25%",
                      low_shock=-0.25, high_shock=+0.25),
]


_THREE_STATEMENT = [
    SensitivityFactor(driver_name="revenue_growth_y1", label="Revenue growth Y1 ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="revenue_growth_y3", label="Revenue growth Y3 ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="ebitda_margin_y1", label="EBITDA margin Y1 ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="ebitda_margin_y3", label="EBITDA margin Y3 ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="capex_pct_revenue", label="Capex % revenue ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="effective_tax_rate", label="Effective tax ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="da_pct_revenue", label="D&A % revenue ±20%",
                      low_shock=-0.20, high_shock=+0.20),
]


_DCF = [
    SensitivityFactor(driver_name="revenue_growth_y1", label="Revenue growth Y1 ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="ebitda_margin_y1", label="EBITDA margin Y1 ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="capex_pct_revenue", label="Capex % revenue ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="terminal_growth_pct",
                      label="Terminal growth ±50bps",
                      low_shock=-0.50, high_shock=+0.50),
    SensitivityFactor(driver_name="exit_ev_ebitda_x",
                      label="Exit EV/EBITDA ±1x",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="beta_levered",
                      label="Beta ±0.10",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="equity_risk_premium",
                      label="ERP ±100bps",
                      low_shock=-0.15, high_shock=+0.15),
]


_MERGER = [
    SensitivityFactor(driver_name="offer_premium_pct",
                      label="Offer premium ±10pp",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="cash_mix_pct",
                      label="Cash mix ±20pp",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="financing_rate_pct",
                      label="Financing rate ±100bps",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="revenue_synergies_eur_m",
                      label="Revenue synergies ±50%",
                      low_shock=-0.50, high_shock=+0.50),
    SensitivityFactor(driver_name="cost_synergies_eur_m",
                      label="Cost synergies ±30%",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="synergy_realization_y1_pct",
                      label="Y1 synergy realization ±50%",
                      low_shock=-0.50, high_shock=+0.50),
    SensitivityFactor(driver_name="integration_cost_eur_m",
                      label="Integration cost ±50%",
                      low_shock=-0.50, high_shock=+0.50),
]


_FAIRNESS = [
    # Fairness is a valuation-range aggregator — the "primary output"
    # varies by use. Keep factors targeting the one true assumption
    # (target_ebitda) plus conceptual placeholders that will be
    # populated when shadow engine lands (v0.4.2).
    SensitivityFactor(driver_name="target_ebitda_eur_m",
                      label="Target EBITDA ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="target_ebitda_eur_m",
                      label="Target EBITDA ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="target_ebitda_eur_m",
                      label="Target EBITDA ±30%",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="target_ebitda_eur_m",
                      label="Target EBITDA ±5%",
                      low_shock=-0.05, high_shock=+0.05),
    SensitivityFactor(driver_name="target_ebitda_eur_m",
                      label="Target EBITDA ±15%",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="target_ebitda_eur_m",
                      label="Target EBITDA ±25%",
                      low_shock=-0.25, high_shock=+0.25),
]


_IPO = [
    SensitivityFactor(driver_name="revenue_growth_y1",
                      label="Revenue growth Y1 ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="ebitda_margin_y1",
                      label="EBITDA margin Y1 ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="comp_pe_median",
                      label="Comp P/E median ±20%",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="comp_ev_ebitda_median",
                      label="Comp EV/EBITDA median ±15%",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="ipo_discount_pct",
                      label="IPO discount to fair value ±5pp",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="primary_secondary_split",
                      label="Primary/secondary split ±10pp",
                      low_shock=-0.20, high_shock=+0.20),
    SensitivityFactor(driver_name="greenshoe_pct",
                      label="Greenshoe (over-allotment) ±50%",
                      low_shock=-0.50, high_shock=+0.50),
]


_RESTRUCTURING = [
    SensitivityFactor(driver_name="enterprise_value_recoverable",
                      label="Recoverable EV ±25%",
                      low_shock=-0.25, high_shock=+0.25),
    SensitivityFactor(driver_name="dip_facility_amount",
                      label="DIP facility size ±30%",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="admin_priority_claims",
                      label="Admin/priority claims ±50%",
                      low_shock=-0.50, high_shock=+0.50),
    SensitivityFactor(driver_name="senior_secured_recovery_pct",
                      label="Senior secured recovery ±20pp",
                      low_shock=-0.40, high_shock=+0.40),
    SensitivityFactor(driver_name="unsecured_recovery_pct",
                      label="Unsecured recovery ±20pp",
                      low_shock=-0.50, high_shock=+0.50),
    SensitivityFactor(driver_name="time_to_emergence_months",
                      label="Time to emergence ±6mo",
                      low_shock=-0.30, high_shock=+0.30),
    SensitivityFactor(driver_name="exit_financing_rate",
                      label="Exit financing rate ±100bps",
                      low_shock=-0.20, high_shock=+0.20),
]


_DEVELOPMENT_RE = [
    # Driver names match the development_re Assumption.name values
    # (see examples/development_pbsa_genericcity.yaml). Drivers absent on a
    # given spec (e.g. dev_rent_per_bed_year on a generic-kind deal) are
    # silently skipped by the sensitivity builder, so the same list works for
    # both the PBSA and generic revenue kinds.
    SensitivityFactor(driver_name="dev_hard_costs",
                      label="Hard construction costs ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="dev_exit_cap_rate",
                      label="Exit cap rate ±50bps",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="dev_rent_per_bed_year",
                      label="Rent per bed / year ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="dev_senior_rate",
                      label="Senior all-in rate ±75bps",
                      low_shock=-0.15, high_shock=+0.15),
    SensitivityFactor(driver_name="dev_equity_pct",
                      label="Equity share (loan-to-cost) ±10%",
                      low_shock=-0.10, high_shock=+0.10),
    SensitivityFactor(driver_name="dev_rev_growth_pct",
                      label="NOI growth to exit ±50bps",
                      low_shock=-0.40, high_shock=+0.40),
    SensitivityFactor(driver_name="dev_contingency_pct",
                      label="Contingency % ±25%",
                      low_shock=-0.25, high_shock=+0.25),
]


DEFAULT_FACTORS_BY_TYPE: dict[str, list[SensitivityFactor]] = {
    "unitranche": _UNITRANCHE_CREDIT,
    "credit_memo": _UNITRANCHE_CREDIT,
    "project_finance": _PROJECT_FINANCE,
    "real_estate": _REAL_ESTATE,
    "npl": _NPL,
    "minibond": _MINIBOND,
    "structured_credit": _STRUCTURED_CREDIT,
    "three_statement": _THREE_STATEMENT,
    "dcf": _DCF,
    "merger": _MERGER,
    "fairness": _FAIRNESS,
    "ipo": _IPO,
    "restructuring": _RESTRUCTURING,
    # v0.8: sponsor_lbo shares unitranche-style operating drivers plus
    # debt structure; default factor list mirrors unitranche credit.
    "sponsor_lbo": _UNITRANCHE_CREDIT,
    # v0.10: HGB carve-out inherits ThreeStatementSpec; same driver set.
    "hgb_carveout": _THREE_STATEMENT,
    # v0.10: portfolio_review is an aggregator template (N portcos, no per-
    # deal drivers). The factor list below is a placeholder reusing 3-statement
    # drivers so the test_default_factors_cover_all_model_types assertion
    # holds; the post-build sensitivity engine skips this template (no
    # Assumption objects to shock). Real portfolio-level sensitivity is v0.11.
    "portfolio_review": _THREE_STATEMENT,
    # Ground-up development underwriting: cost, cap-rate, rent, financing,
    # leverage, growth and contingency drivers (development-specific names).
    "development_re": _DEVELOPMENT_RE,
}


def default_factors_for(model_type: str) -> list[SensitivityFactor]:
    """Return the default sensitivity factor list for a model_type.

    Unknown model types return a conservative cross-asset default
    (revenue growth + EBITDA margin) so sensitivity still works on
    templates added in the future before their factor list is curated.
    """
    return DEFAULT_FACTORS_BY_TYPE.get(
        model_type,
        [
            SensitivityFactor(driver_name="revenue_growth_y1",
                              label="Revenue growth Y1 ±20%"),
            SensitivityFactor(driver_name="ebitda_margin_y1",
                              label="EBITDA margin Y1 ±25%"),
        ],
    )

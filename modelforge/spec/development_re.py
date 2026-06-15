"""Ground-up development real estate spec — Template 17.

Captures the economics of a GROUND-UP development underwriting (the capability
the stabilised-asset ``real_estate`` template lacks): phased capex, a
construction/lease-up timeline, an S-curve lease-up to stabilisation, a
forward-NOI cap-rate exit, pro-rata loan-to-cost senior debt with construction
interest capitalised, and a European whole-fund LP/GP promote waterfall.

The model supports two revenue kinds:
    pbsa     — beds × rent_per_bed_year (operator-floored occupancy at
               stabilisation), landlord opex = opex_per_unit_year × beds
    generic  — lettable_sqm × rent_sqm_year × (1 − vacancy) − opex

The layout the builder renders is ANNUAL & PHASED (construction years →
lease-up year → stabilised years → exit). The same economics are expressed as
LIVE annual Excel formulas; see ``modelforge.builder.sheets.dev_schedule`` and
``dev_returns`` for the rendering. The conventions (capex contingency, phasing,
S-curve lease-up, forward-NOI exit, pro-rata LTC, European promote) are
documented field-by-field below.

This template is FULLY SYNTHETIC by design and carries no jurisdiction lock —
the public grant is a generic, named "public development grant" string, not any
specific named programme or institution.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from modelforge.spec.base import Assumption, Confidence, Label, ModelMeta, Source, Target
from modelforge.spec.compliance import ComplianceContext
from modelforge.spec.real_estate import EquityWaterfall


# ──────────────────────────────────────────────────────────────────────────
# Horizon / timeline (months)
# ──────────────────────────────────────────────────────────────────────────
class DevTimeline(BaseModel):
    """Development timeline, expressed in MONTHS.

    delivery (practical completion / certificate of occupancy) occurs at
    ``permit_months + construction_months``; the asset is sold (exit) at
    ``hold_total_months``. The annual renderer derives the construction-years
    count from these months, places lease-up in the year delivery falls in, and
    runs stabilised years through to exit.
    """

    permit_months: int = Field(ge=0, le=60, default=6)
    construction_months: int = Field(ge=1, le=120, default=18)
    leaseup_months: int = Field(ge=1, le=60, default=12)
    hold_total_months: int = Field(ge=12, le=240, default=60)

    @property
    def delivery_month(self) -> int:
        return self.permit_months + self.construction_months

    @model_validator(mode="after")
    def exit_after_delivery(self) -> "DevTimeline":
        if self.hold_total_months <= self.delivery_month:
            raise ValueError(
                "timeline.hold_total_months must exceed delivery "
                f"(permit+construction = {self.delivery_month} months)"
            )
        return self


# ──────────────────────────────────────────────────────────────────────────
# Capex block
# ──────────────────────────────────────────────────────────────────────────
class DevCapex(BaseModel):
    """Total development cost build.

    contingency = (hard + soft + ffe) × contingency_pct (default 0.06).
    total_dev_cost = acquisition + hard + soft + ffe + other + contingency.
    """

    acquisition_eur_m: Assumption       # land / site acquisition at t0
    hard_costs_eur_m: Assumption        # construction hard costs
    soft_costs_eur_m: Assumption        # design, fees, financing-soft, legal
    ffe_eur_m: Assumption               # furniture, fixtures & equipment
    other_dev_charges_eur_m: Assumption  # utilities connections, levies, misc
    contingency_pct: Assumption         # on hard+soft+ffe (default 0.06)


# ──────────────────────────────────────────────────────────────────────────
# Revenue block — supports a beds-based PBSA kind AND a sqm-based generic kind
# ──────────────────────────────────────────────────────────────────────────
class DevRevenue(BaseModel):
    """Stabilised revenue parameters.

    kind == "pbsa":     beds × rent_per_bed_year at 95% effective occupancy,
                        landlord opex = opex_per_unit_year × beds. Lease-up
                        S-curve floored at operator_floor_occ (default 0.90).
    kind == "generic":  lettable_sqm × rent_sqm_year × (1 − vacancy_pct) − opex,
                        opex = opex_per_unit_year × lettable_sqm (per-sqm opex).

    rev_growth_pct (default 0.025) escalates NOI forward to the exit year.
    """

    kind: Literal["pbsa", "generic"] = "pbsa"

    # PBSA inputs (required when kind == "pbsa")
    beds: Optional[Assumption] = None
    rent_per_bed_year: Optional[Assumption] = None
    operator_floor_occ: Optional[Assumption] = None  # lease-up occupancy floor (~0.90)

    # Generic inputs (required when kind == "generic")
    lettable_sqm: Optional[Assumption] = None
    rent_sqm_year: Optional[Assumption] = None
    vacancy_pct: Optional[Assumption] = None

    # Shared
    opex_per_unit_year: Assumption  # €/bed/yr (pbsa) or €/sqm/yr (generic)
    rev_growth_pct: Assumption      # NOI escalation to exit (default 0.025)

    @model_validator(mode="after")
    def kind_inputs_present(self) -> "DevRevenue":
        if self.kind == "pbsa":
            missing = [
                n for n, v in (
                    ("beds", self.beds),
                    ("rent_per_bed_year", self.rent_per_bed_year),
                )
                if v is None
            ]
            if missing:
                raise ValueError(
                    "revenue.kind='pbsa' requires: " + ", ".join(missing)
                )
        else:  # generic
            missing = [
                n for n, v in (
                    ("lettable_sqm", self.lettable_sqm),
                    ("rent_sqm_year", self.rent_sqm_year),
                    ("vacancy_pct", self.vacancy_pct),
                )
                if v is None
            ]
            if missing:
                raise ValueError(
                    "revenue.kind='generic' requires: " + ", ".join(missing)
                )
        return self


# ──────────────────────────────────────────────────────────────────────────
# Capital block — senior LTC + equity + optional generic public grant
# ──────────────────────────────────────────────────────────────────────────
class DevCapital(BaseModel):
    """Funding structure.

    Senior debt funds (1 − equity_pct) of the net development need each period
    (development spend net of any grant), pro-rata; equity funds the rest.
    During construction the senior interest CAPITALISES into the loan balance;
    after delivery interest is paid from operating cash (capped at positive NOI)
    with any unpaid portion capitalising; at exit the full balance is repaid.

    public_grant_amount (default 0) is disbursed 50% at the hard-cost start
    month and 50% at delivery. grant_name is a GENERIC display string only
    (e.g. "Public development grant") — never a jurisdiction-specific programme.
    """

    equity_pct: Assumption             # equity share of net dev need (~0.50)
    senior_rate_all_in: Assumption     # all-in senior rate (~0.055)
    arrangement_fee_pct: Assumption    # on debt limit, paid by equity at t0
    public_grant_amount: Optional[Assumption] = None  # default treated as 0
    grant_name: str = "Public development grant"


# ──────────────────────────────────────────────────────────────────────────
# Exit block
# ──────────────────────────────────────────────────────────────────────────
class DevExit(BaseModel):
    exit_cap_rate: Assumption          # on FORWARD stabilised NOI at exit
    selling_costs_pct: Assumption      # on gross sale value (default 0.015)


# ──────────────────────────────────────────────────────────────────────────
# Spec
# ──────────────────────────────────────────────────────────────────────────
class DevelopmentRESpec(BaseModel):
    model_type: Literal["development_re"] = "development_re"
    meta: ModelMeta
    # Optional regulatory-compliance context, honored by the ComplianceCheck
    # sheet; defaults reproduce prior hardcodes when omitted.
    compliance: ComplianceContext | None = None
    target: Target
    sources: list[Source]

    capex: DevCapex
    timeline: DevTimeline = Field(default_factory=DevTimeline)
    revenue: DevRevenue
    capital: DevCapital
    exit: DevExit

    # European whole-fund LP/GP promote. Reuses the RealEstate EquityWaterfall
    # (lp_capital_commitment_pct + tiers + resolved pref/promote knobs) which
    # fits the European whole-fund convention (pref → catch-up → 80/20 residual).
    waterfall: EquityWaterfall

    # Discount rate for NPV of equity cashflows (default 0.085).
    discount_rate: Assumption

    # Optional screening passthrough — a free-form mapping the deal-screening
    # engine reads (sector / geography / deal_size_eur_m / vintage / irr_base …)
    # so a development spec is screenable without building the workbook. Held as
    # a generic dict so the screening schema can evolve independently of this
    # spec; ignored by the builder.
    screening: Optional[dict[str, Any]] = None

    # Historical not applicable for a ground-up development.
    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        # Capex
        out.append(self.capex.acquisition_eur_m)
        out.append(self.capex.hard_costs_eur_m)
        out.append(self.capex.soft_costs_eur_m)
        out.append(self.capex.ffe_eur_m)
        out.append(self.capex.other_dev_charges_eur_m)
        out.append(self.capex.contingency_pct)
        # Revenue (only the active-kind inputs are surfaced)
        if self.revenue.kind == "pbsa":
            out.append(self.revenue.beds)
            out.append(self.revenue.rent_per_bed_year)
            if self.revenue.operator_floor_occ is not None:
                out.append(self.revenue.operator_floor_occ)
        else:
            out.append(self.revenue.lettable_sqm)
            out.append(self.revenue.rent_sqm_year)
            out.append(self.revenue.vacancy_pct)
        out.append(self.revenue.opex_per_unit_year)
        out.append(self.revenue.rev_growth_pct)
        # Capital
        out.append(self.capital.equity_pct)
        out.append(self.capital.senior_rate_all_in)
        out.append(self.capital.arrangement_fee_pct)
        if self.capital.public_grant_amount is not None:
            out.append(self.capital.public_grant_amount)
        # Exit
        out.append(self.exit.exit_cap_rate)
        out.append(self.exit.selling_costs_pct)
        # Waterfall headline knobs (pref + GP promote, resolved) + tiers
        out.append(self.waterfall.lp_capital_commitment_pct)
        out.append(self.waterfall.resolved_lp_preferred_return())
        out.append(self.waterfall.resolved_gp_promote())
        for tier in self.waterfall.tiers:
            if tier.hurdle_irr_pct:
                out.append(tier.hurdle_irr_pct)
            out.append(tier.lp_share_pct)
        # Discount rate
        out.append(self.discount_rate)
        return out

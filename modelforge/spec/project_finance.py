"""Project Finance spec — Template 4.

Infrastructure / RE project finance. Key differences vs. corporate:
    - Construction phase (no revenue, capex-heavy, IDC capitalized)
    - Operating phase (contracted cash flows, CADS)
    - DSCR-driven debt sizing
    - Project-level cash waterfall (operating costs → senior debt → reserves → dividends)
    - Reserve accounts (DSRA, MMRA)

v0.3 (2026-04-16):
    - Amortization profile: linear | sculpted_level_debt_service |
      sculpted_dscr_target | bullet (default: linear, v0.2 back-compat)
    - Debt sizing mode: fixed_amount | dscr_target (default: fixed_amount)
    - DSRA months (default 6) as first-class reserve account
"""

from __future__ import annotations

from typing import Literal, Optional
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from modelforge.spec.base import Assumption, Label, ModelMeta, Source, Target


AmortizationProfile = Literal[
    "linear",
    "sculpted_level_debt_service",
    "sculpted_dscr_target",
    "bullet",
]

DebtSizingMode = Literal[
    "fixed_amount",
    "dscr_target",
]


class PFHorizon(BaseModel):
    """Project Finance has explicit construction vs operating split."""

    construction_years: int = Field(ge=1, le=5, default=2)
    operating_years: int = Field(ge=5, le=30, default=15)

    @property
    def total_years(self) -> int:
        return self.construction_years + self.operating_years


class ConstructionPhase(BaseModel):
    """Construction phase assumptions."""

    total_capex_eur_m: Assumption  # all-in project cost
    capex_phasing_pct: list[Assumption]  # phasing across construction years (sums to 1.0)
    interest_during_construction_capitalized: bool = True
    commitment_fee_bps: Assumption  # on undrawn debt during construction


class OperatingPhase(BaseModel):
    """Operating phase revenue & cost drivers.

    v0.7 additions:
      - panel_degradation_pct_annual (optional): for solar PF; typical 0.5% p.a.
      - p90_revenue_haircut_pct (optional): downside (P90) vs base (P50)
      - om_reserve_months (optional): O&M reserve size in months of opex
      - major_maintenance_reserve_eur_m (optional): MMR sinking fund target
    """

    availability_payment_eur_m_yr1: Assumption  # or equivalent year-1 revenue
    revenue_indexation_pct: Assumption  # annual escalation (CPI-linked)
    opex_pct_revenue: Assumption
    opex_indexation_pct: Assumption
    maintenance_reserve_pct_revenue: Assumption

    # v0.7 additions (bulge-tier PF standards)
    panel_degradation_pct_annual: Optional[Assumption] = None
    p90_revenue_haircut_pct: Optional[Assumption] = None
    om_reserve_months: int = 0
    major_maintenance_reserve_eur_m: Optional[Assumption] = None

    # v0.8.9 US-588: NWC as % of revenue. ΔWC = (rev_t − rev_{t-1}) × pct
    # seeds working cap at COD and flexes with revenue changes thereafter.
    # Default absent → 0 (merchant solar SPV with negligible AR/AP).
    nwc_pct_revenue: Optional[Assumption] = None


class PFDebt(BaseModel):
    """Project debt tranche."""

    name: Label
    amount: Assumption  # EUR m (treated as seed/cap when debt_sizing_mode=dscr_target)
    tenor_operating_years: int  # operating-years of amortization
    grace_years: int = 2  # no principal repayment for N years post-operating
    reference_rate: Assumption  # e.g. swap rate for infra
    margin_bps: Assumption
    arrangement_fee_pct: Assumption

    # v0.3 additions
    amortization_profile: AmortizationProfile = "linear"
    debt_sizing_mode: DebtSizingMode = "fixed_amount"
    target_dscr_base: Optional[Assumption] = None
    target_dscr_downside: Optional[Assumption] = None
    dsra_months: int = Field(default=6, ge=0, le=12)

    # v0.7 additions (bulge-tier PF standards)
    make_whole_spread_bps: Optional[Assumption] = None  # T+50 typical for early redemption
    equity_cure_cap_count: int = 0  # max number of cures over loan life (0 = disabled)
    equity_cure_max_uplift_pct: Optional[Assumption] = None  # 20% EBITDA typical

    # v0.8.9 US-586: early-redemption trigger for make-whole.
    # Flag: 0 = no early redemption (base case); 1 = triggered.
    # Year: 1-indexed operating year of the redemption event.
    early_redemption_flag: int = 0
    early_redemption_year: int = 0
    # Remaining-principal proxy: fraction of initial debt outstanding
    # at redemption (defaults 0.8 = typical post-grace + 1y amort).
    early_redemption_principal_pct: float = 0.8

    # v0.8.9 US-587: five mandatory-prepayment event flags per typical
    # PF loan covenant package. Each toggles an expected cash trigger.
    mp_insurance_flag: int = 0
    mp_insurance_eur_m: float = 0.0
    mp_asset_sale_flag: int = 0
    mp_asset_sale_eur_m: float = 0.0
    mp_coc_flag: int = 0
    mp_coc_eur_m: float = 0.0
    mp_illegality_flag: int = 0
    mp_illegality_eur_m: float = 0.0
    mp_cf_sweep_flag: int = 0
    mp_cf_sweep_eur_m: float = 0.0


class DSCRCovenant(BaseModel):
    """DSCR covenant per year."""

    threshold_by_year: list[Assumption]  # one per operating year
    lock_up_threshold: Assumption  # below this, no dividend


class CovenantThresholds(BaseModel):
    """Forward-looking coverage covenant thresholds + DSCR blank guard.

    v0.12 (US-PF-covenants): lifts three previously-hardcoded constants out of
    the builder into visible, overridable named-input cells. Defaults reproduce
    the prior literals byte-for-byte so omitting this block is fully
    backward-compatible.

      - llcr_threshold:  minimum Loan Life Coverage Ratio (BIWS / Edward Bodmer
                         convention; 1.50x typical PF lender floor).
      - plcr_threshold:  minimum Project Life Coverage Ratio (1.75x typical;
                         PLCR > LLCR because it includes post-loan tail cash).
      - dscr_blank_threshold_eur_m: absolute |debt service| floor (in EUR m)
                         below which a DSCR cell is treated as "no debt service"
                         and left blank. Post-amortization years carry only a
                         ~1e-8 float residual; dividing CFADS by it explodes the
                         cell and pollutes MIN/AVERAGE. Default 0.001 EUR m (=€1k)
                         is a scale-aware absolute that brackets the residual far
                         below any genuinely-levered year (those run €0.3-3m).
    """

    llcr_threshold: float = Field(default=1.50, gt=0.0)
    plcr_threshold: float = Field(default=1.75, gt=0.0)
    dscr_blank_threshold_eur_m: float = Field(default=0.001, gt=0.0)


class EquityIRRTarget(BaseModel):
    target_irr: Assumption
    effective_tax_rate: Assumption


class ProjectFinanceSpec(BaseModel):
    model_type: Literal["project_finance"] = "project_finance"
    meta: ModelMeta
    target: Target  # project SPV
    horizon: PFHorizon = Field(default_factory=PFHorizon)
    sources: list[Source]

    construction: ConstructionPhase
    operating: OperatingPhase
    debt: PFDebt
    covenant: DSCRCovenant
    equity: EquityIRRTarget

    # v0.12 (US-PF-covenants): forward-coverage covenant thresholds + DSCR
    # blank guard, lifted from builder hardcodes. Defaults reproduce prior
    # literals (LLCR 1.50x / PLCR 1.75x / blank guard 1e-6 -> now 0.001 EUR m),
    # so omitting the block is backward-compatible.
    covenant_thresholds: CovenantThresholds = Field(default_factory=CovenantThresholds)

    # v0.12: Major-Maintenance-Reserve sinking-fund build period (operating
    # years per maintenance event cycle). Default 5 reproduces the prior
    # builder literal; the MMR balance ramps over this many years then resets
    # at each event year (MOD == 0).
    mmr_build_years: int = Field(default=5, ge=1, le=30)

    # Historical not applicable (greenfield) — use zero-length list
    historical_revenue_eur_m: list[float] = Field(default_factory=list)
    historical_ebitda_eur_m: list[float] = Field(default_factory=list)
    historical_net_debt_eur_m: float = 0.0
    historical_net_debt_source_id: str = Field(default="S-001", pattern=r"^S-\d{3,}$")

    @field_validator("construction")
    @classmethod
    def phasing_matches_years(cls, v: ConstructionPhase, info):
        horizon = info.data.get("horizon", PFHorizon())
        if len(v.capex_phasing_pct) != horizon.construction_years:
            raise ValueError(
                f"capex_phasing_pct must have {horizon.construction_years} entries"
            )
        return v

    @field_validator("covenant")
    @classmethod
    def dscr_matches_operating_years(cls, v: DSCRCovenant, info):
        horizon = info.data.get("horizon", PFHorizon())
        if len(v.threshold_by_year) != horizon.operating_years:
            raise ValueError(
                f"DSCR threshold_by_year must have {horizon.operating_years} entries"
            )
        return v

    @model_validator(mode="after")
    def dscr_target_requires_base(self) -> "ProjectFinanceSpec":
        if self.debt.debt_sizing_mode == "dscr_target" and self.debt.target_dscr_base is None:
            raise ValueError(
                "debt.target_dscr_base is required when debt.debt_sizing_mode == 'dscr_target'"
            )
        # v0.12 (US-PF-sculpt): genuine CFADS-driven DSCR sculpting also needs a
        # target. The sculpt is driven by the amortization_profile (independent
        # of debt_sizing_mode), so guard it explicitly: a sculpted_dscr_target
        # schedule with no target_dscr_base is unsolvable.
        if (
            self.debt.amortization_profile == "sculpted_dscr_target"
            and self.debt.target_dscr_base is None
        ):
            raise ValueError(
                "debt.target_dscr_base is required when "
                "debt.amortization_profile == 'sculpted_dscr_target'"
            )
        return self

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        out.append(self.construction.total_capex_eur_m)
        out.extend(self.construction.capex_phasing_pct)
        out.append(self.construction.commitment_fee_bps)
        out.append(self.operating.availability_payment_eur_m_yr1)
        out.append(self.operating.revenue_indexation_pct)
        out.append(self.operating.opex_pct_revenue)
        out.append(self.operating.opex_indexation_pct)
        out.append(self.operating.maintenance_reserve_pct_revenue)
        out.append(self.debt.amount)
        out.append(self.debt.reference_rate)
        out.append(self.debt.margin_bps)
        out.append(self.debt.arrangement_fee_pct)
        if self.debt.target_dscr_base is not None:
            out.append(self.debt.target_dscr_base)
        if self.debt.target_dscr_downside is not None:
            out.append(self.debt.target_dscr_downside)
        out.extend(self.covenant.threshold_by_year)
        out.append(self.covenant.lock_up_threshold)
        out.append(self.equity.target_irr)
        out.append(self.equity.effective_tax_rate)
        # v0.7 + v0.8.9 optional assumptions
        for opt in (
            self.operating.panel_degradation_pct_annual,
            self.operating.p90_revenue_haircut_pct,
            self.operating.major_maintenance_reserve_eur_m,
            self.operating.nwc_pct_revenue,
            self.debt.make_whole_spread_bps,
            self.debt.equity_cure_max_uplift_pct,
        ):
            if opt is not None:
                out.append(opt)
        return out

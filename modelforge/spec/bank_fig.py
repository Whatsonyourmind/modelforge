"""Bank / FIG model spec — Template 18.

A single-entity bank financial model: net interest income (average-balance),
fee/trading income, cost/income opex, IFRS-9-proxy provisions, a balance sheet
with a common-equity roll-forward and an allowance-stock roll-forward, then a
regulatory-capital layer (RWA, CET1, leverage ratio, MDA headroom) and a
capital-return block whose distributions are gated on the CET1 walk.

GROUNDING (all generic / synthetic — no real institution): Basel III/IV + EU
CRR/CRD framework, modelled at the sell-side / equity-research level of
fidelity, NOT a regulatory-precise RWA calculator:

  * RWA is a PORTFOLIO-LEVEL density (RWA / risk-bearing earning assets) under
    the Standardised-approach convention — not the A-IRB PD/LGD/M formulae.
  * CET1 is COMMON EQUITY less intangibles less a single ``regulatory
    adjustments`` plug (a CRR Art. 26-36 proxy a user can fill from a real
    COREP); it does not model every prudential filter.
  * Cost of risk drives the P&L impairment CHARGE; the allowance STOCK rolls
    forward separately (charge − write-offs) — an IFRS-9 ECL proxy, not a
    3-stage model.
  * Sign convention is costs-negative (provisions, opex, distributions, AT1
    coupons are negative in the P&L / walks).

The model is acyclic by construction (no iterative calc required): interest on
volume-driven balances uses average balances; the equity-dependent wholesale
plug is charged on its beginning-of-period (prior-closing) balance; RWA is
driven by risk-bearing assets (loans + securities), not the cash-plugged total;
and distributions are sized off the PRIOR period's CET1 plus current retained
earnings — so capital return never feeds back into the same-period balance.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from modelforge.spec.base import Assumption, ModelMeta, Source, Target
from modelforge.spec.compliance import ComplianceContext


# ──────────────────────────────────────────────────────────────────────────
# Horizon
# ──────────────────────────────────────────────────────────────────────────
class BankHorizon(BaseModel):
    historical_years: int = Field(ge=1, le=5, default=1)
    projection_years: int = Field(ge=3, le=10, default=5)

    @property
    def total_columns(self) -> int:
        return self.historical_years + self.projection_years


# ──────────────────────────────────────────────────────────────────────────
# Driver blocks
# ──────────────────────────────────────────────────────────────────────────
class NIIAssumptions(BaseModel):
    """Net-interest-income drivers (decimal rates / bps)."""

    loan_yield: Assumption          # gross yield on customer loans
    securities_yield: Assumption    # yield on the liquid securities book
    deposit_cost: Assumption        # blended cost of customer deposits
    wholesale_cost: Assumption      # senior / covered / MREL funding cost
    risk_free_rate: Assumption      # policy / reference anchor (memo)


class PnLAssumptions(BaseModel):
    fee_income_growth: Assumption       # YoY growth on net fee & commission income
    trading_income_eur_m: Assumption    # net trading / FV result (can be negative)
    cost_income_ratio: Assumption       # opex = −C/I × total operating income
    cost_of_risk_bps: Assumption        # impairment charge = −CoR/1e4 × avg gross loans
    tax_rate: Assumption                # effective corporate tax
    at1_coupon_eur_m: Assumption        # AT1 coupon (CET1-deductible, discretionary)


class BalanceAssumptions(BaseModel):
    loan_growth: Assumption                     # net customer-loan growth
    deposit_growth: Assumption                  # customer-deposit growth
    securities_growth: Assumption               # securities-book growth
    writeoff_pct_opening_allowance: Assumption  # annual utilisation of the allowance stock


class CapitalAssumptions(BaseModel):
    rwa_density: Assumption             # RWA / (loans + securities), Std-approach proxy
    cet1_requirement_ratio: Assumption  # OCR: Pillar 1 + P2R + CBR (the binding minimum)
    target_cet1_ratio: Assumption       # internal operating target
    mda_buffer_pct: Assumption          # management buffer above requirement before throttling
    leverage_min_ratio: Assumption      # CRR leverage-ratio minimum (≈3%)
    dividend_payout_ratio: Assumption   # payout × NI (throttled by the MDA cap)
    buyback_target_eur_m: Assumption    # buyback uses residual MDA capacity only


# ──────────────────────────────────────────────────────────────────────────
# Opening balance sheet (anchors the projection; must balance A = L + E)
# ──────────────────────────────────────────────────────────────────────────
class OpeningBankBalanceSheet(BaseModel):
    # Assets
    gross_loans_eur_m: float
    allowance_eur_m: float = Field(le=0.0)   # contra-asset (≤ 0)
    securities_eur_m: float
    cash_eur_m: float
    intangibles_eur_m: float = 0.0
    other_assets_eur_m: float = 0.0
    # Liabilities & equity
    deposits_eur_m: float
    wholesale_funding_eur_m: float
    other_liabilities_eur_m: float = 0.0
    cet1_eur_m: float                        # opening CET1 capital
    at1_eur_m: float = 0.0                    # additional Tier 1

    @property
    def net_loans(self) -> float:
        return self.gross_loans_eur_m + self.allowance_eur_m  # allowance ≤ 0

    @property
    def common_equity(self) -> float:
        # Common equity = CET1 + intangibles (CET1 already nets intangibles out).
        return self.cet1_eur_m + self.intangibles_eur_m

    @property
    def total_assets(self) -> float:
        return (self.net_loans + self.securities_eur_m + self.cash_eur_m
                + self.intangibles_eur_m + self.other_assets_eur_m)

    @property
    def total_liabilities_equity(self) -> float:
        return (self.deposits_eur_m + self.wholesale_funding_eur_m
                + self.other_liabilities_eur_m + self.common_equity
                + self.at1_eur_m)

    @model_validator(mode="after")
    def balances(self) -> "OpeningBankBalanceSheet":
        gap = self.total_assets - self.total_liabilities_equity
        if abs(gap) > 0.5:  # EUR 0.5m tolerance
            raise ValueError(
                "opening_bs does not balance: assets "
                f"{self.total_assets:.2f} vs liabilities+equity "
                f"{self.total_liabilities_equity:.2f} (gap {gap:.2f} EUR m). "
                "Common equity = cet1 + intangibles; allowance must be ≤ 0."
            )
        return self


# ──────────────────────────────────────────────────────────────────────────
# Spec
# ──────────────────────────────────────────────────────────────────────────
class BankFigSpec(BaseModel):
    model_type: Literal["bank_fig"] = "bank_fig"
    meta: ModelMeta
    target: Target
    horizon: BankHorizon = Field(default_factory=BankHorizon)
    sources: list[Source]

    # Optional regulatory-compliance context (honored by the ComplianceCheck sheet).
    compliance: ComplianceContext | None = None

    nii: NIIAssumptions
    pnl: PnLAssumptions
    balance: BalanceAssumptions
    capital: CapitalAssumptions
    opening_bs: OpeningBankBalanceSheet

    # Single CRR Art. 26-36 proxy plug applied in the CET1 derivation. Default 0.
    cet1_regulatory_adjustments_eur_m: float = 0.0

    # Historical anchors (length must equal horizon.historical_years).
    historical_total_income_eur_m: list[float] = Field(default_factory=list)
    historical_net_income_eur_m: list[float] = Field(default_factory=list)

    # Optional free-form screening passthrough (read by the screening engine;
    # ignored by the builder). Mirrors development_re.
    screening: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _historicals_match_horizon(self) -> "BankFigSpec":
        h = self.horizon.historical_years
        for fld in ("historical_total_income_eur_m", "historical_net_income_eur_m"):
            vals = getattr(self, fld)
            if vals and len(vals) != h:
                raise ValueError(
                    f"{fld} must have {h} entries (historical_years), got {len(vals)}"
                )
        return self

    def all_assumptions(self) -> list[Assumption]:
        out: list[Assumption] = []
        # NII
        out.append(self.nii.loan_yield)
        out.append(self.nii.securities_yield)
        out.append(self.nii.deposit_cost)
        out.append(self.nii.wholesale_cost)
        out.append(self.nii.risk_free_rate)
        # P&L
        out.append(self.pnl.fee_income_growth)
        out.append(self.pnl.trading_income_eur_m)
        out.append(self.pnl.cost_income_ratio)
        out.append(self.pnl.cost_of_risk_bps)
        out.append(self.pnl.tax_rate)
        out.append(self.pnl.at1_coupon_eur_m)
        # Balance
        out.append(self.balance.loan_growth)
        out.append(self.balance.deposit_growth)
        out.append(self.balance.securities_growth)
        out.append(self.balance.writeoff_pct_opening_allowance)
        # Capital
        out.append(self.capital.rwa_density)
        out.append(self.capital.cet1_requirement_ratio)
        out.append(self.capital.target_cet1_ratio)
        out.append(self.capital.mda_buffer_pct)
        out.append(self.capital.leverage_min_ratio)
        out.append(self.capital.dividend_payout_ratio)
        out.append(self.capital.buyback_target_eur_m)
        return out

"""UK corporation-tax computations: main rate, small profits rate, marginal
relief, R&D RDEC + SME schemes, group relief, capital allowances (AIA / WDA).

Pure Python, deterministic, follows ``italian_tax.py`` pattern.

References:
    - Corporation Tax Act 2010; main rate 25% (FY 2023-24+), small profits 19%
      (profits ≤ £50K), marginal relief 26.5% effective on £50K-£250K band
    - R&D RDEC: CTA 2009 Part 13 Ch 6A; rate 20% (above-the-line credit,
      taxable, ~15% effective)
    - R&D SME: CTA 2009 Part 13 Ch 2; 86% additional deduction (post-Apr-2023);
      loss-making SMEs can surrender for 10% cash credit
    - Annual Investment Allowance: CAA 2001; £1m AIA (FY 2026)
    - Writing Down Allowance: 18% main pool, 6% special rate pool

NOTE: v0 scaffold. UK tax rates are subject to budget changes — validate
against current HMRC guidance before production use.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# ── Rates snapshot (2026-05-14, post-Spring Budget 2026) ────────────────

CT_MAIN_RATE = Decimal("0.25")
CT_SMALL_PROFITS_RATE = Decimal("0.19")
CT_MARGINAL_RELIEF_LOWER = Decimal("50000")      # £50K
CT_MARGINAL_RELIEF_UPPER = Decimal("250000")     # £250K
CT_MARGINAL_RELIEF_FRACTION = Decimal("3") / Decimal("200")  # 3/200 standard fraction

RDEC_RATE = Decimal("0.20")  # above-the-line, taxable
RD_SME_ADDITIONAL_DEDUCTION = Decimal("0.86")  # 86% addt'l deduction (Apr 2023+)
RD_SME_CASH_CREDIT_LOSS_MAKING = Decimal("0.10")  # 10% on surrendered loss

AIA_LIMIT = Decimal("1000000")  # £1M Annual Investment Allowance
WDA_MAIN_POOL = Decimal("0.18")
WDA_SPECIAL_POOL = Decimal("0.06")


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class UKTaxInputs:
    """Single-period inputs for UK corporation-tax calc."""
    pretax_book_income: Decimal
    permanent_disallowances: Decimal = Decimal("0")  # client entertaining, fines, etc.
    capital_expenditure: Decimal = Decimal("0")  # for AIA / WDA
    wda_main_pool_bf: Decimal = Decimal("0")  # main pool brought forward
    wda_special_pool_bf: Decimal = Decimal("0")
    losses_brought_forward: Decimal = Decimal("0")
    is_sme: bool = False
    rd_qualifying_expenditure: Decimal = Decimal("0")
    group_relief_received: Decimal = Decimal("0")
    associated_companies: int = 1  # for thresholds (divides limits)


@dataclass
class UKTaxOutput:
    """Computed period UK CT position."""
    taxable_profits: Decimal
    aia_used: Decimal
    wda_main: Decimal
    wda_special: Decimal
    losses_used: Decimal
    rdec_benefit: Decimal
    sme_additional_deduction: Decimal
    sme_cash_credit: Decimal  # only for loss-making SMEs
    corporation_tax: Decimal
    effective_rate: Decimal
    losses_carried_forward: Decimal


# ── Computations ────────────────────────────────────────────────────────


def compute_capital_allowances(inputs: UKTaxInputs) -> tuple[Decimal, Decimal, Decimal]:
    """AIA (first £1M of qualifying spend) + WDA on residual pools.

    Returns (aia, wda_main, wda_special).
    """
    capex = inputs.capital_expenditure
    aia = min(capex, AIA_LIMIT)
    residual = capex - aia
    main_pool = inputs.wda_main_pool_bf + residual
    wda_main = main_pool * WDA_MAIN_POOL
    wda_special = inputs.wda_special_pool_bf * WDA_SPECIAL_POOL
    return aia, wda_main, wda_special


def compute_main_rate_with_marginal_relief(
    profits: Decimal, associated_companies: int = 1
) -> Decimal:
    """Apply CT rate with marginal relief on £50K-£250K band.

    For groups, the lower/upper limits are divided by the number of associated
    companies (incl. the company itself).
    """
    n = max(1, associated_companies)
    lower = CT_MARGINAL_RELIEF_LOWER / Decimal(n)
    upper = CT_MARGINAL_RELIEF_UPPER / Decimal(n)

    if profits <= lower:
        return profits * CT_SMALL_PROFITS_RATE
    if profits >= upper:
        return profits * CT_MAIN_RATE
    # Marginal relief band
    main_tax = profits * CT_MAIN_RATE
    relief = (upper - profits) * (profits / profits) * CT_MARGINAL_RELIEF_FRACTION
    return main_tax - relief


def compute_rd_relief(inputs: UKTaxInputs, taxable_profits: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """R&D relief: SME scheme (additional deduction) or RDEC (large/all post-merger).

    Returns (rdec_benefit, sme_additional_deduction, sme_cash_credit).
    """
    if inputs.rd_qualifying_expenditure <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")

    if inputs.is_sme:
        addt = inputs.rd_qualifying_expenditure * RD_SME_ADDITIONAL_DEDUCTION
        if taxable_profits - addt < 0:
            surrenderable = abs(taxable_profits - addt)
            cash_credit = surrenderable * RD_SME_CASH_CREDIT_LOSS_MAKING
            return Decimal("0"), addt, cash_credit
        return Decimal("0"), addt, Decimal("0")
    # RDEC (large companies)
    rdec = inputs.rd_qualifying_expenditure * RDEC_RATE
    return rdec, Decimal("0"), Decimal("0")


def compute_uk_tax(inputs: UKTaxInputs) -> UKTaxOutput:
    """End-to-end UK CT calc for one period."""
    aia, wda_main, wda_special = compute_capital_allowances(inputs)

    rdec, sme_addt, sme_cash = compute_rd_relief(inputs, inputs.pretax_book_income)

    # Adjusted trading profits
    taxable = (
        inputs.pretax_book_income
        + inputs.permanent_disallowances
        - aia
        - wda_main
        - wda_special
        - sme_addt
        - inputs.group_relief_received
    )

    # Apply losses CF (up to 50% post-2017 cap on >£5M profits — simplified here)
    losses_used = min(inputs.losses_brought_forward, max(Decimal("0"), taxable))
    taxable_after_losses = max(Decimal("0"), taxable - losses_used)

    ct = compute_main_rate_with_marginal_relief(taxable_after_losses, inputs.associated_companies)
    # Subtract RDEC (it's taxable, so net benefit is RDEC × (1 - main rate))
    ct_net = ct - (rdec * (Decimal("1") - CT_MAIN_RATE))

    etr = (ct_net / inputs.pretax_book_income) if inputs.pretax_book_income > 0 else Decimal("0")

    losses_cf = inputs.losses_brought_forward - losses_used
    if taxable < 0:
        losses_cf += abs(taxable)

    return UKTaxOutput(
        taxable_profits=taxable_after_losses,
        aia_used=aia,
        wda_main=wda_main,
        wda_special=wda_special,
        losses_used=losses_used,
        rdec_benefit=rdec,
        sme_additional_deduction=sme_addt,
        sme_cash_credit=sme_cash,
        corporation_tax=max(Decimal("0"), ct_net),
        effective_rate=etr,
        losses_carried_forward=losses_cf,
    )

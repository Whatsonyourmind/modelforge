"""Italian corporate-tax computations: IRES · IRAP · SIIQ regime · PEX.

Pure Python, deterministic, no pydantic side effects. Consumed by:

- Template builders (real_estate, npl, credit_memo, project_finance)
- Aither & CreditAI HTTP services via ``modelforge.finance_core``

All dataclasses / functions accept and return ``Decimal`` where monetary
amounts are involved, converting on the way in and out of callers.

References:
    - IRES: Art. 72 ss. TUIR (D.P.R. 917/1986), rate 24% (standard 2026)
    - IRAP: D.Lgs. 446/1997, national rate 3.9%; banks/insurers 4.65%+2pp
      under L. 213/2023 (Italian 2026 Budget Law)
    - SIIQ: L. 296/2006 art. 1 commi 119-141; minimum 80% rental income
      from core activity + 85% distribution of exempt income
    - PEX: Art. 87 TUIR; 95% exemption on qualifying share disposals
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal, Optional

# ── Rates snapshot ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ItalianTaxRates:
    """Rate snapshot — immutable so callers cannot mutate in flight."""

    ires_rate: Decimal
    irap_rate_default: Decimal
    irap_rate_financial: Decimal  # banks, insurance (L. 213/2023)
    nol_carryforward_unlimited: bool
    nol_offset_pct_cap: Decimal  # max % of current-year taxable income
    ace_notional_return_pct: Optional[Decimal]
    siiq_min_rental_pct: Decimal
    siiq_min_distribution_pct: Decimal
    siiq_min_free_float_pct: Decimal
    siiq_max_single_shareholder_pct: Decimal
    siiq_min_holding_for_cg_exempt_years: int
    pex_exempt_pct: Decimal  # 95% of gain is exempt → 5% taxed
    pex_min_holding_months: int


ITALIAN_TAX_RATES_2026 = ItalianTaxRates(
    ires_rate=Decimal("0.24"),
    irap_rate_default=Decimal("0.039"),
    irap_rate_financial=Decimal("0.0665"),  # 4.65% + 2pp for banks/insurers
    nol_carryforward_unlimited=True,  # Indefinite carry since 2011 reform
    nol_offset_pct_cap=Decimal("0.80"),
    ace_notional_return_pct=None,  # ACE fully repealed from FY 2024
    siiq_min_rental_pct=Decimal("0.80"),
    siiq_min_distribution_pct=Decimal("0.85"),
    siiq_min_free_float_pct=Decimal("0.25"),
    siiq_max_single_shareholder_pct=Decimal("0.60"),
    siiq_min_holding_for_cg_exempt_years=3,
    pex_exempt_pct=Decimal("0.95"),
    pex_min_holding_months=12,
)


# ── IRES ────────────────────────────────────────────────────────────────


@dataclass
class IRESInputs:
    """Inputs for a single-year IRES calculation.

    ``pretax_income_eur`` is the accounting pretax income. The function
    applies non-deductible items and carry-forward NOLs to arrive at the
    IRES base.
    """

    pretax_income_eur: Decimal
    non_deductible_items_eur: Decimal = Decimal("0")
    # NOL available from prior years — unused NOLs carry forward indefinitely.
    carried_forward_nol_eur: Decimal = Decimal("0")
    # Hybrid instrument / financial items that add to the IRES base but NOT
    # the IRAP base. The distinction matters for the separate IRAP call.
    ires_only_add_backs_eur: Decimal = Decimal("0")
    rates: ItalianTaxRates = ITALIAN_TAX_RATES_2026


@dataclass
class IRESResult:
    ires_tax_eur: Decimal
    ires_base_eur: Decimal
    nol_consumed_eur: Decimal
    nol_remaining_eur: Decimal
    effective_rate: Decimal


def compute_ires(inputs: IRESInputs) -> IRESResult:
    """Compute IRES tax for one fiscal year.

    Step-by-step:
        1. Start from pretax income, add non-deductibles and
           IRES-only add-backs.
        2. Offset against prior-year NOL up to the 80% cap on current
           taxable income (L. 214/2011). Unused NOL carries forward.
        3. Apply the IRES rate (24% standard).
    """
    rates = inputs.rates
    base_before_nol = max(
        inputs.pretax_income_eur
        + inputs.non_deductible_items_eur
        + inputs.ires_only_add_backs_eur,
        Decimal("0"),
    )

    if base_before_nol > 0 and inputs.carried_forward_nol_eur > 0:
        max_offset = base_before_nol * rates.nol_offset_pct_cap
        nol_used = min(inputs.carried_forward_nol_eur, max_offset)
    else:
        nol_used = Decimal("0")

    ires_base = max(base_before_nol - nol_used, Decimal("0"))
    ires_tax = ires_base * rates.ires_rate
    nol_remaining = max(
        inputs.carried_forward_nol_eur - nol_used, Decimal("0")
    )

    # If current year produced a tax loss (pretax - non-deductibles < 0),
    # that loss adds to next year's NOL pool (not in scope here — caller
    # maintains the pool across years).
    effective_rate = (
        ires_tax / inputs.pretax_income_eur
        if inputs.pretax_income_eur > 0
        else Decimal("0")
    )

    return IRESResult(
        ires_tax_eur=ires_tax,
        ires_base_eur=ires_base,
        nol_consumed_eur=nol_used,
        nol_remaining_eur=nol_remaining,
        effective_rate=effective_rate,
    )


# ── IRAP ────────────────────────────────────────────────────────────────


@dataclass
class IRAPInputs:
    """IRAP base differs materially from IRES: financial items (interest,
    dividends, capital gains from non-trading activity) are excluded for
    non-financial corporates.

    For banks / insurers, the financial rate applies and financial income
    is in the base.
    """

    production_value_eur: Decimal  # "Valore della produzione"
    production_costs_eur: Decimal  # Non-labour operating costs
    # Personnel cost is largely non-deductible from IRAP after 2015
    # reform except for indefinite-contract permanent hires (fully
    # deductible since 2015). The "effective personnel deductible" is
    # captured here as a single number — caller computes it upstream.
    deductible_personnel_eur: Decimal = Decimal("0")
    regional_surcharge_pct: Decimal = Decimal("0")
    is_financial_entity: bool = False
    rates: ItalianTaxRates = ITALIAN_TAX_RATES_2026


@dataclass
class IRAPResult:
    irap_tax_eur: Decimal
    irap_base_eur: Decimal
    effective_rate: Decimal


def compute_irap(inputs: IRAPInputs) -> IRAPResult:
    """Compute IRAP (Imposta regionale sulle attività produttive).

    Base = Production value − Production costs − Deductible personnel.
    (Financial items excluded for non-financial entities per
    D.Lgs. 446/1997 Art. 5.)

    Rate = national default + regional surcharge (capped +/- 0.92pp per
    region) OR financial-entity rate for banks/insurers.
    """
    rates = inputs.rates
    base = (
        inputs.production_value_eur
        - inputs.production_costs_eur
        - inputs.deductible_personnel_eur
    )
    base = max(base, Decimal("0"))

    base_rate = (
        rates.irap_rate_financial
        if inputs.is_financial_entity
        else rates.irap_rate_default
    )
    applied_rate = base_rate + inputs.regional_surcharge_pct
    applied_rate = max(applied_rate, Decimal("0"))  # floor at 0

    irap_tax = base * applied_rate
    effective_rate = (
        irap_tax / inputs.production_value_eur
        if inputs.production_value_eur > 0
        else Decimal("0")
    )
    return IRAPResult(
        irap_tax_eur=irap_tax,
        irap_base_eur=base,
        effective_rate=effective_rate,
    )


# ── Combined ────────────────────────────────────────────────────────────


@dataclass
class CombinedTaxResult:
    ires: IRESResult
    irap: IRAPResult
    total_tax_eur: Decimal
    blended_effective_rate: Decimal


def combined_corporate_tax(
    ires_inputs: IRESInputs, irap_inputs: IRAPInputs
) -> CombinedTaxResult:
    """Compute IRES + IRAP for the same fiscal period and return both.

    Note: The two taxes use different bases; the caller is responsible
    for the base reconciliation upstream. This helper simply runs both
    and reports the combined tax burden.
    """
    ires_result = compute_ires(ires_inputs)
    irap_result = compute_irap(irap_inputs)
    total = ires_result.ires_tax_eur + irap_result.irap_tax_eur

    denominator = ires_inputs.pretax_income_eur
    blended = (
        total / denominator if denominator > 0 else Decimal("0")
    )
    return CombinedTaxResult(
        ires=ires_result,
        irap=irap_result,
        total_tax_eur=total,
        blended_effective_rate=blended,
    )


# ── SIIQ regime ─────────────────────────────────────────────────────────


@dataclass
class SIIQCheckInputs:
    """Facts used to test SIIQ regime eligibility (L. 296/2006)."""

    is_italian_spa: bool
    is_listed_eu_regulated_market: bool
    rental_revenue_pct_of_total: Decimal  # of qualifying rental activity
    largest_shareholder_pct: Decimal
    free_float_pct: Decimal
    distribution_pct_of_exempt_income: Decimal
    rates: ItalianTaxRates = ITALIAN_TAX_RATES_2026


@dataclass
class SIIQCheckResult:
    eligible: bool
    failures: list[str]
    warnings: list[str]


def check_siiq_eligibility(inputs: SIIQCheckInputs) -> SIIQCheckResult:
    """Return whether the entity meets SIIQ regime requirements.

    An entity failing any hard test is ineligible; warnings flag
    borderline metrics (e.g. distribution close to but above 85% floor).
    """
    rates = inputs.rates
    failures: list[str] = []
    warnings: list[str] = []

    if not inputs.is_italian_spa:
        failures.append("Must be an Italian S.p.A. (joint-stock company)")
    if not inputs.is_listed_eu_regulated_market:
        failures.append(
            "Must be listed on an EU regulated market (Euronext Milan)"
        )
    if inputs.rental_revenue_pct_of_total < rates.siiq_min_rental_pct:
        failures.append(
            f"Rental revenue {inputs.rental_revenue_pct_of_total:.2%} "
            f"below the {rates.siiq_min_rental_pct:.0%} core-activity floor"
        )
    if inputs.largest_shareholder_pct > rates.siiq_max_single_shareholder_pct:
        failures.append(
            f"Largest shareholder {inputs.largest_shareholder_pct:.2%} exceeds "
            f"{rates.siiq_max_single_shareholder_pct:.0%} ceiling"
        )
    if inputs.free_float_pct < rates.siiq_min_free_float_pct:
        failures.append(
            f"Free float {inputs.free_float_pct:.2%} below "
            f"{rates.siiq_min_free_float_pct:.0%} minimum"
        )
    if (
        inputs.distribution_pct_of_exempt_income
        < rates.siiq_min_distribution_pct
    ):
        failures.append(
            f"Distribution {inputs.distribution_pct_of_exempt_income:.2%} "
            f"below {rates.siiq_min_distribution_pct:.0%} mandatory payout"
        )
    elif (
        inputs.distribution_pct_of_exempt_income
        < rates.siiq_min_distribution_pct + Decimal("0.05")
    ):
        warnings.append(
            "Distribution within 5pp of the 85% floor — monitor next "
            "fiscal year to avoid forfeiting the regime."
        )

    return SIIQCheckResult(
        eligible=not failures,
        failures=failures,
        warnings=warnings,
    )


@dataclass
class SIIQTaxImpactResult:
    rental_income_taxed_eur: Decimal
    rental_income_exempt_eur: Decimal
    non_core_income_taxed_eur: Decimal
    ordinary_tax_due_eur: Decimal
    effective_rate_on_rental: Decimal


def apply_siiq_regime(
    *,
    rental_income_eur: Decimal,
    non_core_taxable_income_eur: Decimal,
    eligibility: SIIQCheckResult,
    rates: ItalianTaxRates = ITALIAN_TAX_RATES_2026,
) -> SIIQTaxImpactResult:
    """Apply the SIIQ regime to rental income.

    Under the regime, qualifying rental income is IRES+IRAP-exempt at
    entity level (taxation shifts to shareholders via the mandatory
    dividend). Non-core income is taxed ordinarily at the ordinary
    IRES+IRAP combined rate (approximation — IRAP base rebuild is
    caller-side).
    """
    if eligibility.eligible:
        exempt = rental_income_eur
        taxed_rental = Decimal("0")
    else:
        exempt = Decimal("0")
        taxed_rental = rental_income_eur

    ordinary_rate = rates.ires_rate + rates.irap_rate_default
    ordinary_base = taxed_rental + non_core_taxable_income_eur
    ordinary_tax = ordinary_base * ordinary_rate

    effective = (
        ordinary_tax / rental_income_eur
        if rental_income_eur > 0
        else Decimal("0")
    )
    return SIIQTaxImpactResult(
        rental_income_taxed_eur=taxed_rental,
        rental_income_exempt_eur=exempt,
        non_core_income_taxed_eur=non_core_taxable_income_eur,
        ordinary_tax_due_eur=ordinary_tax,
        effective_rate_on_rental=effective,
    )


# ── PEX (Participation Exemption) ──────────────────────────────────────


@dataclass
class PEXCheckInputs:
    """Facts tested against Art. 87 TUIR for PEX eligibility on share disposal."""

    holding_period_months: int
    classified_as_financial_asset_since_first_fy: bool
    subsidiary_not_tax_haven_resident: bool
    subsidiary_exercises_commercial_activity: bool
    rates: ItalianTaxRates = ITALIAN_TAX_RATES_2026


@dataclass
class PEXCheckResult:
    eligible: bool
    failures: list[str]


def check_pex_eligibility(inputs: PEXCheckInputs) -> PEXCheckResult:
    """Return whether a capital-gain disposal qualifies for PEX."""
    rates = inputs.rates
    failures: list[str] = []
    if inputs.holding_period_months < rates.pex_min_holding_months:
        failures.append(
            f"Holding period {inputs.holding_period_months}m below "
            f"{rates.pex_min_holding_months}m minimum"
        )
    if not inputs.classified_as_financial_asset_since_first_fy:
        failures.append(
            "Must have been classified among immobilizzazioni finanziarie "
            "in the first financial statement of the holding period"
        )
    if not inputs.subsidiary_not_tax_haven_resident:
        failures.append(
            "Subsidiary is tax-haven resident — PEX denied "
            "(black-list jurisdictions per D.M. 21/11/2001)"
        )
    if not inputs.subsidiary_exercises_commercial_activity:
        failures.append(
            "Subsidiary is a pure holding / real-estate passive entity — "
            "commercial-activity test (Art. 87 c.1 lett. d) not met"
        )
    return PEXCheckResult(eligible=not failures, failures=failures)


@dataclass
class PEXApplicationResult:
    gross_gain_eur: Decimal
    exempt_gain_eur: Decimal
    taxable_gain_eur: Decimal
    ires_tax_on_gain_eur: Decimal
    effective_rate_on_gain: Decimal


def apply_pex_to_capital_gain(
    *,
    gross_capital_gain_eur: Decimal,
    eligibility: PEXCheckResult,
    rates: ItalianTaxRates = ITALIAN_TAX_RATES_2026,
) -> PEXApplicationResult:
    """Apply PEX to a capital gain.

    Eligible: 95% of the gain is exempt (5% taxed at 24% IRES =
    1.2% effective). Not eligible: full gain taxed at 24% IRES.
    """
    gross = Decimal(gross_capital_gain_eur)
    if gross <= 0:
        return PEXApplicationResult(
            gross_gain_eur=gross,
            exempt_gain_eur=Decimal("0"),
            taxable_gain_eur=gross,
            ires_tax_on_gain_eur=Decimal("0"),
            effective_rate_on_gain=Decimal("0"),
        )

    if eligibility.eligible:
        exempt = gross * rates.pex_exempt_pct
        taxable = gross - exempt
    else:
        exempt = Decimal("0")
        taxable = gross

    ires_tax = taxable * rates.ires_rate
    effective = ires_tax / gross if gross > 0 else Decimal("0")
    return PEXApplicationResult(
        gross_gain_eur=gross,
        exempt_gain_eur=exempt,
        taxable_gain_eur=taxable,
        ires_tax_on_gain_eur=ires_tax,
        effective_rate_on_gain=effective,
    )

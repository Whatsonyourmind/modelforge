"""Minibond shadow — Investor Net YTM (after Italian withholding).

Investor cash flow from the bondholder's perspective:

    t=0: -notional − (notional × transaction_cost_bps/10000)
                  − (notional × arrangement_fee_pct)   (investor bears)
    t=1..tenor: + coupon_per_period × (1 − withholding_tax_pct)
                + scheduled principal repayment
                   (amortization profile: linear_from_year OR bullet)

Returns IRR on the net (after-WHT) investor cashflow.
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value, irr


def minibond_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    notional = dv(spec.bond.notional)
    tenor = int(spec.bond.tenor_years)
    arr_fee = dv(spec.bond.arrangement_fee_pct)
    coupon = spec.bond.coupon
    wht = dv(spec.investor_adjustments.withholding_tax_pct)
    txn_bps = dv(spec.investor_adjustments.transaction_cost_bps)
    freq = int(coupon.frequency_per_year or 1)

    # Resolve effective coupon rate
    if coupon.kind == "fixed" and coupon.fixed_rate is not None:
        annual_rate = dv(coupon.fixed_rate)
    elif coupon.kind == "floating":
        ref = dv(coupon.reference_rate_value) if coupon.reference_rate_value else 0.0
        margin = dv(coupon.margin_bps) if coupon.margin_bps else 0.0
        floor = dv(coupon.floor_pct) if coupon.floor_pct else 0.0
        annual_rate = max(ref, floor) + margin / 10_000.0
    else:
        annual_rate = 0.0

    # Amortization
    amort_type = str(spec.bond.amortization).lower()
    amort_start = int(getattr(spec.bond, "amortization_start_year", 1) or 1)
    amort_period = max(tenor - amort_start + 1, 1)

    # Annual cashflow series (shadow simplifies to annual periodicity —
    # if coupon paid semi-annually the annualized net yield is a close
    # approximation, typically off by < 10bps for 5-7y minibonds).
    cf = [0.0] * (tenor + 1)

    # t=0: investor pays notional + transaction cost + arrangement fee
    cf[0] = -notional - notional * (txn_bps / 10_000.0) - notional * arr_fee

    balance = notional
    for t in range(1, tenor + 1):
        # Coupon: paid on outstanding balance, net of withholding
        period_coupon = balance * annual_rate * (1 - wht)
        # Principal repayment per schedule
        if "linear" in amort_type and t >= amort_start:
            principal = notional / amort_period
        elif "bullet" in amort_type and t == tenor:
            principal = balance
        elif t == tenor:
            # default: bullet
            principal = balance
        else:
            principal = 0.0
        principal = min(principal, balance)
        cf[t] = period_coupon + principal
        balance = max(balance - principal, 0.0)

    r = irr(cf, guess=annual_rate * (1 - wht))
    return r if r is not None else 0.0

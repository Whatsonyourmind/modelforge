"""Real Estate shadow — Equity IRR on the Financing sheet.

Walk (simplified vs full emitter):
    t=0: equity outflow = purchase_price × (1 − LTV)
                        − senior × arrangement_fee
                        − transaction_costs × purchase
    t=1..hold−1: NOI − debt_service
    t=hold: NOI_final − debt_service + (exit_sale − balance)
      where NOI_t = gross_rent × (1 + indexation)^(t−1) × (1 − vacancy)
                  × (1 − opex_pct − capex_pct)
            exit_sale = NOI_final × (1 + indexation) / exit_cap_rate
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value, irr


def real_estate_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    hold = int(spec.horizon.hold_years)

    price = dv(spec.property.acquisition_price_eur_m)
    area = dv(spec.property.lettable_area_sqm)
    rent_sqm = dv(spec.property.rent_eur_sqm_year1)
    vacancy = dv(spec.property.vacancy_pct)
    rent_idx = dv(spec.property.rent_indexation_pct)
    opex_pct = dv(spec.property.opex_pct_gross_rent)
    capex_pct = dv(spec.property.capex_pct_gross_rent)

    ltv = dv(spec.financing.ltv_pct)
    senior_rate = dv(spec.financing.senior_interest_rate)
    senior_tenor = int(spec.financing.senior_tenor_years)
    arr_fee = dv(spec.financing.arrangement_fee_pct)
    amort = str(spec.financing.senior_amortization).lower()

    exit_cap = dv(spec.exit.exit_cap_rate)
    txn_costs = dv(spec.exit.transaction_costs_pct)

    senior = price * ltv
    # Amortization schedule
    amort_period = max(senior_tenor, 1)

    # Equity outflow at t=0
    equity_cf: list[float] = []
    initial_equity = price * (1 - ltv) + senior * arr_fee
    equity_cf.append(-initial_equity)

    # Operating period
    balance = senior
    gross_rent_base = area * rent_sqm / 1_000_000.0  # convert to €m
    last_noi = 0.0
    for t in range(1, hold + 1):
        gross_rent = gross_rent_base * ((1 + rent_idx) ** (t - 1)) * (1 - vacancy)
        noi = gross_rent * (1 - opex_pct - capex_pct)
        interest = balance * senior_rate
        if "linear" in amort or "amort" in amort:
            repay = min(senior / amort_period, balance)
        elif t == hold:
            repay = 0.0  # bullet balance repaid via exit sale
        else:
            repay = 0.0
        debt_service = interest + repay
        last_noi = noi
        if t < hold:
            equity_cf.append(noi - debt_service)
        else:
            # Exit sale at cap rate applied to forward NOI
            exit_gross = last_noi * (1 + rent_idx) / max(exit_cap, 1e-6)
            exit_net = exit_gross * (1 - txn_costs)
            equity_at_exit = noi - debt_service + (exit_net - max(balance - repay, 0.0))
            equity_cf.append(equity_at_exit)
        balance = max(balance - repay, 0.0)

    r = irr(equity_cf, guess=0.10)
    return r if r is not None else 0.0

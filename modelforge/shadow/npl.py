"""NPL shadow — Equity IRR on the collection waterfall.

Simplifications vs full emitter:
    * Waterfall: senior repays first from net collections, then mezz,
      then equity. Interest accrued when available; principal after.
    * Data-tape cost treated as t=0 equity outflow.

    t=0: equity = (purchase_price − senior_note − mezz_note)
                + setup_fee + data_tape_cost
    t=1..N: gross_coll_t = (cum_curve[t] − cum_curve[t−1]) × GBV
            net_coll_t = gross_coll_t × (1 − servicing% − legal%)
            senior + mezz consume their share; residual → equity
    IRR on equity_cf.
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value, irr


def npl_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    N = int(spec.horizon.collection_years)
    gbv = dv(spec.portfolio.gbv_eur_m)
    pp_pct = dv(spec.portfolio.purchase_price_pct_gbv)
    purchase = gbv * pp_pct
    sen_pct = dv(spec.capital.senior_note_pct_purchase)
    sen_rate = dv(spec.capital.senior_note_rate)
    sen_tenor = int(spec.capital.senior_note_tenor_years)
    mezz_pct = dv(spec.capital.mezz_note_pct_purchase)
    mezz_rate = dv(spec.capital.mezz_note_rate)
    senior = purchase * sen_pct
    mezz = purchase * mezz_pct
    equity = purchase - senior - mezz

    serv_pct = dv(spec.servicing.servicing_fee_pct_collections)
    setup_pct = dv(spec.servicing.setup_fee_pct_gbv)
    legal_pct = dv(spec.servicing.legal_fee_pct_collections)
    data_tape = dv(spec.servicing.data_tape_cost_eur_m)

    # Collection curve (cumulative % of GBV). Pad or truncate to N.
    cum_pcts = [dv(a) for a in spec.portfolio.cumulative_collection_curve_pct]
    if len(cum_pcts) < N:
        # Extrapolate flat at last value
        cum_pcts = cum_pcts + [cum_pcts[-1] if cum_pcts else 0.0] * (N - len(cum_pcts))
    cum_pcts = cum_pcts[:N]

    # Equity cashflow
    equity_cf = [-equity - gbv * setup_pct - data_tape]

    sen_bal = senior
    mezz_bal = mezz
    prev_cum = 0.0
    for t in range(1, N + 1):
        gross_coll = (cum_pcts[t - 1] - prev_cum) * gbv
        prev_cum = cum_pcts[t - 1]
        net_coll = gross_coll * (1 - serv_pct - legal_pct)

        # Pay senior interest + any available principal within tenor
        sen_int = sen_bal * sen_rate if t <= sen_tenor else 0.0
        sen_avail = min(net_coll, sen_int)
        net_coll -= sen_avail
        sen_principal = 0.0
        if t <= sen_tenor and sen_bal > 0 and net_coll > 0:
            sen_principal = min(net_coll, sen_bal)
            net_coll -= sen_principal
            sen_bal -= sen_principal
        # If we missed interest this year, it accrues to balance
        if sen_int - sen_avail > 0:
            sen_bal += (sen_int - sen_avail)

        # Mezz interest + principal
        mezz_int = mezz_bal * mezz_rate
        mezz_avail = min(net_coll, mezz_int)
        net_coll -= mezz_avail
        if mezz_bal > 0 and net_coll > 0:
            mezz_principal = min(net_coll, mezz_bal)
            net_coll -= mezz_principal
            mezz_bal -= mezz_principal
        if mezz_int - mezz_avail > 0:
            mezz_bal += (mezz_int - mezz_avail)

        # Remainder to equity
        equity_cf.append(net_coll)

    r = irr(equity_cf, guess=0.15)
    return r if r is not None else 0.0

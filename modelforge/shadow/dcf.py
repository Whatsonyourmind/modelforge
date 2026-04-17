"""DCF shadow engine — exact Enterprise Value recomputation.

Mirrors modelforge/builder/sheets/dcf_valuation.py:

    WACC = Ke × (E/V) + Kd × (1-t) × (D/V)
    FCF_t = NOPAT_t + D&A_t - capex_t - Δ NWC_t
    EV = Σ FCF_t / (1+WACC)^t  +  TV / (1+WACC)^p
    TV = average(Gordon TV, Exit EV/EBITDA TV)
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value


def dcf_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    # WACC build
    rf = dv(spec.wacc.risk_free_rate)
    erp = dv(spec.wacc.equity_risk_premium)
    beta = dv(spec.wacc.beta_levered)
    kd_pt = dv(spec.wacc.pretax_cost_of_debt)
    tax = dv(spec.wacc.effective_tax_rate)
    dw = dv(spec.wacc.target_debt_weight)

    ke = rf + beta * erp
    kd_at = kd_pt * (1 - tax)
    wacc = ke * (1 - dw) + kd_at * dw
    if wacc <= 0:
        return 0.0

    # Explicit-period FCF walk
    p = spec.horizon.projection_years
    rev = spec.target.revenue_last_fy_eur_m
    da_pct = dv(spec.fcf.da_pct_revenue)
    capex_pct = dv(spec.fcf.capex_pct_revenue)
    nwc_pct = dv(spec.fcf.nwc_pct_revenue_delta)

    fcfs: list[float] = []
    last_ebitda = 0.0
    prev_rev = rev
    for i in range(p):
        g = dv(spec.fcf.revenue_growth_by_year[i])
        m = dv(spec.fcf.ebitda_margin_by_year[i])
        rev_t = prev_rev * (1 + g)
        ebitda = rev_t * m
        da = rev_t * da_pct
        ebit = ebitda - da
        nopat = ebit * (1 - tax)
        capex = rev_t * capex_pct
        delta_nwc = (rev_t - prev_rev) * nwc_pct if i > 0 else 0.0
        fcf = nopat + da - capex - delta_nwc
        fcfs.append(fcf)
        last_ebitda = ebitda
        prev_rev = rev_t

    # Terminal value (average of Gordon + Exit multiple, per emitter)
    g_term = dv(spec.terminal.terminal_growth_pct)
    exit_x = dv(spec.terminal.exit_ev_ebitda_x)
    if wacc <= g_term:
        tv_gordon = fcfs[-1] * 10  # cap to prevent division blow-up
    else:
        tv_gordon = fcfs[-1] * (1 + g_term) / (wacc - g_term)
    tv_exit = last_ebitda * exit_x
    tv = (tv_gordon + tv_exit) / 2.0

    # PV of explicit FCF + PV of TV
    pv_fcf = sum(fcfs[i] / (1 + wacc) ** (i + 1) for i in range(p))
    pv_tv = tv / (1 + wacc) ** p
    ev = pv_fcf + pv_tv
    return ev

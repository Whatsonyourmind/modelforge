"""Project Finance shadow engine — exact Sponsor Equity IRR.

Simplified vs the full emitter (ignores sculpted-DSCR-target solver;
uses the sized debt as-is). Sufficient for ±shock sensitivity and MC
distribution shaping, which is the shadow engine's purpose.

    t=0..(c-1):  equity = capex × (1 - debt_pct) per phase
    t=c..(c+o):  CADS = revenue - opex - tax
                 debt service = interest + amort (per existing profile)
                 equity_cf = CADS - debt_service + equity_tax_credit
    IRR on equity_cf
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value, irr


def pf_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    c = spec.horizon.construction_years
    o = spec.horizon.operating_years

    total_capex = dv(spec.construction.total_capex_eur_m)
    debt_amount = dv(spec.debt.amount)
    debt_amount = min(debt_amount, total_capex)
    equity_amount = max(total_capex - debt_amount, 1.0)

    # Construction phasing — list of Assumption objects
    phase_drivers = spec.construction.capex_phasing_pct
    phasing = [dv(p) for p in phase_drivers] if phase_drivers else [1.0 / c] * c
    s = sum(phasing) or 1.0
    phasing = [x / s for x in phasing]
    phasing = (phasing + [0.0] * c)[:c]

    # Operating path
    rev_y1 = dv(spec.operating.availability_payment_eur_m_yr1)
    rev_index = dv(spec.operating.revenue_indexation_pct)
    opex_pct = dv(spec.operating.opex_pct_revenue)
    opex_index = dv(spec.operating.opex_indexation_pct)
    tax_rate = dv(spec.equity.effective_tax_rate)

    # Debt terms
    # PF debt.reference_rate may be an Assumption directly (not a
    # ReferenceRate sub-model) depending on spec version.
    _rate_node = spec.debt.reference_rate
    if hasattr(_rate_node, 'rate_decimal'):
        swap_rate = dv(_rate_node.rate_decimal)
    else:
        swap_rate = dv(_rate_node)
    margin_bps = dv(spec.debt.margin_bps)
    rate = swap_rate + margin_bps / 10_000.0
    grace = int(spec.debt.grace_years) if getattr(spec.debt, 'grace_years', None) else 0
    op_tenor = min(int(spec.debt.tenor_operating_years), o)

    equity_cf: list[float] = []

    # Construction: equity outflow
    for i in range(c):
        phase_capex = total_capex * phasing[i]
        phase_equity = phase_capex * (equity_amount / total_capex)
        equity_cf.append(-phase_equity)

    # Operating: CADS - debt service per year
    balance = debt_amount
    amort_period = max(op_tenor - grace, 1)
    amort_per_year = debt_amount / amort_period
    for t in range(o):
        rev = rev_y1 * ((1 + rev_index) ** t)
        opex = rev * opex_pct * ((1 + opex_index) ** t)
        # Debt service only within op_tenor
        if t < op_tenor:
            interest = balance * rate
            if t < grace:
                repay = 0.0
            else:
                repay = min(amort_per_year, balance)
        else:
            interest = 0.0
            repay = 0.0
        ebit = rev - opex
        tax = max(ebit * tax_rate, 0.0)
        cads = ebit - tax
        debt_service = interest + repay
        equity_cf.append(cads - debt_service)
        balance = max(balance - repay, 0.0)

    r = irr(equity_cf, guess=0.08)
    return r if r is not None else 0.0

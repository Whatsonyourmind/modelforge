"""3-statement shadow — Y1 projected Net Income.

Walk:
    revenue_y1 = hist_rev × (1 + revenue_growth_y1)
    ebitda_y1  = revenue_y1 × ebitda_margin_y1
    d&a_y1     = revenue_y1 × da_pct_revenue
    ebit_y1    = ebitda_y1 − d&a_y1
    interest_y1 = opening_debt × interest_on_debt_pct
    ebt_y1     = ebit_y1 − interest_y1
    tax_y1     = max(ebt_y1, 0) × effective_tax_rate
    net_income_y1 = ebt_y1 − tax_y1
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value


def three_statement_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    hist_rev = (spec.historical_revenue_eur_m[-1]
                if spec.historical_revenue_eur_m
                else spec.target.revenue_last_fy_eur_m)
    g = dv(spec.pl.revenue_growth_by_year[0])
    m = dv(spec.pl.ebitda_margin_by_year[0])
    da_pct = dv(spec.pl.da_pct_revenue)
    int_pct = dv(spec.pl.interest_on_debt_pct)
    tax_rate = dv(spec.pl.effective_tax_rate)

    rev_y1 = hist_rev * (1 + g)
    ebitda_y1 = rev_y1 * m
    da_y1 = rev_y1 * da_pct
    ebit_y1 = ebitda_y1 - da_y1
    interest_y1 = spec.opening_bs.debt_eur_m * int_pct
    ebt_y1 = ebit_y1 - interest_y1
    tax_y1 = max(ebt_y1, 0.0) * tax_rate
    return ebt_y1 - tax_y1

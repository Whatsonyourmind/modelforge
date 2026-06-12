"""Merger shadow engine — Y1 accretion/dilution %.

Walks the pro-forma P&L with REAL D&A + interest per party, then
returns Y1 accretion/dilution vs acquirer's Y1 standalone EPS.
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value


def merger_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    # Deal structure
    offer_premium = dv(spec.deal.offer_premium_pct)
    cash_mix = dv(spec.deal.cash_mix_pct)
    fin_rate = dv(spec.deal.financing_rate_pct)
    tax_rate = dv(spec.deal.effective_tax_rate)

    # Synergies
    rev_syn_rr = dv(spec.synergies.revenue_synergies_eur_m)
    cost_syn_rr = dv(spec.synergies.cost_synergies_eur_m)
    syn_y1_pct = dv(spec.synergies.synergy_realization_y1_pct)
    integ_cost = dv(spec.synergies.integration_cost_eur_m)

    # Offer
    target_px = spec.target_financials.share_price_eur
    offer_px = target_px * (1 + offer_premium)
    equity_price = offer_px * spec.target_financials.shares_outstanding_m
    cash_cons = equity_price * cash_mix
    stock_cons = equity_price * (1 - cash_mix)
    new_shares = stock_cons / spec.acquirer.share_price_eur if spec.acquirer.share_price_eur > 0 else 0.0
    incr_int = -cash_cons * fin_rate

    # Y1 pro-forma P&L using REAL D&A + interest
    acq = spec.acquirer
    tgt = spec.target_financials

    # Growth assumptions read from the spec so the shadow ground truth stays in
    # lockstep with the live merger_proforma sheet (which reads the same fields).
    # Hardcoding 1.03/1.04 made an analyst's growth overrides a silent no-op in
    # the shadow — diverging the tornado / Monte Carlo from the rendered model.
    acq_g = getattr(spec, "acquirer_revenue_growth_pct", 0.03)
    tgt_g = getattr(spec, "target_revenue_growth_pct", 0.04)
    int_g = getattr(spec, "combined_interest_growth_pct", 0.03)
    da_g = getattr(spec, "combined_da_growth_pct", 0.03)
    eps_g = getattr(spec, "standalone_eps_growth_pct", 0.03)

    # Year 1 = first projection year. Revenues grown per spec; synergies ramp
    # at syn_y1_pct.
    rev_y1 = (acq.revenue_eur_m * (1 + acq_g) + tgt.revenue_eur_m * (1 + tgt_g)
              + rev_syn_rr * syn_y1_pct)
    # EBITDA at the acquirer + target FY0 margins (proxy — growth applied to the
    # revenue line, margins held).
    acq_margin = acq.ebitda_eur_m / max(acq.revenue_eur_m, 1.0)
    tgt_margin = tgt.ebitda_eur_m / max(tgt.revenue_eur_m, 1.0)
    ebitda = (acq.revenue_eur_m * (1 + acq_g) * acq_margin
              + tgt.revenue_eur_m * (1 + tgt_g) * tgt_margin
              + cost_syn_rr * syn_y1_pct
              - integ_cost)  # one-time Y1 hit

    # Walk EBITDA → EBIT using real combined D&A (grown per spec)
    da_combined = (acq.da_eur_m + tgt.da_eur_m) * (1 + da_g)
    ebit = ebitda - da_combined

    # Interest: standalone combined + incremental
    standalone_int = ((acq.interest_expense_eur_m + tgt.interest_expense_eur_m)
                      * (1 + int_g))
    pretax = ebit - standalone_int + incr_int
    tax = max(pretax * tax_rate, 0.0)
    pf_ni = pretax - tax

    pf_shares = acq.shares_outstanding_m + new_shares
    pf_eps = pf_ni / pf_shares if pf_shares > 0 else 0.0

    # Standalone acquirer Y1 EPS (grown per spec)
    std_eps = (acq.net_income_eur_m * (1 + eps_g)) / max(acq.shares_outstanding_m, 1.0)

    if std_eps <= 0:
        return 0.0
    return pf_eps / std_eps - 1.0  # accretion / dilution %

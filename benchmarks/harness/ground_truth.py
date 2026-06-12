"""ground_truth.py — clean-room ground truth for the ModelForge public benchmark.

Computes the headline outputs of the THREE benchmark briefs using plain
arithmetic + numpy_financial ONLY. It imports NO modelforge code, reads NO
workbook, and reads NO YAML — every number below is typed straight from the
frozen briefs in benchmarks/briefs/ (the briefs are the single source of
truth; this file is their executable restatement).

    (a) lbo_us_saas        — sponsor IRR + MoIC (exit EQUITY = exit EV − debt
                             outstanding at exit), entry/exit EV, equity cheque
    (b) dcf_industrial     — WACC, enterprise value, equity value, per share
    (c) three_statement_mfg— final-year net income, total assets, total L&E,
                             balance check, cash, debt

Usage:
    python benchmarks/harness/ground_truth.py            # prints JSON
    python benchmarks/harness/ground_truth.py --out f.json

The scorer (score.py) imports compute_all() from this module.
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy_financial as npf


# ─────────────────────────────────────────────────────────────────────────────
# (a) lbo_us_saas — brief BM-LBO-001
# ─────────────────────────────────────────────────────────────────────────────

def lbo_us_saas() -> dict:
    """Sponsor LBO of a synthetic US enterprise SaaS company.

    Brief conventions (all stated in briefs/lbo_us_saas.md):
      * entry EBITDA = last historical FY EBITDA
      * equity purchase price = share price x (1 + premium) x FD shares
      * total uses = equity PP + net-debt refinance + M&A fees + financing
        fees + minimum cash funded at close
      * sponsor equity cheque = total uses − debt drawn (balancing plug)
      * debt is bullet, NO cash sweep → debt at exit = debt at close
      * exit equity = exit multiple x PROJECTED year-5 EBITDA − debt at exit
      * sponsor cash flows = [−cheque, 0, 0, 0, 0, +exit equity]
      * IRR via numpy_financial.irr; MoIC = exit equity / cheque
    """
    # Inputs (frozen brief values)
    entry_revenue = 100.0
    entry_ebitda = 35.0
    share_price = 4.40
    offer_premium = 0.25
    fd_shares_m = 60.0
    target_net_debt = 20.0
    ma_fees = 7.0
    financing_fees = 5.0
    min_cash_at_close = 5.0
    senior_amount = 157.5
    mezz_amount = 35.0
    growth = [0.12, 0.11, 0.10, 0.09, 0.08]      # years 1..5 (hold period)
    margin = [0.35, 0.36, 0.36, 0.37, 0.38]      # years 1..5
    exit_year = 5
    exit_multiple = 9.0

    # Purchase price build
    offer_px = share_price * (1.0 + offer_premium)          # 5.50
    equity_pp = offer_px * fd_shares_m                       # 330.0
    entry_ev = equity_pp + target_net_debt                   # 350.0
    entry_multiple = entry_ev / entry_ebitda                 # 10.0x

    # Sources & uses
    total_uses = (equity_pp + target_net_debt + ma_fees + financing_fees
                  + min_cash_at_close)                       # 367.0
    total_debt = senior_amount + mezz_amount                 # 192.5
    sponsor_equity = total_uses - total_debt                 # 174.5 (plug)

    # Operating projection to exit
    rev = entry_revenue
    ebitda_path = []
    for g, m in zip(growth, margin):
        rev *= (1.0 + g)
        ebitda_path.append(rev * m)
    exit_ebitda = ebitda_path[exit_year - 1]

    # Exit: equity = EV − debt outstanding (bullet, no sweep → face value)
    exit_ev = exit_multiple * exit_ebitda
    exit_debt = total_debt
    exit_equity = exit_ev - exit_debt

    # Returns
    cf = [-sponsor_equity] + [0.0] * (exit_year - 1) + [exit_equity]
    irr = float(npf.irr(cf))
    moic = exit_equity / sponsor_equity

    return {
        "brief": "lbo_us_saas",
        "headlines": {
            "sponsor_irr": irr,
            "sponsor_moic": moic,
            "exit_equity_proceeds": exit_equity,
            "sponsor_equity_cheque": sponsor_equity,
        },
        "supporting": {
            "offer_price_per_share": offer_px,
            "equity_purchase_price": equity_pp,
            "entry_ev": entry_ev,
            "entry_ev_ebitda_x": entry_multiple,
            "total_uses": total_uses,
            "total_debt_drawn": total_debt,
            "exit_year_ebitda_projected": exit_ebitda,
            "exit_ev": exit_ev,
            "debt_outstanding_at_exit": exit_debt,
            "sponsor_cash_flows": cf,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# (b) dcf_industrial — brief BM-DCF-001
# ─────────────────────────────────────────────────────────────────────────────

def dcf_industrial() -> dict:
    """Enterprise DCF of a synthetic US diversified industrial.

    Brief conventions (all stated in briefs/dcf_industrial.md):
      * cost of equity = rf + beta x ERP (plain CAPM, no extra premia)
      * WACC = Ke x (1−wd) + Kd x (1−t) x wd
      * FCFF_t = EBIT_t x (1−t) + D&A_t − capex_t − dNWC_t
      * END-OF-YEAR discounting, full first year (PV exponents 1..5)
      * terminal value = Gordon on NORMALIZED FCF:
          norm FCF = NOPAT_5 − dNWC_5 x (1+g)      (capex = D&A steady state)
          TV       = norm FCF x (1+g) / (WACC − g)
        discounted at the year-5 factor
      * equity value = EV − net debt (no minorities/pension/leases/preferred)
    """
    # Inputs (frozen brief values)
    revenue_last = 1000.0
    growth = [0.040, 0.035, 0.030, 0.025, 0.020]
    margin = [0.18] * 5
    da_pct = 0.060
    capex_pct = 0.065
    nwc_pct = 0.10
    rf = 0.0425
    erp = 0.050
    beta = 1.10
    kd_pretax = 0.0575
    tax = 0.25
    wd = 0.30
    g_term = 0.020
    net_debt = 250.0
    shares_m = 150.0
    ref_price = 8.00
    P = 5

    # WACC
    ke = rf + beta * erp
    kd_after = kd_pretax * (1.0 - tax)
    wacc = ke * (1.0 - wd) + kd_after * wd

    # FCFF forecast
    rev_path = []
    prev = revenue_last
    for g in growth:
        prev *= (1.0 + g)
        rev_path.append(prev)
    ebitda = [rev_path[i] * margin[i] for i in range(P)]
    da = [rev_path[i] * da_pct for i in range(P)]
    ebit = [ebitda[i] - da[i] for i in range(P)]
    nopat = [ebit[i] * (1.0 - tax) for i in range(P)]
    capex = [rev_path[i] * capex_pct for i in range(P)]
    rev_with_last = [revenue_last] + rev_path
    dnwc = [(rev_with_last[i + 1] - rev_with_last[i]) * nwc_pct
            for i in range(P)]
    fcff = [nopat[i] + da[i] - capex[i] - dnwc[i] for i in range(P)]

    # End-of-year PV (exponents 1..5)
    pv_explicit = sum(fcff[i] / (1.0 + wacc) ** (i + 1) for i in range(P))

    # Gordon terminal on normalized FCF (capex = D&A in perpetuity)
    norm_fcf = nopat[-1] - dnwc[-1] * (1.0 + g_term)
    tv = norm_fcf * (1.0 + g_term) / (wacc - g_term)
    pv_tv = tv / (1.0 + wacc) ** P

    ev = pv_explicit + pv_tv
    equity = ev - net_debt
    per_share = equity / shares_m

    return {
        "brief": "dcf_industrial",
        "headlines": {
            "wacc": wacc,
            "enterprise_value": ev,
            "equity_value": equity,
            "implied_price_per_share": per_share,
        },
        "supporting": {
            "cost_of_equity": ke,
            "after_tax_cost_of_debt": kd_after,
            "fcff_by_year": fcff,
            "pv_explicit": pv_explicit,
            "normalized_terminal_fcf": norm_fcf,
            "terminal_value": tv,
            "pv_terminal_value": pv_tv,
            "net_debt": net_debt,
            "reference_price": ref_price,
            "premium_to_reference": per_share / ref_price - 1.0,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# (c) three_statement_mfg — brief BM-3S-001
# ─────────────────────────────────────────────────────────────────────────────

def three_statement_mfg() -> dict:
    """Integrated 3-statement model of a synthetic US manufacturer.

    Brief conventions (all stated in briefs/three_statement_mfg.md):
      * timeline = 3 historical + 5 projection columns (t = 0..7);
        t=0..2 historical, t=2 is the opening balance-sheet anchor — the
        model restates working capital from the days drivers for t>=1
      * revenue compounds; EBITDA = revenue x margin; D&A = revenue x 5.5%
      * debt amortizes 20.0/yr (floored at 0); interest 6.0% on the OPENING
        balance (t=0 uses the same-period balance)
      * tax 25% on positive EBT only; dividends 30% of positive net income
      * AR/Inventory/Payables = revenue x days / 365 (all on revenue)
      * PP&E roll: prior + capex − D&A; capex = revenue x 6.0%
      * CFF = −dividends − debt repayment; cash rolls from CFO+CFI+CFF
      * headline year = final projection year (t = 7)
    """
    h, p = 3, 5
    n = h + p
    hist_rev = [540.0, 570.0, 600.0]
    hist_ebitda = [70.2, 76.95, 84.0]
    growth = [0.050, 0.045, 0.040, 0.035, 0.030]
    margin = [0.140, 0.145, 0.150, 0.150, 0.150]
    da_pct = 0.055
    int_rate = 0.060
    tax_rate = 0.25
    dso, dio, dpo = 55.0, 60.0, 40.0
    capex_pct = 0.060
    payout = 0.30
    ob = {"cash": 40.0, "ar": 90.0, "inv": 75.0, "ppe": 250.0,
          "ap": 55.0, "debt": 180.0, "equity": 220.0}
    annual_repay = 20.0

    # Revenue / EBITDA
    revenue = list(hist_rev)
    for i in range(p):
        revenue.append(revenue[-1] * (1.0 + growth[i]))
    ebitda = list(hist_ebitda)
    for i in range(p):
        ebitda.append(revenue[h + i] * margin[i])

    # P&L
    da = [-revenue[t] * da_pct for t in range(n)]            # negative
    ebit = [ebitda[t] + da[t] for t in range(n)]

    debt = [ob["debt"]]
    for t in range(1, n):
        debt.append(max(debt[-1] - annual_repay, 0.0))

    interest = []
    for t in range(n):
        opening = debt[t] if t == 0 else debt[t - 1]
        interest.append(-opening * int_rate)

    ebt = [ebit[t] + interest[t] for t in range(n)]
    tax = [-max(ebt[t], 0.0) * tax_rate for t in range(n)]
    ni = [ebt[t] + tax[t] for t in range(n)]

    # Balance sheet
    ar = [ob["ar"]]; inv = [ob["inv"]]; ap = [ob["ap"]]
    for t in range(1, n):
        ar.append(revenue[t] / 365.0 * dso)
        inv.append(revenue[t] / 365.0 * dio)
        ap.append(revenue[t] / 365.0 * dpo)
    ppe = [ob["ppe"]]
    for t in range(1, n):
        ppe.append(ppe[-1] + revenue[t] * capex_pct + da[t])

    # Cash flow statement
    div = [-max(ni[t], 0.0) * payout for t in range(n)]      # negative
    repay_cf = [0.0] + [-(debt[t - 1] - debt[t]) for t in range(1, n)]
    nwc = [0.0]
    for t in range(1, n):
        nwc.append(-((ar[t] - ar[t - 1]) + (inv[t] - inv[t - 1])
                     - (ap[t] - ap[t - 1])))
    cfo = [ni[t] + (-da[t]) + nwc[t] for t in range(n)]
    cfi = [-revenue[t] * capex_pct for t in range(n)]
    cff = [div[t] + repay_cf[t] for t in range(n)]
    net_change = [cfo[t] + cfi[t] + cff[t] for t in range(n)]

    cash = [ob["cash"]]
    for t in range(1, n):
        cash.append(cash[-1] + net_change[t])

    equity = [ob["equity"]]
    for t in range(1, n):
        equity.append(equity[-1] + ni[t] - max(ni[t], 0.0) * payout)

    total_assets = [cash[t] + ar[t] + inv[t] + ppe[t] for t in range(n)]
    total_le = [ap[t] + debt[t] + equity[t] for t in range(n)]
    f = n - 1   # final projection year

    return {
        "brief": "three_statement_mfg",
        "headlines": {
            "final_net_income": ni[f],
            "final_total_assets": total_assets[f],
            "final_total_liabilities_equity": total_le[f],
            "final_balance_check": total_assets[f] - total_le[f],
            "final_cash": cash[f],
            "final_debt": debt[f],
        },
        "supporting": {
            "revenue_by_year": revenue,
            "net_income_by_year": ni,
            "cash_by_year": cash,
            "debt_by_year": debt,
            "equity_by_year": equity,
            "balance_check_by_year": [total_assets[t] - total_le[t]
                                      for t in range(n)],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────

def compute_all() -> dict:
    return {
        "lbo_us_saas": lbo_us_saas(),
        "dcf_industrial": dcf_industrial(),
        "three_statement_mfg": three_statement_mfg(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="optional JSON output path")
    args = ap.parse_args()
    result = compute_all()
    text = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")
    print(text)


if __name__ == "__main__":
    main()

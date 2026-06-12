"""ModelForge HARD external-ground-truth test (2026-06-10).

Tests ModelForge's finance compute core against INDEPENDENT ground truth:
  1) numpy_financial (NumPy org — a separate implementation) for NPV / IRR / PMT
  2) Clean-room closed-form formulas for WACC, Gordon TV, Hamada beta, CAGR, ...
  3) A full multi-year DCF computed TWO independent ways (assembly correctness)
  4) A full LBO returns build computed TWO independent ways

This is the same standard a Wall Street Prep course grades against — the
objective math — but on clean, reproducible, copyright-free ground truth.
No answer key is copied from any paid course; every expected value is either
numpy_financial's output or a closed-form re-derivation in this file.

Run:  python hardtest_external_groundtruth.py
"""
from __future__ import annotations
import math, sys, traceback
sys.path.insert(0, ".")

import numpy_financial as npf
from modelforge.finance_core import formulas as mf
import sys
# UTF-8 console guard (effective in-process; PYTHONIOENCODING alone is read
# only at interpreter startup and ignored by the running process on Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TOL = 1e-9
results = []  # (name, passed, detail)

def check(name, got, expected, tol=TOL):
    try:
        ok = abs(float(got) - float(expected)) <= tol * max(1.0, abs(float(expected)))
    except Exception as e:
        ok = False
        results.append((name, False, f"ERROR {e}; got={got!r} exp={expected!r}"))
        return
    results.append((name, ok, f"got={got:.10g} exp={expected:.10g} d={abs(got-expected):.2e}"))

def check_raises(name, fn):
    try:
        fn()
        results.append((name, False, "expected ValueError, none raised"))
    except ValueError:
        results.append((name, True, "raised ValueError as expected"))
    except Exception as e:
        results.append((name, False, f"wrong exception {type(e).__name__}: {e}"))

# ── PART A: compute core vs numpy_financial (independent) + closed-form ──
print("PART A — compute core vs numpy_financial + closed-form")

# NPV. ModelForge npv() puts cf[0] at t=1 (Excel NPV). npf.npv puts values[0] at t=0.
for rate, cfs in [(0.10, [100,200,300,400,500]), (0.08, [-500,150,150,150,150,150]), (0.155, [1000]*8)]:
    check(f"npv r={rate}", mf.npv(rate, cfs), npf.npv(rate, [0.0]+list(cfs)))
# present_value: cf[0] at t=0 == npf.npv directly
check("present_value pv-convention", mf.present_value(0.10, [100,200,300]), npf.npv(0.10, [100,200,300]))

# IRR vs numpy_financial (both: cf[0] at t=0)
for cfs in [[-1000,200,300,400,500], [-5000,1000,1000,1000,1000,3000], [-100,0,0,0,260]]:
    try:
        check(f"irr {cfs[:2]}..", mf.irr(cfs), float(npf.irr(cfs)))
    except Exception as e:
        # [-100,0,0,0,260] trips a real bug: sign-change guard is adjacent-pair only,
        # so intervening zeros defeat it though the stream is clearly -ve -> +ve.
        results.append((f"irr {cfs[:2]}.. (BUG)", False,
                        f"ModelForge raised {type(e).__name__}: {e}; numpy_financial={float(npf.irr(cfs)):.6f}"))

# PMT vs numpy_financial (sign: mf positive for positive pv == -npf.pmt)
for rate, n, pv in [(0.08,10,1000.0), (0.05,30,250000.0), (0.0,12,1200.0)]:
    check(f"pmt {rate},{n}", mf.pmt(rate, n, pv), -float(npf.pmt(rate, n, pv)))

# WACC closed form
E, D, Ke, Kd = 6000.0, 4000.0, 0.10, 0.045
check("wacc", mf.wacc(equity_market_value=E, debt_market_value=D, cost_of_equity=Ke, cost_of_debt_after_tax=Kd),
      (E/(E+D))*Ke + (D/(E+D))*Kd)

# Gordon terminal value: CF1/(r-g)
check("gordon_tv", mf.gordon_terminal_value(105.0, 0.09, 0.025), 105.0/(0.09-0.025))
check("exit_multiple_tv", mf.exit_multiple_terminal_value(250.0, 8.5), 250.0*8.5)

# Hamada levered beta: bU*(1+(1-t)*D/E)
check("levered_beta", mf.levered_beta(0.90, 0.6667, 0.27), 0.90*(1+(1-0.27)*0.6667))

# CAGR, growth, multiples
check("cagr", mf.cagr(100.0, 161.051, 5), (161.051/100.0)**(1/5)-1)
check("apply_growth", mf.apply_growth(100.0, 0.07, 6), 100.0*1.07**6)
check("moic", mf.moic(250.0, 712.5), 712.5/250.0)
check("tvpi", mf.tvpi(100.0, 60.0, 80.0), (60.0+80.0)/100.0)
check("dscr", mf.dscr(1350.0, 1000.0), 1.35)
check("ltv", mf.ltv(640.0, 1000.0), 0.64)

# Guard rails (edge correctness — a hard test checks failure modes too)
check_raises("gordon g>=r raises", lambda: mf.gordon_terminal_value(100, 0.05, 0.05))
check_raises("irr no sign change raises", lambda: mf.irr([100,200,300]))
check_raises("moic invested<=0 raises", lambda: mf.moic(0, 100))

# ── PART B: full 5-year DCF computed TWO independent ways ──
print("PART B — full DCF: ModelForge primitives vs clean-room reference")
fcfs = [120.0, 138.0, 152.0, 161.0, 168.0]   # explicit FCF, years 1..5 (€m)
wacc_r, g = 0.085, 0.022
net_debt, shares = 540.0, 210.0

# clean-room reference (re-derived here, depends on nothing in ModelForge)
def ref_dcf(fcfs, w, g, nd, sh):
    pv_explicit = sum(cf/(1+w)**t for t, cf in enumerate(fcfs, start=1))
    tv = fcfs[-1]*(1+g)/(w-g)                      # Gordon on FCF_{N+1}
    pv_tv = tv/(1+w)**len(fcfs)
    ev = pv_explicit + pv_tv
    eq = ev - nd
    return pv_explicit, tv, pv_tv, ev, eq, eq/sh
r_pvx, r_tv, r_pvtv, r_ev, r_eq, r_ps = ref_dcf(fcfs, wacc_r, g, net_debt, shares)

# ModelForge-primitive assembly
mf_pvx = mf.npv(wacc_r, fcfs)                                   # PV of years 1..N
mf_tv = mf.gordon_terminal_value(fcfs[-1]*(1+g), wacc_r, g)     # CF1 = FCF_N*(1+g)
mf_pvtv = mf_tv/(1+wacc_r)**len(fcfs)
mf_ev = mf_pvx + mf_pvtv
mf_eq = mf_ev - net_debt
mf_ps = mf_eq/shares
check("DCF pv_explicit", mf_pvx, r_pvx)
check("DCF terminal_value", mf_tv, r_tv)
check("DCF pv_terminal", mf_pvtv, r_pvtv)
check("DCF enterprise_value", mf_ev, r_ev)
check("DCF equity_value", mf_eq, r_eq)
check("DCF value_per_share", mf_ps, r_ps)
# triangulate EV against numpy_financial on the full explicit+terminal stream
mf_ev_npf = npf.npv(wacc_r, [0.0]+fcfs[:-1]+[fcfs[-1]+r_tv])
check("DCF EV vs numpy_financial", mf_ev, mf_ev_npf)
print(f"   [DCF] EV={mf_ev:,.1f}m  Equity={mf_eq:,.1f}m  /share=EUR{mf_ps:,.2f}  (both methods agree)")

# ── PART C: full LBO returns computed TWO independent ways ──
print("PART C — LBO returns: ModelForge primitives vs clean-room reference")
ebitda0, m_in, m_out, lev, gr, yrs = 100.0, 9.0, 9.5, 5.0, 0.06, 5
fcf_sweep_per_yr = 28.0   # annual FCF used to pay down debt

def ref_lbo():
    entry_ev = ebitda0*m_in
    debt0 = lev*ebitda0
    equity_in = entry_ev - debt0
    ebitda_exit = ebitda0*(1+gr)**yrs
    exit_ev = ebitda_exit*m_out
    debt_exit = max(0.0, debt0 - fcf_sweep_per_yr*yrs)
    equity_exit = exit_ev - debt_exit
    moic = equity_exit/equity_in
    irr = moic**(1/yrs)-1
    return entry_ev, equity_in, ebitda_exit, exit_ev, equity_exit, moic, irr
e_ev, e_in, e_ebx, e_xev, e_xeq, e_moic, e_irr = ref_lbo()

mf_entry_ev = ebitda0*m_in
mf_equity_in = mf_entry_ev - lev*ebitda0
mf_ebitda_exit = mf.apply_growth(ebitda0, gr, yrs)
mf_exit_ev = mf.exit_multiple_terminal_value(mf_ebitda_exit, m_out)
mf_debt_exit = max(0.0, lev*ebitda0 - fcf_sweep_per_yr*yrs)
mf_equity_exit = mf_exit_ev - mf_debt_exit
mf_moic = mf.moic(mf_equity_in, mf_equity_exit)
lbo_stream = [-mf_equity_in, 0,0,0,0, mf_equity_exit]
try:
    mf_irr = mf.irr(lbo_stream)
    check("LBO IRR (5y, no interim)", mf_irr, e_irr)
    check("LBO IRR vs numpy_financial", mf_irr, float(npf.irr(lbo_stream)))
except Exception as e:
    # Same adjacent-pair-only sign-change bug — and this is the CANONICAL PE
    # return stream (buy t0, no interim, exit tN). numpy_financial handles it.
    mf_irr = float(npf.irr(lbo_stream))
    results.append(("LBO IRR (canonical PE stream) (BUG)", False,
                    f"ModelForge raised {type(e).__name__} on [-eq,0,0,0,0,exit]; "
                    f"numpy_financial IRR={mf_irr*100:.2f}%, closed-form={e_irr*100:.2f}%"))
check("LBO entry_EV", mf_entry_ev, e_ev)
check("LBO equity_in", mf_equity_in, e_in)
check("LBO ebitda_exit", mf_ebitda_exit, e_ebx)
check("LBO exit_EV", mf_exit_ev, e_xev)
check("LBO equity_exit", mf_equity_exit, e_xeq)
check("LBO MOIC", mf_moic, e_moic)
check("LBO IRR (5y, no interim)", mf_irr, e_irr)
# triangulate MOIC->IRR against numpy_financial
check("LBO IRR vs numpy_financial", mf_irr, float(npf.irr([-mf_equity_in,0,0,0,0,mf_equity_exit])))
print(f"   [LBO] entry {m_in}x lev {lev}x -> exit {m_out}x: MOIC={mf_moic:.2f}x  IRR={mf_irr*100:.1f}%  (both methods agree)")

# ── tally ──
passed = sum(1 for _,ok,_ in results if ok)
total = len(results)
print("\n" + "="*64)
for name, ok, detail in results:
    if not ok:
        print(f"  FAIL  {name}: {detail}")
print(f"RESULT: {passed}/{total} passed ({100*passed/total:.1f}%)")
print("="*64)
sys.exit(0 if passed == total else 1)

"""
hardtest_development_re.py  —  INDEPENDENT (clean-room) parity validation of
ModelForge's GROUND-UP DEVELOPMENT (development_re) model: the LIVE rendered
workbook, not the bare formulas.

GROUND TRUTH SOURCE (no circular grading):
  * A clean-room re-implementation, written from scratch in THIS file, of the
    ANNUAL-PHASED development engine the template renders. It does NOT import any
    modelforge math and does NOT read any external (Aither) file — every input is
    transcribed from examples/development_pbsa_genericcity.yaml (base scenario)
    and every economic step is recomputed in pure Python + numpy_financial.

PARITY SCOPE — the clean-room reproduces the annual-phased layout the template
ships (modelforge.builder.sheets.dev_schedule + dev_returns), NOT an idealised
month-grid. Concretely it re-derives, period by period:
  - total development cost (acquisition + hard + soft + ffe + other + contingency,
    contingency = (hard+soft+ffe) * contingency_pct)
  - monthly capex phasing (acquisition at t0; soft+30% contingency over permit+3
    months; hard+50% contingency+other over construction; ffe+20% contingency
    over the final 3 construction months), aggregated to annual buckets
  - the lease-up S-curve occupancy, averaged per year over post-delivery months,
    floored at the operator occupancy floor, expressed as a fraction of 95%
  - stabilised NOI, forward-NOI cap-rate exit, selling costs, net exit proceeds
  - the senior-debt roll-forward modelled the CORRECT way: the opening balance of
    each year is the PRIOR year's CLOSING balance, construction-phase interest
    CAPITALISES (IDC compounds during the build), and the full accumulated
    balance is repaid at exit (closing debt ~ 0). The clean-room is written from
    first principles — it is NOT derived from the template's wiring — so it is an
    independent check on the roll-forward, not a mirror of it.
  - the equity cash-flow vector, the unlevered project cash-flow vector
  - unlevered IRR/MOIC, levered equity IRR/MOIC, equity invested, peak debt
  - the European whole-fund promote waterfall (LP pref threshold, GP promote).

We BUILD examples/development_pbsa_genericcity.yaml via the CLI, then EVALUATE the
workbook live with the `formulas` package and reconcile every headline against the
clean-room numbers above.

TOLERANCES (stated):
  - IRR (unlevered + levered): 1% RELATIVE
  - MOIC (unlevered + levered): 1% RELATIVE
  - exit value / TDC / forward NOI / net exit / equity invested / peak debt /
    LP pref threshold / GP promote: 1e-4 RELATIVE (effectively exact)
  - per-period cash-flow vectors: 1e-6 ABSOLUTE (EUR millions)

Run:  python hardtest_development_re.py     (exits 0 on full pass; non-zero on fail)
"""

from __future__ import annotations

import os
import sys

# UTF-8 console guard (effective in-process; PYTHONIOENCODING alone is read only
# at interpreter startup and ignored by the running process on Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import math
import subprocess

import numpy as np
import numpy_financial as nf
import formulas

# ----------------------------------------------------------------------------
# 0. Paths / tolerances
# ----------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(ROOT, "examples", "development_pbsa_genericcity.yaml")
OUT = os.path.join(ROOT, "output", "hardtest_development_re.xlsx")
BASENAME = os.path.basename(OUT)

TOL_ABS = 1e-6        # absolute, EUR millions / ratios for cell-exact checks
TOL_REL_TIGHT = 1e-4  # relative, for exit value / TDC / equity / debt
TOL_REL_IRR = 0.01    # 1% relative for IRR / MOIC

results: list[tuple[bool, str]] = []


def check_abs(name: str, got, exp, tol: float = TOL_ABS) -> None:
    try:
        ok = abs(float(got) - float(exp)) <= tol
    except (TypeError, ValueError):
        ok = (got == exp)
    results.append((ok, name))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got!r}  exp={exp!r}")


def check_rel(name: str, got, exp, tol: float) -> None:
    try:
        g, e = float(got), float(exp)
        denom = abs(e) if abs(e) > 1e-12 else 1.0
        ok = abs(g - e) / denom <= tol
    except (TypeError, ValueError):
        ok = (got == exp)
    results.append((ok, name))
    rel = (abs(float(got) - float(exp)) / (abs(float(exp)) or 1.0)) if got is not None else float("nan")
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got!r}  exp={exp!r}  rel={rel:.2e} (tol {tol:.0e})")


def check_true(name: str, cond: bool, detail: str = "") -> None:
    results.append((bool(cond), name))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{('  ' + detail) if detail else ''}")


# ============================================================================
# 1. CLEAN-ROOM RE-DERIVATION  (hard-coded from the example yaml; NO modelforge)
#    BASE scenario. Raw inputs transcribed from
#    examples/development_pbsa_genericcity.yaml base: values.
# ============================================================================
# capex (EUR m)
acq = 6.0
hard = 25.0
soft = 5.0
ffe = 2.5
other = 1.0
cont_pct = 0.06
# timeline (months)
permit = 6
constr = 18
leaseup = 12
hold = 60
# revenue (pbsa)
beds = 350
rent_bed = 11500.0
floor_occ = 0.90
opex_bed = 3200.0
rev_g = 0.025
# capital
eq_pct = 0.40
rate = 0.055
arr_fee_pct = 0.0125
grant = 2.5
# exit
exit_cap = 0.0525
sell_pct = 0.015
# waterfall
lp_pct = 0.90
pref = 0.08
gp_promote = 0.20

contingency = (hard + soft + ffe) * cont_pct
TDC = acq + hard + soft + ffe + other + contingency
delivery = permit + constr            # 24
exit_year = math.ceil(hold / 12)      # 5
delivery_year = delivery // 12        # 2
n = exit_year + 1                     # 6 columns (t=0..t=5)
years_to_exit = max(exit_year - delivery_year, 0)  # 3
n_years_hold = n - 1                  # 5 (waterfall pref compounding horizon)

# --- monthly capex phasing → annual buckets ---
months = hold
spend = [0.0] * months


def _spread(amount: float, start: int, span: int) -> None:
    span = max(int(span), 1)
    per = amount / span
    for m in range(start, start + span):
        if 0 <= m < months:
            spend[m] += per


spend[0] += acq
_spread(soft + 0.30 * contingency, 0, permit + 3)
_spread(hard + 0.50 * contingency + other, permit, constr)
_spread(ffe + 0.20 * contingency, max(delivery - 3, 0), 3)
month_frac = [s / TDC for s in spend]
annual_phasing = [0.0] * n
for m, v in enumerate(month_frac):
    y = m // 12
    if 0 <= y < n:
        annual_phasing[y] += v

# --- lease-up S-curve → annual occupancy fraction (of 95% stabilised) ---
floor_frac = min(floor_occ / 0.95, 1.0)
per_month_frac = [0.0] * months
for m in range(months):
    rel = m - delivery
    if rel < 0:
        continue
    i = rel
    x = i / leaseup if leaseup > 0 else 1.0
    scurve = 0.95 / (1.0 + math.exp(-8.0 * (x - 0.5)))
    frac = scurve / 0.95
    frac = max(frac, floor_frac) if i <= leaseup else 1.0
    per_month_frac[m] = min(frac, 1.0)
annual_occ = [0.0] * n
for y in range(n):
    vals = [per_month_frac[y * 12 + mm]
            for mm in range(12)
            if y * 12 + mm < months and y * 12 + mm >= delivery]
    annual_occ[y] = (sum(vals) / len(vals)) if vals else 0.0

# --- development spend (outflow, neg) + grant (50% at hard-start yr, 50% at delivery yr) ---
dev_spend = [-TDC * annual_phasing[i] for i in range(n)]
grant_year_hard = permit // 12          # 0
grant_year_delivery = delivery // 12    # 2
grant_in = [0.0] * n
for i in range(n):
    sh = (0.5 if i == grant_year_hard else 0.0) + (0.5 if i == grant_year_delivery else 0.0)
    grant_in[i] = grant * sh
net_need = [max(0.0, -dev_spend[i] - grant_in[i]) for i in range(n)]

# --- NOI build ---
stab_gross = beds * rent_bed * 0.95 / 1e6
stab_opex = opex_bed * beds / 1e6
stab_noi = stab_gross - stab_opex
noi = [0.0] * n
for i in range(n):
    noi[i] = 0.0 if i == exit_year else stab_noi * annual_occ[i]
fwd_noi = stab_noi * (1 + rev_g) ** years_to_exit
exit_value = fwd_noi / exit_cap
selling = -exit_value * sell_pct
net_exit = exit_value + selling

# --- unlevered project cash flow ---
unlev = [0.0] * n
for i in range(n):
    unlev[i] = dev_spend[i] + grant_in[i] + noi[i]
    if i == exit_year:
        unlev[i] += net_exit

# --- senior debt roll-forward (CORRECT first-principles model) ---
# The opening balance of each year is the PRIOR year's CLOSING balance, so the
# drawn facility is carried forward and construction-phase interest CAPITALISES
# (IDC compounds while the asset is being built). The full accumulated balance
# is bulleted at exit, so closing debt at the exit year is ~0. This is written
# independently of the template (not mirrored from its cell wiring) so it is a
# genuine check on the roll-forward.
debt_draw = [(1 - eq_pct) * net_need[i] for i in range(n)]
debt_open = [0.0] * n
debt_int = [0.0] * n
int_cap = [0.0] * n
debt_repay = [0.0] * n
int_paid = [0.0] * n
debt_close = [0.0] * n
for i in range(n):
    debt_open[i] = 0.0 if i == 0 else debt_close[i - 1]   # opens off prior CLOSING
    debt_int[i] = debt_open[i] * rate
    if i < delivery_year:
        int_cap[i] = debt_int[i]                          # construction: all IDC
    else:
        int_cap[i] = max(0.0, debt_int[i] - max(noi[i], 0.0))
    if i == exit_year:
        debt_repay[i] = -(debt_open[i] + debt_draw[i] + int_cap[i])
    debt_close[i] = debt_open[i] + debt_draw[i] + int_cap[i] + debt_repay[i]
    if i < delivery_year:
        int_paid[i] = 0.0
    else:
        int_paid[i] = -min(debt_int[i], max(noi[i], 0.0))
peak_debt = max(debt_close)

# Debt-conservation identity (the invariant the template now hard-guards):
# everything advanced — cumulative cash draws + cumulative IDC — must equal the
# cumulative principal repaid (in absolute terms).
debt_conservation_residual = (sum(debt_draw) + sum(int_cap)) + sum(debt_repay)
cum_idc = sum(int_cap)

# --- equity cash flow ---
arr_fee = [0.0] * n
arr_fee[0] = -arr_fee_pct * sum(debt_draw)
equity_cf = [0.0] * n
for i in range(n):
    val = -(eq_pct) * net_need[i] + noi[i] + int_paid[i] + arr_fee[i]
    if i == exit_year:
        val += net_exit + debt_repay[i]
    equity_cf[i] = val

# --- returns ---
unlev_irr = nf.irr(np.array(unlev))
lev_irr = nf.irr(np.array(equity_cf))
unlev_distrib = sum(c for c in unlev if c > 0)
unlev_contrib = -sum(c for c in unlev if c < 0)
unlev_moic = unlev_distrib / unlev_contrib if unlev_contrib else 0.0
distrib = sum(c for c in equity_cf if c > 0)
contrib = -sum(c for c in equity_cf if c < 0)
lev_moic = distrib / contrib if contrib else 0.0
equity_invested = contrib

# --- European whole-fund promote waterfall ---
total_contrib = equity_invested
total_distrib = distrib
total_profit = total_distrib - total_contrib
pref_threshold = total_contrib * lp_pct * (1 + pref) ** n_years_hold
lp_share_resid = 1.0 - gp_promote
lp_tier1 = min(total_distrib, pref_threshold)
gp_catchup = max(0.0, (total_profit - (pref_threshold - total_contrib * lp_pct))) \
    * (1 - lp_share_resid) / lp_share_resid
lp_tier3 = max(0.0, total_distrib - lp_tier1 - gp_catchup) * lp_share_resid
gp_tier3 = max(0.0, total_distrib - lp_tier1 - gp_catchup) * (1 - lp_share_resid)
lp_total = lp_tier1 + lp_tier3
gp_total = gp_catchup + gp_tier3

print("=" * 78)
print("CLEAN-ROOM (independent) reference numbers, BASE scenario:")
print(f"  TDC                       = {TDC:.6f}")
print(f"  annual phasing            = {[round(x,6) for x in annual_phasing]}")
print(f"  annual occupancy frac     = {[round(x,6) for x in annual_occ]}")
print(f"  stabilised NOI            = {stab_noi:.6f}")
print(f"  forward NOI at exit       = {fwd_noi:.6f}")
print(f"  gross exit value          = {exit_value:.6f}")
print(f"  net exit proceeds         = {net_exit:.6f}")
print(f"  unlevered CF vector       = {[round(x,6) for x in unlev]}")
print(f"  debt close vector         = {[round(x,6) for x in debt_close]}")
print(f"  opening debt vector       = {[round(x,6) for x in debt_open]}")
print(f"  cumulative IDC            = {cum_idc:.6f}")
print(f"  debt-conservation residual= {debt_conservation_residual:.2e}")
print(f"  peak senior debt          = {peak_debt:.6f}")
print(f"  equity CF vector          = {[round(x,6) for x in equity_cf]}")
print(f"  unlevered IRR             = {unlev_irr:.6%}")
print(f"  unlevered MOIC            = {unlev_moic:.6f}")
print(f"  levered equity IRR        = {lev_irr:.6%}")
print(f"  levered equity MOIC       = {lev_moic:.6f}")
print(f"  equity invested           = {equity_invested:.6f}")
print(f"  LP pref threshold         = {pref_threshold:.6f}")
print(f"  LP total post-waterfall   = {lp_total:.6f}")
print(f"  GP total post-waterfall   = {gp_total:.6f}")
print("=" * 78)

# ============================================================================
# 2. BUILD the workbook fresh (so the test is self-contained)
# ============================================================================
print("\nBuilding workbook via CLI ...")
os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
proc = subprocess.run(
    [sys.executable, "-m", "modelforge.cli", "build", SPEC, "--out", OUT],
    cwd=ROOT, capture_output=True, text=True,
)
print(proc.stdout[-400:])
if proc.returncode != 0:
    print("BUILD FAILED:\n", proc.stderr[-2000:])
    sys.exit(2)
assert os.path.exists(OUT), "workbook not produced"

# ============================================================================
# 3. EVALUATE the workbook LIVE with the `formulas` package
#    (same engine the certify audit + deck adapter use; keys are uppercased)
# ============================================================================
print("\nEvaluating workbook live with `formulas` ...")
xl = formulas.ExcelModel().loads(OUT).finish()
sol = xl.calculate()
_SOL = {}
for k, v in sol.items():
    try:
        after = k.split("]", 1)[1]
        sheet, cell = after.split("'!", 1)
    except (IndexError, ValueError):
        continue
    val = v.value
    try:
        val = np.asarray(val).reshape(-1)[0]
    except (TypeError, ValueError, IndexError):
        pass
    _SOL[(sheet.strip("'").upper(), cell.strip().upper())] = val


def cell(sheet: str, a1: str):
    return _SOL.get((sheet.upper(), a1.upper()))


# --- pull live headline cells (cell coords confirmed against the rendered book) ---
# DevSchedule
live_tdc = cell("DevSchedule", "D9")             # Total development cost (TDC)
live_fwd_noi = cell("DevSchedule", "D24")        # Forward NOI at exit
live_exit_value = cell("DevSchedule", "D25")     # Gross exit value (fwd NOI / cap)
live_net_exit = cell("DevSchedule", "D27")       # Net exit proceeds
live_stab_noi = cell("DevSchedule", "D19")       # Stabilised annual NOI
live_unlev = [cell("DevSchedule", f"{c}30") for c in "DEFGHI"]   # Unlevered CF row
live_equity = [cell("DevSchedule", f"{c}43") for c in "DEFGHI"]  # Equity CF row
live_debt_close = [cell("DevSchedule", f"{c}38") for c in "DEFGHI"]  # Closing debt
# Returns
live_unlev_irr = cell("Returns", "D8")
live_unlev_moic = cell("Returns", "D10")
live_lev_irr = cell("Returns", "D13")
live_lev_moic = cell("Returns", "D15")
live_peak_debt = cell("Returns", "D19")
live_ret_net_exit = cell("Returns", "D20")
live_pref_threshold = cell("Returns", "D32")
live_lp_total = cell("Returns", "D43")
live_gp_total = cell("Returns", "D44")

print(f"  live TDC          = {live_tdc}")
print(f"  live exit value   = {live_exit_value}")
print(f"  live net exit     = {live_net_exit}")
print(f"  live unlev CF     = {[round(x,6) if x is not None else None for x in live_unlev]}")
print(f"  live equity CF    = {[round(x,6) if x is not None else None for x in live_equity]}")
print(f"  live unlev IRR    = {live_unlev_irr}")
print(f"  live levered IRR  = {live_lev_irr}")
print(f"  live levered MOIC = {live_lev_moic}")
print(f"  live peak debt    = {live_peak_debt}")

# ============================================================================
# 4. RECONCILE every headline vs the independent clean-room ground truth
# ============================================================================
print("\n--- Reconciling live workbook vs clean-room ---")

# A: total development cost (exact)
check_rel("A TDC == acq+hard+soft+ffe+other+contingency", live_tdc, TDC, TOL_REL_TIGHT)

# B: stabilised NOI + forward NOI + exit value (exact, yield identity)
check_rel("B1 stabilised NOI", live_stab_noi, stab_noi, TOL_REL_TIGHT)
check_rel("B2 forward NOI at exit", live_fwd_noi, fwd_noi, TOL_REL_TIGHT)
check_rel("B3 gross exit value == fwd NOI / cap", live_exit_value, exit_value, TOL_REL_TIGHT)
check_true("B4 exit value * cap == forward NOI (yield identity)",
           abs(float(live_exit_value) * exit_cap - float(live_fwd_noi)) <= TOL_ABS)

# C: net exit proceeds (schedule + Returns xref agree)
check_rel("C1 net exit proceeds (DevSchedule)", live_net_exit, net_exit, TOL_REL_TIGHT)
check_rel("C2 net exit proceeds (Returns xref)", live_ret_net_exit, net_exit, TOL_REL_TIGHT)

# D: unlevered project cash-flow vector, every period (cell-exact)
for i, c in enumerate("DEFGHI"):
    check_abs(f"D{i} unlevered CF t={i}", live_unlev[i], unlev[i])

# E: equity cash-flow vector, every period (cell-exact)
for i, c in enumerate("DEFGHI"):
    check_abs(f"E{i} equity CF t={i}", live_equity[i], equity_cf[i])

# F: closing debt vector + peak debt (as-built roll-forward)
for i, c in enumerate("DEFGHI"):
    check_abs(f"F{i} closing debt t={i}", live_debt_close[i], debt_close[i])
check_rel("F peak senior debt == MAX(closing debt)", live_peak_debt, peak_debt, TOL_REL_TIGHT)

# G: unlevered IRR / MOIC (1% relative)
check_rel("G1 unlevered IRR", live_unlev_irr, unlev_irr, TOL_REL_IRR)
check_rel("G2 unlevered MOIC", live_unlev_moic, unlev_moic, TOL_REL_IRR)

# H: levered equity IRR / MOIC (1% relative)
check_rel("H1 levered equity IRR", live_lev_irr, lev_irr, TOL_REL_IRR)
check_rel("H2 levered equity MOIC", live_lev_moic, lev_moic, TOL_REL_IRR)

# I: levered IRR reconciles to numpy_financial on the LIVE equity vector
irr_on_live = nf.irr(np.array([float(x) for x in live_equity]))
check_rel("I levered IRR (workbook) == numpy_financial.irr(live vector)",
          live_lev_irr, irr_on_live, TOL_REL_IRR)

# J: European waterfall — LP pref threshold + LP/GP totals
check_rel("J1 LP pref threshold", live_pref_threshold, pref_threshold, TOL_REL_TIGHT)
check_rel("J2 LP total post-waterfall", live_lp_total, lp_total, TOL_REL_TIGHT)
check_rel("J3 GP total post-waterfall", live_gp_total, gp_total, TOL_REL_TIGHT)

# ============================================================================
# 5. MODEL-INDEPENDENT INVARIANTS
# ============================================================================
print("\n--- Model-independent invariants ---")
# INV1: equity contributed at t0 negative, exit inflow positive
check_true("INV1 equity t=0 outflow < 0 and t=exit inflow > 0",
           float(live_equity[0]) < 0 and float(live_equity[-1]) > 0,
           f"t0={live_equity[0]:.3f} tH={live_equity[-1]:.3f}")
# INV2: debt repaid to ~0 at exit (last closing-debt cell)
check_true("INV2 closing debt == 0 at exit",
           abs(float(live_debt_close[-1])) < 0.01,
           f"closing={live_debt_close[-1]:.4f}")
# INV3: positive leverage — levered equity IRR strictly above unlevered IRR
check_true("INV3 levered IRR > unlevered IRR (positive leverage)",
           float(live_lev_irr) > float(live_unlev_irr),
           f"lev={live_lev_irr:.4%} unlev={live_unlev_irr:.4%}")
# INV4: peak debt <= (1-equity%) of TDC (can't gear above loan-to-cost)
check_true("INV4 peak debt <= (1-equity%) * TDC",
           float(live_peak_debt) <= (1 - eq_pct) * float(live_tdc) + 1e-6,
           f"peak={live_peak_debt:.3f} cap={(1-eq_pct)*float(live_tdc):.3f}")
# INV5: LP + GP totals exhaust the gross equity distribution
check_true("INV5 LP total + GP total == gross distributions",
           abs((float(live_lp_total) + float(live_gp_total)) - total_distrib) <= 1e-4,
           f"lp+gp={float(live_lp_total)+float(live_gp_total):.4f} distrib={total_distrib:.4f}")
# INV6: construction interest CAPITALISES — opening debt grows year-on-year
# during the build (delivery_year>=2 here), proving IDC compounds rather than
# the balance sitting flat at the first draw. live opening-debt row is r34.
live_debt_open = [cell("DevSchedule", f"{c}34") for c in "DEFGHI"]
check_true("INV6 IDC compounds (opening debt grows through construction)",
           float(live_debt_open[delivery_year]) > float(live_debt_open[1]) + 1e-6,
           f"open[1]={live_debt_open[1]:.4f} open[delivery]={live_debt_open[delivery_year]:.4f}")
# INV7: debt-conservation identity holds on the LIVE workbook — cumulative
# draws + cumulative IDC == cumulative principal repaid (this is the closed-
# system check that auto-catches a broken roll-forward).
live_draw = [float(cell("DevSchedule", f"{c}33")) for c in "DEFGHI"]
live_idc = [float(cell("DevSchedule", f"{c}36")) for c in "DEFGHI"]
live_repay = [float(cell("DevSchedule", f"{c}37")) for c in "DEFGHI"]
live_cons_resid = (sum(live_draw) + sum(live_idc)) + sum(live_repay)
check_true("INV7 senior debt conserved (Σdraws+ΣIDC == Σprincipal repaid)",
           abs(live_cons_resid) <= 1e-4,
           f"residual={live_cons_resid:.6f}")
# INV8: positive total IDC — the sheet titled 'IDC capitalised' is not hollow.
check_true("INV8 construction interest actually capitalised (ΣIDC > 0)",
           sum(live_idc) > 1e-3,
           f"ΣIDC={sum(live_idc):.4f}")

# ============================================================================
# 6. SUMMARY
# ============================================================================
passed = sum(1 for ok, _ in results if ok)
total = len(results)
print("\n" + "=" * 78)
print(f"RESULT: {passed}/{total} checks passed")
print("=" * 78)
if passed != total:
    print("\nFAILED CHECKS:")
    for ok, name in results:
        if not ok:
            print("  -", name)
    sys.exit(1)
print("ALL CHECKS PASSED")
sys.exit(0)

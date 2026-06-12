"""
hardtest_real_estate.py  —  INDEPENDENT validation of ModelForge's PBSA
(real_estate) model: the LIVE rendered workbook, not the bare formulas.

GROUND TRUTH SOURCES (no circular grading):
  * Clean-room re-derivation written from scratch in THIS file (does NOT import
    modelforge) of the full NOI build, exit value, development cost, profit,
    LTC/LTV, and the equity cashflow vector — straight from the raw spec inputs.
  * numpy_financial.irr / a clean MoIC from the equity cashflow vector.
  * Model-independent invariants (NOI identity, exit==NOI/cap, profit==value-cost,
    loan>=0, LTV/LTC within stated maxima, profit-on-cost==profit/cost).

We BUILD examples/real_estate_pbsa.yaml via the CLI, then EVALUATE the workbook
live with the `formulas` package and reconcile every economic check against the
independent numbers above.

Run:  python hardtest_real_estate.py     (exits 0 on full pass; non-zero on fail)
"""

from __future__ import annotations

import os
import sys
# UTF-8 console guard (effective in-process; PYTHONIOENCODING alone is read
# only at interpreter startup and ignored by the running process on Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import subprocess

import numpy as np
import numpy_financial as nf
import formulas

# ----------------------------------------------------------------------------
# 0. Paths
# ----------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(ROOT, "examples", "real_estate_pbsa.yaml")
OUT = os.path.join(ROOT, "output", "hardtest_real_estate.xlsx")
BASENAME = os.path.basename(OUT)

TOL = 1e-6  # absolute tolerance in EUR millions / ratios (cells are exact)

results: list[tuple[bool, str]] = []


def check(name: str, got, exp, tol: float = TOL) -> None:
    try:
        ok = abs(float(got) - float(exp)) <= tol
    except (TypeError, ValueError):
        ok = (got == exp)
    results.append((ok, name))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: got={got!r}  exp={exp!r}")


def check_true(name: str, cond: bool, detail: str = "") -> None:
    results.append((bool(cond), name))
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}{('  ' + detail) if detail else ''}")


# ----------------------------------------------------------------------------
# 1. CLEAN-ROOM RE-DERIVATION  (hard-coded from the spec yaml; NO modelforge)
#    BASE scenario (scenario_index=2 -> CHOOSE picks the BASE column).
#    All raw inputs transcribed from examples/real_estate_pbsa.yaml base: values.
# ----------------------------------------------------------------------------
HOLD = 7                      # horizon.hold_years
acq_price = 42.0             # acquisition_price_eur_m
area = 7500.0               # lettable_area_sqm
rent_psm = 420.0            # rent_eur_sqm_year1
vacancy = 0.04             # vacancy_pct (BASE)
indexation = 0.035          # rent_indexation_pct
opex_pct = 0.28            # opex_pct_gross_rent
capex_pct = 0.04           # capex_pct_gross_rent
ltv = 0.55                 # ltv_pct (BASE)
rate = 0.0575              # senior_interest_rate (BASE)
arr_fee_pct = 0.015         # arrangement_fee_pct
exit_cap = 0.05            # exit_cap_rate (BASE)
txn_pct = 0.025            # transaction_costs_pct
lp_pct = 0.95              # lp_capital_commitment_pct

# --- NOI build, year by year (t=1..HOLD), in EUR millions ---
gross = [0.0] * (HOLD + 1)            # index = t
vac_loss = [0.0] * (HOLD + 1)
eff_rent = [0.0] * (HOLD + 1)
opex = [0.0] * (HOLD + 1)
noi = [0.0] * (HOLD + 1)
capex = [0.0] * (HOLD + 1)
cfads = [0.0] * (HOLD + 1)            # CF after capex (pre-debt, pre-tax)

for t in range(1, HOLD + 1):
    if t == 1:
        gross[t] = area * rent_psm / 1_000_000.0
    else:
        gross[t] = gross[t - 1] * (1 + indexation)
    vac_loss[t] = -gross[t] * vacancy
    eff_rent[t] = gross[t] + vac_loss[t]
    opex[t] = -gross[t] * opex_pct
    noi[t] = eff_rent[t] + opex[t]
    capex[t] = -gross[t] * capex_pct
    cfads[t] = noi[t] + capex[t]

# --- Exit (sale at end of hold, off exit-year NOI) ---
exit_noi = noi[HOLD]
exit_value = exit_noi / exit_cap
txn_costs = -exit_value * txn_pct
net_exit = exit_value + txn_costs

# --- Senior debt (bullet, interest on opening balance) ---
loan = acq_price * ltv
interest_annual = -loan * rate
principal_repay = -loan                          # at exit only

# --- Project (unlevered) cashflow vector, t=0..HOLD ---
proj_cf = [0.0] * (HOLD + 1)
proj_cf[0] = -acq_price + cfads[0]               # acq is negative; cfads[0]=0
for t in range(1, HOLD):
    proj_cf[t] = cfads[t]
proj_cf[HOLD] = cfads[HOLD] + net_exit

# --- Equity cashflow vector, t=0..HOLD ---
equity_cf = [0.0] * (HOLD + 1)
equity_cf[0] = proj_cf[0] + loan                 # debt draw at close
for t in range(1, HOLD + 1):
    ic = interest_annual
    pr = principal_repay if t == HOLD else 0.0
    equity_cf[t] = proj_cf[t] + ic + pr

# --- Equity IRR & MoIC via numpy_financial / clean MoIC ---
equity_irr_np = nf.irr(np.array(equity_cf))
distrib = sum(c for c in equity_cf if c > 0)
contrib = -sum(c for c in equity_cf if c < 0)
moic_np = distrib / contrib if contrib else 0.0

# --- Development cost / profit / margins (clean-room) ---
# This is an ACQUISITION (not ground-up): there is no land/construction/fees
# split. Total "development/acquisition cost on equity basis":
#   equity invested = abs(equity_cf[0])
# Total project cost incl. finance costs = acquisition + arrangement fee +
# cumulative cash interest over the hold (the spec has no separate land/build).
arr_fee = loan * arr_fee_pct
cum_interest = -interest_annual * HOLD            # positive cost
total_cost_incl_finance = acq_price + arr_fee + cum_interest
profit_on_value = exit_value + txn_costs - total_cost_incl_finance

# Profit-on-cost (development margin) clean-room, gross-value basis (no debt):
profit_gross = net_exit - acq_price               # net sale - acquisition
poc_gross = profit_gross / acq_price

print("=" * 78)
print("CLEAN-ROOM (independent) reference numbers, BASE scenario:")
print(f"  gross rent t1..t7         = {[round(g,6) for g in gross[1:]]}")
print(f"  NOI t1..t7                = {[round(x,6) for x in noi[1:]]}")
print(f"  exit-year NOI             = {exit_noi:.6f}")
print(f"  exit value (NOI/cap)      = {exit_value:.6f}")
print(f"  net sale proceeds         = {net_exit:.6f}")
print(f"  loan (acq*ltv)            = {loan:.6f}")
print(f"  equity_cf vector          = {[round(x,6) for x in equity_cf]}")
print(f"  equity IRR (numpy_fin)    = {equity_irr_np:.6%}")
print(f"  equity MoIC               = {moic_np:.6f}")
print(f"  profit (net exit - acq)   = {profit_gross:.6f}")
print(f"  profit-on-cost (gross)    = {poc_gross:.6%}")
print("=" * 78)

# ----------------------------------------------------------------------------
# 2. BUILD the workbook fresh (so the test is self-contained)
# ----------------------------------------------------------------------------
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

# ----------------------------------------------------------------------------
# 3. EVALUATE the workbook LIVE with the `formulas` package
# ----------------------------------------------------------------------------
print("\nEvaluating workbook live with `formulas` ...")
xl = formulas.ExcelModel().loads(OUT).finish()
sol = xl.calculate()

# This `formulas` build keeps original case for BOTH the filename and the sheet
# name in the cell key: '[hardtest_real_estate.xlsx]DCF'!A1 . Build the key with
# the exact (openpyxl) sheet name; fall back to an uppercased variant if needed.
_SOL_KEYS = set(sol.keys())


def cell(sheet: str, a1: str):
    candidates = [
        "'[" + BASENAME + "]" + sheet + "'!" + a1,
        "'[" + BASENAME.upper() + "]" + sheet.upper() + "'!" + a1,
        "'[" + BASENAME + "]" + sheet.upper() + "'!" + a1,
    ]
    key = next((k for k in candidates if k in _SOL_KEYS), candidates[0])
    v = sol[key].value
    try:
        # often a 1x1 numpy array
        return float(np.asarray(v).reshape(-1)[0])
    except (TypeError, ValueError):
        arr = np.asarray(v).reshape(-1)
        return arr[0]


# --- pull live cell values ---
# DCF sheet
live_gross = [cell("DCF", f"{c}11") for c in "EFGHIJK"]      # t=1..7
live_noi = [cell("DCF", f"{c}15") for c in "EFGHIJK"]
live_exit_noi = cell("DCF", "D20")
live_exit_value = cell("DCF", "D21")
live_txn = cell("DCF", "D22")
live_net_exit = cell("DCF", "D23")
live_acq = cell("DCF", "D8")

# Financing sheet
live_loan = cell("Financing", "D8")
live_interest = cell("Financing", "E9")
live_principal = cell("Financing", "K10")
live_equity_cf = [cell("Financing", f"{c}13") for c in "DEFGHIJK"]
live_eq_irr = cell("Financing", "D16")
live_eq_moic = cell("Financing", "D17")

print(f"  live NOI t1..t7   = {[round(x,6) for x in live_noi]}")
print(f"  live exit value   = {live_exit_value:.6f}")
print(f"  live equity_cf    = {[round(x,6) for x in live_equity_cf]}")
print(f"  live equity IRR   = {live_eq_irr:.6%}")
print(f"  live equity MoIC  = {live_eq_moic:.6f}")

# ----------------------------------------------------------------------------
# 4. RECONCILE every economic check vs the independent ground truth
# ----------------------------------------------------------------------------
print("\n--- Reconciling live workbook vs clean-room / numpy_financial ---")

# CHECK A: Acquisition price sign on DCF
check("A1 DCF acquisition price (D8) == -acq", live_acq, -acq_price)

# CHECK B: Gross potential rent each year matches clean-room
for i, c in enumerate("EFGHIJK"):
    check(f"B{i+1} DCF gross rent t={i+1}", live_gross[i], gross[i + 1])

# CHECK C: Stabilised/each-year NOI == gross*(1-vac) - opex  (clean-room identity)
for i, c in enumerate("EFGHIJK"):
    indep_noi = gross[i + 1] * (1 - vacancy) - gross[i + 1] * opex_pct
    check(f"C{i+1} DCF NOI t={i+1} == gross*(1-vac)-opex", live_noi[i], indep_noi)

# CHECK D: exit-year NOI == NOI[hold]
check("D exit-year NOI (DCF D20) == NOI[t=7]", live_exit_noi, noi[HOLD])

# CHECK E: exit value == stabilised(exit) NOI / exit yield
check("E exit value == exit NOI / exit cap", live_exit_value, exit_noi / exit_cap)

# CHECK F: transaction costs and net sale proceeds
check("F1 transaction costs == -value*txn%", live_txn, -exit_value * txn_pct)
check("F2 net sale proceeds == value + txn", live_net_exit, net_exit)

# CHECK G: loan == acq*ltv;  LTC and LTV within stated maxima
check("G1 loan amount == acq * ltv", live_loan, loan)
ltc = live_loan / acq_price            # acquisition is the only 'cost' line
ltv_on_value_now = live_loan / acq_price  # value at entry == acq price
ltv_on_exit_value = live_loan / exit_value
check("G2 LTC == loan / acquisition cost", ltc, ltv)
check_true("G3 LTV at close <= max LTV (0.60)", ltv_on_value_now <= 0.60 + 1e-9,
           f"LTV={ltv_on_value_now:.4f}")
check_true("G4 LTV vs exit value <= 0.60", ltv_on_exit_value <= 0.60 + 1e-9,
           f"LTV_exit={ltv_on_exit_value:.4f}")

# CHECK H: senior interest == -loan*rate (bullet), principal repay == -loan at exit
check("H1 cash interest (E9) == -loan*rate", live_interest, -loan * rate)
check("H2 principal repayment (K10) == -loan", live_principal, -loan)

# CHECK I: equity cashflow vector matches clean-room, every period
for i, c in enumerate("DEFGHIJK"):
    check(f"I{i} equity CF t={i}", live_equity_cf[i], equity_cf[i])

# CHECK J: equity IRR reconciles to numpy_financial on the LIVE equity vector
irr_on_live = nf.irr(np.array(live_equity_cf))
check("J1 equity IRR (workbook) == numpy_financial.irr(live vector)",
      live_eq_irr, irr_on_live, tol=1e-6)
check("J2 equity IRR (workbook) == numpy_financial.irr(clean-room vector)",
      live_eq_irr, equity_irr_np, tol=1e-6)

# CHECK K: equity MoIC reconciles to clean MoIC on the LIVE vector
live_distrib = sum(c for c in live_equity_cf if c > 0)
live_contrib = -sum(c for c in live_equity_cf if c < 0)
moic_on_live = live_distrib / live_contrib
check("K equity MoIC (workbook) == distrib/contrib (clean)",
      live_eq_moic, moic_on_live)

# ----------------------------------------------------------------------------
# 5. MODEL-INDEPENDENT INVARIANTS (must hold every period / in aggregate)
# ----------------------------------------------------------------------------
print("\n--- Model-independent invariants ---")

# INV1: debt never negative
check_true("INV1 loan amount >= 0", live_loan >= 0, f"loan={live_loan:.4f}")

# INV2: profit == exit value - total cost  (value-basis identity, clean-room)
# Using gross profit = net exit - acquisition (no debt) as the model's economic
# profit; reconcile against the model's own derived net_exit & acq.
model_profit_gross = live_net_exit - acq_price
check("INV2 profit == net sale proceeds - acquisition", model_profit_gross,
      net_exit - acq_price)

# INV3: profit-on-cost / development margin == profit / total cost (clean-room)
model_poc = model_profit_gross / acq_price
check("INV3 profit-on-cost == profit / acquisition cost", model_poc, poc_gross)

# INV4: NOI identity holds for EVERY year (already C, assert aggregate too)
all_noi_ok = all(
    abs(live_noi[i] - (gross[i + 1] * (1 - vacancy) - gross[i + 1] * opex_pct)) <= TOL
    for i in range(HOLD)
)
check_true("INV4 NOI = gross*(1-vac)-opex holds every period", all_noi_ok)

# INV5: equity contribution at t0 is negative (capital out), exit inflow positive
check_true("INV5 equity t=0 outflow < 0 and t=hold inflow > 0",
           live_equity_cf[0] < 0 and live_equity_cf[HOLD] > 0,
           f"t0={live_equity_cf[0]:.3f} tH={live_equity_cf[HOLD]:.3f}")

# INV6: exit value == NOI / cap exactly (yield identity)
check_true("INV6 exit value * cap == exit NOI",
           abs(live_exit_value * exit_cap - live_exit_noi) <= TOL)

# ----------------------------------------------------------------------------
# 6. SCOPE NOTE — development-cost split (land+construction+fees)
#    The deal-type checklist mentions "total dev cost == land + construction +
#    fees + finance costs". This spec is an ACQUISITION of a stabilised asset:
#    no land/construction/fee lines exist. We verify the finance-cost pieces
#    the model DOES carry (arrangement fee + interest) are internally consistent.
# ----------------------------------------------------------------------------
print("\n--- Finance-cost components (acquisition deal; no ground-up split) ---")
live_arr_fee_pct = cell("Financing", "D51")
check("S1 arrangement fee % surfaced == spec 1.5%", live_arr_fee_pct, arr_fee_pct)
# cumulative interest over hold from the model's interest line
live_int_each = [cell("Financing", f"{c}9") for c in "EFGHIJK"]
live_cum_int = -sum(live_int_each)
check("S2 cumulative cash interest == loan*rate*hold", live_cum_int,
      loan * rate * HOLD)

# ----------------------------------------------------------------------------
# 7. SUMMARY
# ----------------------------------------------------------------------------
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

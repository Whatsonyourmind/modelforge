"""hardtest_comps_fairness.py — INDEPENDENT validation of ModelForge's fairness /
trading-comps football-field deliverable (examples/fairness_amplifon.yaml).

NO CIRCULAR GRADING. Every EXPECTED value below is derived clean-room in pure
Python from the raw spec inputs (peer multiples, subject EBITDA/revenue, net
debt, shares, price, 52W range). This file does NOT import modelforge for any
EXPECTED-side computation. The ACTUAL side is read from the LIVE rendered Excel
workbook, evaluated cell-by-cell with the `formulas` package.

Layer tested: live-excel (the rendered .xlsx, formulas recalculated).

Ground truth used:
  (b) clean-room re-derivation written from scratch in this file
  (c) model-independent invariants (median/mean ordering, EV<->equity bridge,
      football-field min<=median<=max ordering, round-trip of implied multiples)
"""

import os
import statistics
import sys

import numpy as np
import formulas

REPO = os.path.dirname(os.path.abspath(__file__))
WB_PATH = os.path.join(REPO, "output", "hardtest_comps_fairness.xlsx")
BASE = os.path.basename(WB_PATH)

TOL = 1e-6  # absolute tolerance for €m / x values

# ────────────────────────────────────────────────────────────────────────────
# CLEAN-ROOM GROUND TRUTH — typed by hand from examples/fairness_amplifon.yaml.
# These are the RAW spec inputs, NOT anything ModelForge computed.
# ────────────────────────────────────────────────────────────────────────────
TRADING_PEERS = [
    # (name, ev_ebitda_x, ev_revenue_x)
    ("Sonova Holding", 14.5, 3.1),
    ("Demant A/S",     13.0, 2.7),
    ("GN Store Nord",  11.5, 2.1),
    ("Cochlear",       25.0, 7.2),
]
TXN_PEERS = [
    ("Sonova / Sennheiser Consumer", 16.0, 3.5),
    ("WS Audiology / Widex-Sivantos", 14.0, 3.3),
    ("EQT / HTL-Strefa (audio adjacency)", 12.5, 2.8),
]

# Subject (Base scenario active values — scenario_index defaults to 2 = Base)
SUBJ_EBITDA = 530.0
SUBJ_REVENUE = 2300.0
NET_DEBT = 950.0
SHARES = 226.0
PRICE = 25.0
PRICE_52W_LOW = 22.0
PRICE_52W_HIGH = 29.0
SPREAD = 1.0  # ±1x

# Static DCF / LBO EV ranges (these come from the spec; they are inputs, not
# anything ModelForge derived — so using them as EXPECTED is non-circular).
DCF_LOW, DCF_HIGH = 7200.0, 9100.0
LBO_LOW, LBO_HIGH = 6200.0, 7400.0

# ── clean-room derived peer statistics
trade_ebitda = [p[1] for p in TRADING_PEERS]
trade_rev = [p[2] for p in TRADING_PEERS]
txn_ebitda = [p[1] for p in TXN_PEERS]
txn_rev = [p[2] for p in TXN_PEERS]

MED_TRADE_EBITDA = statistics.median(trade_ebitda)   # 13.75
MEAN_TRADE_EBITDA = statistics.mean(trade_ebitda)     # 16.0
MED_TRADE_REV = statistics.median(trade_rev)          # 2.9
MEAN_TRADE_REV = statistics.mean(trade_rev)
MED_TXN_EBITDA = statistics.median(txn_ebitda)        # 14.0
MEAN_TXN_EBITDA = statistics.mean(txn_ebitda)
MED_TXN_REV = statistics.median(txn_rev)
MEAN_TXN_REV = statistics.mean(txn_rev)

# ────────────────────────────────────────────────────────────────────────────
print("Loading + recalculating workbook with `formulas` ...")
if not os.path.exists(WB_PATH):
    print(f"FATAL: workbook not found at {WB_PATH}")
    sys.exit(2)

_xl = formulas.ExcelModel().loads(WB_PATH).finish()
_sol = _xl.calculate()


def cell(sheet_upper, a1):
    """Read one cell from the live-recalculated workbook -> python float/scalar."""
    key = "'[" + BASE + "]" + sheet_upper + "'!" + a1
    v = _sol[key].value
    if isinstance(v, np.ndarray):
        v = v.reshape(-1)[0]
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


# ── results accumulator
_checks = []


def check(name, got, expected, tol=TOL):
    ok = (isinstance(got, (int, float)) and isinstance(expected, (int, float))
          and abs(float(got) - float(expected)) <= tol)
    _checks.append((name, ok, got, expected))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}: got={got!r} expected={expected!r}")
    return ok


def check_true(name, cond, detail=""):
    _checks.append((name, bool(cond), detail, "True"))
    flag = "PASS" if cond else "FAIL"
    print(f"[{flag}] {name}  {detail}")
    return bool(cond)


print("\n=== A. PER-PEER MULTIPLES round-trip (workbook inputs == spec inputs) ===")
# TradingComps rows 6..9, col B = EV/EBITDA, col C = EV/Revenue
for i, (name, ee, er) in enumerate(TRADING_PEERS):
    r = 6 + i
    check(f"TradingComps B{r} ({name} EV/EBITDA)", cell("TRADINGCOMPS", f"B{r}"), ee)
    check(f"TradingComps C{r} ({name} EV/Revenue)", cell("TRADINGCOMPS", f"C{r}"), er)
for i, (name, ee, er) in enumerate(TXN_PEERS):
    r = 6 + i
    check(f"TransactionComps B{r} ({name} EV/EBITDA)", cell("TRANSACTIONCOMPS", f"B{r}"), ee)
    check(f"TransactionComps C{r} ({name} EV/Revenue)", cell("TRANSACTIONCOMPS", f"C{r}"), er)

print("\n=== B. PEER-SET MEDIAN & MEAN (EV/EBITDA and EV/Revenue) ===")
check("Trading median EV/EBITDA", cell("TRADINGCOMPS", "B11"), MED_TRADE_EBITDA)
check("Trading mean EV/EBITDA",   cell("TRADINGCOMPS", "B12"), MEAN_TRADE_EBITDA)
check("Trading median EV/Revenue", cell("TRADINGCOMPS", "C11"), MED_TRADE_REV)
check("Trading mean EV/Revenue",   cell("TRADINGCOMPS", "C12"), MEAN_TRADE_REV)
check("Txn median EV/EBITDA", cell("TRANSACTIONCOMPS", "B10"), MED_TXN_EBITDA)
check("Txn mean EV/EBITDA",   cell("TRANSACTIONCOMPS", "B11"), MEAN_TXN_EBITDA)
check("Txn median EV/Revenue", cell("TRANSACTIONCOMPS", "C10"), MED_TXN_REV)
check("Txn mean EV/Revenue",   cell("TRANSACTIONCOMPS", "C11"), MEAN_TXN_REV)

print("\n=== C. IMPLIED EV == median peer EV/EBITDA x subject EBITDA (±1x band) ===")
# FootballField row 6 = Trading comps method; row 7 = Transaction comps method.
exp_trade_ev_low = (MED_TRADE_EBITDA - SPREAD) * SUBJ_EBITDA   # 12.75*530 = 6757.5
exp_trade_ev_high = (MED_TRADE_EBITDA + SPREAD) * SUBJ_EBITDA  # 14.75*530 = 7817.5
exp_trade_ev_mid = (exp_trade_ev_low + exp_trade_ev_high) / 2  # == MED*EBITDA = 7287.5
check("FF B6 trading EV low  = (med-1)*EBITDA", cell("FOOTBALLFIELD", "B6"), exp_trade_ev_low)
check("FF C6 trading EV high = (med+1)*EBITDA", cell("FOOTBALLFIELD", "C6"), exp_trade_ev_high)
check("FF D6 trading EV mid  = med*EBITDA",     cell("FOOTBALLFIELD", "D6"), exp_trade_ev_mid)
# central-multiple identity: mid EV / EBITDA must equal the peer median exactly
check("Implied central EV/EBITDA backs out to peer median",
      cell("FOOTBALLFIELD", "D6") / SUBJ_EBITDA, MED_TRADE_EBITDA)

exp_txn_ev_low = (MED_TXN_EBITDA - SPREAD) * SUBJ_EBITDA       # 13*530 = 6890
exp_txn_ev_high = (MED_TXN_EBITDA + SPREAD) * SUBJ_EBITDA      # 15*530 = 7950
check("FF B7 txn EV low  = (med-1)*EBITDA", cell("FOOTBALLFIELD", "B7"), exp_txn_ev_low)
check("FF C7 txn EV high = (med+1)*EBITDA", cell("FOOTBALLFIELD", "C7"), exp_txn_ev_high)

print("\n=== C2. EV/Revenue CROSS-CHECK (independent multiple, same subject EV) ===")
# The model uses EV/EBITDA to set the trading band. A fairness EV/Revenue
# cross-check: what EV would the SAME peer median EV/Revenue imply on subject
# revenue, and is the model's central EV/EBITDA-implied EV in a sane relation?
ev_rev_implied = MED_TRADE_REV * SUBJ_REVENUE   # 2.9 * 2300 = 6670
print(f"   (info) EV/Revenue-implied EV @ peer median {MED_TRADE_REV}x*{SUBJ_REVENUE} = {ev_rev_implied}")
# Cross-check invariant: implied EV/Revenue of the model's central trading EV
# should equal model_central_EV / subject_revenue, and that ratio must lie
# between the min and max peer EV/Revenue (peers bracket the subject).
central_ev = cell("FOOTBALLFIELD", "D6")
implied_subject_ev_rev = central_ev / SUBJ_REVENUE
check_true("Subject implied EV/Revenue within peer EV/Rev [min,max]",
           min(trade_rev) <= implied_subject_ev_rev <= max(trade_rev),
           f"implied EV/Rev={implied_subject_ev_rev:.3f}  peer range [{min(trade_rev)},{max(trade_rev)}]")

print("\n=== D. EV<->EQUITY BRIDGE: equity == EV - net debt; implied per share ===")
# For EVERY method row 6..10, the equity bridge and per-share must hold.
METHOD_ROWS = {
    6: "Trading comps", 7: "Transaction comps", 8: "DCF", 9: "LBO", 10: "52W range",
}
for r in METHOD_ROWS:
    ev_low = cell("FOOTBALLFIELD", f"B{r}")
    ev_high = cell("FOOTBALLFIELD", f"C{r}")
    eq_low = cell("FOOTBALLFIELD", f"E{r}")
    eq_high = cell("FOOTBALLFIELD", f"F{r}")
    px_low = cell("FOOTBALLFIELD", f"G{r}")
    px_high = cell("FOOTBALLFIELD", f"H{r}")
    prem_low = cell("FOOTBALLFIELD", f"I{r}")
    prem_high = cell("FOOTBALLFIELD", f"J{r}")
    m = METHOD_ROWS[r]
    # bridge: equity = EV - net debt (no minority/pref/associates in this spec)
    check(f"[{m}] equity low = EV low - net debt", eq_low, ev_low - NET_DEBT)
    check(f"[{m}] equity high = EV high - net debt", eq_high, ev_high - NET_DEBT)
    # implied per share = equity / shares
    check(f"[{m}] implied price low = equity low / shares", px_low, (ev_low - NET_DEBT) / SHARES)
    check(f"[{m}] implied price high = equity high / shares", px_high, (ev_high - NET_DEBT) / SHARES)
    # premium = implied price / current price - 1
    check(f"[{m}] premium low = px_low/price - 1", prem_low, px_low / PRICE - 1)
    check(f"[{m}] premium high = px_high/price - 1", prem_high, px_high / PRICE - 1)

print("\n=== E. STATIC DCF/LBO + 52W method values match spec inputs ===")
check("FF B8 DCF EV low", cell("FOOTBALLFIELD", "B8"), DCF_LOW)
check("FF C8 DCF EV high", cell("FOOTBALLFIELD", "C8"), DCF_HIGH)
check("FF B9 LBO EV low", cell("FOOTBALLFIELD", "B9"), LBO_LOW)
check("FF C9 LBO EV high", cell("FOOTBALLFIELD", "C9"), LBO_HIGH)
# 52W: EV = shares*price + net_debt
check("FF B10 52W EV low = shares*52Wlow + net debt",
      cell("FOOTBALLFIELD", "B10"), SHARES * PRICE_52W_LOW + NET_DEBT)
check("FF C10 52W EV high = shares*52Whigh + net debt",
      cell("FOOTBALLFIELD", "C10"), SHARES * PRICE_52W_HIGH + NET_DEBT)

print("\n=== F. FOOTBALL-FIELD AGGREGATES (min/median/max across methods) ===")
ev_lows = [cell("FOOTBALLFIELD", f"B{r}") for r in range(6, 11)]
ev_highs = [cell("FOOTBALLFIELD", f"C{r}") for r in range(6, 11)]
eq_lows = [cell("FOOTBALLFIELD", f"E{r}") for r in range(6, 11)]
eq_highs = [cell("FOOTBALLFIELD", f"F{r}") for r in range(6, 11)]
check("Summary EV low min (B14)", cell("FOOTBALLFIELD", "B14"), min(ev_lows))
check("Summary EV high max (B15)", cell("FOOTBALLFIELD", "B15"), max(ev_highs))
check("Summary EV low median (B16)", cell("FOOTBALLFIELD", "B16"), statistics.median(ev_lows))
check("Summary EV high median (B17)", cell("FOOTBALLFIELD", "B17"), statistics.median(ev_highs))
check("Summary EV midpoint (B18)", cell("FOOTBALLFIELD", "B18"),
      (statistics.median(ev_lows) + statistics.median(ev_highs)) / 2)
check("Summary equity low min (B19)", cell("FOOTBALLFIELD", "B19"), min(eq_lows))
check("Summary equity high max (B20)", cell("FOOTBALLFIELD", "B20"), max(eq_highs))
check("Summary range spread % (B22)", cell("FOOTBALLFIELD", "B22"),
      (max(ev_highs) - min(ev_lows)) / ((statistics.median(ev_lows) + statistics.median(ev_highs)) / 2))
check("Summary method count (B23)", cell("FOOTBALLFIELD", "B23"), 5.0)

print("\n=== G. INTERNAL ORDERING INVARIANTS (model-independent) ===")
# Per method: low <= mid <= high
for r in range(6, 11):
    lo = cell("FOOTBALLFIELD", f"B{r}")
    mid = cell("FOOTBALLFIELD", f"D{r}")
    hi = cell("FOOTBALLFIELD", f"C{r}")
    check_true(f"row {r}: EV low <= mid <= high", lo <= mid + TOL <= hi + 2 * TOL,
               f"{lo} <= {mid} <= {hi}")
# Aggregate ordering: min <= median(low) and median(high) <= max ; min <= max
check_true("min EV low <= median EV low", min(ev_lows) <= statistics.median(ev_lows) + TOL)
check_true("median EV high <= max EV high", statistics.median(ev_highs) <= max(ev_highs) + TOL)
check_true("football min EV low < max EV high", min(ev_lows) < max(ev_highs))
# Equity bridge sign: every equity value < its EV (positive net debt)
check_true("all equity values strictly below EV (net debt > 0)",
           all(eq_lows[i] < ev_lows[i] for i in range(5))
           and all(eq_highs[i] < ev_highs[i] for i in range(5)))

print("\n=== H. ROUND-TRIP: implied multiples back out exactly to peer inputs ===")
# Take the model's central trading EV, divide by subject EBITDA -> must equal
# the *median of the raw peer EV/EBITDA list* re-computed here from scratch.
rt_trade = cell("FOOTBALLFIELD", "D6") / SUBJ_EBITDA
check("Round-trip: central trading EV / EBITDA == peer median (clean-room)",
      rt_trade, statistics.median([p[1] for p in TRADING_PEERS]))
rt_txn = cell("FOOTBALLFIELD", "D7") / SUBJ_EBITDA
check("Round-trip: central txn EV / EBITDA == peer median (clean-room)",
      rt_txn, statistics.median([p[1] for p in TXN_PEERS]))
# And the band endpoints back out to median±spread exactly
check("Round-trip: trading EV low / EBITDA == median - 1",
      cell("FOOTBALLFIELD", "B6") / SUBJ_EBITDA, MED_TRADE_EBITDA - SPREAD)
check("Round-trip: trading EV high / EBITDA == median + 1",
      cell("FOOTBALLFIELD", "C6") / SUBJ_EBITDA, MED_TRADE_EBITDA + SPREAD)

# ────────────────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok, *_ in _checks if ok)
total = len(_checks)
print("\n" + "=" * 60)
print(f"RESULT: {passed}/{total} checks passed")
print("=" * 60)
if passed != total:
    print("\nFAILURES:")
    for name, ok, got, exp in _checks:
        if not ok:
            print(f"  - {name}: got={got!r} expected={exp!r}")
    sys.exit(1)
print("ALL CHECKS PASS (live-excel, independent ground truth).")
sys.exit(0)

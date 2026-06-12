"""hardtest_npl_portfolio.py — INDEPENDENT validation of ModelForge's NPL
portfolio recovery-waterfall model (examples/npl_mixed_portfolio.yaml ->
modelforge/builder/sheets/npl_waterfall.py -> sheet 'CollectionWaterfall').

CORE RULE: every EXPECTED value is computed OUTSIDE ModelForge — either by a
clean-room re-derivation written here from the raw spec inputs (NO modelforge
import), by numpy_financial (NumPy org), or as a model-independent invariant
(cash conservation, gross-collections identity, MoIC identity).

We test the LIVE RENDERED WORKBOOK: build via the CLI, then evaluate every
cell with the `formulas` package and reconcile against the clean-room numbers.

Run:  python hardtest_npl_portfolio.py
Exits 0 iff every check passes (or prints a precise FAIL with evidence).
"""

from __future__ import annotations

import os
import subprocess
import sys
# UTF-8 console guard (effective in-process; PYTHONIOENCODING alone is read
# only at interpreter startup and ignored by the running process on Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy_financial as npf
import formulas

# ---------------------------------------------------------------------------
# CLEAN-ROOM GROUND TRUTH  (hand-transcribed from examples/npl_mixed_portfolio.yaml,
# BASE scenario = scenario_index 2. NO modelforge import anywhere in this file.)
# ---------------------------------------------------------------------------
GBV = 200.0                      # A-001 base
PURCHASE_PCT = 0.18              # A-002 base
SERVICING_FEE = 0.08             # A-020 base
SETUP_FEE_PCT = 0.003            # A-021 base
LEGAL_FEE = 0.03                 # A-022 base
DATA_TAPE = 0.08                 # A-023 base (eur_m)
SENIOR_PCT = 0.50                # A-030 base
SENIOR_RATE = 0.055              # A-031 base
MEZZ_PCT = 0.20                  # A-032 base
MEZZ_RATE = 0.10                 # A-033 base

# Cumulative collection curve % of GBV, base column (A-010..A-019)
CUM = [0.03, 0.08, 0.15, 0.22, 0.28, 0.32, 0.35, 0.37, 0.39, 0.40]  # Y1..Y10
N_YEARS = 10
N = N_YEARS + 1  # t=0..t=10

# Derived clean-room values --------------------------------------------------
purchase = GBV * PURCHASE_PCT                       # 36.0
senior = purchase * SENIOR_PCT                      # 18.0
mezz = purchase * MEZZ_PCT                          # 7.2

# Annual gross collections from the cumulative curve.
# t=0 -> 0; t=k -> (CUM[k-1] - CUM[k-2]) * GBV   (CUM[-1] treated as 0 at k=1)
gross = [0.0]
prev = 0.0
for k in range(N_YEARS):
    gross.append((CUM[k] - prev) * GBV)
    prev = CUM[k]
# total expected recovery == GBV * terminal cumulative recovery
total_recovery = GBV * CUM[-1]                      # 200 * 0.40 = 80.0

# Servicing + legal (negative), one-off setup + data tape at t0 (negative)
servicing = [0.0] + [-gross[i] * SERVICING_FEE for i in range(1, N)]
legal = [0.0] + [-gross[i] * LEGAL_FEE for i in range(1, N)]
setup_t0 = -GBV * SETUP_FEE_PCT                     # -0.6
datatape_t0 = -DATA_TAPE                            # -0.08

# Net collections to fund (matches builder rows): t0 = setup + data tape;
# t>=1 = gross + servicing + legal
net = [setup_t0 + datatape_t0]
for i in range(1, N):
    net.append(gross[i] + servicing[i] + legal[i])

# Interest service: per-year -(senior*rate + mezz*rate), t0 = 0
interest = [0.0] + [-(senior * SENIOR_RATE + mezz * MEZZ_RATE) for _ in range(1, N)]

# Equity CF to fund — SUBORDINATION-CORRECT (audit fix #16). Equity receives
# ONLY the strict-priority residual: zero until senior + mezz are fully retired.
# Replicate the builder's waterfall (senior principal -> mezz principal ->
# equity residual) clean-room, from raw inputs only (no modelforge import).
so = [0.0] * N   # senior principal outstanding
spp = [0.0] * N  # senior principal paid this year
mo = [0.0] * N   # mezz principal outstanding
res = [0.0] * N  # residual to equity
so[0], mo[0] = senior, mezz
for i in range(1, N):
    avail = max(net[i] + interest[i], 0.0)
    spp[i] = min(avail, so[i - 1])
    so[i] = max(so[i - 1] - spp[i], 0.0)
    if so[i] <= 0.01:
        mo[i] = max(mo[i - 1] - max(net[i] + interest[i] - spp[i], 0.0), 0.0)
    else:
        mo[i] = mo[i - 1]
    if so[i] <= 0.01 and mo[i] <= 0.01:
        res[i] = max(net[i] + interest[i] - spp[i] - (mo[i - 1] - mo[i]), 0.0)
    else:
        res[i] = 0.0
equity = []
for i in range(N):
    if i == 0:
        equity.append(-purchase + senior + mezz + net[0])
    else:
        equity.append(res[i])

# IRR via numpy_financial (independent of ModelForge)
irr_npf = npf.irr(equity)

# MoIC identity (independent): sum(positive CF) / |sum(negative CF)|
pos = sum(c for c in equity if c > 0)
neg = abs(sum(c for c in equity if c < 0))
moic_expected = pos / neg if neg else 0.0

# Gross-money multiple per spec wording: total net collections / purchase price
total_net_collections = sum(net)
gross_money_multiple = total_net_collections / purchase

# ---------------------------------------------------------------------------
# BUILD the live workbook (rebuild fresh so the test is self-contained)
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output", "hardtest_npl_portfolio.xlsx")
os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)


def build_workbook():
    cmd = [
        sys.executable, "-m", "modelforge.cli", "build",
        "examples/npl_mixed_portfolio.yaml", "--out", OUT,
    ]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("BUILD FAILED:\n", r.stdout, r.stderr)
        sys.exit(2)
    if not os.path.exists(OUT):
        print("BUILD produced no file at", OUT)
        sys.exit(2)


# ---------------------------------------------------------------------------
# EVALUATE live with formulas
# ---------------------------------------------------------------------------
SHEET = "COLLECTIONWATERFALL"  # formulas uppercases sheet keys
COLS = ["D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"]  # t=0..t=10


def loader():
    base = os.path.basename(OUT)
    xl = formulas.ExcelModel().loads(OUT).finish()
    sol = xl.calculate()

    def g(a1, sheet=SHEET):
        key = "'[" + base + "]" + sheet + "'!" + a1
        v = sol[key].value
        try:
            return float(v[0, 0])
        except Exception:
            try:
                return float(v)
            except Exception:
                return v

    return g


def row(g, r):
    return [g(f"{c}{r}") for c in COLS]


# ---------------------------------------------------------------------------
# CHECK harness
# ---------------------------------------------------------------------------
TOL = 1e-6
results = []  # (name, passed, detail)


def check(name, got, exp, tol=TOL):
    try:
        ok = abs(float(got) - float(exp)) <= tol * max(1.0, abs(float(exp)))
    except Exception:
        ok = (got == exp)
    results.append((name, ok, f"got={got!r} exp={exp!r}"))


def check_true(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def main():
    build_workbook()
    g = loader()

    # Row map (verified via openpyxl dump):
    # 8 gbv, 9 purchase, 12 cum%, 13 gross, 16 servicing, 17 legal, 18 setup,
    # 19 datatape, 21 net, 24 senior, 25 mezz, 26 interest, 28 equity,
    # 31 IRR, 32 MoIC, 33 gross recovery, 36 cum cash, 37 senior O/S,
    # 38 senior paid, 40 mezz O/S, 41 residual to equity.

    # --- Static portfolio stats ---
    check("gbv", g("D8"), GBV)
    check("purchase_price", g("D9"), purchase)
    check("senior_note_size", g("D24"), senior)
    check("mezz_note_size", g("D25"), mezz)

    # --- CHECK 1: gross collections == GBV * incremental cumulative recovery,
    #              and sum == total expected recovery (GBV * terminal cum) ---
    live_gross = row(g, 13)
    for i in range(N):
        check(f"gross_collections_t{i}", live_gross[i], gross[i])
    check("sum_gross_collections_==_total_recovery", sum(live_gross[1:]), total_recovery)
    # cumulative curve terminal == 0.40 and <= 1.0
    live_cum = row(g, 12)
    check("terminal_cum_recovery", live_cum[-1], CUM[-1])
    check_true("collection_curve_<=_1", all(v <= 1.0 + 1e-12 for v in live_cum),
               f"cum={live_cum}")
    check_true("collection_curve_monotone_nondecreasing",
               all(live_cum[i + 1] >= live_cum[i] - 1e-12 for i in range(N - 1)),
               f"cum={live_cum}")

    # --- CHECK 2: net cashflow_t == gross_t - servicing_t - legal_t (t>=1) ---
    live_serv = row(g, 16)
    live_legal = row(g, 17)
    live_net = row(g, 21)
    for i in range(N):
        check(f"net_collections_t{i}", live_net[i], net[i])
    # explicit identity per period (independent of the builder's own net formula):
    for i in range(1, N):
        recomputed = live_gross[i] + live_serv[i] + live_legal[i]
        check(f"net_identity_t{i}", live_net[i], recomputed)
    # servicing/legal sign + magnitude vs gross
    for i in range(1, N):
        check(f"servicing_fee_t{i}", live_serv[i], -live_gross[i] * SERVICING_FEE)
        check(f"legal_fee_t{i}", live_legal[i], -live_gross[i] * LEGAL_FEE)

    # --- CHECK 3: gross-money multiple == total net collections / purchase ---
    live_total_net = sum(live_net)
    check("total_net_collections", live_total_net, total_net_collections)
    check("gross_money_multiple", live_total_net / g("D9"), gross_money_multiple)

    # --- CHECK 4: IRR on equity CF reconciles to numpy_financial.irr ---
    live_equity = row(g, 36)   # Equity CF to fund (moved below the waterfall)
    for i in range(N):
        check(f"equity_cf_t{i}", live_equity[i], equity[i])
    live_irr = g("D39")
    # ground truth = numpy_financial on the LIVE equity vector (model-independent solver)
    irr_on_live = npf.irr(live_equity)
    check("IRR_vs_numpy_financial_on_live_CF", live_irr, irr_on_live, tol=1e-5)
    # and reconcile to the clean-room equity vector's IRR too
    check("IRR_vs_numpy_financial_cleanroom", live_irr, irr_npf, tol=1e-5)
    # MoIC identity
    check("MoIC_vs_identity", g("D40"), moic_expected, tol=1e-6)

    # --- CHECK 5: cash conservation in the strict-priority waterfall ---
    # The waterfall distributes net collections to: senior principal, mezz
    # principal, interest, and residual equity. The cumulative-cash row is the
    # running sum of net collections; the model splits each year's distributable
    # cash (net + interest) into senior-principal-paid + (mezz paydown) +
    # residual. We assert NO cash is created/lost: the sum of all cash that
    # leaves the pool over the deal == total net collections + total interest
    # paid (interest is a real outflow), AND ending equity distributions
    # reconcile.
    live_cum_cash = row(g, 29)   # Cumulative cash available (waterfall block)
    # cumulative cash == running sum of net collections (invariant)
    run = 0.0
    for i in range(N):
        run += live_net[i]
        check(f"cum_cash_running_sum_t{i}", live_cum_cash[i], run)
    # ending cumulative cash == total net collections
    check("ending_cum_cash_==_total_net", live_cum_cash[-1], live_total_net)

    # Distributable each year (t>=1) = net + interest. Split conservation:
    # senior_paid + mezz_paydown + residual_equity == max(net+interest,0)
    # whenever positive (the model only distributes non-negative cash).
    live_senior_paid = row(g, 31)   # Senior principal paid (this year)
    live_senior_os = row(g, 30)     # Senior principal outstanding
    live_mezz_os = row(g, 33)       # Mezz principal outstanding
    live_residual = row(g, 34)      # Residual to equity
    live_interest = row(g, 26)      # Total interest (senior + mezz)
    # CASH CONSERVATION (post-fix): the strict-priority waterfall must conserve
    # cash in EVERY year, INCLUDING the transition year where the mezz note is
    # fully retired. The distributable cash each year (net + interest, when
    # positive) is split into exactly three buckets: senior principal paid,
    # mezz principal paid down, and residual equity. They must sum to the
    # distributable cash with NO phantom cash created. The invariant is
    # model-independent (it is an accounting identity over the pool, not a
    # comparison of any model row to itself).
    # Previously this block DOCUMENTED a defect: residual_to_equity (row 41)
    # subtracted only senior_paid and NOT the same-year mezz paydown, so the
    # transition year leaked exactly the mezz paydown (~3.63). That is now fixed
    # (residual nets out the mezz paydown too), so we assert leak == 0 everywhere
    # including the transition year.
    leak_years = []
    for i in range(1, N):
        distributable = live_net[i] + live_interest[i]
        mezz_paydown = live_mezz_os[i - 1] - live_mezz_os[i]
        allocated = live_senior_paid[i] + mezz_paydown + live_residual[i]
        if distributable <= 0:
            continue
        # conservation MUST hold in every period now (including the transition year)
        check(f"waterfall_cash_conservation_t{i}", allocated, distributable, tol=1e-6)
        leak = allocated - distributable
        if abs(leak) > 1e-6:
            leak_years.append((i, leak, mezz_paydown))
    # there must be ZERO leaking years after the fix
    check_true("zero_waterfall_leak_years", len(leak_years) == 0,
               f"leak_years={leak_years}")
    # GLOBAL conservation: total cash distributed (senior+mezz principal +
    # residual + interest) must EQUAL cash available; no phantom cash. The
    # transition-year mezz-paydown double-count is now eliminated -> global
    # leak == 0.
    cash_available = sum(live_net[1:])  # positive collections net of fees, t>=1
    total_senior_prin = sum(live_senior_paid[1:])
    total_mezz_prin = sum(live_mezz_os[i - 1] - live_mezz_os[i] for i in range(1, N))
    total_residual = sum(live_residual[1:])
    total_interest_out = sum(-live_interest[i] for i in range(1, N))
    total_distributed = total_senior_prin + total_mezz_prin + total_residual + total_interest_out
    global_leak = total_distributed - cash_available
    # ground truth: the bug is fixed -> NO phantom cash; leak is exactly zero
    check("global_cash_leak_is_zero", global_leak, 0.0, tol=1e-6)
    # sanity: senior+mezz principal fully repaid == their face (they DO get paid)
    check("total_senior_principal_repaid_==_face", total_senior_prin, senior)
    check("total_mezz_principal_repaid_==_face", total_mezz_prin, mezz)

    # Debt never negative; outstanding balances non-negative every period
    for i in range(N):
        check_true(f"senior_os_nonneg_t{i}", live_senior_os[i] >= -1e-9,
                   f"senior_os={live_senior_os[i]}")
        check_true(f"mezz_os_nonneg_t{i}", live_mezz_os[i] >= -1e-9,
                   f"mezz_os={live_mezz_os[i]}")
        check_true(f"senior_paid_nonneg_t{i}", live_senior_paid[i] >= -1e-9,
                   f"senior_paid={live_senior_paid[i]}")

    # senior principal can never be paid down below 0 / above its face
    check_true("senior_os_start_==_face", abs(live_senior_os[0] - senior) < 1e-9,
               f"{live_senior_os[0]} vs {senior}")
    check_true("mezz_os_start_==_face", abs(live_mezz_os[0] - mezz) < 1e-9,
               f"{live_mezz_os[0]} vs {mezz}")

    # --- report ---
    npass = sum(1 for _, ok, _ in results if ok)
    ntot = len(results)
    print(f"\n{'='*70}")
    print(f"NPL portfolio live-Excel reconciliation: {npass}/{ntot} checks PASS")
    print(f"{'='*70}")
    fails = [(n, d) for n, ok, d in results if not ok]
    if fails:
        print("\nFAILURES:")
        for n, d in fails:
            print(f"  FAIL  {n}: {d}")
    # headline economics
    print("\n--- HEADLINE NUMBERS (live workbook) ---")
    print(f"  GBV                         = {g('D8'):.4f}")
    print(f"  Purchase price (18% GBV)    = {g('D9'):.4f}")
    print(f"  Total gross collections     = {sum(live_gross[1:]):.4f}  (=GBV*40% = {total_recovery:.4f})")
    print(f"  Total net collections       = {live_total_net:.6f}")
    print(f"  Gross-money multiple        = {live_total_net / g('D9'):.6f}x  (net coll / purchase)")
    print(f"  Equity IRR (workbook)       = {live_irr:.6f}")
    print(f"  Equity IRR (numpy_financial)= {irr_on_live:.6f}")
    print(f"  Equity MoIC (workbook)      = {g('D40'):.6f}  (identity = {moic_expected:.6f})")
    print(f"  Ending cumulative cash      = {live_cum_cash[-1]:.6f}  (=total net)")

    # report cash conservation explicitly (defect FIXED)
    print("\n--- CASH CONSERVATION (waterfall display block, post-fix) ---")
    print(f"  Cash available in pool (t>=1)   = {cash_available:.4f}")
    print(f"  Cash distributed by waterfall   = {total_distributed:.4f}")
    print(f"  PHANTOM CASH LEAK               = {global_leak:.4f}  (must be 0 -> cash conserved)")
    print("  Fix: residual_to_equity (row 34) subtracts BOTH the senior principal")
    print("  paid AND the same-year mezz principal paydown, so the mezz-retirement")
    print("  cash is not double-counted as equity residual. The headline equity CF")
    print("  (row 36) reads the strict-priority residual — zero until senior+mezz")
    print("  are retired — and the IRR/MoIC (rows 39/40) read it. (audit fix #16)")

    if fails:
        sys.exit(1)
    print("\nALL CHECKS PASS (cash conservation holds in every period, incl. the transition year)")
    sys.exit(0)


if __name__ == "__main__":
    main()

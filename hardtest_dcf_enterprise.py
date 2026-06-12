"""hardtest_dcf_enterprise.py — INDEPENDENT validation of ModelForge's full
assembled DCF / enterprise-valuation model (examples/dcf_enel.yaml).

NO CIRCULAR GRADING. Every EXPECTED value below is produced by ONE of:
  (a) numpy_financial (NumPy org) — npv / irr triangulation,
  (b) a clean-room re-derivation written from scratch in THIS file that does
      NOT import modelforge (hardcoded BASE-scenario inputs copied from the
      Assumptions sheet + first-principles DCF math),
  (c) model-independent invariants (EV == PV(FCFF)+PV(TV); equity bridge
      additivity; FCFF identity EBIT*(1-t)+D&A-capex-dNWC; Gordon vs exit
      cross-checks; TV discount-factor consistency),
  (d) a free CITABLE external anchor: Aswath Damodaran's Europe cost-of-capital
      dataset (utilities sector) — pages.stern.nyu.edu/~adamodar.

We BUILD the live workbook with the CLI, then EVALUATE every assertion against
the live rendered cells via the `formulas` package. The modelforge code NEVER
computes the EXPECTED side of any assertion.
"""

from __future__ import annotations

import math
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
import warnings

warnings.filterwarnings("ignore")

import numpy_financial as npf  # ground truth (a)

REPO = os.path.dirname(os.path.abspath(__file__))
WB_PATH = os.path.join(REPO, "output", "hardtest_dcf_enterprise.xlsx")
SPEC = os.path.join(REPO, "examples", "dcf_enel.yaml")
TOL = 1e-6          # relative tolerance for exact-math checks
TOL_LOOSE = 1e-4    # for floating accumulation

PASS = 0
FAIL = 0
RESULTS = []


def check(name, got, expected, tol=TOL, abs_ok=False):
    global PASS, FAIL
    if expected == 0 or abs_ok:
        ok = abs(got - expected) <= max(tol, 1e-9)
    else:
        ok = abs(got - expected) / abs(expected) <= tol
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append((status, name, got, expected))
    print(f"[{status}] {name}: got={got:.8g} expected={expected:.8g}")
    return ok


def check_bool(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        RESULTS.append(("PASS", name, detail, ""))
        print(f"[PASS] {name} {detail}")
    else:
        FAIL += 1
        RESULTS.append(("FAIL", name, detail, ""))
        print(f"[FAIL] {name} {detail}")
    return cond


# ---------------------------------------------------------------------------
# 1. BUILD the live workbook
# ---------------------------------------------------------------------------
print("=== Building workbook via modelforge CLI ===")
r = subprocess.run(
    [sys.executable, "-m", "modelforge.cli", "build", SPEC, "--out", WB_PATH],
    cwd=REPO, capture_output=True, text=True,
)
print(r.stdout[-400:])
if r.returncode != 0:
    print("BUILD FAILED:\n", r.stderr[-2000:])
    sys.exit(2)
assert os.path.exists(WB_PATH), "workbook not produced"

# ---------------------------------------------------------------------------
# 2. EVALUATE the live workbook with the `formulas` package
# ---------------------------------------------------------------------------
print("\n=== Evaluating live workbook (formulas package) ===")
import formulas

base = os.path.basename(WB_PATH)
sol = formulas.ExcelModel().loads(WB_PATH).finish().calculate()


def cell(sheet, a1):
    v = sol["'[" + base + "]" + sheet.upper() + "'!" + a1].value
    try:
        return float(v[0, 0])
    except Exception:
        return float(v)


# ---------------------------------------------------------------------------
# 3. CLEAN-ROOM re-derivation — hardcoded BASE-scenario inputs.
#    These literals are copied from the Assumptions sheet (Base column G),
#    NOT computed by modelforge. scenario_index=2 -> CHOOSE picks Base.
# ---------------------------------------------------------------------------
# WACC inputs (Base)
rf = 0.039
mature_erp = 0.0423
sov_spread = 0.0165
vol_ratio = 1.50
lam = 0.65
pretax_kd = 0.045
tax = 0.28
d_weight = 0.40
size_prem = 0.0
alpha_bps = 0.0

# Comparable betas (E.ON, Iberdrola, EDF, Engie, RWE): (beta_L, D/E, tax)
comps = [
    (0.78, 1.05, 0.30),
    (0.82, 0.92, 0.25),
    (0.75, 1.55, 0.26),
    (0.88, 0.87, 0.26),
    (0.92, 0.72, 0.30),
]

# FCF drivers (Base)
rev_last = 95000.0
growth = [0.03, 0.03, 0.025, 0.025, 0.02]
margin = [0.238, 0.240, 0.242, 0.245, 0.245]
da_pct = 0.10
capex_pct = 0.12
nwc_pct = 0.05

# Terminal / bridge (Base)
g_term = 0.015
exit_x = 7.0
terminal_choice = 2          # 2 = exit multiple
mid_year = 0.5               # mid_year_convention: true
stub_years = 1.0            # stub_period_days: 365
net_debt = 60000.0
minority = 14000.0
pension = 1800.0
preferred = 0.0
lease = 4800.0
cross_hold = 2500.0
shares = 10166.0
price = 6.45
P = 5                        # projection years, no fade

# --- Clean-room Hamada relever (mirrors comparable_betas.py method, but the
#     EXPECTED is computed here independently, not read from modelforge) ---
unlev = [bL / (1 + (1 - t) * de) for (bL, de, t) in comps]
unlev_sorted = sorted(unlev)
median_unlev = unlev_sorted[len(unlev_sorted) // 2]  # 5 comps -> middle
target_de = d_weight / (1 - d_weight)
relevered_beta = median_unlev * (1 + (1 - tax) * target_de)

# --- Clean-room WACC ---
eff_erp = mature_erp + sov_spread * vol_ratio * lam
cost_equity = rf + relevered_beta * eff_erp + size_prem + alpha_bps / 10000.0
after_tax_kd = pretax_kd * (1 - tax)
e_weight = 1 - d_weight
wacc = cost_equity * e_weight + after_tax_kd * d_weight

# --- Clean-room FCF forecast (5 projection years) ---
rev = []
prev = rev_last
for gr in growth:
    prev = prev * (1 + gr)
    rev.append(prev)
ebitda = [rev[i] * margin[i] for i in range(P)]
da = [rev[i] * da_pct for i in range(P)]                # positive magnitude
ebit = [ebitda[i] - da[i] for i in range(P)]
tax_amt = [max(ebit[i] * tax, 0.0) for i in range(P)]
nopat = [ebit[i] - tax_amt[i] for i in range(P)]
capex = [rev[i] * capex_pct for i in range(P)]
# dNWC for proj years: first proj (FY1) = (rev[0]-rev_last)*nwc_pct, etc.
rev_with_hist = [rev_last] + rev
dnwc = [(rev_with_hist[i + 1] - rev_with_hist[i]) * nwc_pct for i in range(P)]
# FCFF identity = EBIT*(1-t) + D&A - capex - dNWC
fcff = [nopat[i] + da[i] - capex[i] - dnwc[i] for i in range(P)]

# --- Clean-room explicit-period PV (mid-year: exponents 0.5,1.5,2.5,3.5,4.5) ---
pv_explicit = sum(fcff[i] / (1 + wacc) ** (stub_years + i - mid_year) for i in range(P))
# i=0 -> stub_years+0-0.5 = 0.5 ; i=4 -> 4.5  ✓

# numpy_financial triangulation (ground truth a): npv of the mid-year stream.
# npf.npv assumes year-end (t=1..n). Mid-year stream = year-end npv * (1+wacc)^0.5.
pv_explicit_npf = npf.npv(wacc, [0.0] + fcff) * (1 + wacc) ** 0.5

# --- Clean-room terminal value ---
# Normalized terminal FCF per builder: NOPAT_T + dNWC_norm  (capex==D&A cancel)
# dNWC in the sheet is stored NEGATIVE (=-(...)). Normalized = sheet_dNWC*(1+g).
nopat_T = nopat[-1]
dnwc_T_sheet = -dnwc[-1]                       # sheet stores it negative
norm_dnwc = dnwc_T_sheet * (1 + g_term)
norm_fcf = nopat_T + norm_dnwc
tv_gordon = norm_fcf * (1 + g_term) / (wacc - g_term)
tv_exit = ebitda[-1] * exit_x
tv_used = tv_exit if terminal_choice == 2 else tv_gordon
tv_discount_years = stub_years + P - 1 - mid_year   # 1+5-1-0.5 = 4.5
pv_tv = tv_used / (1 + wacc) ** tv_discount_years

# --- Clean-room EV -> equity bridge ---
ev = pv_explicit + pv_tv
equity = ev - net_debt - minority - pension - preferred - lease + cross_hold
per_share = equity / shares
premium = per_share / price - 1
implied_ev_ebitda_y1 = ev / ebitda[0]

print("\n--- Clean-room derived headline numbers ---")
print(f"  median unlevered beta = {median_unlev:.6f}")
print(f"  relevered beta        = {relevered_beta:.6f}")
print(f"  effective ERP         = {eff_erp:.6f}")
print(f"  cost of equity        = {cost_equity:.6f}")
print(f"  after-tax Kd          = {after_tax_kd:.6f}")
print(f"  WACC                  = {wacc:.6f}")
print(f"  PV(explicit FCFF)     = {pv_explicit:,.2f}")
print(f"  TV (exit, used)       = {tv_used:,.2f}")
print(f"  PV(TV)                = {pv_tv:,.2f}")
print(f"  Enterprise Value      = {ev:,.2f}")
print(f"  Equity Value          = {equity:,.2f}")
print(f"  Implied / share       = {per_share:.4f}")

# ---------------------------------------------------------------------------
# 4. RECONCILE every economic check vs the live workbook
# ---------------------------------------------------------------------------
print("\n=== WACC BUILD (live vs clean-room) ===")
# Hamada relever
check("ComparableBetas median unlevered beta", cell("ComparableBetas", "E12"), median_unlev)
check("ComparableBetas relevered beta (Hamada)", cell("ComparableBetas", "E17"), relevered_beta)
check("WACCBuild beta used == relevered", cell("WACCBuild", "D11"), relevered_beta)
# Effective ERP (Damodaran CRP decomposition)
check("WACCBuild effective ERP", cell("WACCBuild", "D10"), eff_erp)
# CAPM cost of equity
check("WACCBuild cost of equity (CAPM)", cell("WACCBuild", "D12"), cost_equity)
# after-tax cost of debt
check("WACCBuild after-tax cost of debt", cell("WACCBuild", "D15"), after_tax_kd)
# equity weight
check("WACCBuild equity weight 1-D", cell("WACCBuild", "D17"), e_weight)
# WACC
check("WACCBuild WACC", cell("WACCBuild", "D18"), wacc)
check("WACCBuild wacc_rate named range", cell("WACCBuild", "D18"), wacc)

print("\n=== FCFF IDENTITY per year: EBIT*(1-t)+D&A-capex-dNWC ===")
# live FCF row is FCFForecast row 16, projection cols G..K
proj_cols = ["G", "H", "I", "J", "K"]
for i, col in enumerate(proj_cols):
    live_fcf = cell("FCFForecast", f"{col}16")
    # independent identity recompute (clean-room)
    expected = ebit[i] * (1 - tax) + da[i] - capex[i] - dnwc[i]
    check(f"FCFF identity FY{i+1}", live_fcf, expected)
    # also assert live EBIT, EBITDA match clean-room
    check(f"  EBITDA FY{i+1}", cell("FCFForecast", f"{col}8"), ebitda[i])
    check(f"  EBIT FY{i+1}", cell("FCFForecast", f"{col}10"), ebit[i])

print("\n=== PV of explicit FCFF (live vs clean-room vs numpy_financial) ===")
live_pv = cell("Valuation", "D5")
check("PV explicit vs clean-room", live_pv, pv_explicit)
check("PV explicit vs numpy_financial (npf.npv triangulation)", live_pv, pv_explicit_npf, tol=TOL_LOOSE)

print("\n=== TERMINAL VALUE ===")
check("TV Gordon (normalized)", cell("Valuation", "D9"), tv_gordon)
check("TV exit EV/EBITDA = EBITDA_T * m", cell("Valuation", "D10"), tv_exit)
check("TV chosen (choice=2 -> exit)", cell("Valuation", "D12"), tv_used)
check("PV of terminal value", cell("Valuation", "D13"), pv_tv)
# Independent TV/exit cross-check: TV must equal EBITDA_T * exit multiple
check_bool("TV exit cross-check  EBITDA_T*7.0",
           abs(cell("Valuation", "D10") - ebitda[-1] * 7.0) < 1.0,
           f"(EBITDA_T={ebitda[-1]:.2f} x7 = {ebitda[-1]*7:.2f})")

print("\n=== EV / EQUITY BRIDGE (invariants) ===")
live_ev = cell("Valuation", "D14")
check("Enterprise Value vs clean-room", live_ev, ev)
# INVARIANT: EV == PV(explicit) + PV(TV)  (read straight from live cells)
check_bool("INVARIANT EV == D5 + D13",
           abs(live_ev - (cell("Valuation", "D5") + cell("Valuation", "D13"))) < 1e-3,
           f"({live_ev:.4f})")
live_equity = cell("Valuation", "D21")
check("Equity Value vs clean-room", live_equity, equity)
# INVARIANT: equity == EV - net debt - MI - pension - pref - lease + cross
bridge_items = [cell("Valuation", f"D{rr}") for rr in range(14, 21)]  # D14..D20
check_bool("INVARIANT Equity == sum(bridge D14:D20)",
           abs(live_equity - sum(bridge_items)) < 1e-3,
           f"({live_equity:.4f} vs {sum(bridge_items):.4f})")
# Each bridge sign correct
check("(-) Net debt line", cell("Valuation", "D15"), -net_debt)
check("(-) Minority interest line", cell("Valuation", "D16"), -minority)
check("(-) Pension deficit line", cell("Valuation", "D17"), -pension)
check("(-) Preferred line", cell("Valuation", "D18"), -preferred, abs_ok=True)
check("(-) IFRS16 lease line", cell("Valuation", "D19"), -lease)
check("(+) Cross-holdings line", cell("Valuation", "D20"), cross_hold)

print("\n=== PER SHARE ===")
check("Implied price per share == equity/shares", cell("Valuation", "D24"), per_share)
check("Current price line", cell("Valuation", "D25"), price)
check("Premium / (discount) %", cell("Valuation", "D26"), premium)
check("Implied EV/EBITDA Y1", cell("Valuation", "D22"), implied_ev_ebitda_y1)

print("\n=== INVARIANT: implied-g cross-check (D11) ===")
# Builder's implied-g cell (FIXED, closed-form): the value of g for which the
# Gordon perpetuity reproduces the exit-multiple TV. Clean-room algebra:
#   TV = CF0*(1+g)/(wacc-g)  =>  TV*wacc - TV*g = CF0 + CF0*g
#                            =>  g = (wacc*TV - CF0)/(TV + CF0)
# CF0 = normalized terminal FCF, TV = exit-multiple TV. Computed here from
# first principles (NOT read from the model) so the EXPECTED side stays
# independent. Replaces the prior hybrid approximation
# (wacc - CF0*(1+g)/TV) which understated implied-g (~0.032% vs ~0.115%).
implied_g_expected = (wacc * tv_exit - norm_fcf) / (tv_exit + norm_fcf)
check("Implied g from exit multiple (D11)", cell("Valuation", "D11"), implied_g_expected)
# Round-trip invariant: feeding this g back through Gordon must reproduce the
# exit-multiple TV (independent of the model), confirming the closed form.
tv_from_implied_g = norm_fcf * (1 + implied_g_expected) / (wacc - implied_g_expected)
check_bool("Implied-g round-trips to exit TV (Gordon[g]==exit TV)",
           abs(tv_from_implied_g - tv_exit) < 1.0,
           f"(Gordon[g]={tv_from_implied_g:.2f} vs exit TV={tv_exit:.2f})")

print("\n=== INVARIANT: WACC > g (Gordon validity) ===")
check_bool("WACC > terminal growth", wacc > g_term, f"(wacc={wacc:.4f} > g={g_term})")

# ---------------------------------------------------------------------------
# 5. EXTERNAL ANCHOR — Damodaran Europe cost-of-capital, utilities sector.
#    Source: https://pages.stern.nyu.edu/~adamodar/pc/datasets/waccEurope.xls
#    (Industry Averages tab, "Europe", updated Jan 2026). Parsed independently.
#    Utility (General) Europe : Cost of Equity 7.31%, Cost of Capital 4.62%
#    Power Europe            : Cost of Equity 7.20%, Cost of Capital 4.91%
#    These are pan-European averages; Enel carries an Italy CRP, so a modest
#    premium over the average is EXPECTED. We sanity-band, not exact-match.
# ---------------------------------------------------------------------------
print("\n=== EXTERNAL ANCHOR (Damodaran Europe utilities) ===")
DAM_UTIL_COE = 0.0731       # Utility (General) Europe cost of equity
DAM_POWER_COE = 0.0720      # Power Europe cost of equity
DAM_UTIL_COC = 0.0462       # Utility (General) Europe cost of capital
DAM_POWER_COC = 0.0491      # Power Europe cost of capital
DAM_UTIL_BETA = 0.6367      # Utility (General) Europe levered beta
live_wacc = cell("WACCBuild", "D18")
live_coe = cell("WACCBuild", "D12")
live_beta = cell("WACCBuild", "D11")
# WACC band: from European-average COC (4.6%) up to COE (~7.3%) — a CRP-loaded
# Italian utility WACC should land inside this sector band.
check_bool("Model WACC within Damodaran EU utility band [4.6%,7.5%]",
           DAM_UTIL_COC - 0.005 <= live_wacc <= DAM_UTIL_COE + 0.002,
           f"(WACC={live_wacc:.4%}; EU util COC={DAM_UTIL_COC:.2%}..COE={DAM_UTIL_COE:.2%})")
# Cost of equity band: should sit near/above EU utility COE given Italy CRP.
check_bool("Model cost of equity within [6.5%,9.0%] vs Damodaran EU util COE 7.31%",
           0.065 <= live_coe <= 0.090,
           f"(Ke={live_coe:.4%}; Damodaran EU util COE={DAM_UTIL_COE:.2%}, Power={DAM_POWER_COE:.2%})")
# Beta band: regulated-utility relevered beta should be defensive (<1), and in
# the neighborhood of the Damodaran EU utility levered beta (0.64).
check_bool("Model beta defensive (<1.0) & near Damodaran EU util beta 0.64",
           0.5 <= live_beta <= 1.0,
           f"(beta={live_beta:.3f}; Damodaran EU util levered beta={DAM_UTIL_BETA})")

# ---------------------------------------------------------------------------
# 6. SUMMARY
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"TOTAL CHECKS: {PASS + FAIL}   PASS: {PASS}   FAIL: {FAIL}")
print("=" * 60)
if FAIL:
    print("\nFAILURES:")
    for st, nm, g, e in RESULTS:
        if st == "FAIL":
            print(f"  {nm}: got={g} expected={e}")
sys.exit(0 if FAIL == 0 else 1)

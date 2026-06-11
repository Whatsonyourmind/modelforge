"""hardtest_minibond.py — Independent validation of ModelForge's minibond model.

LAYER: live-excel. Builds output/hardtest_minibond.xlsx via the CLI, evaluates it
with the `formulas` package (live Excel calc), and reconciles every economic check
against INDEPENDENT ground truth:
  - numpy_financial (IRR/duration math is hand-rolled here, not imported from modelforge)
  - clean-room re-derivations written from scratch in THIS file (no modelforge import)
  - model-independent invariants (sum(amort)==face; outstanding>=0; price==disc CF at YTM;
    par bond => YTM==coupon)

NO modelforge function ever computes an EXPECTED value. All expecteds are external.

Run:  PYTHONIOENCODING=utf-8 python hardtest_minibond.py
Exits 0 iff every assertion that is a genuine invariant / model-internal-consistency
check passes. Checks that EXPOSE a real ModelForge defect are recorded as BUGS and
printed, but do NOT crash the harness (the defect is the finding).
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import numpy as np
import numpy_financial as npf
import formulas

XLSX = os.path.abspath(os.path.join(os.path.dirname(__file__), "output", "hardtest_minibond.xlsx"))
BASE = os.path.basename(XLSX)

# ── Spec constants (read straight from the YAML, NOT computed by modelforge) ──
FACE = 20.0            # bond.notional.base
COUPON = 0.065         # bond.coupon.fixed_rate.base
TENOR = 6              # bond.tenor_years
AMORT_START = 3        # bond.amortization_start_year (linear_from_year)
ARRANGE_PCT = 0.015    # bond.arrangement_fee_pct.base
LEGAL = 0.10           # bond.legal_fees_eur_m.base
LISTING = 0.015        # bond.listing_fees_eur_m.base
RATING = 0.04          # bond.rating_fees_eur_m.base
WHT = 0.26             # investor_adjustments.withholding_tax_pct.base
TX_BPS = 50            # investor_adjustments.transaction_cost_bps.base

TOL = 1e-9

results = []   # (name, passed, expected, actual, note)
bugs = []      # human-readable defect descriptions


def record(name, passed, expected, actual, note="", is_invariant=True):
    results.append((name, passed, expected, actual, note, is_invariant))
    tag = "PASS" if passed else ("BUG " if not is_invariant else "FAIL")
    print(f"[{tag}] {name}: expected={expected!r} actual={actual!r} {note}")


# ── Live-Excel evaluation ────────────────────────────────────────────────────
sol = formulas.ExcelModel().loads(XLSX).finish().calculate()


def cell(sheet, a1):
    key = "'[" + BASE + "]" + sheet.upper() + "'!" + a1
    v = sol[key].value
    if hasattr(v, "shape"):
        v = np.asarray(v).ravel()[0]
    return float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v


# Column map: index 0..9 -> A2023..E2032 ; bond Year k (1..6) is col index h+k-1 = 3+k-1
COLS = list("DEFGHIJKLM")          # data cols, index 0 == A2023
def dcol(idx):  # idx is 0-based across the 10 data columns
    return COLS[idx]

H = 3  # historical years

# ════════════════════════════════════════════════════════════════════════════
# CLEAN-ROOM GROUND TRUTH (written from scratch, no modelforge)
# ════════════════════════════════════════════════════════════════════════════
# A 6y amortizing bond, €20m, drawn in full at close (t=0). Linear amort starts
# bond-year 3 -> 4 equal repayments of 5 at end of years 3,4,5,6. Coupon on the
# OUTSTANDING (period-opening) face — the standard bond convention.
opening_face = [20.0, 20.0, 20.0, 15.0, 10.0, 5.0]      # years 1..6
amort_true   = [0.0, 0.0, 5.0, 5.0, 5.0, 5.0]            # end-of-year repayments
coupon_true  = [round(of * COUPON, 10) for of in opening_face]
assert abs(sum(amort_true) - FACE) < TOL                # sanity of ground truth

# Par cashflow (price == face): clean-room par YTM must equal the coupon exactly.
par_cf = [-FACE] + [coupon_true[i] + amort_true[i] for i in range(6)]
par_ytm_cleanroom = npf.irr(par_cf)

# Macaulay / modified duration at par (hand-rolled, not from modelforge).
y = par_ytm_cleanroom
pv_inflows = sum(par_cf[t] / (1 + y) ** t for t in range(1, 7))
mac_dur_cleanroom = sum(t * par_cf[t] / (1 + y) ** t for t in range(1, 7)) / pv_inflows
mod_dur_cleanroom = mac_dur_cleanroom / (1 + y)

# ════════════════════════════════════════════════════════════════════════════
# READ THE MODEL'S RENDERED VALUES (live Excel)
# ════════════════════════════════════════════════════════════════════════════
# Bond Year k -> data-col index H + k - 1
bond_open  = [cell("BondStructure", dcol(H + k - 1) + "8")  for k in range(1, 7)]
bond_close = [cell("BondStructure", dcol(H + k - 1) + "11") for k in range(1, 7)]
bond_amort = [cell("BondStructure", dcol(H + k - 1) + "10") for k in range(1, 7)]
bond_avg   = [cell("BondStructure", dcol(H + k - 1) + "14") for k in range(1, 7)]
bond_int   = [cell("BondStructure", dcol(H + k - 1) + "16") for k in range(1, 7)]
net_proceeds = cell("BondStructure", "D24")

gross_ytm = cell("InvestorReturns", "D15")
net_ytm   = cell("InvestorReturns", "D16")
eir       = cell("InvestorReturns", "D17")
moic      = cell("InvestorReturns", "D18")
gross_cf  = [cell("InvestorReturns", dcol(t) + "8") for t in range(8)]   # t=0..7
net_cf    = [cell("InvestorReturns", dcol(t) + "12") for t in range(8)]

print("\n--- MODEL RENDERED ---")
print("opening face per bond-year:", bond_open)
print("amort per bond-year       :", bond_amort)
print("model interest (signed)   :", bond_int)
print("model avg balance         :", bond_avg)
print("net proceeds to issuer    :", net_proceeds)
print("gross YTM / net YTM / EIR :", gross_ytm, net_ytm, eir)
print("gross CF (t=0..7)         :", gross_cf)
print()

# ════════════════════════════════════════════════════════════════════════════
# CHECK 1 — Amortization profile: principal repayments sum EXACTLY to face,
#           outstanding never < 0, bond fully repaid at maturity. (INVARIANT)
# ════════════════════════════════════════════════════════════════════════════
amort_abs_model = [-a for a in bond_amort]   # model stores amort as negative
record("amort sums to face",
       abs(sum(amort_abs_model) - FACE) < 1e-9,
       FACE, sum(amort_abs_model), is_invariant=True)
record("outstanding never negative",
       all(c >= -1e-9 for c in bond_close),
       ">=0 all periods", min(bond_close), is_invariant=True)
record("fully amortized at maturity (close year6 == 0)",
       abs(bond_close[5]) < 1e-9,
       0.0, bond_close[5], is_invariant=True)
record("amortizing handled (4 equal repayments of face/4)",
       all(abs(amort_abs_model[i] - (FACE / 4 if i >= 2 else 0.0)) < 1e-9 for i in range(6)),
       [0, 0, 5, 5, 5, 5], amort_abs_model, is_invariant=True)

# ════════════════════════════════════════════════════════════════════════════
# CHECK 2 — Coupon_t == outstanding_face_t * coupon_rate  (ground truth:
#           clean-room). The bond is drawn in full at close and repays principal
#           at period-END, so the coupon accrues on the period-OPENING
#           OUTSTANDING face (= opening + that year's drawdown). This is the
#           standard bond convention and is now a genuine INVARIANT: the model
#           must reproduce the clean-room coupon schedule exactly.
#           (Fix 2026-06-11: model previously accrued on the (opening+closing)/2
#           AVERAGE balance, halving the year-1 coupon (0.65 vs 1.30) and
#           breaking the par-bond identity. The interest row now references the
#           outstanding face. avg_balance is retained only as a display row.)
# ════════════════════════════════════════════════════════════════════════════
model_coupon = [-i for i in bond_int]   # interest stored negative
coupon_on_outstanding_ok = all(abs(model_coupon[k] - coupon_true[k]) < 1e-6 for k in range(6))
record("Coupon_t == outstanding_face * rate (std bond convention)",
       coupon_on_outstanding_ok,
       coupon_true, model_coupon,
       note="coupon accrues on period-opening outstanding face",
       is_invariant=True)   # corrected: was is_invariant=False while the
                            # model accrued on the average balance (the defect).
if not coupon_on_outstanding_ok:
    bugs.append(
        "Coupon NOT on outstanding face. Year-1 coupon = "
        f"{model_coupon[0]} vs correct {coupon_true[0]}. Total model coupons "
        f"{sum(model_coupon):.4f} vs standard {sum(coupon_true):.4f}."
    )

# Total-coupon reconciliation (model coupons == outstanding-face * rate). The
# outstanding face for each bond-year is the model's CLOSE in the draw year
# (opening 0 + drawdown 20) and its OPEN in every later year — i.e. exactly the
# clean-room `opening_face` schedule. The expected leg is built clean-room from
# the spec face schedule, NOT from any model output (no circular grading). This
# is the model's OWN internal identity and SHOULD hold exactly (invariant).
# (Previously this pinned `coupon == avg_balance * rate`, which ENCODED the
#  buggy average-balance accrual; updated 2026-06-11 to the correct base.)
outstanding_face_truth = [round(of, 10) for of in opening_face]   # [20,20,20,15,10,5]
internal_coupon_ok = all(
    abs(model_coupon[k] - outstanding_face_truth[k] * COUPON) < 1e-9 for k in range(6)
)
record("model coupon == outstanding_face * rate (internal identity)",
       internal_coupon_ok, "outstanding_face*rate", "matches", is_invariant=True)

# ════════════════════════════════════════════════════════════════════════════
# CHECK 3 — YTM IDENTITY: at the model's reported YTM, NPV(gross CF)==0, and the
#           model YTM equals an independent npf.irr of the SAME rendered CF.
#           (INVARIANT — tests the IRR solver, not the cashflow economics.)
# ════════════════════════════════════════════════════════════════════════════
gross_cf_for_irr = gross_cf[:]                      # t=0..7 as rendered
ytm_npf = npf.irr(gross_cf_for_irr)
record("model Gross YTM == numpy_financial.irr(same CF)",
       abs(gross_ytm - ytm_npf) < 1e-7, ytm_npf, gross_ytm, is_invariant=True)
npv_at_ytm = sum(gross_cf_for_irr[t] / (1 + gross_ytm) ** t for t in range(len(gross_cf_for_irr)))
record("price==disc CF: NPV(gross CF @ model YTM) == 0",
       abs(npv_at_ytm) < 1e-6, 0.0, npv_at_ytm, is_invariant=True)
record("model EIR == model Gross YTM (same CF, IFRS9)",
       abs(eir - gross_ytm) < 1e-12, gross_ytm, eir, is_invariant=True)

net_ytm_npf = npf.irr(net_cf)
record("model Net YTM == numpy_financial.irr(net CF)",
       abs(net_ytm - net_ytm_npf) < 1e-7, net_ytm_npf, net_ytm, is_invariant=True)

# ════════════════════════════════════════════════════════════════════════════
# CHECK 4 — PAR ANCHOR (free textbook identity): a bond priced at par yields its
#           coupon. Clean-room par bond => YTM == coupon (6.50%). The MODEL'S
#           construction for the equivalent par bond must reproduce the same
#           identity. With the corrected outstanding-face coupon, the model's
#           implied par-YTM equals the coupon exactly -> genuine INVARIANT.
#           (Fix 2026-06-11: previously the model halved the first coupon
#           (avg-balance), so the implied par-YTM came out ~5.04% and this was
#           recorded as a DEFECT/bug with is_invariant=False. The coupon now
#           accrues on the outstanding face, restoring par-YTM == coupon.)
# ════════════════════════════════════════════════════════════════════════════
record("clean-room: par amortizer YTM == coupon (textbook anchor)",
       abs(par_ytm_cleanroom - COUPON) < 1e-9, COUPON, par_ytm_cleanroom, is_invariant=True)

# Model-equivalent par bond: gross CF with NO investor tx add-on (pure par price),
# using the MODEL'S coupon line + amort, t=0..6. Expected leg = COUPON, read
# straight from the YAML (independent of any model output).
model_par_cf = [-FACE] + [model_coupon[i] + amort_abs_model[i] for i in range(6)]
model_par_ytm = npf.irr(model_par_cf)
par_anchor_ok = abs(model_par_ytm - COUPON) < 1e-4
record("MODEL par-bond YTM == coupon (par-bond identity)",
       par_anchor_ok, COUPON, model_par_ytm,
       note="coupon on outstanding face restores par identity",
       is_invariant=True)   # corrected: was is_invariant=False while the
                            # avg-balance coupon broke the identity (the defect).
if not par_anchor_ok:
    bugs.append(
        f"Model priced at par yields {model_par_ytm*100:.3f}% vs coupon {COUPON*100:.3f}% "
        f"(gap {(COUPON-model_par_ytm)*100:.2f}pp). A par bond MUST yield its coupon; the "
        f"live Gross YTM is {gross_ytm*100:.2f}% (the residual spread above coupon is the "
        f"investor's {TX_BPS}bps transaction add-on, not a coupon defect)."
    )

# ════════════════════════════════════════════════════════════════════════════
# CHECK 5 — Macaulay / modified duration vs from-scratch clean-room. The model
#           renders NO duration cell -> SCOPE GAP. We still publish the
#           independent ground-truth value so reviewers have it.
# ════════════════════════════════════════════════════════════════════════════
DURATION_CELL_EXISTS = False  # confirmed by full BondStructure/InvestorReturns dump
record("Macaulay/modified duration rendered by model",
       DURATION_CELL_EXISTS,
       f"Mac={mac_dur_cleanroom:.4f}, Mod={mod_dur_cleanroom:.4f}",
       "NOT RENDERED", note="scope gap: no duration cell in workbook",
       is_invariant=False)
if not DURATION_CELL_EXISTS:
    bugs.append(
        "GAP: model renders no Macaulay/modified duration cell. Clean-room par-bond "
        f"Macaulay duration = {mac_dur_cleanroom:.4f}y, modified = {mod_dur_cleanroom:.4f}y "
        "(provided for reference; nothing in the workbook to reconcile against)."
    )

# ════════════════════════════════════════════════════════════════════════════
# CHECK 6 — Issuer all-in cost == npf.irr(issuer CF) and (with fees) > coupon.
#           No issuer-side all-in-cost cell exists in the model -> GAP. We build
#           the issuer cashflow from RENDERED net proceeds + RENDERED coupons +
#           amort and solve the IRR ourselves (clean-room).
# ════════════════════════════════════════════════════════════════════════════
# Independent check on net proceeds: net = face - arrange - legal - listing - rating
expected_net = FACE - FACE * ARRANGE_PCT - LEGAL - LISTING - RATING
record("net proceeds == face - all upfront fees (independent)",
       abs(net_proceeds - expected_net) < 1e-9, expected_net, net_proceeds,
       is_invariant=True)

issuer_cf = [net_proceeds] + [-(model_coupon[i] + amort_abs_model[i]) for i in range(6)]
issuer_all_in = npf.irr(issuer_cf)
ISSUER_CELL_EXISTS = False
record("issuer all-in cost rendered by model",
       ISSUER_CELL_EXISTS,
       f"clean-room irr={issuer_all_in:.4f}", "NOT RENDERED",
       note="scope gap: no issuer all-in-cost cell", is_invariant=False)
if not ISSUER_CELL_EXISTS:
    bugs.append(
        "GAP: no issuer all-in-cost cell. Clean-room issuer IRR (net proceeds "
        f"{net_proceeds:.3f} vs model coupons+principal) = {issuer_all_in*100:.3f}%. "
        f"With the corrected outstanding-face coupons it is ABOVE the {COUPON*100:.2f}% "
        "coupon, as the 'all-in > coupon when upfront fees exist' law requires; only "
        "the rendered cell is missing."
    )

# Sanity: with CORRECT coupons, issuer all-in WOULD exceed the coupon (proves the
# 'all-in > coupon' economic law holds once the coupon defect is removed).
issuer_cf_true = [expected_net] + [-(coupon_true[i] + amort_true[i]) for i in range(6)]
issuer_all_in_true = npf.irr(issuer_cf_true)
record("clean-room: issuer all-in (correct coupons) > coupon",
       issuer_all_in_true > COUPON, ">6.50%", f"{issuer_all_in_true*100:.3f}%",
       is_invariant=True)

# ════════════════════════════════════════════════════════════════════════════
# CHECK 7 — WHT plumbing: net coupon == gross coupon * (1 - WHT) each period;
#           principal NOT taxed. (INVARIANT on the model's own net-CF line.)
# ════════════════════════════════════════════════════════════════════════════
wht_ok = True
for t in range(1, 7):
    g = gross_cf[t]
    nft = net_cf[t]
    interest_part = model_coupon[t - 1]
    principal_part = amort_abs_model[t - 1]
    expected_net_t = interest_part * (1 - WHT) + principal_part
    if abs(nft - expected_net_t) > 1e-7:
        wht_ok = False
record("net CF == coupon*(1-WHT) + principal (WHT plumbing)",
       wht_ok, "coupon taxed, principal not", "matches" if wht_ok else "MISMATCH",
       is_invariant=True)

# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════
invariant_checks = [r for r in results if r[5]]
invariant_pass = [r for r in invariant_checks if r[1]]
all_checks = results
all_pass = [r for r in results if r[1]]

print("\n" + "=" * 70)
print(f"TOTAL checks: {len(all_checks)}  passed: {len(all_pass)}")
print(f"INVARIANT/consistency checks: {len(invariant_checks)}  passed: {len(invariant_pass)}")
print(f"DEFECTS / GAPS exposed: {len(bugs)}")
for b in bugs:
    print("  * " + b)
print("=" * 70)

# Harness exits 0 iff every genuine INVARIANT held. Defect-exposing checks are
# findings, not harness failures.
failed_invariants = [r for r in invariant_checks if not r[1]]
if failed_invariants:
    print("INVARIANT FAILURES (harness fails):")
    for r in failed_invariants:
        print("  !", r[0])
    sys.exit(1)
print("All invariants held. Defects/gaps reported above as findings.")
sys.exit(0)

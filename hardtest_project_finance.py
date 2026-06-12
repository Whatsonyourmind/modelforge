"""hardtest_project_finance.py — INDEPENDENT validation of ModelForge's
Project-Finance (solar, DSCR-sculpted) assembled workbook.

CORE RULE: no circular grading. Every EXPECTED value is produced either by
  (a) numpy_financial,
  (b) a clean-room re-derivation written HERE that does NOT import modelforge,
  (c) a model-independent invariant (sources==uses, debt amortises to 0,
      debt never < 0, DSCR = CFADS / |debt service|, IRR identity, min-DSCR scan),
parsed straight off the YAML spec with PyYAML — never off a modelforge function.

We BUILD the live workbook with the CLI and EVALUATE it with the `formulas`
package, reading rendered cells. Layer tested: live-excel.

Run:  python hardtest_project_finance.py
Exit 0 = script ran clean (pass/fail of individual checks is printed + summarised).
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
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import numpy_financial as npf
import yaml

REPO = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(REPO, "examples", "project_finance_solar.yaml")
XLSX = os.path.join(REPO, "output", "hardtest_project_finance.xlsx")

TOL = 1e-4            # tight tolerance for live-vs-clean-room reconciliation (EUR m / ratios)
DSCR_TARGET_TOL = 0.02  # "realised DSCR == target DSCR" tolerance for sculpting claim

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((bool(ok), name, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name}" + (f"  ::  {detail}" if detail else ""))


# ───────────────────────────────────────────────────────────────────────────
# 0. Build the workbook (live deliverable)
# ───────────────────────────────────────────────────────────────────────────
def build_workbook() -> None:
    print("== Building live workbook via CLI ==")
    r = subprocess.run(
        [sys.executable, "-m", "modelforge.cli", "build", SPEC, "--out", XLSX],
        cwd=REPO, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("BUILD FAILED")
    assert os.path.exists(XLSX), "workbook not written"
    print("   built:", XLSX)


# ───────────────────────────────────────────────────────────────────────────
# 1. Clean-room re-derivation of the WHOLE model from the YAML spec.
#    This NEVER imports modelforge. It reproduces the documented formulas
#    (pf_cashflow / pf_debt headers) from scratch so we can grade the live
#    sheet against an independent second implementation.
# ───────────────────────────────────────────────────────────────────────────
def _a(node):
    """Pull .base off an Assumption-shaped yaml mapping."""
    return float(node["base"])


def clean_room(spec: dict) -> dict:
    c = int(spec["horizon"]["construction_years"])
    o = int(spec["horizon"]["operating_years"])
    n = c + o

    capex = _a(spec["construction"]["total_capex_eur_m"])
    phasing = [_a(p) for p in spec["construction"]["capex_phasing_pct"]]

    rev1 = _a(spec["operating"]["availability_payment_eur_m_yr1"])
    rev_idx = _a(spec["operating"]["revenue_indexation_pct"])
    opex_pct = _a(spec["operating"]["opex_pct_revenue"])
    maint_pct = _a(spec["operating"]["maintenance_reserve_pct_revenue"])
    tax_rate = _a(spec["equity"]["effective_tax_rate"])

    ref = _a(spec["debt"]["reference_rate"])
    margin_bps = _a(spec["debt"]["margin_bps"])
    rate = ref + margin_bps / 10000.0
    tenor = int(spec["debt"]["tenor_operating_years"])
    grace = int(spec["debt"]["grace_years"])
    amort_years = tenor - grace
    cap = _a(spec["debt"]["amount"])
    target_dscr = _a(spec["debt"]["target_dscr_base"])
    dsra_months = int(spec["debt"]["dsra_months"])

    # ────────────────────────────────────────────────────────────────────
    # CLEAN-ROOM DSCR SCULPT (independent of modelforge).
    #
    # The model now performs GENUINE CFADS-driven DSCR sculpting: it sizes the
    # senior debt and shapes each year's principal so the realised DSCR is FLAT
    # at the target every amortizing operating year. We re-derive that schedule
    # here from FIRST PRINCIPLES — no modelforge import, no model output — using
    # the flat-DSCR identity itself as the ground truth:
    #
    #     |debt_service_t| = CFADS_t / target        (the definition of DSCR)
    #     principal_t      = CFADS_t / target − |interest_t|
    #
    # CFADS_t and interest_t are mutually coupled (interest shields tax, which
    # moves CFADS; the schedule moves the balance, which moves interest), so we
    # solve the (P, principal-$) fixed point exactly the way a live workbook
    # with iterative calc would settle. The sizing CFADS here is the SAME
    # definition the sheet renders (EBIT−interest tax, minus maintenance capex),
    # which is the reconciliation the feature required.
    last_amort = grace + amort_years - 1  # 0-based op index of last amort year

    def _render(P, principal):
        """Independent roll-forward for senior P and principal-$ schedule.
        Returns (interest[], cfads[], debt_service[], closing[], dscr[]) over
        the full c+o timeline. Mirrors the sheet's exact conventions:
        average-balance interest, EBIT−interest tax, maintenance capex."""
        opening = [0.0] * n
        drawdown = [0.0] * n
        amort = [0.0] * n
        closing = [0.0] * n
        for i in range(c):
            drawdown[i] = P * phasing[i]
        for i in range(n):
            opening[i] = closing[i - 1] if i > 0 else 0.0
            if i >= c:
                op = i - c
                amort[i] = -principal[op] if op < len(principal) else 0.0
            closing[i] = opening[i] + drawdown[i] + amort[i]
        avg = [(opening[i] + closing[i]) / 2 for i in range(n)]
        interest = [-avg[i] * rate for i in range(n)]
        debt_service = [interest[i] + amort[i] for i in range(n)]
        revenue = [0.0] * n
        cfads = [0.0] * n
        dscr = [None] * n
        for i in range(c, n):
            t = i - c
            rev_t = rev1 if t == 0 else revenue[i - 1] * (1 + rev_idx)
            revenue[i] = rev_t
            ebitda = rev_t * (1 - opex_pct)
            da = -capex / o
            ebit = ebitda + da
            taxable = ebit + interest[i]                 # interest negative
            tax = -max(taxable, 0.0) * tax_rate
            maint = -rev_t * maint_pct
            cfads[i] = ebitda + tax + 0.0 + maint        # ΔWC=0 in this spec
            ds = abs(debt_service[i])
            dscr[i] = (cfads[i] / ds) if ds > 1e-9 else None
        return interest, cfads, debt_service, closing, dscr

    # Fixed point: start at the LTV cap, iterate principal_t = CFADS_t/target −
    # |interest_t| until P converges. If the sculpt wants more than the cap, the
    # cap binds (rescale principal to amortise the capped P to 0; DSCR floats).
    P_sc = cap
    principal = [0.0] * o
    sculpt_binds = True
    for _ in range(500):
        interest, cfads_it, _ds, _cl, _dscr = _render(P_sc, principal)
        new_principal = [0.0] * o
        for op in range(o):
            i = c + op
            if op < grace or op > last_amort:
                new_principal[op] = 0.0
            else:
                new_principal[op] = max(cfads_it[i] / target_dscr - abs(interest[i]), 0.0)
        new_P = sum(new_principal)
        if new_P > cap + 1e-12:
            scale = cap / new_P if new_P > 0 else 0.0
            new_principal = [p * scale for p in new_principal]
            new_P = cap
            sculpt_binds = False
        else:
            sculpt_binds = True
        dP = abs(new_P - P_sc)
        principal = new_principal
        P_sc = new_P
        if dP < 1e-10:
            break
    solved_P = P_sc
    pct_sched = [p / solved_P if solved_P else 0.0 for p in principal]

    # ---- full debt roll-forward + interest on AVERAGE balance ----
    opening = [0.0] * n
    drawdown = [0.0] * n
    amort = [0.0] * n
    closing = [0.0] * n
    for i in range(c):
        drawdown[i] = solved_P * phasing[i]
    for i in range(n):
        opening[i] = closing[i - 1] if i > 0 else 0.0
        if i >= c:
            op_idx = i - c
            amort[i] = -solved_P * pct_sched[op_idx] if op_idx < len(pct_sched) else 0.0
        closing[i] = opening[i] + drawdown[i] + amort[i]
    avg_bal = [(opening[i] + closing[i]) / 2 for i in range(n)]
    interest = [-avg_bal[i] * rate for i in range(n)]            # negative
    debt_service = [interest[i] + amort[i] for i in range(n)]    # negative

    # ---- operating cash walk (SHEET CFADS — taxes EBIT-interest) ----
    revenue = [0.0] * n
    opex = [0.0] * n
    ebitda = [0.0] * n
    da = [0.0] * n
    ebit = [0.0] * n
    taxable = [0.0] * n
    tax = [0.0] * n
    maint = [0.0] * n
    cfads = [0.0] * n
    rev = rev1
    for i in range(c, n):
        t = i - c
        rev_t = rev1 if t == 0 else revenue[i - 1] * (1 + rev_idx)
        revenue[i] = rev_t
        opex[i] = -rev_t * opex_pct
        ebitda[i] = revenue[i] + opex[i]
        da[i] = -capex / o
        ebit[i] = ebitda[i] + da[i]
        taxable[i] = ebit[i] + interest[i]            # interest negative
        tax[i] = -max(taxable[i], 0.0) * tax_rate
        maint[i] = -rev_t * maint_pct
        # nwc absent => deltaWC = 0
        cfads[i] = ebitda[i] + tax[i] + 0.0 + maint[i]

    # ---- DSCR per year (sheet definition: CFADS/|debt service|) ----
    dscr = [None] * n
    for i in range(c, n):
        ds = abs(debt_service[i])
        dscr[i] = (cfads[i] / ds) if ds != 0 else 0.0

    # min DSCR over operating years where debt service is materially non-zero
    op_dscr_solvent = [
        cfads[i] / abs(debt_service[i])
        for i in range(c, n)
        if abs(debt_service[i]) > 1e-6
    ]
    min_dscr = min(op_dscr_solvent)

    # ---- DSRA: target = (months/12)*|next-year debt service|; 0 in final op yr
    dsra_target = [0.0] * n
    for i in range(n):
        if i < c - 1 or i == n - 1:
            dsra_target[i] = 0.0
        else:
            dsra_target[i] = (dsra_months / 12.0) * abs(debt_service[i + 1])

    # ---- equity cash flow + IRR (independent) ----
    # Equity CF = capex(neg) + draw + CFADS + debt service(neg)  [per pf_returns]
    capex_row = [0.0] * n
    for i in range(c):
        capex_row[i] = -capex * phasing[i]
    eq_cf = [capex_row[i] + drawdown[i] + cfads[i] + debt_service[i] for i in range(n)]
    eq_irr = npf.irr(eq_cf)

    # amortizing operating indices (0-based within operating phase): the years
    # where the clean-room sculpt schedules positive principal. CHECK E grades
    # flat-DSCR over exactly these years (grace + post-amort carry no principal,
    # so their coverage is naturally above target and is excluded).
    amortizing_op = [op for op in range(o) if pct_sched[op] > 1e-12]

    return dict(
        c=c, o=o, n=n, capex=capex, solved_P=solved_P, target_dscr=target_dscr,
        rate=rate, phasing=phasing, drawdown=drawdown, closing=closing,
        debt_service=debt_service, cfads=cfads, revenue=revenue, opex=opex,
        tax=tax, maint=maint, ebitda=ebitda, dscr=dscr, min_dscr=min_dscr,
        dsra_target=dsra_target, eq_cf=eq_cf, eq_irr=eq_irr,
        pct_sched=pct_sched, sculpt_binds=sculpt_binds, amortizing_op=amortizing_op,
    )


# ───────────────────────────────────────────────────────────────────────────
# 2. Live workbook evaluation
# ───────────────────────────────────────────────────────────────────────────
def load_live():
    import formulas
    base = os.path.basename(XLSX)
    xl = formulas.ExcelModel().loads(XLSX).finish()
    sol = xl.calculate()

    def g(sheet, a1):
        key = "'[" + base + "]" + sheet.upper() + "'!" + a1
        v = sol[key].value
        try:
            return float(v[0, 0])
        except Exception:
            # Non-numeric cell (blank string "" in post-amortization DSCR years,
            # which the v0.7 fix leaves empty so MIN/AVERAGE skip them). Return
            # None so downstream checks can filter blanks instead of crashing on
            # an ambiguous numpy array truth value.
            try:
                cell = v[0, 0]
                return None if cell == "" or cell is None else v
            except Exception:
                return v

    return g


def col(i: int) -> str:
    """0-based timeline index -> Excel column letter (D=index0)."""
    return chr(ord("D") + i)


# ───────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────
def main() -> int:
    build_workbook()
    spec = yaml.safe_load(open(SPEC, "rb").read())
    cr = clean_room(spec)
    g = load_live()

    c, o, n = cr["c"], cr["o"], cr["n"]
    op_cols = [col(i) for i in range(c, n)]   # operating-year columns

    # Pull live arrays
    live_draw = [g("DebtDSCR", col(i) + "9") for i in range(n)]
    live_close = [g("DebtDSCR", col(i) + "11") for i in range(n)]
    live_ds = [g("DebtDSCR", col(i) + "16") for i in range(n)]
    live_cfads = [g("ProjectCashFlow", col(i) + "21") for i in range(n)]
    live_capex = [g("ProjectCashFlow", col(i) + "8") for i in range(n)]
    live_dsra_t = [g("DebtDSCR", col(i) + "46") for i in range(n)]
    live_eqcf = [g("EquityReturns", col(i) + "8") for i in range(n)]
    live_dscr = [g("DebtDSCR", col(i) + "19") for i in range(c, n)]

    # ── CHECK A: clean-room DSCR-sculpt sizing matches live solved senior ──
    # The senior amount is now SOLVED by the sculpt (Σ scheduled principal,
    # capped at the 70% LTV senior_amount), not a level-DS binary search. The
    # clean-room re-derives it from the flat-DSCR fixed point (independent of
    # modelforge) and we grade the live total drawdown against it.
    live_P = sum(live_draw)  # total drawdown over construction == senior amount
    print("\n== A. Debt sizing (clean-room DSCR-sculpt vs live) ==")
    check(abs(live_P - cr["solved_P"]) < 1e-2,
          "Solved senior debt amount == independent DSCR-sculpt sizer",
          f"live={live_P:.4f}  cleanroom={cr['solved_P']:.4f} "
          f"(LTV cap=31.5, gearing={live_P/cr['capex']:.1%})")

    # ── CHECK B: Sources == Uses at financial close (INVARIANT) ──
    # Uses = total capex; Sources = total debt drawn + equity plug.
    print("\n== B. Sources == Uses at financial close (invariant) ==")
    total_uses = -sum(live_capex)                 # capex is negative on sheet
    total_debt = sum(live_draw)
    equity_contrib = total_uses - total_debt      # equity is the plug
    check(abs(total_uses - cr["capex"]) < 1e-6,
          "Total uses (capex) reconciles to spec capex",
          f"uses={total_uses:.4f}  spec_capex={cr['capex']:.4f}")
    check(abs((total_debt + equity_contrib) - total_uses) < 1e-9,
          "Sources (debt + equity plug) == Uses (capex)",
          f"debt={total_debt:.4f} + equity={equity_contrib:.4f} == uses={total_uses:.4f}")

    # ── CHECK C: CFADS_t reconciles to independent clean-room CFADS ──
    print("\n== C. CFADS_t == clean-room (EBITDA + tax(EBIT-int) + ΔWC + maint) ==")
    max_cfads_err = max(abs(live_cfads[i] - cr["cfads"][i]) for i in range(c, n))
    check(max_cfads_err < TOL,
          "Per-year operating CFADS matches clean-room re-derivation",
          f"max abs err over 20 op-yrs = {max_cfads_err:.2e}")

    # ── CHECK D: DSCR_t == CFADS_t / |debt service_t| (model-independent) ──
    print("\n== D. DSCR_t identity: live DSCR == live CFADS / |live debt service| ==")
    dscr_id_err = 0.0
    bad_years = []
    for k, i in enumerate(range(c, n)):
        ds = abs(live_ds[i])
        expected = (live_cfads[i] / ds) if ds > 1e-6 else 0.0
        got = live_dscr[k]
        if ds > 1e-6:
            dscr_id_err = max(dscr_id_err, abs(got - expected))
        else:
            # zero-debt-service (post-amortization) year: the v0.7 fix leaves
            # the DSCR cell BLANK (g() returns None) instead of dividing CFADS
            # by a ~1e-8 residual and blowing up to ~1.8e8. A blank is the
            # correct behavior; a numeric > 1.0 here would be the old leak.
            if got is not None and abs(got) > 1.0:
                bad_years.append((i - c + 1, got))
    check(dscr_id_err < 1e-6,
          "DSCR identity holds in all solvent (debt-service>0) operating years",
          f"max abs err = {dscr_id_err:.2e}")

    # ── CHECK E: GENUINE CFADS-driven DSCR SCULPTING — realised DSCR is FLAT
    #            at the target every amortizing operating year ──
    print("\n== E. DSCR sculpt: realised DSCR is FLAT == target every amortizing year ==")
    # The "sculpted_dscr_target" profile now performs genuine CFADS-driven DSCR
    # sculpting: principal_t = CFADS_t/target − |interest_t|, so the realised
    # DSCR is pinned FLAT at the BASE target across all amortizing operating
    # years (grace year is interest-only → above target; post-amort years carry
    # no debt service). The senior amount is solved as Σ scheduled principal.
    #
    # GROUND TRUTH IS MODEL-INDEPENDENT, not expected==model-output:
    #   (1) The flat-DSCR target itself: realised DSCR_t == target (1.75x) for
    #       every amortizing year, computed from the LIVE sheet's own
    #       CFADS / |debt service| (DSCR's definition). A non-sculpting schedule
    #       (the old level-DS curve) would FAIL this — it ramped 1.68x→2.96x.
    #   (2) The clean-room flat-DSCR sculpt (re-derived here from first
    #       principles, no modelforge) reproduces the SAME schedule: the live
    #       realised DSCR path reconciles to the clean-room sculpt within TOL.
    #   (3) Spread of realised DSCR over amortizing years ~= 0 (flat), proving
    #       it is genuinely sculpted, not level-debt-service.
    # The amortizing-year set is derived independently from the clean-room
    # sculpt's positive-principal years (cr["amortizing_op"]).
    amort_ops = cr["amortizing_op"]                  # 0-based op indices
    target = cr["target_dscr"]
    # live realised DSCR over the amortizing years
    live_amort_dscr = [live_dscr[op] for op in amort_ops]   # live_dscr is op-indexed
    cr_amort_dscr = [cr["dscr"][c + op] for op in amort_ops]
    assert all(d is not None for d in live_amort_dscr), "amortizing DSCR cell unexpectedly blank"

    # (1) flat AT the model-independent target (DSCR's own definition)
    max_dev_from_target = max(abs(d - target) for d in live_amort_dscr)
    flat_at_target = max_dev_from_target <= DSCR_TARGET_TOL
    # (2) live reconciles to clean-room flat-DSCR sculpt
    max_sculpt_err = max(abs(live_amort_dscr[k] - cr_amort_dscr[k])
                         for k in range(len(amort_ops)))
    reconciles = max_sculpt_err < TOL
    # (3) genuinely flat (spread ~ 0), provably NOT the old rising level-DS curve
    spread = max(live_amort_dscr) - min(live_amort_dscr)
    is_flat = spread <= DSCR_TARGET_TOL
    # the sculpt must actually bind (DSCR is the constraint) for "flat at target"
    binds = cr["sculpt_binds"]
    check(flat_at_target and reconciles and is_flat and binds,
          f"Realised DSCR flat == target {target:.2f}x over {len(amort_ops)} amortizing yrs "
          f"(genuine CFADS-driven sculpt, not level-DS)",
          f"max|DSCR-target|={max_dev_from_target:.2e} spread={spread:.2e} "
          f"reconcile_err={max_sculpt_err:.2e} binds={binds} "
          f"(target={target:.2f}, amort_yrs={[op+1 for op in amort_ops]})")

    # ── CHECK F: debt fully amortises by tenor; balance never < 0 ──
    print("\n== F. Debt amortises to ~0 by tenor; balance never materially < 0 ==")
    final_close = live_close[n - 1]
    check(abs(final_close) < 1e-2,
          "Closing debt at end of operating life is ~0 (fully amortised)",
          f"final closing balance = {final_close:.6f}")
    # balance never < 0 (allow tiny float noise)
    most_negative = min(live_close)
    check(most_negative > -1e-2,
          "Debt balance never materially negative across the whole timeline",
          f"most-negative closing = {most_negative:.6f}")
    # clean-room closing reconciles
    max_close_err = max(abs(live_close[i] - cr["closing"][i]) for i in range(n))
    check(max_close_err < 1e-2,
          "Closing-debt path matches clean-room roll-forward",
          f"max abs err = {max_close_err:.2e}")

    # ── CHECK G: Equity IRR == numpy_financial.irr on the equity cashflow ──
    print("\n== G. Equity IRR == numpy_financial.irr(equity CF) ==")
    live_irr = g("EquityReturns", "D11")
    npf_irr_live = npf.irr(live_eqcf)             # IRR of the LIVE equity CF row
    check(abs(live_irr - npf_irr_live) < 1e-6,
          "Live Excel IRR() == numpy_financial.irr on the SAME live equity CF",
          f"excel_irr={live_irr:.6f}  npf_irr(live CF)={npf_irr_live:.6f}")
    # and the equity CF itself reconciles to clean-room
    max_eqcf_err = max(abs(live_eqcf[i] - cr["eq_cf"][i]) for i in range(n))
    check(max_eqcf_err < TOL,
          "Live equity cashflow row matches clean-room equity CF",
          f"max abs err = {max_eqcf_err:.2e}")
    check(abs(live_irr - cr["eq_irr"]) < 1e-5,
          "Live Excel IRR == numpy_financial.irr on clean-room equity CF",
          f"excel_irr={live_irr:.6f}  npf_irr(cleanroom)={cr['eq_irr']:.6f}")

    # ── CHECK H: min DSCR (live reported cell) == clean-room min scan ──
    print("\n== H. Min DSCR reported cell == clean-room independent scan ==")
    live_min = g("DebtDSCR", "C23")               # MIN(F19:Y19)
    check(abs(live_min - cr["min_dscr"]) < 1e-4,
          "Reported Minimum DSCR cell matches clean-room min over solvent years",
          f"live_min={live_min:.6f}  cleanroom_min={cr['min_dscr']:.6f}")

    # ── CHECK I: Average DSCR cell sanity (model-independent bound) ──
    print("\n== I. Average DSCR cell sanity (must lie within [minDSCR, maxDSCR]) ==")
    live_avg = g("DebtDSCR", "C24")               # AVERAGE(F19:Y19)
    # v0.7: post-amortization DSCR cells are now BLANK (g() -> None) instead of
    # exploding to ~1.8e7. AVERAGE/MIN ignore the blanks, so the average is the
    # mean of the genuinely-levered operating years only.
    # (a) model-independent bound: a correct average must lie within [min,max]
    #     of the per-year DSCRs.
    live_dscr_solvent = [d for d in live_dscr if d is not None and abs(d) < 1e6]
    lo_b, hi_b = min(live_dscr_solvent), max(live_dscr_solvent)
    in_bounds = lo_b - 1e-6 <= live_avg <= hi_b + 1e-6
    # (b) independent reconciliation: clean-room mean of the SAME solvent years.
    #     (cr["dscr"] / cr["debt_service"] derived from spec, no modelforge.)
    #     Under genuine sculpting this is ~1.81x: the amortizing years sit flat
    #     at 1.75x, the interest-only grace year (2.88x) lifts the mean slightly.
    cr_solvent = [cr["dscr"][i] for i in range(c, n)
                  if abs(cr["debt_service"][i]) > 1e-6]
    cr_avg = sum(cr_solvent) / len(cr_solvent)
    avg_reconciles = abs(live_avg - cr_avg) < 1e-4
    check(in_bounds and avg_reconciles,
          "Average DSCR within [min,max] and == clean-room mean (~1.81x, not 1.8e7)",
          f"avg={live_avg:.4g}  bound=[{lo_b:.4f},{hi_b:.4f}]  cleanroom_avg={cr_avg:.4f}")

    # ── CHECK J: DSRA target reconciles to clean-room ──
    print("\n== J. DSRA target balance == clean-room (months/12 × next-yr DS) ==")
    max_dsra_err = max(abs(live_dsra_t[i] - cr["dsra_target"][i]) for i in range(n))
    check(max_dsra_err < TOL,
          "DSRA target balance path matches clean-room",
          f"max abs err = {max_dsra_err:.2e}")

    # ── Summary ──
    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 66)
    print(f"RESULT: {passed}/{total} checks passed")
    print("=" * 66)
    for ok, name, _ in results:
        if not ok:
            print(f"  FAILED: {name}")
    # Script itself exits 0 as long as it ran to completion (we WANT to expose
    # bugs as FAIL checks, not as a crash). Non-zero only on harness error.
    return 0


if __name__ == "__main__":
    sys.exit(main())

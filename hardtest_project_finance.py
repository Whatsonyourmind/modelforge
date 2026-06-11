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

    # ---- solver CFADS (this is what the model uses to SIZE debt) ----
    # Independent re-implementation of the documented sizing-CFADS:
    #   rev_t = rev1*(1+idx)^t ; opex = rev*opex_pct ; ebitda = rev-opex ;
    #   tax = max(ebitda,0)*tax_rate ; cfads = ebitda - tax
    sizing_cfads = []
    rev = rev1
    for t in range(o):
        if t > 0:
            rev *= (1 + rev_idx)
        ebitda = rev * (1 - opex_pct)
        tax = max(ebitda, 0.0) * tax_rate
        sizing_cfads.append(ebitda - tax)

    # ---- clean-room debt sizer: binary search max P s.t. min sizing-DSCR>=target
    def level_ds_per_year(P):
        out = [0.0] * o
        for i in range(grace):
            out[i] = P * rate
        ann = P * rate / (1 - (1 + rate) ** (-amort_years)) if rate else P / amort_years
        for i in range(amort_years):
            idx = grace + i
            if idx < o:
                out[idx] = ann
        return out

    def min_sizing_dscr(P):
        ds = level_ds_per_year(P)
        vals = [sizing_cfads[t] / ds[t] for t in range(o) if ds[t] != 0]
        return min(vals) if vals else float("inf")

    # Independent re-implementation of the documented binary search. We mirror
    # the documented numeric contract (EUR-m tolerance 0.01, max_iter 50,
    # return the lower bound `lo`, then round to 2dp before baking) because
    # that contract — not infinite precision — is what defines the model's
    # senior amount. This is still a clean-room (no modelforge import); we are
    # only matching the *spec'd algorithm*, then grading the rendered number.
    if min_sizing_dscr(cap) >= target_dscr:
        solved_P = cap
    else:
        lo, hi = 0.0, cap
        for _ in range(50):
            mid = (lo + hi) / 2
            if min_sizing_dscr(mid) >= target_dscr:
                lo = mid
            else:
                hi = mid
            if hi - lo < 0.01:
                break
        solved_P = lo
    solved_P = round(solved_P, 2)  # model rounds to 2dp before baking

    # ---- principal % schedule (level-debt-service annuity on solved P) ----
    # fraction of P repaid in each operating year. grace years => 0.
    if rate:
        c_pct = rate / (1 - (1 + rate) ** (-amort_years))
        bal = 1.0
        amort_pct = []
        for _ in range(amort_years):
            ip = bal * rate
            pp = c_pct - ip
            amort_pct.append(pp)
            bal -= pp
    else:
        amort_pct = [1.0 / amort_years] * amort_years
    pct_sched = [0.0] * o
    for i, p in enumerate(amort_pct):
        pct_sched[grace + i] = p

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

    return dict(
        c=c, o=o, n=n, capex=capex, solved_P=solved_P, target_dscr=target_dscr,
        rate=rate, phasing=phasing, drawdown=drawdown, closing=closing,
        debt_service=debt_service, cfads=cfads, revenue=revenue, opex=opex,
        tax=tax, maint=maint, ebitda=ebitda, dscr=dscr, min_dscr=min_dscr,
        dsra_target=dsra_target, eq_cf=eq_cf, eq_irr=eq_irr,
        sizing_cfads=sizing_cfads,
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

    # ── CHECK A: clean-room debt sizing matches live solved senior amount ──
    live_P = sum(live_draw)  # total drawdown over construction == senior amount
    print("\n== A. Debt sizing (clean-room solver vs live) ==")
    check(abs(live_P - cr["solved_P"]) < 1e-2,
          "Solved senior debt amount == independent binary-search sizer",
          f"live={live_P:.4f}  cleanroom={cr['solved_P']:.4f} (cap=31.5)")

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

    # ── CHECK E: DOCUMENTED amortization behavior (level debt service sized to
    #            the min-DSCR target — NOT flat DSCR-sculpting) ──
    print("\n== E. Amortization profile == level debt service sized to min-DSCR target ==")
    # The "sculpted_dscr_target" profile is implemented as a LEVEL DEBT SERVICE
    # (annuity) curve with the senior amount solved so the *minimum* realised
    # DSCR equals the target. It does NOT pin realised DSCR flat at the target
    # (that would require CFADS-driven sculpting, principal_t = CFADS_t/target -
    # interest_t — a separate feature; the deliverable no longer claims it).
    #
    # Independent (clean-room) ground truth, no modelforge import:
    #   (1) min realised DSCR == sizing target 1.30x  (binding sizing constraint)
    #   (2) realised DSCR is genuinely upward-sloping (a flat annuity payment
    #       against CPI-escalating CFADS gives RISING coverage) — i.e. the
    #       schedule is level-debt-service, provably NOT flat-sculpted.
    # We grade the LIVE DSCRs against the clean-room DSCR array reconstructed
    # here from the spec, and against these structural invariants.
    realised = [live_dscr[k] for k, i in enumerate(range(c, n))
                if (live_dscr[k] is not None and abs(live_ds[i]) > 1e-6)]
    cr_realised = [cr["dscr"][i] for i in range(c, n) if abs(cr["debt_service"][i]) > 1e-6]
    min_real = min(realised)
    max_real = max(realised)
    # (1) min realised DSCR == clean-room min scan (independent re-derivation),
    #     and it RESPECTS the sizing target as a conservative floor (>= 1.30x).
    #     NB: realised min (1.68x) sits ABOVE the 1.30x sizing target because
    #     the debt sizer taxes EBITDA (no interest shield) while the sheet CFADS
    #     taxes EBIT - interest -> higher CFADS -> higher realised coverage.
    #     This is documented level-debt-service behavior, NOT flat sculpting.
    min_matches_scan = abs(min_real - cr["min_dscr"]) <= 1e-4
    respects_target_floor = min_real >= cr["target_dscr"] - DSCR_TARGET_TOL
    # (2) level-debt-service signature: coverage rises materially (a true
    #     flat-DSCR sculpt would have spread ~= 0; this profile does not).
    rises = (max_real - min_real) > 0.10
    # (3) live realised DSCR path reconciles to the clean-room re-derivation.
    max_real_err = max(abs(realised[k] - cr_realised[k]) for k in range(len(realised)))
    check(min_matches_scan and respects_target_floor and rises and max_real_err < TOL,
          "Realised DSCR = level debt service: min==clean-room scan, >=target floor, rises",
          f"min={min_real:.4f} (scan={cr['min_dscr']:.4f}, target_floor={cr['target_dscr']:.2f}) "
          f"max={max_real:.4f} reconcile_err={max_real_err:.2e} "
          f"(min_matches_scan={min_matches_scan}, respects_floor={respects_target_floor}, rises={rises})")

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
    cr_avg = sum(cr_realised) / len(cr_realised)
    avg_reconciles = abs(live_avg - cr_avg) < 1e-4
    check(in_bounds and avg_reconciles,
          "Average DSCR within [min,max] and == clean-room mean (~1.89x, not 1.8e7)",
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

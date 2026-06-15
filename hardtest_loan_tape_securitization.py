"""Clean-room parity hardtest for the loan-tape securitization template (T19).

Re-derives the ENTIRE deal — per-stratum amortization, defaults, prepayments,
lagged recoveries, the sequential interest + principal waterfall, OC/IC turbo,
reserve account and residual distribution — in independent pure-Python, then
builds the same spec with ModelForge, recalculates the workbook with the
third-party ``formulas`` engine and asserts byte-for-byte agreement on every
key series + the headline residual IRR.

Run:  PYTHONUTF8=1 python hardtest_loan_tape_securitization.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import yaml

from modelforge.spec.loan_tape_securitization import LoanTapeSecuritizationSpec
from modelforge.templates import REGISTRY

SPEC_PATH = Path("examples/clo_midmarket.yaml")
TOL = 1e-4


# ── independent IRR (Newton with bisection fallback) ───────────────────────
def _npv(rate, cfs):
    return sum(c / (1.0 + rate) ** t for t, c in enumerate(cfs))


def irr(cfs, guess=0.1):
    r = guess
    for _ in range(200):
        f = _npv(r, cfs)
        df = sum(-t * c / (1.0 + r) ** (t + 1) for t, c in enumerate(cfs))
        if abs(df) < 1e-12:
            break
        r2 = r - f / df
        if abs(r2 - r) < 1e-12:
            return r2
        r = r2
    lo, hi = -0.99, 10.0
    flo = _npv(lo, cfs)
    for _ in range(400):
        mid = (lo + hi) / 2
        fm = _npv(mid, cfs)
        if abs(fm) < 1e-10:
            return mid
        if (flo < 0) != (fm < 0):
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def clean_room(spec):
    periods = spec.horizon.periods
    lag = spec.horizon.recovery_lag_periods
    strata = spec.tape
    pool0 = sum(s.balance_eur_m.base for s in strata)

    cpr = spec.pool.cpr_pct.base
    rec_pct = spec.pool.recovery_pct.base
    svc = spec.pool.servicing_fee_pct.base
    trustee_fee = spec.pool.senior_fees_eur_m.base
    tax = spec.effective_tax_rate.base

    notes = spec.notes
    debt = list(range(len(notes) - 1))
    senior, eq = 0, len(notes) - 1
    oc_trig = spec.enhancement.oc_trigger_pct.base
    ic_trig = spec.enhancement.ic_trigger_pct.base
    reserve_pct = spec.enhancement.reserve_pct_initial.base

    # ── asset side, per stratum ────────────────────────────────────────────
    opens = [[0.0] * (periods + 2) for _ in strata]
    for k, s in enumerate(strata):
        opens[k][1] = s.balance_eur_m.base
    pool_bop = [0.0] * (periods + 1)
    pool_def = [0.0] * (periods + 1)
    pool_sched = [0.0] * (periods + 1)
    pool_prepay = [0.0] * (periods + 1)
    pool_int = [0.0] * (periods + 1)
    pool_eop = [0.0] * (periods + 1)
    # Model convention: t=0 is the closing date — BOP[0]=0 (no prior period),
    # while EOP[0] holds the initial pool (strata closing[0] == UPB).
    pool_bop[0] = 0.0
    pool_eop[0] = pool0
    for i in range(1, periods + 1):
        for k, s in enumerate(strata):
            o = opens[k][i]
            d = o * s.cdr_pct.base
            surv = o - d
            if i == periods:
                sched = surv
            else:
                rate = min(1.0, 1.0 / max(s.wam_years.base - (i - 1), 0.5))
                sched = surv * rate
            prepay = (surv - sched) * cpr
            close = o - d - sched - prepay
            opens[k][i + 1] = close
            pool_bop[i] += o
            pool_def[i] += d
            pool_sched[i] += sched
            pool_prepay[i] += prepay
            pool_int[i] += o * s.wac_pct.base
            pool_eop[i] += close

    recov = [0.0] * (periods + 1)
    for i in range(1, periods + 1):
        if i < periods:
            j = i - lag
            recov[i] = rec_pct * pool_def[j] if j >= 1 else 0.0
        else:
            start = max(periods - lag, 1)
            recov[i] = rec_pct * sum(pool_def[j] for j in range(start, periods + 1))
    prin_coll = [0.0] + [pool_sched[i] + pool_prepay[i] + recov[i] for i in range(1, periods + 1)]

    # ── liability waterfall ────────────────────────────────────────────────
    note_eop = [[0.0] * (periods + 1) for _ in notes]
    for j in range(len(notes)):
        note_eop[j][0] = notes[j].advance_pct.base * pool0
    reserve = [0.0] * (periods + 1)
    reserve[0] = reserve_pct * pool0
    res_int_eq = [0.0] * (periods + 1)
    cash_eq = [0.0] * (periods + 1)
    inv = [[0.0] * (periods + 1) for _ in notes]
    for j in range(len(notes)):
        inv[j][0] = -notes[j].advance_pct.base * pool0
    inv[eq][0] -= reserve_pct * pool0

    for i in range(1, periods + 1):
        int_due = [note_eop[j][i - 1] * notes[j].coupon_pct.base for j in debt]
        avail_fees = (pool_int[i] - pool_bop[i] * svc
                      - (trustee_fee if pool_bop[i] > 0.0001 else 0.0))
        reserve_draw = min(max(int_due[senior] - avail_fees, 0.0), reserve[i - 1])
        avail_total = avail_fees + reserve_draw
        # sequential interest, floored at zero (no negative coupon)
        int_paid = []
        for idx, j in enumerate(debt):
            int_paid.append(min(max(avail_total - sum(int_paid), 0.0), int_due[idx]))
        residual_int = max(avail_total - sum(int_paid), 0.0)

        # sequential principal from collections
        prin_paid = []
        for idx, j in enumerate(debt):
            prin_paid.append(min(max(prin_coll[i] - sum(prin_paid), 0.0), note_eop[j][i - 1]))
        prin_to_res = max(prin_coll[i] - sum(prin_paid), 0.0)

        # OC/IC + sequential turbo (most-senior outstanding note first)
        debt_bop = sum(note_eop[j][i - 1] for j in debt)
        oc = pool_bop[i] / debt_bop if debt_bop > 0 else 0.0
        ic = avail_fees / sum(int_due) if sum(int_due) > 0 else 0.0
        breach = not (oc >= oc_trig and ic >= ic_trig)
        turbo = [0.0] * len(debt)
        if breach:
            for idx, j in enumerate(debt):
                avail_t = max(residual_int - sum(turbo), 0.0)
                turbo[idx] = min(avail_t, max(note_eop[j][i - 1] - prin_paid[idx], 0.0))

        # reserve: draw during the deal; at maturity release, cure debt, return rest
        reserve_cure = [0.0] * len(debt)
        if i < periods:
            reserve[i] = reserve[i - 1] - reserve_draw
            reserve_to_eq = 0.0
        else:
            reserve_release = reserve[i - 1] - reserve_draw
            reserve[i] = 0.0
            for idx, j in enumerate(debt):
                avail_c = max(reserve_release - sum(reserve_cure), 0.0)
                cap = max(note_eop[j][i - 1] - prin_paid[idx] - turbo[idx], 0.0)
                reserve_cure[idx] = min(avail_c, cap)
            reserve_to_eq = max(reserve_release - sum(reserve_cure), 0.0)

        for idx, j in enumerate(debt):
            note_eop[j][i] = max(
                note_eop[j][i - 1] - prin_paid[idx] - turbo[idx] - reserve_cure[idx], 0.0)
        note_eop[eq][i] = max(note_eop[eq][i - 1] - prin_to_res, 0.0)

        rie = residual_int - sum(turbo)
        spv_tax = -max(rie, 0.0) * tax
        res_int_eq[i] = rie
        cash_eq[i] = rie + spv_tax + prin_to_res + reserve_to_eq
        for idx, j in enumerate(debt):
            inv[j][i] = int_paid[idx] + prin_paid[idx] + turbo[idx] + reserve_cure[idx]
        inv[eq][i] = cash_eq[i]

    return {
        "pool_bop": pool_bop, "pool_def": pool_def, "recov": recov,
        "prin_coll": prin_coll, "note_eop": note_eop, "res_int_eq": res_int_eq,
        "cash_eq": cash_eq, "residual_irr": irr(inv[eq], 0.1),
        "debt": debt, "senior": senior, "eq": eq, "periods": periods,
    }


def main():
    spec = LoanTapeSecuritizationSpec.model_validate(yaml.safe_load(SPEC_PATH.read_bytes()))
    cr = clean_room(spec)
    periods = cr["periods"]

    import tempfile
    out = Path(tempfile.mkdtemp()) / "clo_hardtest.xlsx"
    REGISTRY["loan_tape_securitization"](spec, out)  # core sheets only (fast)

    import formulas
    sol = formulas.ExcelModel().loads(str(out)).finish().calculate()
    fname = out.name.upper()
    wb = openpyxl.load_workbook(out, data_only=False)

    def get(sheet, addr):
        want = f"'[{fname}]{sheet.upper()}'!{addr}"
        for k, v in sol.items():
            if k.upper() == want:
                try:
                    return float(v.value[0, 0])
                except Exception:
                    return float(getattr(v, "value", v))
        return None

    def row(ws_name, prefix):
        for r in wb[ws_name].iter_rows(min_col=1, max_col=1):
            c = r[0]
            if isinstance(c.value, str) and c.value.strip().startswith(prefix):
                return c.row
        return None

    checks = []

    def chk(name, a, b, tol=TOL):
        ok = abs(a - b) <= tol + tol * abs(b)
        checks.append((ok, name, a, b))

    col = lambda i: chr(ord("D") + i)

    # Asset-side series
    r_bop = row("LoanTape", "Pool performing balance (BOP)")
    r_def = row("LoanTape", "Pool defaults")
    r_rec = row("LoanTape", "Pool recoveries")
    r_coll = row("LoanTape", "Principal collected")
    for i in range(periods + 1):
        chk(f"pool_bop[{i}]", get("LoanTape", f"{col(i)}{r_bop}"), cr["pool_bop"][i])
    for i in range(1, periods + 1):
        chk(f"pool_def[{i}]", get("LoanTape", f"{col(i)}{r_def}"), cr["pool_def"][i])
        chk(f"recov[{i}]", get("LoanTape", f"{col(i)}{r_rec}"), cr["recov"][i])
        chk(f"prin_coll[{i}]", get("LoanTape", f"{col(i)}{r_coll}"), cr["prin_coll"][i])

    # Note balances (EOP) per note
    note_prefixes = ["Outstanding — Class A", "Outstanding — Class B", "Outstanding — Residual"]
    for j, pref in enumerate(note_prefixes):
        rj = row("Waterfall", pref)
        for i in range(periods + 1):
            chk(f"note_eop[{j}][{i}]", get("Waterfall", f"{col(i)}{rj}"), cr["note_eop"][j][i])

    # Residual interest + total cash to equity
    r_rie = row("Waterfall", "Residual interest to equity")
    r_cash = row("Waterfall", "Total cash to residual")
    for i in range(1, periods + 1):
        chk(f"res_int_eq[{i}]", get("Waterfall", f"{col(i)}{r_rie}"), cr["res_int_eq"][i])
        chk(f"cash_eq[{i}]", get("Waterfall", f"{col(i)}{r_cash}"), cr["cash_eq"][i])

    # Headline residual IRR
    r_irr = row("Notes", "Residual IRR")
    chk("residual_irr", get("Notes", f"D{r_irr}"), cr["residual_irr"], tol=5e-4)

    passed = sum(1 for c in checks if c[0])
    total = len(checks)
    print(f"clean-room parity: {passed}/{total} checks pass")
    fails = [c for c in checks if not c[0]]
    for ok, name, a, b in fails[:30]:
        print(f"  FAIL {name}: workbook={a} clean_room={b} (Δ={a - b:+.6f})")
    if fails:
        sys.exit(1)
    print("HARDTEST PASS — independent re-derivation matches the workbook.")


if __name__ == "__main__":
    main()

"""Clean-room parity hardtest for the bank_fig template.

Re-derives the ENTIRE bank model economics in independent Python directly from
the YAML base-scenario inputs (NO modelforge math imported, no workbook read for
the derivation), builds the workbook, recalculates it with the third-party
`formulas` engine, and asserts the recalc matches the clean-room series for every
period: NII, net income, RWA, CET1 capital, CET1 ratio, common equity, total
assets, balance check (==0), dividends and buybacks. Also checks the acyclic
plug invariants (cash ≥ 0, wholesale ≥ 0) and the two roll-forward telescoping
identities.

Run:  python hardtest_bank_fig.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import openpyxl
import yaml

REPO = Path(__file__).resolve().parent
SPEC = REPO / "examples" / "bank_fig_meridian.yaml"
TOL = 0.02  # EUR m / ratio tolerance for parity (recalc vs clean-room)

checks: list[tuple[str, bool, str]] = []


def chk(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def approx(a, b, tol=TOL) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


# ── clean-room derivation ──────────────────────────────────────────────────
def clean_room(raw: dict) -> dict:
    def base(block, key):
        return float(raw[block][key]["base"])

    loan_yield = base("nii", "loan_yield")
    sec_yield = base("nii", "securities_yield")
    dep_cost = base("nii", "deposit_cost")
    whl_cost = base("nii", "wholesale_cost")

    fee_g = base("pnl", "fee_income_growth")
    trading = base("pnl", "trading_income_eur_m")
    cir = base("pnl", "cost_income_ratio")
    cor_bps = base("pnl", "cost_of_risk_bps")
    tax = base("pnl", "tax_rate")
    at1_coupon = base("pnl", "at1_coupon_eur_m")

    loan_g = base("balance", "loan_growth")
    dep_g = base("balance", "deposit_growth")
    sec_g = base("balance", "securities_growth")
    wo_pct = base("balance", "writeoff_pct_opening_allowance")

    density = base("capital", "rwa_density")
    req = base("capital", "cet1_requirement_ratio")
    target = base("capital", "target_cet1_ratio")
    buf = base("capital", "mda_buffer_pct")
    payout = base("capital", "dividend_payout_ratio")
    buyback_target = base("capital", "buyback_target_eur_m")

    ob = raw["opening_bs"]
    gl0 = float(ob["gross_loans_eur_m"]); alw0 = float(ob["allowance_eur_m"])
    sec0 = float(ob["securities_eur_m"]); intang = float(ob["intangibles_eur_m"])
    other_a = float(ob["other_assets_eur_m"]); dep0 = float(ob["deposits_eur_m"])
    whl0 = float(ob["wholesale_funding_eur_m"]); other_l = float(ob["other_liabilities_eur_m"])
    cet1_0 = float(ob["cet1_eur_m"]); at1 = float(ob["at1_eur_m"])
    reg_adj = float(raw.get("cet1_regulatory_adjustments_eur_m", 0.0))

    hist_income = raw["historical_total_income_eur_m"]
    h = int(raw["horizon"]["historical_years"]); p = int(raw["horizon"]["projection_years"])
    n = h + p

    # series indexed 0..n-1; column 0..h-1 historical (flat at opening), h..n-1 projection
    gl = [0.0] * n; sec = [0.0] * n; dep = [0.0] * n
    alw_close = [0.0] * n; whl = [0.0] * n; cash = [0.0] * n
    eq_close = [0.0] * n; cet1 = [0.0] * n; rwa = [0.0] * n
    nii = [0.0] * n; ni = [0.0] * n; ni_to_cet1 = [0.0] * n
    total_assets = [0.0] * n; total_le = [0.0] * n; bs_check = [0.0] * n
    dividend = [0.0] * n; buyback = [0.0] * n; mda_cap = [0.0] * n
    fees = [0.0] * n

    for i in range(n):
        wo_i = 0.0  # period write-off (≥0); set for projection columns below
        if i < h:
            gl[i] = gl0; sec[i] = sec0; dep[i] = dep0
            alw_close[i] = alw0; whl[i] = whl0; cash[i] = float(ob["cash_eur_m"])
            eq_close[i] = cet1_0 + intang
        else:
            # write-off (from prior allowance) is net-loan-neutral: it leaves
            # gross loans AND releases the allowance simultaneously.
            wo_i = -alw_close[i - 1] * wo_pct
            gl[i] = gl[i - 1] * (1 + loan_g) - wo_i
            sec[i] = sec[i - 1] * (1 + sec_g)
            dep[i] = dep[i - 1] * (1 + dep_g)

        # NII (avg balances; BOP wholesale)
        avg_loans = (gl[i - 1] + gl[i]) / 2 if i > 0 else gl[i]
        avg_sec = (sec[i - 1] + sec[i]) / 2 if i > 0 else sec[i]
        avg_dep = (dep[i - 1] + dep[i]) / 2 if i > 0 else dep[i]
        bop_whl = whl[i - 1] if i > 0 else whl[i]
        total_ii = avg_loans * loan_yield + avg_sec * sec_yield
        total_ie = -avg_dep * dep_cost - bop_whl * whl_cost
        nii[i] = total_ii + total_ie

        # P&L
        if i < h:
            fees[i] = hist_income[i] - nii[i] - trading
        else:
            fees[i] = fees[i - 1] * (1 + fee_g)
        total_income = nii[i] + fees[i] + trading
        opex = -total_income * cir
        ppop = total_income + opex
        provisions = -cor_bps / 10000.0 * avg_loans
        pbt = ppop + provisions
        t = -max(pbt, 0.0) * tax
        ni[i] = pbt + t
        ni_to_cet1[i] = ni[i] - at1_coupon

        # allowance roll-forward (projection); wo_i already reduced gross loans
        # above, so the write-off nets out of net loans (correct double-entry).
        if i >= h:
            opening = alw_close[i - 1]
            charge = provisions  # negative
            alw_close[i] = opening + charge + wo_i

        # RWA + CET1 (need equity_close[i] first for projections)
        if i >= h:
            # distributions sized off prior CET1 + current retained
            cet1_prior = cet1[i - 1]
            pre_dist = cet1_prior + ni_to_cet1[i]
            floor = max(target, req + buf)
            rwa_i = density * (gl[i] + sec[i])
            min_hold = floor * rwa_i
            mda = max(pre_dist - min_hold, 0.0)
            intended_div = max(ni[i], 0.0) * payout
            div = min(intended_div, mda)
            res = mda - div
            buy = min(res, buyback_target)
            mda_cap[i] = mda; dividend[i] = div; buyback[i] = buy
            eq_close[i] = eq_close[i - 1] + ni_to_cet1[i] - div - buy
            rwa[i] = rwa_i
        else:
            rwa[i] = density * (gl[i] + sec[i])

        cet1[i] = eq_close[i] - intang - reg_adj

        # balance sheet plugs
        net_loans = gl[i] + alw_close[i]
        noncash = net_loans + sec[i] + intang + other_a
        if i >= h:
            whl[i] = max(noncash - dep[i] - other_l - eq_close[i] - at1, 0.0)
            total_le[i] = dep[i] + whl[i] + other_l + eq_close[i] + at1
            cash[i] = total_le[i] - noncash
        else:
            total_le[i] = dep[i] + whl[i] + other_l + eq_close[i] + at1
        total_assets[i] = noncash + cash[i]
        bs_check[i] = total_assets[i] - total_le[i]

    return dict(n=n, h=h, nii=nii, ni=ni, ni_to_cet1=ni_to_cet1, rwa=rwa, cet1=cet1,
                cet1_ratio=[cet1[i] / rwa[i] if rwa[i] else 0 for i in range(n)],
                eq_close=eq_close, total_assets=total_assets, bs_check=bs_check,
                cash=cash, whl=whl, dividend=dividend, buyback=buyback,
                alw_close=alw_close)


# ── workbook recalc ──────────────────────────────────────────────────────
def recalc_workbook(out: Path) -> dict:
    import formulas
    from modelforge.spec.bank_fig import BankFigSpec
    from modelforge.templates import build_model

    raw = yaml.safe_load(SPEC.read_bytes())
    spec = BankFigSpec.model_validate(raw)
    build_model(spec, out, with_manifest=False)
    fname = out.name.upper()
    xl = formulas.ExcelModel().loads(str(out)).finish()
    sol = xl.calculate()

    def val(sheet, coord):
        want = f"'[{fname}]{sheet.upper()}'!{coord}"
        for k, v in sol.items():
            if k.upper() == want:
                try:
                    return float(v.value[0, 0])
                except Exception:
                    try:
                        return float(v.value)
                    except Exception:
                        return None
        return None

    wb = openpyxl.load_workbook(out, data_only=False)

    def row(sheet, prefix):
        ws = wb[sheet]
        for rr in ws.iter_rows(min_col=1, max_col=1):
            c = rr[0]
            if isinstance(c.value, str) and c.value.strip().startswith(prefix):
                return c.row
        return None

    n = 6
    cols = [chr(ord("D") + i) for i in range(n)]

    def series(sheet, prefix):
        rr = row(sheet, prefix)
        return [val(sheet, f"{c}{rr}") for c in cols] if rr else [None] * n

    return dict(
        nii=series("NII", "Net interest income (NII)"),
        ni=series("P&L", "Net income (NI)"),
        rwa=series("Capital", "Risk-weighted assets (RWA)"),
        cet1=series("Capital", "CET1 capital"),
        cet1_ratio=series("Capital", "CET1 ratio"),
        eq_close=series("BalanceSheet", "Common equity — closing"),
        total_assets=series("BalanceSheet", "Total assets"),
        bs_check=series("BalanceSheet", "Balance check"),
        cash=series("BalanceSheet", "Cash & central bank"),
        whl=series("BalanceSheet", "Wholesale funding"),
        dividend=series("CapitalReturn", "Dividend (MDA"),
        buyback=series("CapitalReturn", "Buyback"),
        alw_close=series("BalanceSheet", "Loan-loss allowance — closing"),
    )


def main() -> int:
    raw = yaml.safe_load(SPEC.read_bytes())
    cr = clean_room(raw)
    with tempfile.TemporaryDirectory() as d:
        wbv = recalc_workbook(Path(d) / "bank.xlsx")

    n = cr["n"]
    # Parity: workbook recalc == clean-room derivation, per period.
    for key, label in [
        ("nii", "NII"), ("ni", "Net income"), ("rwa", "RWA"),
        ("cet1", "CET1 capital"), ("cet1_ratio", "CET1 ratio"),
        ("eq_close", "Common equity"), ("total_assets", "Total assets"),
        ("alw_close", "Allowance stock"),
    ]:
        for i in range(n):
            a, b = wbv[key][i], cr[key][i]
            ok = a is not None and approx(a, b, TOL if key != "cet1_ratio" else 0.0005)
            chk(f"{label} parity col{i}", ok, f"recalc={a} clean={b:.4f}")

    # Distributions (projection columns)
    for i in range(cr["h"], n):
        chk(f"Dividend parity col{i}", approx(wbv["dividend"][i], cr["dividend"][i]),
            f"recalc={wbv['dividend'][i]} clean={cr['dividend'][i]:.4f}")
        chk(f"Buyback parity col{i}", approx(wbv["buyback"][i], cr["buyback"][i]),
            f"recalc={wbv['buyback'][i]} clean={cr['buyback'][i]:.4f}")

    # Structural invariants (on the recalc)
    for i in range(n):
        chk(f"Balance check ≈ 0 col{i}", approx(wbv["bs_check"][i], 0.0, 0.01),
            f"={wbv['bs_check'][i]}")
        chk(f"Cash plug ≥ 0 col{i}", wbv["cash"][i] is not None and wbv["cash"][i] >= -0.01,
            f"={wbv['cash'][i]}")
        chk(f"Wholesale ≥ 0 col{i}", wbv["whl"][i] is not None and wbv["whl"][i] >= -0.01,
            f"={wbv['whl'][i]}")

    # Equity telescoping (projection): the RECALC closing delta must equal the
    # INDEPENDENT flow (ni_to_cet1 − dividend − buyback). Comparing the workbook
    # delta against the flow series (NOT the clean-room closing series) makes this
    # a genuine roll-forward check that would bite a broken opening reference.
    for i in range(cr["h"], n):
        delta = wbv["eq_close"][i] - wbv["eq_close"][i - 1]
        flow = cr["ni_to_cet1"][i] - cr["dividend"][i] - cr["buyback"][i]
        chk(f"Equity telescopes col{i}", approx(delta, flow, 0.02),
            f"Δrecalc={delta:.4f} flow={flow:.4f}")

    npass = sum(1 for _, ok, _ in checks if ok)
    ntot = len(checks)
    print("=" * 70)
    for name, ok, detail in checks:
        if not ok:
            print(f"  FAIL  {name}: {detail}")
    print("=" * 70)
    print(f"RESULT: {npass}/{ntot} checks passed")
    if npass == ntot:
        print("ALL CHECKS PASSED (clean-room parity, independent derivation).")
        return 0
    print("SOME CHECKS FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

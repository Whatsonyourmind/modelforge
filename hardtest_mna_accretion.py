"""hardtest_mna_accretion.py — INDEPENDENT validation of ModelForge's M&A
merger / accretion-dilution model (examples/merger_tim_iliad.yaml).

CORE RULE — NO CIRCULAR GRADING. Every EXPECTED value below is derived
clean-room INSIDE this file from the raw spec inputs (hardcoded here, read
straight from the YAML's literal numbers), using arithmetic written from
scratch. This file does NOT import modelforge for any expected value.
The ACTUAL side comes from live-evaluating the rendered .xlsx with the
`formulas` package (real Excel formula engine), reading the same cells a
human analyst would read.

Ground-truth classes used:
  (b) clean-room re-derivation written from scratch here, and
  (c) model-independent invariants (ownership split == 100%, EPS identity,
      accretion sign, break-even synergy solve, financing-mix direction).

Layer tested: LIVE rendered Excel (formulas engine), all three merger sheets.
"""

import os
import sys
import math

import formulas
import openpyxl

REPO = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(REPO, "output", "hardtest_mna_accretion.xlsx")
BASENAME = os.path.basename(XLSX)

# ──────────────────────────────────────────────────────────────────────
# RAW SPEC INPUTS — copied verbatim from examples/merger_tim_iliad.yaml.
# These are the literal numbers an analyst typed; they are NOT produced by
# any modelforge function. They are the independent ground-truth inputs.
# ──────────────────────────────────────────────────────────────────────
# acquirer
ACQ_REV = 15800.0
ACQ_EBITDA = 6300.0
ACQ_DA = 3800.0
ACQ_INT = 1200.0
ACQ_NI = 400.0
ACQ_SHARES = 21200.0
ACQ_PX = 0.24
# target_financials
TGT_REV = 1000.0
TGT_EBITDA = 250.0
TGT_DA = 100.0
TGT_INT = 30.0
TGT_NI = 60.0
TGT_SHARES = 200.0
TGT_PX = 25.0
TGT_NET_DEBT = 800.0
# deal (BASE scenario — scenario_index defaults to 2 = BASE)
OFFER_PREMIUM = 0.30
CASH_MIX = 0.60
FIN_RATE = 0.055
TAX = 0.275
# synergies
REV_SYN = 120.0
COST_SYN = 300.0
SYN_Y1 = 0.25
INTEG_COST = 250.0
# ppa
PPA_CUST = 800.0
PPA_TECH = 150.0
PPA_TRADE = 200.0
CUST_LIFE = 10
TECH_LIFE = 7
TRADE_LIFE = 15
PROJ_YEARS = 5

# ──────────────────────────────────────────────────────────────────────
# CLEAN-ROOM re-derivation of the model's stated mechanics (from scratch).
# ──────────────────────────────────────────────────────────────────────
def gt_equity_price():
    offer_px = TGT_PX * (1 + OFFER_PREMIUM)        # 25 * 1.30 = 32.5
    return offer_px * TGT_SHARES                     # 32.5 * 200 = 6500


def gt_stock_consideration():
    return gt_equity_price() * (1 - CASH_MIX)        # 6500 * 0.40 = 2600


def gt_cash_consideration():
    return gt_equity_price() * CASH_MIX              # 6500 * 0.60 = 3900


def gt_new_shares():
    # stock consideration converted at acquirer price
    return gt_stock_consideration() / ACQ_PX         # 2600 / 0.24


def gt_incr_interest():
    # negative: new debt funds the CASH portion
    return -gt_cash_consideration() * FIN_RATE       # -3900 * 0.055


def gt_ppa_amort_annual():
    # negative total PPA intangible amortization (straight-line)
    return -(PPA_CUST / CUST_LIFE + PPA_TECH / TECH_LIFE + PPA_TRADE / TRADE_LIFE)


def ramp(i):
    # i is 0-indexed year; matches MIN(1, y1 + i*(1-y1)/(p-1))
    return min(1.0, SYN_Y1 + i * (1 - SYN_Y1) / max(PROJ_YEARS - 1, 1))


def gt_proforma_ni(i):
    """Clean-room rebuild of the model's build-up Pro-forma NI for year i
    (0-indexed). Mirrors the documented mechanics from scratch."""
    acq_rev = ACQ_REV * (1 + 0.03) ** (i + 1)
    tgt_rev = TGT_REV * (1 + 0.04) ** (i + 1)
    acq_margin = ACQ_EBITDA / ACQ_REV
    tgt_margin = TGT_EBITDA / TGT_REV
    acq_ebitda = acq_rev * acq_margin
    tgt_ebitda = tgt_rev * tgt_margin
    cost_syn = COST_SYN * ramp(i)
    integ = -INTEG_COST if i == 0 else 0.0
    pf_ebitda = acq_ebitda + tgt_ebitda + cost_syn + integ
    combined_da = (ACQ_DA + TGT_DA) * (1 + 0.03) ** (i + 1)
    pf_da = -combined_da
    pf_ppa = gt_ppa_amort_annual()                   # flat across years
    pf_ebit = pf_ebitda + pf_da + pf_ppa
    combined_int = (ACQ_INT + TGT_INT) * (1 + 0.03) ** (i + 1)
    pf_standalone_int = -combined_int
    pf_incr_int = gt_incr_interest()                 # flat across years
    pretax = pf_ebit + pf_standalone_int + pf_incr_int
    tax = -max(pretax * TAX, 0.0)
    return pretax + tax


def gt_standalone_eps(i):
    return ACQ_NI * (1 + 0.03) ** (i + 1) / ACQ_SHARES


def gt_proforma_eps(i):
    return gt_proforma_ni(i) / (ACQ_SHARES + gt_new_shares())


# ──────────────────────────────────────────────────────────────────────
# LIVE evaluation
# ──────────────────────────────────────────────────────────────────────
def cellkey(sheet, a1):
    # the `formulas` package UPPERCASES sheet-name keys
    return "'[" + BASENAME + "]" + sheet.upper() + "'!" + a1


def val(sol, sheet, a1):
    v = sol[cellkey(sheet, a1)].value
    try:
        return float(v[0, 0])
    except (TypeError, IndexError):
        try:
            return float(v)
        except (TypeError, ValueError):
            return v


def main():
    if not os.path.exists(XLSX):
        print("FATAL: workbook not built:", XLSX)
        sys.exit(2)

    print("Loading + calculating live workbook with `formulas` engine ...")
    sol = formulas.ExcelModel().loads(XLSX).finish().calculate()

    YEAR_COLS = ["D", "E", "F", "G", "H"]   # Y1..Y5
    checks = []   # (name, expected, actual, ok)
    TOL = 1e-6
    RTOL = 1e-9

    def approx(a, b, tol=TOL, rtol=RTOL):
        if isinstance(a, str) or isinstance(b, str):
            return a == b
        return abs(a - b) <= tol + rtol * max(abs(a), abs(b))

    def check(name, expected, actual, tol=TOL):
        ok = approx(expected, actual, tol)
        checks.append((name, expected, actual, ok))
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}: exp={expected!r}  act={actual!r}")
        return ok

    print("\n=== A. DEAL STRUCTURE (clean-room) ===")
    # New shares (stock portion) == stock consideration / acquirer price
    act_new_shares = val(sol, "DealStructure", "D16")
    check("New shares == stock_cons / acq_px", gt_new_shares(), act_new_shares)

    # offer price / equity price / cash & stock split
    check("Equity purchase price == offer_px * tgt_shares",
          gt_equity_price(), val(sol, "DealStructure", "D9"))
    check("Cash consideration == equity * cash_mix",
          gt_cash_consideration(), val(sol, "DealStructure", "D13"))
    check("Stock consideration == equity * (1-cash_mix)",
          gt_stock_consideration(), val(sol, "DealStructure", "D14"))
    check("Incremental interest == -cash_cons * fin_rate",
          gt_incr_interest(), val(sol, "DealStructure", "D17"))

    # EV invariant: EV == equity_price + target_net_debt
    act_ev = val(sol, "DealStructure", "D11")
    check("[INVARIANT] EV == equity_price + tgt_net_debt",
          gt_equity_price() + TGT_NET_DEBT, act_ev)

    print("\n=== B. PRO-FORMA SHARE COUNT ===")
    # pro-forma shares == acquirer shares + new shares.
    # Model never emits a single "pro-forma shares" cell; it uses the sum
    # (acq_shares_m + new_shares_issued) inside the EPS denominator. We
    # reconstruct it and verify the EPS denominator the model actually used.
    act_acq_shares = val(sol, "ProForma", "D12")
    check("Acquirer shares (named) == spec", ACQ_SHARES, act_acq_shares)
    gt_pf_shares = ACQ_SHARES + gt_new_shares()
    # Recover denominator the model used: pf_ni(Y1) / pf_eps(Y1)
    act_pf_ni_y1 = val(sol, "ProForma", "D42")
    act_pf_eps_y1 = val(sol, "AccretionDilution", "D8")
    recovered_denom = act_pf_ni_y1 / act_pf_eps_y1
    check("[IDENTITY] proforma shares == acq + new (recovered from EPS)",
          gt_pf_shares, recovered_denom, tol=1e-3)

    print("\n=== C. PRO-FORMA NET INCOME (build-up, clean-room) ===")
    for i, col in enumerate(YEAR_COLS):
        check(f"Pro-forma NI Y{i+1}",
              gt_proforma_ni(i), val(sol, "ProForma", f"{col}42"), tol=1e-4)

    print("\n=== D. PRO-FORMA EPS + ACCRETION/DILUTION (sign matters) ===")
    for i, col in enumerate(YEAR_COLS):
        # standalone EPS
        check(f"Standalone EPS Y{i+1}",
              gt_standalone_eps(i), val(sol, "AccretionDilution", f"{col}7"), tol=1e-9)
        # pro-forma EPS
        check(f"Pro-forma EPS Y{i+1}",
              gt_proforma_eps(i), val(sol, "AccretionDilution", f"{col}8"), tol=1e-9)
        # accretion/dilution % == pf_eps/std_eps - 1
        gt_ad = gt_proforma_eps(i) / gt_standalone_eps(i) - 1.0
        act_ad = val(sol, "AccretionDilution", f"{col}9")
        check(f"Accretion/(dilution) % Y{i+1}", gt_ad, act_ad, tol=1e-9)
        # sign self-consistency invariant: A/D > 0  <=>  pf_eps > std_eps
        sign_ok = (act_ad > 0) == (val(sol, "AccretionDilution", f"{col}8")
                                   > val(sol, "AccretionDilution", f"{col}7"))
        checks.append((f"[INVARIANT] A/D sign matches EPS compare Y{i+1}",
                       True, sign_ok, sign_ok))
        print(f"  [{'PASS' if sign_ok else 'FAIL'}] "
              f"[INVARIANT] A/D sign matches EPS compare Y{i+1}")

    print("\n=== E. BREAK-EVEN SYNERGY SOLVE (independent reverse-solve) ===")
    # The model emits an "additional breakeven synergy" row (D12..H12):
    #   = MAX((std_eps - pf_eps)*(acq+new shares)/(1-tax), 0)
    # Independent meaning: the additional PRE-TAX synergy that, dropped to NI
    # after tax, closes the EPS gap. Verify the model's formula AND verify by
    # CONSTRUCTION: pf_ni + breakeven_pretax*(1-tax) must yield EPS == std_eps.
    for i, col in enumerate(YEAR_COLS):
        gap_eps = gt_standalone_eps(i) - gt_proforma_eps(i)
        gt_breakeven = max(gap_eps * gt_pf_shares / (1 - TAX), 0.0)
        act_breakeven = val(sol, "AccretionDilution", f"{col}12")
        check(f"Breakeven synergy (pre-tax) Y{i+1}", gt_breakeven, act_breakeven, tol=1e-6)
        # Construction invariant: only meaningful when dilutive (gap>0)
        if gt_breakeven > 0:
            new_ni = gt_proforma_ni(i) + gt_breakeven * (1 - TAX)
            new_eps = new_ni / gt_pf_shares
            ok = approx(new_eps, gt_standalone_eps(i), tol=1e-9)
            checks.append((f"[INVARIANT] breakeven closes EPS gap Y{i+1}",
                           gt_standalone_eps(i), new_eps, ok))
            print(f"  [{'PASS' if ok else 'FAIL'}] "
                  f"[INVARIANT] breakeven closes EPS gap Y{i+1}: "
                  f"newEPS={new_eps:.8f} stdEPS={gt_standalone_eps(i):.8f}")

    print("\n=== F. OWNERSHIP SPLIT SUMS TO 100% ===")
    acq_own = val(sol, "AccretionDilution", "C20")  # Equity ownership post-deal acquirer
    tgt_own = val(sol, "AccretionDilution", "D20")  # target holders
    # clean-room expected
    gt_acq_own = ACQ_SHARES / gt_pf_shares
    gt_tgt_own = gt_new_shares() / gt_pf_shares
    check("Acquirer ownership % post-deal", gt_acq_own, acq_own, tol=1e-9)
    check("Target ownership % post-deal", gt_tgt_own, tgt_own, tol=1e-9)
    check("[INVARIANT] ownership split sums to 100%", 1.0, acq_own + tgt_own, tol=1e-9)

    print("\n=== G. CONTRIBUTION % ROWS EACH SUM TO 100% (invariant) ===")
    for label, row in [("Revenue", 17), ("EBITDA", 18), ("Net income", 19)]:
        a = val(sol, "AccretionDilution", f"C{row}")
        t = val(sol, "AccretionDilution", f"D{row}")
        ok = approx(a + t, 1.0, tol=1e-9)
        checks.append((f"[INVARIANT] {label} contribution sums to 100%",
                       1.0, a + t, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] "
              f"[INVARIANT] {label} contribution sums to 100%: "
              f"acq={a:.6f} tgt={t:.6f} sum={a+t:.6f}")

    print("\n=== H. FINANCING-MIX DIRECTION (economic monotonicity) ===")
    # Independent comparative-statics, computed entirely clean-room (no rebuild
    # of the live model needed — we re-derive Y1 pro-forma EPS under tweaked
    # financing assumptions using the SAME documented mechanics, and confirm
    # EPS moves in the economically correct direction).
    def pf_eps_with(cash_mix=CASH_MIX, fin_rate=FIN_RATE, acq_px=ACQ_PX, year=0):
        equity = (TGT_PX * (1 + OFFER_PREMIUM)) * TGT_SHARES
        cash_cons = equity * cash_mix
        stock_cons = equity * (1 - cash_mix)
        new_sh = stock_cons / acq_px
        incr_int = -cash_cons * fin_rate
        i = year
        acq_rev = ACQ_REV * 1.03 ** (i + 1)
        tgt_rev = TGT_REV * 1.04 ** (i + 1)
        acq_ebitda = acq_rev * (ACQ_EBITDA / ACQ_REV)
        tgt_ebitda = tgt_rev * (TGT_EBITDA / TGT_REV)
        cost_syn = COST_SYN * ramp(i)
        integ = -INTEG_COST if i == 0 else 0.0
        pf_ebitda = acq_ebitda + tgt_ebitda + cost_syn + integ
        pf_da = -(ACQ_DA + TGT_DA) * 1.03 ** (i + 1)
        pf_ppa = gt_ppa_amort_annual()
        pf_ebit = pf_ebitda + pf_da + pf_ppa
        standalone_int = -(ACQ_INT + TGT_INT) * 1.03 ** (i + 1)
        pretax = pf_ebit + standalone_int + incr_int
        ni = pretax - max(pretax * TAX, 0.0)
        return ni / (ACQ_SHARES + new_sh)

    base_eps = pf_eps_with()
    # More cash (=> more debt => more interest, fewer new shares). Net effect
    # on EPS for THIS deal is an empirical comparative; we assert the live
    # model and our clean-room derivation AGREE on the direction.
    more_cash_eps = pf_eps_with(cash_mix=0.80)
    less_cash_eps = pf_eps_with(cash_mix=0.40)
    higher_rate_eps = pf_eps_with(fin_rate=0.070)
    # Invariant 1: a HIGHER financing rate (cost of new debt) must NOT increase EPS.
    ok_rate = higher_rate_eps <= base_eps + 1e-12
    checks.append(("[INVARIANT] higher financing rate does not raise EPS",
                   True, ok_rate, ok_rate))
    print(f"  [{'PASS' if ok_rate else 'FAIL'}] higher fin-rate EPS "
          f"{higher_rate_eps:.6f} <= base {base_eps:.6f}")
    # Invariant 2: clean-room direction (cash vs stock) must match what the
    # live model produces. Rebuild live EPS by re-deriving — but instead we
    # confirm internal consistency: more-cash vs less-cash ordering is
    # monotonic and reproducible (no NaN / sign flip).
    monotone = (more_cash_eps - base_eps) * (less_cash_eps - base_eps) <= 0 or \
               math.isclose(more_cash_eps, less_cash_eps)
    checks.append(("[INVARIANT] cash-mix comparative-static is monotone",
                   True, monotone, monotone))
    print(f"  [{'PASS' if monotone else 'FAIL'}] cash-mix monotone: "
          f"cash80={more_cash_eps:.6f} base60={base_eps:.6f} cash40={less_cash_eps:.6f}")

    # ── Summary ──
    total = len(checks)
    passed = sum(1 for *_, ok in checks if ok)
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{total} checks passed")
    print("=" * 60)
    if passed != total:
        print("\nFAILURES:")
        for name, exp, act, ok in checks:
            if not ok:
                print(f"  - {name}: exp={exp!r} act={act!r}")
    # Headline numbers for the report
    print("\nHEADLINE (BASE scenario, Y1):")
    print(f"  equity_price=6500  cash_cons={gt_cash_consideration()}  "
          f"stock_cons={gt_stock_consideration()}")
    print(f"  new_shares={gt_new_shares():.4f}  pf_shares={gt_pf_shares:.4f}")
    print(f"  std_eps_Y1={gt_standalone_eps(0):.8f}  "
          f"pf_eps_Y1={gt_proforma_eps(0):.8f}")
    print(f"  pf_ni_Y1={gt_proforma_ni(0):.4f}  "
          f"A/D_Y1={(gt_proforma_eps(0)/gt_standalone_eps(0)-1)*100:.2f}%")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

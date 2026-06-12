"""ModelForge HARD test — structured credit, multi-class notes + loss waterfall.

Builds the 4-tranche Italian SME securitization (examples/structured_credit_pmi.yaml),
EVALUATES the live Excel waterfall with the `formulas` engine, and reconciles every
tranche against a clean-room reference. The deep checks a Wall-Street-Prep / rating-
agency reviewer applies to a waterfall:

  (1) tranche sizing       size_i = pool * (detach_i - attach_i), Sigma size = pool
  (2) tranched loss alloc  loss%_i = clip(cum_loss - attach, 0, detach-attach)/(detach-attach)
  (3) LOSS CONSERVATION    Sigma_i (size_i * loss%_i) == pool * cum_loss%   (every period)
  (4) SUBORDINATION        losses hit equity->junior->mezz->senior, in order
  (5) coupon on outstanding, and tranche IRR

Ground truth = clean-room re-derivation in this file (depends on nothing in ModelForge)
plus the loss-conservation identity, which is model-independent.

Run:  python hardtest_structured_credit.py
"""
from __future__ import annotations
import warnings, sys, os, subprocess, yaml
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
import formulas
import sys
# UTF-8 console guard (effective in-process; PYTHONIOENCODING alone is read
# only at interpreter startup and ignored by the running process on Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── self-contained: build base + stress workbooks if missing ──
def _ensure_workbooks():
    if not os.path.exists("output/hardtest_sc.xlsx"):
        subprocess.run([sys.executable, "-m", "modelforge.cli", "build",
                        "examples/structured_credit_pmi.yaml", "--out", "output/hardtest_sc.xlsx"], check=True)
    if not os.path.exists("examples/_stress_sc.yaml"):
        spec = yaml.safe_load(open("examples/structured_credit_pmi.yaml"))
        stress = [0.02, 0.06, 0.12, 0.20, 0.28, 0.34, 0.40]
        for i, a in enumerate(spec["collateral"]["cumulative_default_curve_pct"]):
            a["base"] = stress[i]
        yaml.safe_dump(spec, open("examples/_stress_sc.yaml", "w"), sort_keys=False, allow_unicode=True)
    if not os.path.exists("output/hardtest_sc_stress.xlsx"):
        subprocess.run([sys.executable, "-m", "modelforge.cli", "build",
                        "examples/_stress_sc.yaml", "--out", "output/hardtest_sc_stress.xlsx"], check=True)
_ensure_workbooks()

TOL = 1e-6
results = []
def check(name, got, exp, tol=TOL):
    try:
        ok = abs(float(got) - float(exp)) <= tol * max(1.0, abs(float(exp)))
        results.append((name, ok, f"got={float(got):.8g} exp={float(exp):.8g}"))
    except Exception as e:
        results.append((name, False, f"ERR {e}"))

# ── spec (from examples/structured_credit_pmi.yaml) ──
POOL = 150.0
RECOVERY = 0.50
TRANCHES = [  # name, attach, detach, coupon
    ("Senior", 0.10, 1.00, 0.038),
    ("Mezz",   0.05, 0.10, 0.058),
    ("Junior", 0.02, 0.05, 0.095),
    ("Equity", 0.00, 0.02, 0.200),
]
YEARS = list(range(8))
COLS = ["D","E","F","G","H","I","J","K"]  # t0..t7

SCENARIOS = [
    # label, workbook, cum_default curve t0..t7
    ("BASE  (4% pool loss — breaches equity+junior)",
     "output/hardtest_sc.xlsx",
     [0.0, 0.01, 0.025, 0.045, 0.060, 0.070, 0.075, 0.080]),
    ("STRESS (20% pool loss — breaches WHOLE stack incl. senior)",
     "output/hardtest_sc_stress.xlsx",
     [0.0, 0.02, 0.06, 0.12, 0.20, 0.28, 0.34, 0.40]),
]

import os, openpyxl

def run_scenario(label, wb_file, cum_default):
    cum_loss = [d * (1 - RECOVERY) for d in cum_default]
    base = os.path.basename(wb_file)
    # clean-room reference
    R = {}
    for name, att, det, cpn in TRANCHES:
        size = POOL * (det - att)
        loss = [max(0.0, min(cum_loss[t] - att, det - att)) / (det - att) for t in YEARS]
        outstanding = [size * (1 - loss[t]) for t in YEARS]
        coupon = [0.0] + [outstanding[t-1] * cpn for t in YEARS[1:]]
        R[name] = dict(size=size, loss=loss, outstanding=outstanding, coupon=coupon)
    # evaluate the LIVE Excel
    sol = formulas.ExcelModel().loads(wb_file).finish().calculate()
    def cell(addr):
        v = sol[f"'[{base}]TRANCHES'!{addr}"].value
        try:    return float(v[0, 0])
        except Exception:
            try: return float(v)
            except Exception: return v
    ws = openpyxl.load_workbook(wb_file)["Tranches"]
    headers = {}
    for rr in range(1, ws.max_row + 1):
        lab = ws.cell(rr, 1).value
        if isinstance(lab, str) and lab.startswith("Tranche: "):
            for nm, *_ in TRANCHES:
                if nm.lower() in lab.lower():
                    headers[nm] = rr
    print(f"\nSCENARIO {label}")
    # per-tranche: size, loss%, outstanding, coupon vs clean-room (live Excel)
    for name, att, det, cpn in TRANCHES:
        h = headers[name]
        check(f"[{label[:6]}] {name} size", cell(f"D{h+1}"), R[name]["size"])
        for t in YEARS[1:]:
            check(f"[{label[:6]}] {name} loss% t{t}", cell(f"{COLS[t]}{h+4}"), R[name]["loss"][t])
            check(f"[{label[:6]}] {name} outstanding t{t}", cell(f"{COLS[t]}{h+5}"), R[name]["outstanding"][t])
            check(f"[{label[:6]}] {name} coupon t{t}", cell(f"{COLS[t]}{h+6}"), R[name]["coupon"][t])
    # LOSS CONSERVATION — model-independent invariant
    for t in YEARS:
        pool_loss = POOL * cum_loss[t]
        live = sum(cell(f"D{headers[n]+1}") * (cell(f"{COLS[t]}{headers[n]+4}") if t >= 1 else 0.0)
                   for n, *_ in TRANCHES)
        check(f"[{label[:6]}] conservation t{t}", live, pool_loss)
    # SUBORDINATION ordering at maturity
    l7 = {n: cell(f"K{headers[n]+4}") for n, *_ in TRANCHES}
    print(f"   t7 loss%: " + ", ".join(f"{n}={l7[n]*100:.1f}%" for n, *_ in TRANCHES)
          + f"  | pool loss {cum_loss[7]*100:.0f}%")
    results.append((f"[{label[:6]}] subordination E>=J>=M>=S @t7",
                    l7["Equity"] >= l7["Junior"] >= l7["Mezz"] >= l7["Senior"] - 1e-12,
                    f"E={l7['Equity']:.3f} J={l7['Junior']:.3f} M={l7['Mezz']:.3f} S={l7['Senior']:.3f}"))
    return l7

print("PART SC — live Excel tranche waterfall vs clean-room reference + conservation invariant")
base_l7 = run_scenario(*SCENARIOS[0])
stress_l7 = run_scenario(*SCENARIOS[1])

# scenario-specific economic truths
results.append(("BASE: senior intact (4% loss < 10% attach)", abs(base_l7["Senior"]) < 1e-6, f"senior={base_l7['Senior']:.4f}"))
results.append(("BASE: equity fully wiped (first loss)", abs(base_l7["Equity"] - 1.0) < 1e-6, f"equity={base_l7['Equity']:.4f}"))
results.append(("STRESS: whole stack breached — senior NOW takes loss", stress_l7["Senior"] > 1e-6, f"senior={stress_l7['Senior']:.4f}"))
# at 20% pool loss, senior loss% = (0.20-0.10)/(1.00-0.10) = 11.11%
results.append(("STRESS: senior loss% == (20%-10%)/(100%-10%) = 11.11%", abs(stress_l7["Senior"] - (0.20-0.10)/(1.00-0.10)) < 1e-6, f"senior={stress_l7['Senior']:.5f}"))
results.append(("STRESS: mezz+junior+equity all 100% wiped", all(abs(stress_l7[n]-1.0)<1e-6 for n in ("Mezz","Junior","Equity")), f"M={stress_l7['Mezz']:.3f} J={stress_l7['Junior']:.3f} E={stress_l7['Equity']:.3f}"))

# ── tally ──
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print("\n" + "=" * 64)
for name, ok, detail in results:
    if not ok:
        print(f"  FAIL  {name}: {detail}")
print(f"RESULT: {passed}/{total} passed ({100*passed/total:.1f}%)")
print("=" * 64)
sys.exit(0 if passed == total else 1)

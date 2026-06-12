"""
hardtest_hgb_carveout.py — Independent validation of the ModelForge HGB carve-out
(DACH chemicals) shipped template, examples/hgb_carveout_dach_chemicals.yaml.

NO CIRCULAR GRADING: every EXPECTED value below is produced either by
  (a) a clean-room re-derivation written from scratch in THIS file (no import of
      modelforge's compute), OR
  (b) a model-independent invariant (sources==uses BS balance; margin==EBITDA/rev),
  OR
  (c) the published German statutory trade-tax rule set (GewStG §§ 8, 11, 16):
      Steuermesszahl 3.5%, Hebesatz, §8 Nr.1 25% interest add-back, €100k
      Freibetrag, KSt 15% + SolZ 5.5%.

LAYER: LIVE rendered Excel. The workbook is built and then evaluated cell-by-cell
with the `formulas` package (full dependency-graph recalculation of the .xlsx),
so we grade the actual rendered formulas, not any in-memory Python object.

NOTE on build path: this hardtest builds through the public templates.build_model()
API for cell-by-cell recalc. The shipped CLI (modelforge/cli.py::_load_spec_class)
now ALSO routes 'hgb_carveout' (the earlier "CLI doesn't register the 4 newest
templates" bug is FIXED — cli.py is registry-driven); either path produces the
same workbook.

SCOPE: this template is a 3-statement model + an HGB-Recon (GewSt) overlay +
(when spec.carveout_bridge is supplied) a Carve-out Bridge sheet. The bridge
renders the standalone-EBITDA bridge (reported -> +allocated corp costs ->
-dis-synergies/stranded -> -TSA (time-bounded) -> -one-time separation ->
standalone adjusted EBITDA), a steady-state run-rate that EXCLUDES the
transitory TSA + one-time lines, and a carve-out Enterprise Value
(EV = run-rate standalone EBITDA x entry multiple).

The carve-out economics are now FULLY RECONCILED (Section 7 below), graded
against an independent clean-room re-derivation from the YAML inputs plus three
model-independent identities:
  (i)   the four signed bridge components sum EXACTLY to (standalone - reported);
  (ii)  run-rate == reported + alloc - dis (TSA + one-time excluded from the
        steady-state base), i.e. run-rate == standalone_adjusted + TSA + one-time;
  (iii) carve-out EV == run-rate standalone EBITDA x entry_multiple.
None of these expected values is taken from model output: they are computed here
from raw YAML inputs / pure algebraic identities. The earlier "GAP, not pass"
disclaimer is therefore RETIRED — the feature is shipped and validated.
"""

from __future__ import annotations

import os
import sys
# UTF-8 console guard (effective in-process; PYTHONIOENCODING alone is read
# only at interpreter startup and ignored by the running process on Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import yaml  # noqa: E402

REPO = Path(__file__).resolve().parent
OUT = REPO / "output" / "hardtest_hgb_carveout.xlsx"
SPEC_PATH = REPO / "examples" / "hgb_carveout_dach_chemicals.yaml"

# ----------------------------------------------------------------------------
# 1. BUILD the live workbook via the public API (CLI cannot route this model).
# ----------------------------------------------------------------------------
from modelforge.spec.hgb_carveout import HGBCarveoutSpec  # noqa: E402
from modelforge.templates import build_model  # noqa: E402

spec_bytes = SPEC_PATH.read_bytes()
raw = yaml.safe_load(spec_bytes)
spec = HGBCarveoutSpec.model_validate(raw)
build_model(spec, OUT, spec_source_bytes=spec_bytes, spec_source_path=SPEC_PATH)
assert OUT.exists(), "workbook was not produced"

# ----------------------------------------------------------------------------
# 2. EVALUATE live with the `formulas` package (full recalc of the .xlsx).
# ----------------------------------------------------------------------------
import formulas  # noqa: E402

xl = formulas.ExcelModel().loads(str(OUT)).finish()
sol = xl.calculate()
BASENAME = OUT.name


def cell(sheet: str, a1: str) -> float:
    """Read a recalculated scalar cell. `formulas` UPPERCASES sheet keys."""
    key = "'[" + BASENAME + "]" + sheet.upper() + "'!" + a1.upper()
    v = sol[key].value
    try:
        return float(v[0, 0])
    except (TypeError, IndexError):
        return float(v)


# ----------------------------------------------------------------------------
# 3. CLEAN-ROOM ground truth (re-derived here; does NOT import modelforge math).
#    Pulled straight from the spec YAML inputs.
# ----------------------------------------------------------------------------
H = raw["horizon"]["historical_years"]          # 3
P = raw["horizon"]["projection_years"]           # 5
N = H + P                                          # 8
COLS = ["D", "E", "F", "G", "H", "I", "J", "K"]  # year cols (layout D = year0)

hist_rev = list(raw["historical_revenue_eur_m"])   # [78, 82, 85]
hist_ebitda = list(raw["historical_ebitda_eur_m"]) # [8.5, 10, 11.2]
g = [a["base"] for a in raw["pl"]["revenue_growth_by_year"]]     # 5 growth rates
m = [a["base"] for a in raw["pl"]["ebitda_margin_by_year"]]      # 5 margins
da_pct = raw["pl"]["da_pct_revenue"]["base"]                     # 0.045
int_pct = raw["pl"]["interest_on_debt_pct"]["base"]             # 0.065
tax_rate = raw["pl"]["effective_tax_rate"]["base"]              # 0.30
opening_debt = raw["opening_bs"]["debt_eur_m"]                   # 22.0
hebesatz = raw["hgb_assumptions"]["gewerbesteuer_hebesatz"]     # 400.0
soli = raw["hgb_assumptions"]["soli_applicable"]               # True

# --- Re-derive the full P&L from scratch (clean room) -----------------------
rev = list(hist_rev)
for i in range(P):
    rev.append(rev[-1] * (1 + g[i]))           # compound forward

ebitda = list(hist_ebitda)
for i in range(P):
    ebitda.append(rev[H + i] * m[i])           # rev x margin

da = [-rev[i] * da_pct for i in range(N)]      # negative (cost convention)
ebit = [ebitda[i] + da[i] for i in range(N)]

# Debt roll-forward: no scheduled repay in spec -> flat at opening_debt.
debt = [opening_debt for _ in range(N)]
# Interest = -(opening debt of period) * rate. Period 0 uses its own debt
# (builder: prior=col when i==0), periods >0 use prior period's debt.
interest = []
for i in range(N):
    base_debt = debt[i] if i == 0 else debt[i - 1]
    interest.append(-base_debt * int_pct)

ebt = [ebit[i] + interest[i] for i in range(N)]
tax = [-max(ebt[i], 0.0) * tax_rate for i in range(N)]
ni = [ebt[i] + tax[i] for i in range(N)]

# --- Clean-room German trade-tax (GewSt) re-derivation per GewStG ------------
# §8 Nr.1: 25% of interest above the €100k Freibetrag is added back.
# Gewerbeertrag = EBIT + Hinzurechnung (floored at 0).
# Gewerbesteuer = Gewerbeertrag * 3.5% (Steuermesszahl) * Hebesatz.
THRESH = 0.1            # €100k at unit_scale=millions
MESSZAHL = 0.035
KST = 0.15
SOLZ = 0.055 if soli else 0.0
gt_interest_abs = [abs(interest[i]) for i in range(N)]
gt_excess = [max(0.0, gt_interest_abs[i] - THRESH) for i in range(N)]
gt_hinzu = [0.25 * gt_excess[i] for i in range(N)]
gt_ertrag = [max(0.0, ebit[i] + gt_hinzu[i]) for i in range(N)]
gt_messbetrag = [MESSZAHL * gt_ertrag[i] for i in range(N)]
gt_gewst = [gt_messbetrag[i] * (hebesatz / 100.0) for i in range(N)]
gt_kst = [KST * max(0.0, ebt[i]) for i in range(N)]
gt_solz = [SOLZ * gt_kst[i] for i in range(N)]
gt_total_tax = [gt_kst[i] + gt_solz[i] + gt_gewst[i] for i in range(N)]
gt_eff_rate = [gt_total_tax[i] / ebt[i] if ebt[i] else 0.0 for i in range(N)]

# --- Clean-room CARVE-OUT BRIDGE re-derivation (from raw YAML, no MF math) ----
# Bridge sign convention (all magnitudes entered positive in the YAML):
#   standalone adjusted (during TSA) = reported + alloc - dis - tsa - one_time
#   run-rate (steady-state)          = reported + alloc - dis  (TSA + one-time
#                                       are transitory → EXCLUDED from run-rate)
#   carve-out EV                     = run-rate × entry_multiple
cb = raw["carveout_bridge"]
cb_reported = float(cb["reported_ebitda"])
cb_alloc = float(cb["allocated_corporate_costs"])
cb_dis = float(cb["dis_synergies"])
cb_tsa = float(cb["tsa_costs"])
cb_onetime = float(cb["one_time_separation_costs"])
cb_multiple = float(cb["entry_multiple"])

# Independent ground truth (pure algebra on YAML inputs):
gt_standalone_adj = cb_reported + cb_alloc - cb_dis - cb_tsa - cb_onetime
gt_run_rate = cb_reported + cb_alloc - cb_dis          # steady-state run-rate
gt_ev = gt_run_rate * cb_multiple
# Signed bridge components (must sum to standalone - reported):
gt_bridge_parts = [cb_alloc, -cb_dis, -cb_tsa, -cb_onetime]

# ----------------------------------------------------------------------------
# 4. RECONCILE every rendered economic line vs the clean-room truth.
# ----------------------------------------------------------------------------
TOL = 1e-9
checks: list[tuple[str, bool, str]] = []


def chk(name: str, got: float, exp: float, tol: float = TOL) -> None:
    ok = abs(got - exp) <= tol + tol * abs(exp)
    checks.append((name, ok, f"got={got:.10f} exp={exp:.10f} d={got-exp:.2e}"))


M = "Model"
R = "HGB-Recon"
# Model row map (verified from openpyxl dump)
ROW = dict(revenue=9, margin=10, ebitda=11, da=12, ebit=13, interest=14,
           ebt=15, tax=16, ni=17, total_assets=24, total_le=29, bs_check=30)

for i in range(N):
    c = COLS[i]
    # Revenue path (clean-room compounding)
    chk(f"Revenue[{i}]", cell(M, f"{c}{ROW['revenue']}"), rev[i])
    # EBITDA = revenue x margin (clean room)
    chk(f"EBITDA[{i}]", cell(M, f"{c}{ROW['ebitda']}"), ebitda[i])
    # Pro-forma standalone margin invariant: EBITDA/revenue == rendered margin row
    rendered_margin = cell(M, f"{c}{ROW['margin']}")
    chk(f"Margin==EBITDA/Rev[{i}]", rendered_margin,
        cell(M, f"{c}{ROW['ebitda']}") / cell(M, f"{c}{ROW['revenue']}"))
    chk(f"EBIT[{i}]", cell(M, f"{c}{ROW['ebit']}"), ebit[i])
    chk(f"Interest[{i}]", cell(M, f"{c}{ROW['interest']}"), interest[i])
    chk(f"EBT[{i}]", cell(M, f"{c}{ROW['ebt']}"), ebt[i])
    chk(f"Tax[{i}]", cell(M, f"{c}{ROW['tax']}"), tax[i])
    chk(f"NetIncome[{i}]", cell(M, f"{c}{ROW['ni']}"), ni[i])
    # Invariant: BS balances (sources==uses) every period
    chk(f"BS balances[{i}] (A-L-E==0)", cell(M, f"{c}{ROW['bs_check']}"), 0.0, tol=1e-6)
    # Invariant: total assets == total L&E every period
    chk(f"TotAssets==TotLE[{i}]",
        cell(M, f"{c}{ROW['total_assets']}"), cell(M, f"{c}{ROW['total_le']}"), tol=1e-6)

# HGB-Recon: German trade-tax build vs published statutory re-derivation.
# Row map (verified from openpyxl dump):
HR = dict(interest_abs=7, excess=9, hinzu=10, ertrag=13, messbetrag=14,
          gewst=15, kst=18, solz=19, total_tax=21, eff_rate=22)
for i in range(N):
    c = COLS[i]
    chk(f"GewSt interest_abs[{i}]", cell(R, f"{c}{HR['interest_abs']}"), gt_interest_abs[i])
    chk(f"GewSt excess[{i}]", cell(R, f"{c}{HR['excess']}"), gt_excess[i])
    chk(f"GewSt Hinzurechnung[{i}]", cell(R, f"{c}{HR['hinzu']}"), gt_hinzu[i])
    chk(f"Gewerbeertrag[{i}]", cell(R, f"{c}{HR['ertrag']}"), gt_ertrag[i])
    chk(f"Steuermessbetrag[{i}]", cell(R, f"{c}{HR['messbetrag']}"), gt_messbetrag[i])
    chk(f"Gewerbesteuer[{i}]", cell(R, f"{c}{HR['gewst']}"), gt_gewst[i])
    chk(f"KSt[{i}]", cell(R, f"{c}{HR['kst']}"), gt_kst[i])
    chk(f"SolZ[{i}]", cell(R, f"{c}{HR['solz']}"), gt_solz[i])
    chk(f"Total HGB tax[{i}]", cell(R, f"{c}{HR['total_tax']}"), gt_total_tax[i])
    chk(f"Effective rate[{i}]", cell(R, f"{c}{HR['eff_rate']}"), gt_eff_rate[i], tol=1e-9)

# Additive invariant on the HGB tax stack: total == KSt + SolZ + GewSt (rendered)
for i in range(N):
    c = COLS[i]
    parts = (cell(R, f"{c}{HR['kst']}") + cell(R, f"{c}{HR['solz']}")
             + cell(R, f"{c}{HR['gewst']}"))
    chk(f"HGB tax parts sum to total[{i}]", cell(R, f"{c}{HR['total_tax']}"), parts)

# ----------------------------------------------------------------------------
# 4b. RECONCILE the CARVE-OUT BRIDGE + carve-out EV vs the clean-room truth.
#     (This is the flipped check: the feature now EXISTS and is graded against
#      independent ground truth + model-independent identities, not GAP'd.)
# ----------------------------------------------------------------------------
CB = "Carve-out Bridge"
# Row map (verified from the rendered sheet):
CBR = dict(reported=6, alloc=7, dis=8, tsa=9, onetime=10, standalone_adj=11,
           addback_tsa=14, addback_onetime=15, run_rate=16, entry_multiple=19,
           ev=20, chk_parts=23, chk_runrate=24, chk_ev=25)

# (a) Inputs echo the YAML exactly (no silent transformation).
chk("CB reported EBITDA input", cell(CB, f"D{CBR['reported']}"), cb_reported)
chk("CB allocated corp costs input", cell(CB, f"D{CBR['alloc']}"), cb_alloc)
chk("CB dis-synergies input", cell(CB, f"D{CBR['dis']}"), cb_dis)
chk("CB TSA cost input", cell(CB, f"D{CBR['tsa']}"), cb_tsa)
chk("CB one-time separation input", cell(CB, f"D{CBR['onetime']}"), cb_onetime)
chk("CB entry multiple input", cell(CB, f"D{CBR['entry_multiple']}"), cb_multiple)

# (b) Standalone adjusted EBITDA == clean-room reported+alloc-dis-tsa-onetime.
got_standalone = cell(CB, f"D{CBR['standalone_adj']}")
chk("CB standalone adjusted EBITDA (during TSA)", got_standalone, gt_standalone_adj)

# (c) MODEL-INDEPENDENT IDENTITY #1: the four signed bridge components sum
#     EXACTLY to (standalone - reported). Components are read live, the target
#     is read live, and the equality is the invariant (parts-sum-to-total).
got_alloc = cell(CB, f"D{CBR['alloc']}")
got_dis = -cell(CB, f"D{CBR['dis']}")        # subtracted in the bridge
got_tsa = -cell(CB, f"D{CBR['tsa']}")        # subtracted
got_onetime = -cell(CB, f"D{CBR['onetime']}")  # subtracted
got_reported = cell(CB, f"D{CBR['reported']}")
parts_sum = got_alloc + got_dis + got_tsa + got_onetime
chk("CB bridge parts sum == (standalone - reported)",
    parts_sum, got_standalone - got_reported)
# And the parts themselves match the clean-room signed parts.
for j, (got_p, exp_p) in enumerate(
        zip([got_alloc, got_dis, got_tsa, got_onetime], gt_bridge_parts)):
    chk(f"CB signed bridge part[{j}]", got_p, exp_p)

# (d) MODEL-INDEPENDENT IDENTITY #2: run-rate (steady-state) EXCLUDES TSA +
#     one-time, i.e. run-rate == reported + alloc - dis, AND equivalently
#     run-rate == standalone_adjusted + tsa + one-time (the transitory lines
#     added back). Both forms graded; both must hold to the cent.
got_run_rate = cell(CB, f"D{CBR['run_rate']}")
chk("CB run-rate == reported+alloc-dis (clean room)", got_run_rate, gt_run_rate)
chk("CB run-rate == standalone_adj + TSA + one-time (exclusion identity)",
    got_run_rate,
    got_standalone + cell(CB, f"D{CBR['addback_tsa']}")
    + cell(CB, f"D{CBR['addback_onetime']}"))
# The two transitory add-back lines must equal the original cost magnitudes.
chk("CB TSA add-back == TSA cost", cell(CB, f"D{CBR['addback_tsa']}"), cb_tsa)
chk("CB one-time add-back == one-time cost",
    cell(CB, f"D{CBR['addback_onetime']}"), cb_onetime)

# (e) MODEL-INDEPENDENT IDENTITY #3: carve-out EV == run-rate × multiple, both
#     vs the live product and vs the clean-room EV computed from YAML inputs.
got_ev = cell(CB, f"D{CBR['ev']}")
chk("CB EV == run-rate × entry multiple (live)",
    got_ev, got_run_rate * cell(CB, f"D{CBR['entry_multiple']}"))
chk("CB EV == clean-room run-rate × multiple", got_ev, gt_ev)

# (f) The sheet's OWN three live integrity checks must each recalc to 1.
chk("CB on-sheet check: parts sum to total == 1",
    cell(CB, f"D{CBR['chk_parts']}"), 1.0)
chk("CB on-sheet check: run-rate excludes TSA+one-time == 1",
    cell(CB, f"D{CBR['chk_runrate']}"), 1.0)
chk("CB on-sheet check: EV == run-rate × multiple == 1",
    cell(CB, f"D{CBR['chk_ev']}"), 1.0)

# ----------------------------------------------------------------------------
# 5. CROSS-CHECK the workbook's own QC sheet flags all-pass (live recalc).
# ----------------------------------------------------------------------------
qc_all = cell("QC", "C4")
chk("Workbook QC ALL-PASS == 1", qc_all, 1.0)

# ----------------------------------------------------------------------------
# 6. REPORT
# ----------------------------------------------------------------------------
passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\nHGB carve-out live-Excel reconciliation: {passed}/{total} checks pass")
for name, ok, detail in checks:
    if not ok:
        print(f"  FAIL {name}: {detail}")

# A few representative reconciled numbers for the evidence trail.
print("\n--- representative reconciled values (live cell == clean-room) ---")
print(f"  Rev FY+5 (K9):       {cell(M,'K9'):.4f}  (expect {rev[-1]:.4f})")
print(f"  EBITDA FY+5 (K11):   {cell(M,'K11'):.4f}  (expect {ebitda[-1]:.4f})")
print(f"  Margin FY+5 (K10):   {cell(M,'K10'):.4f}  (= EBITDA/Rev invariant)")
print(f"  Gewerbesteuer K15:   {cell(R,'K15'):.5f}  (expect {gt_gewst[-1]:.5f})")
print(f"  HGB eff rate K22:    {cell(R,'K22'):.5f}  (expect {gt_eff_rate[-1]:.5f})")
print(f"  Total HGB tax K21:   {cell(R,'K21'):.5f}  (KSt+SolZ+GewSt invariant)")
print("\n--- carve-out bridge (live cell == clean-room) ---")
print(f"  Reported EBITDA D6:        {cell(CB,'D6'):.4f}  (input {cb_reported:.4f})")
print(f"  Standalone adj  D11:       {cell(CB,'D11'):.4f}  (expect {gt_standalone_adj:.4f})")
print(f"  Run-rate EBITDA D16:       {cell(CB,'D16'):.4f}  (expect {gt_run_rate:.4f})")
print(f"  Carve-out EV    D20:       {cell(CB,'D20'):.4f}  (expect {gt_ev:.4f})")
print(f"  Bridge parts Σ == Δ?       "
      f"{parts_sum:.6f} == {got_standalone - got_reported:.6f}")

sys.exit(0 if passed == total else 1)

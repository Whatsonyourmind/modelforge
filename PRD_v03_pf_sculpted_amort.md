# PRD — ModelForge v0.3: Project Finance Sculpted Amortization + DSCR-Target Debt Sizing

| Field | Value |
|---|---|
| **Feature ID** | MF-v03-001 |
| **Owner** | L. Stanisljevic |
| **Target release** | ModelForge v0.3.0 |
| **Effort** | 1–2 engineering days |
| **Priority** | P0 — quality blocker for Template 4 (Project Finance) |
| **Status** | Draft, ready for execution |
| **Depends on** | ModelForge v0.2 (shipped 2026-04-16, commit `5dff28f`) |
| **Related artifacts** | `VALIDATION_REPORT.md`, `SCORECARD.md`, `SOTA_AUDIT.md` |

---

## 1. Problem statement

Template 4 (Project Finance, `modelforge/spec/project_finance.py` + `modelforge/builder/sheets/pf_debt.py`) ships with two structural simplifications that cause the base scenario to fail its own DSCR covenants when stress-tested against real deal parameters.

### 1.1 Evidence of the defect

From the 2026-04-16 validation run (`VALIDATION_REPORT.md` §"Friction found — Project Finance DSCR breaches"):

```text
Enfinity Global 276MW Italian Solar PV — €214M senior non-recourse
                  C1     C2     O1      O2      O3      O4      O5
CADS              0.00   0.00   3.35    3.41    3.47    3.53    3.59
Debt service     -0.31  -1.07  -1.53   -3.34   -3.25   -3.16   -3.07
DSCR              --     --    2.19    1.02    1.07    1.12    1.17
DSCR threshold    --     --    1.20    1.25    1.25    1.30    1.30
Breach?            —     —      0       1       1       1       1
```

Both PF workbooks (demo `project_finance_solar.xlsx` and real `real_enfinity_solar_pf.xlsx`) register 10+ DSCR breaches over a 20-year operating horizon in BASE. The engine is computationally correct; the model is wrong.

### 1.2 Root causes

1. **Linear amortization** (`=-senior_amount / amort_years`) front-loads principal against a flat revenue profile. Real infra PF uses a **sculpted curve** — either level-debt-service or DSCR-targeted — to match the cash profile.
2. **Debt is an input, not a solved output.** Real lenders size senior debt *from* a target DSCR (typically 1.30x BASE / 1.10x downside). The template takes `senior_amount` as an `Assumption`, so users who plug in real deal numbers against our simplified revenue curves will always breach.
3. No **DSRA (Debt Service Reserve Account)**. Market-standard infra PF carries 6 months of reserve; absence makes year-1 breaches look more acute than they are.

### 1.3 Commercial impact

- **Today**: Luka cannot pitch Template 4 output to a credit committee — the base scenario fails its own covenants. Estimated 20-30% of Italian PNRR + FER X deal flow that touches his pipeline is PF.
- **After fix**: Template 4 jumps from **6/10 → 9/10** on the bulge-tier scorecard (per `SCORECARD.md` weights), bringing the overall ModelForge weighted score from **8.1 → 8.3** and closing the single most cited limitation in the validation report.

---

## 2. Goals & non-goals

### 2.1 Goals

1. PF base scenario must pass all DSCR covenants on both demo (`project_finance_solar.yaml`) and real (`real_enfinity_solar_pf.yaml`) specs with zero user re-tuning.
2. Add two new amortization profiles: **sculpted level-debt-service** and **sculpted DSCR-target**.
3. Add a **DSCR-target debt sizing mode** with deterministic iterative solver.
4. Add **DSRA (6-month default)** as a first-class reserve line on the PF cashflow sheet.
5. All changes are backwards-compatible: existing YAMLs continue to build with zero edits (defaults preserve v0.2 behaviour).
6. Every new cell respects the ModelForge locked architectural rules: live formula, blue/black/green colour convention, named range on Assumptions, source-traceable when numeric.

### 2.2 Non-goals

- **Production degradation curves** (0.5%/yr module degradation) — queued for separate v0.3 line item.
- **First-year COD ramp factor** (`y1_ramp_factor = 0.85`) — separate line item.
- **Multi-tranche PF** (senior + mezz + sub) — out of scope; single senior tranche today.
- **Refinancing / mini-perm structures** — out of scope.
- **Interest rate hedge accounting** — out of scope.
- **Sensitivity sweeps on amort profile** — lands with roadmap item #3.

---

## 3. Users & user stories

### 3.1 Personas

- **P1 — Luka (primary)**: credit/structured finance analyst building PF models for Italian mid-market clients. Needs a committee-grade deliverable in hours, not days.
- **P2 — Client MD (e.g., Enfinity-style sponsor, FER X bidder)**: reviews the PF workbook before pitching lenders. Expects DSCR discipline and DSRA as standard.
- **P3 — Rating agency / lender analyst**: reads the workbook downstream. Expects sculpted amort, DSCR-target sizing, and provenance.

### 3.2 Stories

- **US-1** (P1): *As Luka, I want to flip `debt_sizing_mode: dscr_target` in the YAML and have ModelForge solve the senior debt amount that exactly meets BASE DSCR 1.30x, so I don't hand-iterate.*
- **US-2** (P1): *As Luka, I want the Enfinity spec's existing €214M senior amount to pass covenants under `amortization_profile: sculpted_level_debt_service`, so the real-deal workbook ships clean.*
- **US-3** (P2): *As a sponsor MD, I want to see a Debt Schedule that matches what ING/Rabobank/BNPP would issue — sculpted amort + DSRA — so I can put this in front of lenders without re-drawing it.*
- **US-4** (P3): *As a lender analyst, I want every debt-schedule cell to remain a live formula with its solver inputs named and cited, so I can audit the debt sizing mechanism.*
- **US-5** (P1): *As Luka, I want v0.2 PF workbooks to keep building without YAML changes, so I don't regress eight already-shipped deliverables.*

---

## 4. Functional requirements

### FR-1 — Spec extensions (`modelforge/spec/project_finance.py`)

Add two enumerations and two new fields on `PFDebt`:

```python
from typing import Literal

AmortizationProfile = Literal[
    "linear",                           # v0.2 behaviour (default for back-compat)
    "sculpted_level_debt_service",      # equal total debt-service per period
    "sculpted_dscr_target",             # principal solved each period to hit target DSCR
    "bullet",                           # interest-only, principal at maturity
]

DebtSizingMode = Literal[
    "fixed_amount",                     # v0.2 behaviour (default)
    "dscr_target",                      # iterative solver
]

class PFDebt(BaseModel):
    name: Label
    amount: Assumption                  # treated as seed/cap when debt_sizing_mode=dscr_target
    tenor_operating_years: int
    grace_years: int = 2
    reference_rate: Assumption
    margin_bps: Assumption
    arrangement_fee_pct: Assumption
    # NEW in v0.3
    amortization_profile: AmortizationProfile = "linear"
    debt_sizing_mode: DebtSizingMode = "fixed_amount"
    target_dscr_base: Optional[Assumption] = None     # required when dscr_target
    target_dscr_downside: Optional[Assumption] = None # optional, used by worst scenario
    dsra_months: int = Field(default=6, ge=0, le=12)  # DSRA sizing
```

Add a pydantic `model_validator` that errors clearly when `debt_sizing_mode == "dscr_target"` but `target_dscr_base is None`.

### FR-2 — Solver (`modelforge/builder/sheets/pf_debt.py` or new `pf_solver.py`)

Two deterministic solvers, both implemented in Python at build time (write resulting numeric values into named ranges on Assumptions; formulas in the workbook then reference those named ranges — no Excel-side iterative calc dependency).

#### FR-2a — Level-debt-service amortization schedule

For a given senior `amount`, `tenor_operating_years`, `grace_years`, and all-in rate `r`:

```
amort_years  = tenor_operating_years - grace_years
# Level debt-service constant C such that: Σ discounted payments = amount
# Closed form (standard annuity): C = amount * r / (1 - (1+r)^-amort_years)
# Principal in period t = C - interest_t
# Interest_t = opening_balance_t * r
```

Output: a list of principal repayments `[0]*grace_years + [p_1, p_2, ..., p_N]` written as **numbers** into a named range `pf_amort_schedule_pct` (expressed as % of original amount so scenario-scaling stays clean).

#### FR-2b — DSCR-target sizing

Pre-compute projected CADS per operating year (CADS = Revenue × (1 − Opex%) − Tax, already computed deterministically from the Operating spec). Then:

```
target_dscr = spec.debt.target_dscr_base.base  # BASE scenario
max_debt_service_per_year = CADS_t / target_dscr
# Solve for principal amount P such that level debt service at rate r over amort_years
# equals min(max_debt_service_per_year across amort period)
P = binary_search(
    lower=0,
    upper=spec.debt.amount.base,        # input treated as cap
    objective=lambda p: max_ds(level_schedule(p, r, amort_years))
                         <= min_t(max_debt_service_per_year)
)
```

- Tolerance: 0.01 EUR m (€10k).
- Max iterations: 50. Solver MUST terminate — on failure, fall back to `fixed_amount` and emit a warning.
- Resulting `P` overrides `senior_amount` on the Assumptions sheet (still a named range, blue-styled, but labelled "Senior debt (solved)" with cell comment citing DSCR target).

### FR-3 — Debt Schedule sheet changes (`pf_debt.py`)

1. **Rename** the linear amort row to "Scheduled amortization" (unchanged) but change its formula based on `amortization_profile`:
   - `linear` → unchanged (`=-senior_amount / amort_years`)
   - `sculpted_level_debt_service` → `=-senior_amount * INDEX(pf_amort_schedule_pct, op_year_index)`
   - `sculpted_dscr_target` → same as `sculpted_level_debt_service` but schedule is solver-derived
   - `bullet` → `0` for all years except last: `=-senior_amount`
2. **Add DSRA rows** directly under "Total debt service":
   - `DSRA target balance` = `dsra_months / 12 * abs(debt_service_next_year)` for op years, 0 during construction, 0 in final year.
   - `DSRA funding` = change-in-DSRA-balance (negative when funding, positive on release).
   - `DSRA interest` = opening DSRA balance × ref_rate (credit line, optional — default on).
3. **DSCR row** unchanged; it references the new debt-service row automatically.

### FR-4 — Cashflow sheet changes (`pf_cashflow.py`)

Cash waterfall must now subtract DSRA funding *before* DSCR is calculated:

```
Operating cash flow
  − Opex
  − Tax
  = CFADS (Cash Flow Available for Debt Service)   ← used in DSCR numerator
  − Senior debt service (int + principal)
  − DSRA funding                                   ← new line
  = Cash to equity waterfall
```

**Important**: DSCR numerator stays CFADS *before* DSRA (market convention). DSRA only affects distributable cash and lock-up tests. Verify with Macabacus PF reference before shipping.

### FR-5 — Assumptions sheet additions

New named ranges on Assumptions:
- `amortization_profile_code` — integer 1-4 driving a CHOOSE in the Debt Schedule (for display + scenario banners).
- `target_dscr_base` — added only when `debt_sizing_mode=dscr_target`.
- `target_dscr_downside` — same, if set.
- `dsra_months` — always written (default 6).
- `pf_amort_schedule_pct` — array named range (1 × N years).

All follow existing styling: blue for hardcoded inputs, green for cross-sheet refs, cell comment with source citation when numeric comes from a source.

### FR-6 — QC additions (`modelforge/builder/sheets/generic_qc.py`)

Extend the 12-check QC gate to 14 checks for PF specifically (Template 4 only, detected via `spec.model_type == "project_finance"`):

- **QC-13**: "PF — Zero DSCR breaches in BASE scenario" = `=Debt!TotalBreaches_base = 0`
- **QC-14**: "PF — DSRA fully funded by end of Y1 operating" = `=ABS(DSRA_balance_O1 - DSRA_target_O1) < 0.01`

These are hard-fail: if they fail, `qc` CLI exits non-zero and blocks export. This is the new quality gate.

### FR-7 — YAML back-compatibility

- Missing `amortization_profile` → defaults to `"linear"` (v0.2 behaviour).
- Missing `debt_sizing_mode` → defaults to `"fixed_amount"` (v0.2 behaviour).
- Missing `dsra_months` → defaults to `6`, but template also writes `dsra_months: 0` workaround if an existing v0.2 workbook needs exact parity (set via CLI flag `--legacy-dsra-off` for regression tests only).
- All 8 shipped example YAMLs must rebuild without edits. The two PF examples are updated in this PRD's deliverable set.

### FR-8 — CLI surface

No new commands. Existing `modelforge build <yaml>` and `modelforge qc <xlsx>` pick up the new behaviour automatically.

New flag on `build`:
- `--show-solver-steps` (optional) prints solver iterations to stdout for debugging.

---

## 5. Technical design

### 5.1 Module layout

```
modelforge/
  spec/project_finance.py        # extended (FR-1)
  builder/
    pf_solver.py                 # NEW — sculpted amort math + DSCR solver (FR-2)
    sheets/
      pf_debt.py                 # extended (FR-3)
      pf_cashflow.py             # extended DSRA lines (FR-4)
      assumptions.py             # writes new named ranges (FR-5)
      generic_qc.py              # +2 PF-specific checks (FR-6)
  data/pf_amort_reference.csv    # optional — reference schedules for tests
examples/
  project_finance_solar.yaml     # updated to exercise sculpted + dscr_target
  real_enfinity_solar_pf.yaml    # updated; must ship clean
```

### 5.2 Math — sculpted level-debt-service (closed form)

Given principal `P`, rate `r` (all-in annual), and `n` amort years:

```
C = P × r / (1 − (1 + r)^(−n))      # annuity constant
balance_0 = P
for t = 1..n:
    interest_t   = balance_{t−1} × r
    principal_t  = C − interest_t
    balance_t    = balance_{t−1} − principal_t
```

Write `[principal_t / P for t in 1..n]` into `pf_amort_schedule_pct` as percentage-of-original. Then debt schedule formulas multiply by `senior_amount` named range, so scenario scaling stays live.

### 5.3 Math — DSCR-target sizing (binary search)

```python
def solve_dscr_target_debt(
    cfads: list[float],          # length = operating_years
    rate: float,                  # all-in
    amort_years: int,
    grace_years: int,
    target_dscr: float,
    cap: float,                   # initial upper bound (user-supplied amount.base)
    tol: float = 0.01,
    max_iter: int = 50,
) -> float:
    lo, hi = 0.0, cap
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        schedule = level_debt_service(mid, rate, amort_years, grace_years)
        # Per-year DSCR at this mid
        dscrs = [cfads[t] / abs(schedule[t]) if schedule[t] else float("inf")
                 for t in range(len(cfads))]
        min_dscr = min(dscrs)
        if abs(min_dscr - target_dscr) < tol * 0.001:
            return mid
        if min_dscr < target_dscr:    # debt too large → shrink
            hi = mid
        else:                          # debt can grow
            lo = mid
        if (hi - lo) < tol:
            return lo
    return lo
```

**Rationale for binary search over Newton**: CFADS is a step-function of debt (via interest → tax shield interactions), so Newton can overshoot. Binary search is slow but always terminates on a monotone interval. 50 iterations on a €50M–€500M range with €10k tol is <1ms.

### 5.4 Data flow

```
YAML spec
  → ProjectFinanceSpec (pydantic)
  → if debt_sizing_mode == "dscr_target":
       pre_compute_cfads(spec)           # run Operating sheet math in memory
       solved_amount = solve_dscr_target_debt(...)
       spec.debt.amount.base = solved_amount  # mutate in place, set rationale
       spec.debt.amount.rationale += " [solved from target DSCR 1.30x]"
  → base_workbook.emit(spec)             # unchanged downstream
```

The solver runs **once at build time**. The resulting number becomes a hardcoded input on the Assumptions sheet (blue). All Excel formulas reference the named range live — no INDEX(MATCH(...)) gymnastics in cells, no circular Excel iteration.

### 5.5 Scenario handling

Three scenarios (Worst/Base/Best) share one amortization schedule (solved at BASE DSCR target). Margin, reference rate, and CADS still flex by scenario, so DSCR moves by scenario — this is correct lender behaviour (debt is sized once; outcomes vary).

Optional: `target_dscr_downside` re-solves at WORST to stress-test whether even the sized debt clears a downside hurdle. If it fails, emit warning at build time (doesn't block).

### 5.6 Linkage graph updates (`modelforge/graph/`)

Every new cell gets its normal graph nodes + edges. Two new node types:
- `SOLVER:dscr_target_pf` — records solver inputs (CFADS array, rate, target DSCR) + output (solved amount).
- `RESERVE:DSRA` — the DSRA mechanism node, linked to each DSRA row.

Ensures `modelforge lineage <db> <CELL:Assumptions!senior_amount>` shows the solver path.

---

## 6. Acceptance criteria

Each criterion is a pass/fail gate; all must pass before shipping.

| # | Criterion | Verification |
|---|---|---|
| AC-1 | `examples/project_finance_solar.yaml` rebuilds with no YAML changes → identical v0.2 output | `diff` of generated xlsx structural hash |
| AC-2 | `project_finance_solar.yaml` with `amortization_profile: sculpted_level_debt_service` added → BASE DSCR ≥ 1.20× every operating year | `audit_compute.py` DSCR check |
| AC-3 | `real_enfinity_solar_pf.yaml` with `debt_sizing_mode: dscr_target` + `target_dscr_base: 1.30` → solver returns senior in [€180M, €214M] range; BASE DSCR clears 1.30 ± 0.02 | `audit_compute.py` + manual inspection |
| AC-4 | `real_enfinity_solar_pf.yaml` with existing €214M fixed and new `sculpted_level_debt_service` → zero DSCR breaches in BASE | `audit_compute.py` |
| AC-5 | DSRA row present, funded to 6 months of next-year debt service by end of operating Y1 | QC-14 passes |
| AC-6 | QC gate returns 14/14 on both PF workbooks | `modelforge qc` exit code 0 |
| AC-7 | All 7 other templates (Unitranche, Minibond, Credit Memo, RE, NPL, SC, 3S) rebuild unchanged; their QC still reports 8/8 | Full regression run |
| AC-8 | Linkage graph contains `SOLVER:dscr_target_pf` node linked to the solved `Assumptions!senior_amount` cell for dscr_target builds | `modelforge lineage` walk |
| AC-9 | Solver terminates in ≤ 50 iterations on Enfinity spec | Log instrumentation |
| AC-10 | Unit tests added: `test_pf_solver.py` with ≥ 6 cases (annuity math, DSCR solver convergence, edge cases, back-compat) | `pytest` green |
| AC-11 | Sign convention unchanged: all amort rows still negative | Automated sign-convention audit |
| AC-12 | Every new numeric Assumption has an `id`, `name`, `rationale`, `source_id` (even if the source is `SOLVER` for solved values) | Audit script |

---

## 7. Validation plan

### 7.1 Regression suite

Run `audit_suite.py` + `audit_compute.py` across all 10 existing workbooks after the change. Expect:

- 10/10 structural clean.
- 10/10 computational clean (was 8/10 before — the two PF files fix).

### 7.2 Real-deal replay

Build `real_enfinity_solar_pf.yaml` in three configurations and compare:

| Config | amort profile | sizing mode | Expected senior | Expected min DSCR |
|---|---|---|---|---|
| V0.2 baseline | linear | fixed | €214M | 1.02 (breach) |
| V0.3 sculpted | sculpted_level_debt_service | fixed | €214M | ≥ 1.20 |
| V0.3 solved | sculpted_level_debt_service | dscr_target (1.30) | ~€195M | 1.30 ± 0.02 |

Delta between €214M (actual deal) and ~€195M (our solved number) is a *useful* output — tells us our revenue/opex curves assume less optimism than the actual lenders used, or Enfinity absorbed bank appetite for the higher quantum. Either interpretation is defensible; document both in the workbook cover notes.

### 7.3 Unit tests

`tests/test_pf_solver.py`:

1. Level-debt-service annuity math agrees with Excel PMT() to 4 decimals on a known case (€100M, 5%, 10y).
2. DSCR solver converges on a synthetic CFADS array to an analytic answer.
3. Solver returns zero when CFADS is too low to support any debt.
4. Solver caps at `amount.base` when target DSCR easily met.
5. Back-compat: missing new fields → identical output to v0.2 builder.
6. DSRA balance funds correctly and releases at maturity.

### 7.4 Manual QA

Open both PF workbooks in Excel; flip `Cover!C17` across Worst/Base/Best; verify scenario banner colour shifts and DSCR values move coherently.

---

## 8. Risks & mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Binary-search solver fails to converge on pathological CFADS | Low | Medium | 50-iter cap + fallback to fixed_amount + build-time warning |
| R-2 | DSRA cashflow-waterfall change breaks scenario tests | Medium | Medium | AC-7 regression; feature-gated on PF only |
| R-3 | Real Enfinity solver disagrees materially with €214M actual deal → credibility question | Medium | Low | Document the gap with source-cited rationale; offer both modes |
| R-4 | `formulas` library evaluation gap widens with new formulas | Low | Low | Keep all logic in Python; formulas in sheets stay arithmetic-only |
| R-5 | Back-compat regression on the 8 other templates | Low | High | AC-1 / AC-7 are hard blockers; full audit_suite before merge |
| R-6 | Scope creep into production-curve / ramp features | Medium | Medium | Explicit non-goals §2.2; defer to separate v0.3 line items |

---

## 9. Out of scope (explicitly)

- Production degradation curves (separate line item).
- Y1 ramp factor (separate line item).
- Multi-tranche PF / mezz layers.
- Hedge accounting.
- Monte Carlo on amort profile (roadmap #3).
- Data-room ingestion for PF specs (roadmap #1).
- Any change to non-PF templates.

---

## 10. Milestones & timeline

| Day | Milestone | Deliverable |
|---|---|---|
| D1 AM | Spec extensions + solver module | FR-1, FR-2 code; `test_pf_solver.py` green |
| D1 PM | Debt & cashflow sheet rewrites | FR-3, FR-4 code; single PF workbook builds clean |
| D2 AM | QC additions + regression | FR-6 code; `audit_suite.py` passes 10/10 |
| D2 PM | Real-deal validation + ship | AC-1..AC-12 signed off; commit + tag `v0.3.0-pf` |

Stretch (half day): update `SCORECARD.md` with new PF score (6→9); update `VALIDATION_REPORT.md` to mark friction resolved.

---

## 11. Success metrics

Measured 7 days post-ship:

1. **Quality**: `audit_compute.py` reports 10/10 clean on both PF workbooks in BASE. **Target: 100%.**
2. **Scorecard**: PF template weighted score 6/10 → 9/10. **Target: ≥ 9.**
3. **Solver behaviour**: DSCR solver converges within 50 iterations on all test specs. **Target: max 30 iter.**
4. **No regression**: 8 non-PF templates' QC still 8/8. **Target: 0 regression.**
5. **Pitch-readiness**: Luka can hand Template 4 output to a client without manual post-build edits. **Target: binary — yes.**

---

## 12. Rollout

- Single commit titled `feat(pf): v0.3 sculpted amort + DSCR-target sizing + DSRA`.
- Tag `v0.3.0-pf` (partial v0.3 — other roadmap items will incrementally add tags).
- Update `README.md` with new YAML field reference.
- Update `SOTA_AUDIT.md` — add a v0.3 addendum citing the change.
- No migration needed (back-compat preserved).

---

## 13. Follow-up items (post-ship, not blockers)

Queue for separate work:
- `y1_ramp_factor` (first-year COD 85%).
- `production_degradation_pct_annual` (0.5%/yr).
- `refinancing_year` (mini-perm structure support).
- Worst-case DSCR solver (target_dscr_downside = 1.10 in WORST).

These become fast follows (each ≤ half day) once the solver + sculpted amort infrastructure is in place.

---

**Prepared**: 2026-04-16 · **Author**: L. Stanisljevic + Claude · **Ready for execution.**

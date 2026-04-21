# PRD — ModelForge v0.6 "Stress-Test Remediation"

**Status**: drafted 2026-04-21, to be shipped same day (P0/P1) + within 1 week (P2) + v0.6 cycle (P3)
**Owner**: Luka Stanisljevic
**Trigger**: adversarial external audit against WSO / WSP / Macabacus / BIWS on 2026-04-21 surfaced 98 findings (6 CRITICAL / 13 HIGH / 79 MEDIUM). Internal audit had reported 0 errors; gap is the operational risk we ship to paid engagements with today.

---

## Executive summary

v0.5 shipped a 9.75/10 projected scorecard and an "ENGINE DONE" headline. External benchmarking finds **6 CRITICAL bugs** (circular reference without iter-calc in 2 of 13 files; all cells from drawdown column onwards resolve to `None`), **13 HIGH** (off-by-one in 2 templates, hardcoded football field in fairness, flat debt row in 3-statement, hardcoded bridge values in DCF), and **79 MEDIUM** (magic numbers in merger/DCF/fairness, PF tax simplification, sweep formula uses inflated base).

v0.6 closes the gap. After v0.6, the 15 missing audit checks are also in `audit_compute.py` so the internal audit matches external expectations going forward.

---

## Success criteria

Ship v0.6 when:

1. `python adversarial_audit.py` reports **0 CRITICAL, 0 HIGH**, and only expected MEDIUM (e.g. historical-data `-3900` is legitimately hardcoded because it's a reported filing number with a source comment)
2. `python audit_compute.py` implements the 15 new checks from the stress-test report and still reports **0 errors** across all 13 workbooks
3. All 13 workbooks open in Excel without a circular-references warning
4. Debt is fully amortized (`|closing| < 0.01`) at maturity year for every file with a `tenor`
5. Merger accretion/dilution shows reasonable progression (every year's formula references that year's pro-forma NI, and accretion <30% in BASE unless synergies genuinely justify more)
6. Fairness football field updates when a trading comp value changes
7. PF `real_enfinity_solar_pf` DSCR in BASE ≥ 1.30x with tax computed on EBIT (not EBITDA proxy), LLCR computed and reported
8. 3-statement model includes a debt schedule; historical D&A/capex/AR/Inv/PPE pulled from spec historical-data block (not synthesized from %)
9. SCORECARD.md updated with post-v0.6 weighted score
10. No regression in the 349 existing pytest tests; 30+ new tests for the new checks

---

## Scope

In scope — 26 stories grouped by priority:

### P0 — Critical same-day fixes (5 stories)

| ID | Story | Effort |
|----|-------|--------|
| US-060 | Enable iterative calculation in base_workbook | 1h |
| US-061 | Break sweep circular with prior-period leverage | 3h |
| US-062 | Fix minibond amortization off-by-one (start and maturity) | 1h |
| US-063 | Fix unitranche/credit-memo amortization off-by-one | 1h |
| US-064 | Fix merger accretion/dilution column off-by-one and hardcoded standalone EPS | 3h |

### P1 — High-priority fixes this week (6 stories)

| ID | Story | Effort |
|----|-------|--------|
| US-065 | Fairness football field: live-link to Trading/Transaction/DCF/LBO/52W | 4h |
| US-066 | Fairness: replace 950/226/25 magic numbers with Assumptions | 1h |
| US-067 | DCF: replace net_debt/shares_out/current_price hardcodes with Assumptions | 2h |
| US-068 | DCF: add mid-year convention toggle, remove INDIRECT | 2h |
| US-069 | Merger: replace all margin/D&A/interest/share hardcodes with Assumptions | 6h |
| US-070 | DCF: split Gordon vs Exit Multiple TV (no averaging) | 1h |

### P2 — This-week fixes (7 stories)

| ID | Story | Effort |
|----|-------|--------|
| US-071 | PF: proper tax = (EBIT − Interest) × rate, with D&A schedule | 6h |
| US-072 | PF: CFADS = EBITDA − tax − ΔWC − maintenance capex | 3h |
| US-073 | PF: add LLCR and PLCR rows | 2h |
| US-074 | LBO: FCF-to-debt subtracts cash interest before sweep | 2h |
| US-075 | 3-statement: add debt schedule section within Model sheet | 4h |
| US-076 | 3-statement: accept real historical D&A/capex/AR/Inv/PPE from spec | 3h |
| US-077 | Sensitivity: verify tornado propagates to operating drivers after C-1 fix | 2h |

### P3 — v0.6 completion (8 stories)

| ID | Story | Effort |
|----|-------|--------|
| US-078 | Real estate: LP/GP waterfall with pref + catchup + promote | 6h |
| US-079 | NPL: tranched waterfall with priority of payments | 6h |
| US-080 | Comps: add Min / Q1 / Q3 / Max rows (completing distribution) | 1h |
| US-081 | Expand Trading and Transaction comps sets to 6-10 each | 2h |
| US-082 | audit_compute.py: add 15 new checks (see below) | 6h |
| US-083 | Updated SCORECARD.md with post-v0.6 weighted score | 1h |
| US-084 | Migration script: regenerate all 13 workbooks + diff against prior | 2h |
| US-085 | pytest: 30+ new test cases covering the new checks | 4h |

**Out of scope (deferred to v0.7+):**
- Excel add-in (US-010 remains deferred)
- Web UI / multi-tenant (deferred per action plan)
- Equity cure iteration, springing covenants (covenant machinery polish)
- OCR for scanned data-room PDFs
- Cross-doc reconciliation during ingestion

---

## Story details

### US-060 Enable iterative calculation

**Cells affected**: every workbook's calcPr XML.
**Code change**: `modelforge/builder/base_workbook.py` and `modelforge/builder/workbook.py` — after `wb = Workbook()`, add:

```python
wb.calculation.iterate = True
wb.calculation.iterateCount = 100
wb.calculation.iterateDelta = 0.001
```

**Acceptance**: `openpyxl.load_workbook(f).calculation.iterate is True` for all 13 outputs.
**Why**: belt-and-braces — even after US-061 eliminates the structural circular, enabling iter calc means *any* future builder pattern that inadvertently creates a circular will still converge rather than fail silently.

---

### US-061 Break sweep circular with prior-period leverage

**Cells affected**: `DebtSchedule!Gn:Mn` in `unitranche_cdmo.xlsx` and `credit_memo_cdmo.xlsx` where n is the sweep-row in each file.

**Current (broken)**:
```
G19 (sweep) = -IF(G18 > trigger, MAX(Operating!G28,0) * sweep_pct, 0)
G18 (leverage) = G11 / Operating!G13          ← same-period closing
G11 (closing) = G8 + G9 + G10
G10 (amort) = G19                              ← CIRCULAR
```

**New**:
```
G19 (sweep) = -IF(F18 > trigger, MAX(Operating!G28,0) * sweep_pct, 0)
                         ↑↑↑ prior period
F18 (leverage already computed for prior) — resolves first, no cycle.
```

For the first-operating-period (no prior leverage to check against), fall back to the entry leverage ratio at close:
```
G19 (first op year only) = -IF(entry_leverage > trigger, MAX(Operating!G28,0) * sweep_pct, 0)
```
Where `entry_leverage` is a new derived named range = `senior_unitranche_amount / last_historical_ebitda`.

**Code change**: `modelforge/builder/sheets/debt.py` lines 260-290 (cash-sweep block). Also update `formulas.py::cash_sweep` to accept a prior-col leverage ref.

**Acceptance**:
1. `detect_same_period_circular(wb, "DebtSchedule")` returns empty on both files.
2. `openpyxl.load_workbook(f)` evaluation via `formulas` library produces finite values for every debt-schedule cell from drawdown onwards.
3. Lender IRR in Returns sheet is a finite number between 5% and 15% under BASE.

**Why**: the dependency now flows one direction (prior → current), eliminating the cycle by design. Excel opens without a warning and without requiring iter calc.

---

### US-062 / US-063 Minibond + unitranche amortization off-by-one

**Root cause** (`bond_structure.py` and `debt.py`):

```python
maturity_year = h + tenor           # wrong: treats tenor as exclusive years-after-draw
amort_start = h + amortization_start_year  # same off-by-one
```

For tenor=6 with drawdown at Y1 (i=h), maturity IS Y6 (i=h+5). So:

```python
maturity_year = h + tenor - 1       # ✓
amort_start  = h + amortization_start_year - 1   # ✓
```

**Verification example** — minibond notional=20, tenor=6, linear_from_year=3:
- **Before fix**: amort at J,K,L,M of 5 each; closing G:20, H:20, I:20, J:15, K:10, **L:5** (maturity but balance ≠ 0), M:0
- **After fix**: amort at I,J,K,L of 5 each; closing G:20, H:20, I:15, J:10, K:5, **L:0** ✓

**Code change**: 1 line in each of `bond_structure.py` line ~83 and `debt.py` line 109. Add a comment documenting the "Year 1 = drawdown year" convention.

**Acceptance**:
1. For every file with tenor>0, `closing_debt[maturity_year] < 0.01`.
2. Zero net debt at maturity column in computed values.
3. New pytest test: `test_amortization_closes_at_maturity` covering linear, bullet, mandatory_1pct, sculpted profiles.

---

### US-064 Merger accretion/dilution fixes

**Root cause** (`merger_proforma.py` or dedicated accretion builder):
Column iteration uses prior column reference in the loop for cols 4-5 due to a copy-paste bug. Also standalone EPS (row 7) is hardcoded per-year rather than computed.

**Current (broken)** — cols D,E,F,G,H,I on AccretionDilution row 8:
```
D8 = ProForma!D27 / (21200 + DealStructure!D15)
E8 = ProForma!E27 / (21200 + DealStructure!D15)
F8 = ProForma!F27 / (21200 + DealStructure!D15)
G8 = ProForma!F27 / (21200 + DealStructure!D15)   ← DUP of F
H8 = ProForma!G27 / (21200 + DealStructure!D15)   ← off by one
I8 = ProForma!H27 / (21200 + DealStructure!D15)   ← off by one
```

**Fix**: loop over enumerated columns with monotonic reference advance. Also compute standalone EPS as a formula:
```
R7 (standalone acquirer EPS)  Dn = ProForma!acquirer_ni_n / acquirer_shares_out
```

**Acceptance**:
1. No two consecutive cells in AccretionDilution have identical formulas.
2. Standalone EPS is a formula referencing ProForma net income, not a hardcoded number.
3. Accretion % is plausible: Y1 < 30% in BASE unless synergy math genuinely justifies more.

---

### US-065 Fairness football field live-linking

**Current**: all 10 EV low/high cells hardcoded.

**New**: each methodology derives its range from the upstream sheet.

```
Trading comps (EV/EBITDA median ±1×):
  B6 = (MEDIAN(TradingComps!B6:B9) - 1) * fy1_ebitda
  C6 = (MEDIAN(TradingComps!B6:B9) + 1) * fy1_ebitda

Transaction comps (EV/EBITDA median ±1×):
  B7, C7 = same pattern on TransactionComps

DCF range:
  B8 = explicit_pv + PV_of_TV_at_wacc_high     (low DCF)
  C8 = explicit_pv + PV_of_TV_at_wacc_low      (high DCF)
  (new: add hidden DCF shadow calc block with wacc+/-1pp and g+/-0.5pp)

LBO implied EV:
  B9 = equity_required_low * (1 + net_debt_to_equity_ratio)
  C9 = equity_required_high * (1 + ...)

52W range:
  B10 = shares_outstanding * 52w_low
  C10 = shares_outstanding * 52w_high
```

**Code change**: new `fairness_football.py::build_live_links` function. Requires adding an `fy1_ebitda` named range (`=Assumptions!acquirer_ebitda_fy1`) and a mini-DCF shadow calc block (separate hidden sheet `DCF_Shadow` or inline in Football).

**Acceptance**:
1. Changing `TradingComps!B6` (Sonova EV/EBITDA) changes `FootballField!B6:C6`.
2. All 10 EV low/high cells contain formulas, not raw numbers.
3. Football field printout still fits on one page.

---

### US-066 / US-067 Replace magic numbers with Assumptions

New driver names (Italian + English labels, source attribution):

| Driver | En label | Unit | Source |
|--------|----------|------|--------|
| `target_net_debt_eur_m` | Target net debt | EUR m | 10-K / annual report p. [X] |
| `target_shares_outstanding_m` | Target shares out | m shares | Filing / DEF 14A |
| `current_share_price_eur` | Current share price | EUR | Bloomberg / close date [Y] |
| `acquirer_shares_outstanding_m` | Acquirer shares out | m shares | Filing |
| `acquirer_current_share_price_eur` | Acquirer share price | EUR | Bloomberg |

Spec files (`dcf.py`, `merger.py`, `fairness.py`) gain typed `target_market_data: TargetMarketData` block:
```python
class TargetMarketData(BaseModel):
    net_debt: Assumption
    shares_outstanding: Assumption
    current_price: Assumption
    _52w_low: Assumption | None = None
    _52w_high: Assumption | None = None
```

**Acceptance**: adversarial audit reports 0 "Magic number" findings on DCF, merger, fairness.

---

### US-068 DCF mid-year convention

**Current** (`dcf_valuation.py`):
```
Valuation!D5 = SUMPRODUCT(G16:K16, (1+wacc)^-ROW(INDIRECT("1:5")))
```

**New** — add `mid_year_convention: bool` to the DCF spec (default True per Macabacus). Replace INDIRECT with SEQUENCE for Excel 365, fall back to explicit terms:
```
Valuation!D5 = G16/(1+wacc)^t1 + H16/(1+wacc)^t2 + ... + K16/(1+wacc)^t5
where t_i = i - 0.5 * mid_year_toggle
```

For TV:
```
Valuation!D9 = TV / (1+wacc)^(n - 0.5 * mid_year_toggle)
```

**Acceptance**:
1. No INDIRECT function anywhere in the workbook (grep workbook XML).
2. Toggling mid_year_convention between True/False visibly changes EV by ~2-4%.

---

### US-070 DCF: no averaging of Gordon and Exit Multiple

Delete the `=AVERAGE(D6, D7)` row. Keep both TVs side-by-side. The football field (US-065) will show the range.

**Acceptance**: Valuation sheet presents two separate EV rows (Gordon-based, Exit-Multiple-based) with no implicit average.

---

### US-069 Merger: replace all hardcoded acquirer/target historical data

Same pattern as US-066 but for the merger inputs:

```python
class MergerAcquirerData(BaseModel):
    revenue_history: list[Assumption]         # Yn, Yn-1, Yn-2
    ebitda_margin_history: list[Assumption]
    da_history: list[Assumption]
    interest_expense_history: list[Assumption]
    shares_outstanding: Assumption
    current_share_price: Assumption
```

Loop the builder over the history and project lists so no raw numbers appear in formulas.

**Acceptance**: `grep -E "\b[0-9]{4,}\b" output/merger_tim_iliad.xlsx | count` returns 0 hits outside the Sources sheet.

---

### US-071 PF proper tax with D&A shield

**Current** (`pf_cashflow.py` R14):
```
=-MAX(EBITDA, 0) * effective_tax_rate
```

**New**: add new rows to ProjectCashFlow:
```
R_new1  D&A (straight-line)       = -total_capex / useful_life_years         per operating year
R_new2  EBIT                       = EBITDA + D&A                             per operating year
R_new3  Interest paid              = DebtDSCR!total_interest (cross-sheet)    per operating year
R_new4  EBT                        = EBIT + Interest paid                     per operating year
R_new5  Taxable income             = MAX(EBT, 0)                              per operating year
R14 (tax) =-Taxable income * effective_tax_rate
```

Plus optional NOL carryforward block (Italian 5y rule, 80% offset):
```python
# Year 1: NOL_bal_0 = 0; if EBT < 0, NOL_bal += |EBT|
# Year t: taxable = MAX(EBT_t - MIN(EBT_t * 0.8, NOL_avail), 0)
#         NOL_avail -= utilisation; expire after 5 years
```

**Acceptance**:
1. Tax row label no longer says "(on EBITDA proxy)".
2. Y1 tax = 0 if there's an NOL from construction period.
3. Average DSCR base rises by ~10-15% vs. pre-fix (Enfinity).
4. New pytest: `test_pf_tax_matches_ebit_shield`.

---

### US-072 CFADS includes WC and maintenance capex

**Current** (`pf_cashflow.py` R15):
```
CADS = EBITDA + Tax
```

**New**:
```
CFADS = EBITDA + Tax + ΔWC + Maintenance capex
      = EBITDA - cash taxes - ΔWC - maintenance capex    (all negative signs)
```

Add `wc_pct_revenue` and `maintenance_capex_pct_revenue` assumptions (defaults 0 for merchant solar, >0 for PPP/concessions).

**Acceptance**: DSCR label shows "CFADS / |DS|" and row definition on the sheet exposes the full formula.

---

### US-073 LLCR and PLCR

Add two new rows to DebtDSCR sheet:
```
LLCR = NPV(WACC_debt, CFADS over loan life) / (debt outstanding + DSRA)
PLCR = NPV(WACC_debt, CFADS over project life) / (debt outstanding + DSRA)
```
Cite BIWS + Bodmer. Expose in QC with threshold check (LLCR ≥ 1.50 typical).

---

### US-074 LBO FCF subtracts interest

**Current** (`operating.py` R28):
```
FCF = EBITDA + Tax + Capex + ΔNWC
```

**New**:
```
FCF = EBITDA + Tax + Capex + ΔNWC + Cash interest
    = EBITDA - tax - capex - ΔNWC - |interest|
```

Cross-sheet ref: `Cash interest = DebtSchedule!total_interest_row`. Use IFERROR to handle pre-drawdown historical periods.

**Acceptance**: sweep amount computed off a realistic post-interest base; lender IRR lands 1-3pp lower than pre-fix (evidence of reversing over-sweep bias).

---

### US-075 3-statement debt schedule

Add a Debt section within the Model sheet (rows ~27-32):
```
R27  Opening debt        =prior closing
R28  Draws               hardcoded = 0 (or from spec)
R29  Repayments          hardcoded per year (or from spec)
R30  Closing debt        =opening + draws - repay
R31  Cash interest       =-avg_debt * int_rate
R32  CFF debt component  (picked up by main CFS)
```

Interest expense (R14 existing) now references R31. CFF (R40 existing) includes repayments + draws.

**Acceptance**:
1. BS tie still holds at 1e-15.
2. When `initial_debt > 0` and `repayment_schedule` provided, closing debt decreases over time.
3. Interest expense tracks average debt rather than constant BOP opening.

---

### US-076 3-statement real historical data

Spec change (`three_statement.py`):
```python
class HistoricalFinancials(BaseModel):
    revenue: list[float]
    ebitda: list[float]
    da: list[float]
    capex: list[float]
    ar: list[float]
    inventory: list[float]
    ppe: list[float]
    ap: list[float]
    debt: list[float]
    equity: list[float]
    cash: list[float]
```

Builder emits historical columns D/E/F as hardcoded values with source comments linking to the filing page ID; projection columns G-K retain the existing % formulas.

**Acceptance**:
1. `real_stevanato_3statement.xlsx` historical D&A matches filed figure (FY25 ~€131M).
2. Each historical cell carries an openpyxl comment with the source page.

---

### US-078 RE waterfall with pref + promote

New block in `re_financing.py`:
```
Tier 1 (LP pref):       first 8% compounded on LP capital
Tier 2 (GP catchup):    100% to GP until GP gets 20% of total above pref
Tier 3 (Promote):       80/20 split LP/GP on residual
```

Parameterize: `preferred_return_pct`, `gp_catchup_pct`, `promote_split_lp_pct`.

**Acceptance**:
1. Base-case: GP IRR > LP IRR (promote working).
2. Downside case (below pref): GP IRR ≈ LP IRR or LP IRR > GP IRR.
3. Four new test cases covering (above-pref, at-pref, below-pref, no-residual).

---

### US-079 NPL priority of payments

New block in `npl_waterfall.py`:
```
Per period:
  Step 1: Senior interest (senior_rate * senior_outstanding)
  Step 2: Senior principal (up to available CF after interest)
  Step 3: Mezz interest — if insufficient cash, PIK
  Step 4: Mezz principal — after senior retired
  Step 5: Equity distribution — residual
```

Add `senior_amortization_schedule` and `mezz_amortization_schedule` (or target-DSCR sizing).

**Acceptance**:
1. Senior principal goes to 0 before mezz principal begins (or before equity receives cash).
2. When `net_collections < senior_face`, senior has unpaid balance and equity loss = full equity.
3. Mezz PIK balance tracked if cash insufficient.

---

### US-082 Extend audit_compute.py with 15 checks

All 15 checks derived from WSO / WSP / Macabacus / BIWS standards, each with a test case:

1. **Circular-reference detection** (same-period cycles)
2. **Iterative-calc flag** (must be True if sweep present)
3. **Magic-number scan** in non-Assumption sheets (flag raw numbers ≥10)
4. **Duplicate-formula scan** across consecutive columns
5. **Amortization-at-maturity** (`|closing[maturity_col]| < 0.01`)
6. **Mid-year convention toggle** present in DCF spec
7. **WACC weights sum = 100%**
8. **Terminal growth < WACC**
9. **CFS line items all formulas** (no hardcodes)
10. **Retained earnings roll** (RE_t = RE_{t-1} + NI - Div)
11. **Football field cells are formulas**
12. **Comps tables have ≥6 companies and include Min/Q1/Q3/Max**
13. **Accretion EPS is formulaic**
14. **PF tax uses EBIT not EBITDA** (inspect formula contains "-D&A")
15. **CFADS includes WC and maintenance capex** (inspect formula structure)

---

### US-083 SCORECARD update

Re-score on the 25-criterion framework. Projected v0.6 impact:
- Formula discipline: 9.7 → **9.9** (magic numbers eliminated, mid-year convention added)
- Source traceability: 9.4 → 9.5 (more named ranges with Source IDs)
- Modelling completeness: 9.3 → **9.7** (PF tax, LLCR/PLCR, NPL waterfall, RE promote, 3-stmt debt schedule)
- Market alignment: 8.8 → 9.0 (Italian NOL rules explicit)
- Infrastructure: 7.4 → **7.8** (extended audit, better tests)

**Weighted**: 9.0 → **9.5**. Past the Italian-specialist bulge-human score of 9.4 on output quality (the remaining human edge becomes purely judgment + relationships).

---

### US-085 Migration script and diff

`scripts/v06_migration.py`:
```
1. For each spec YAML in examples/:
    a. Build with v0.5 code → save to output/pre_v06/
    b. Build with v0.6 code → save to output/v06/
2. Produce diff report showing:
    - Changed cells (value delta)
    - New rows added
    - Renamed / removed rows
3. Re-run audit_compute and adversarial_audit
```

**Acceptance**:
1. Zero errors / warnings from both audits on v06 output.
2. Diff report committed to `docs/V06_MIGRATION_DIFF.md`.

---

## Test plan

Unit tests (new, ~30 cases):
- `test_circular_detection` — sweep should NOT create a same-period cycle
- `test_iter_calc_enabled` — all workbook outputs have iterate=True
- `test_amort_closes_at_maturity` — every (tenor, profile) combination
- `test_merger_accretion_monotonic_refs` — no two adjacent cols identical
- `test_fairness_football_all_formulaic` — no raw numbers in FootballField
- `test_dcf_no_indirect` — workbook XML has no INDIRECT
- `test_pf_tax_ebit_formula` — tax formula references EBIT row
- `test_re_promote_active` — GP IRR > LP IRR in BASE
- `test_npl_priority_senior_first` — senior principal paid before mezz principal
- `test_three_stmt_debt_roll` — Model!R30 closing debt = roll formula
- `test_audit_new_checks` — 15 new checks present and execute
- `test_no_regression` — all 349 existing tests still pass

Integration tests:
- `test_build_all_13_workbooks` — every spec in examples/ builds without error
- `test_compute_all_13_workbooks` — every workbook evaluates to finite values
- `test_adversarial_audit_post_v06_clean` — CRITICAL=0, HIGH=0

End-to-end:
- Open each workbook in Excel (manual QA): no circular-ref warning, no #REF!, no zero values where numbers expected

---

## Risks

1. **Breaking existing specs** — US-076 (real historical) changes 3-statement spec shape. Mitigate: make history fields optional with defaulting logic.
2. **Numerical regression** — US-071 (proper PF tax) will change DSCR numbers. Mitigate: re-run the solver and document the new defensible numbers in VALIDATION_REPORT.md.
3. **Visible fairness change** — US-065 live-links may produce EV ranges different from the hand-set values. Mitigate: flag the difference explicitly in migration diff; user confirms expected.
4. **Iter-calc instability** — highly unusual in practice but possible if a future builder introduces a truly unconvergent cycle. Mitigate: US-061 removes the known case at the source; iter-calc is belt-and-braces.

---

## Timeline

| Day | Scope |
|-----|-------|
| D0 (today) | PRD approved. P0 stories US-060 → US-064 shipped + tested. Regenerate 2 affected files. |
| D1 | P1 stories US-065 → US-070 shipped. Regenerate fairness, DCF, merger files. |
| D2-D3 | P2 stories US-071 → US-077 shipped. Regenerate all PF + LBO + 3-stmt files. |
| D4-D5 | P3 stories US-078 → US-085 shipped. Full audit clean. SCORECARD updated. |
| D5 EOD | v0.6 tagged. Migration diff published. |

---

## Sources cited in this PRD

- [Common LBO errors — Wall Street Oasis](https://www.wallstreetoasis.com/forum/private-equity/common-lbo-errors)
- [3-Statement Model Complete Guide — Wall Street Prep](https://www.wallstreetprep.com/knowledge/build-integrated-3-statement-financial-model/)
- [How the 3 Statements are Linked — CFI](https://corporatefinanceinstitute.com/resources/accounting/3-financial-statements-linked/)
- [DCF Terminal Value — Macabacus](https://macabacus.com/valuation/dcf-terminal-value)
- [DSCR Full Tutorial — Breaking Into Wall Street](https://breakingintowallstreet.com/kb/project-finance/debt-service-coverage-ratio/)
- [LLCR and PLCR Complexities — Edward Bodmer](https://edbodmer.com/llcr-and-plcr-complexities-and-meaning-for-break-even/)
- [FAST Standard](https://fast-standard.org/)
- [Italian tax: IRES + IRAP 2026 — PwC Tax Summaries](https://taxsummaries.pwc.com/italy/corporate/taxes-on-corporate-income)

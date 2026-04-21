# ModelForge — External Stress-Test Report

**Date**: 2026-04-21
**Auditor**: Claude Opus 4.7 (1M context)
**Scope**: 13 workbooks covering all 8 templates + 3 add-on templates (DCF, merger, fairness) + 2 real-deal specs
**Benchmarks**: Wall Street Oasis (LBO & modeling errors), Wall Street Prep (3-statement linkages, interest basis), Macabacus (DCF & model-audit standards), BreakingIntoWallStreet / Edward Bodmer (PF DSCR/LLCR/CFADS), Corporate Finance Institute (BS tie, RE roll-forward), FAST Standard (structural discipline)

---

## Executive summary

Internal ModelForge audits (`audit_suite.py`, `audit_compute.py`, 349-test pytest suite) return **0 errors across 10 files**. An adversarial audit against external bulge-bracket standards finds:

| Severity | Count | Where |
|----------|-------|-------|
| **CRITICAL** | **6** | Unitranche + Credit Memo debt schedules (circular ref without iter-calc) |
| **HIGH** | **13** | 3-statement debt roll, merger accretion off-by-one, fairness football field hardcoded |
| **MEDIUM** | **79** | Magic numbers in merger / DCF / fairness, PF tax simplification, no mid-year convention |
| **Total** | **98** | Across 13 files |

**Headline**: engine math is solid in 3-statement and PF sculpted amort, but **2 of 13 files will open with a circular-ref warning in Excel**, the new templates shipped v0.4 (merger, DCF, fairness) are **riddled with hardcoded magic numbers and have real formula bugs (off-by-one in merger accretion/dilution, hardcoded football field, duplicate formulas)**, and the minibond amortization schedule is off-by-one at maturity.

Passing ModelForge's internal audit ≠ passing bulge-bracket external audit.

---

## CRITICAL findings

### C-1. Unitranche & Credit Memo: cash-sweep circular reference without iter-calc

**Files**: `unitranche_cdmo.xlsx`, `credit_memo_cdmo.xlsx`
**Sheet / cells**: `DebtSchedule!G11-M11`
**Rule**: formulas cannot form a closed dependency loop unless Excel's iterative calculation is enabled in workbook settings.

**Observed dependency chain** (`unitranche_cdmo.xlsx → DebtSchedule`):

```
G11 (closing debt) = G8 + G9 + G10          ← uses G10
G10 (scheduled amort) = G19                  ← uses G19
G19 (cash sweep) = -IF(G18 > trigger, ...)   ← uses G18
G18 (leverage) = G11 / OperatingModel!G13    ← uses G11  ← CIRCULAR
```

**Workbook iterative-calc setting**: `wb.calculation.iterate = None` (i.e., OFF).

**Verification**: the `formulas` Python engine, trying to evaluate this chain without iterative calc, returns `None` for *every cell from col G through M* of the debt schedule in both files. Downstream:

```
Returns!D8 (Lender CF at t=0): -36.86  ✓
Returns!D11 (Lender IRR):      None    ← broken
Returns!D12 (Lender MoIC):     None    ← broken
Returns!D13 (Lender EIR):      None    ← broken
```

When opened in Excel on a fresh install (iterative calc OFF by default), the user will see a **"Circular References" warning bar**. The debt schedule will show all zeros or `#REF!` depending on calc mode.

**Why internal audit missed it**: `audit_compute.py` checks *non-negativity* of closing debt (`v < -0.01`), but `None` is neither negative nor positive, so the check silently passes. The QC sheet's `ALL_PASS` check also returns `None` and is marked "could not be evaluated" as a warning, not a failure.

**Fix** (recommended — minimal code change): in `modelforge/builder/base_workbook.py`, set

```python
wb.calculation.iterate = True
wb.calculation.iterateCount = 100
wb.calculation.iterateDelta = 0.001
```

before saving any workbook that contains cash-sweep or revolver logic.

**Alternative fix** (recommended — structurally cleaner): break the loop by gating the current-period sweep on the *prior-period* leverage, i.e. `G19 = -IF(F18 > trigger, ...)`. This is the WSO / WSP-preferred approach because it avoids the entire iterative-calc tax.

**WSO reference**: [Common LBO errors — Wall Street Oasis](https://www.wallstreetoasis.com/forum/private-equity/common-lbo-errors) — "Revolver not done correctly if using a non-cash sweep model".

---

### C-2. Same circular exists in all LBO-style models

The same pattern (same-period leverage → sweep → amort → closing) exists anywhere the builder emits a cash-sweep section. Verified on 6 cells (G11, H11, I11) × 2 files = 6 CRITICAL findings, but the pattern recurs through col M in both files. Total affected cells in Excel: ~35 per file.

---

## HIGH findings

### H-1. Merger accretion/dilution: **duplicate formula = year-off-by-one**

**File**: `merger_tim_iliad.xlsx`
**Sheet / cells**: `AccretionDilution!G7:I9`

The hardcoded standalone-EPS row (R7) has col F = col G = `0.02001698`. The pro-forma-EPS row (R8) has col G formula `=ProForma!F27/(21200+...)`, which is **identical** to col F. This is an off-by-one copy-paste error.

Consequence: **the year-3 → year-5 accretion/dilution percentages are shifted one year backwards**. A committee reader looking at the Y4 accretion number is actually seeing Y3 accretion. The trajectory shape is distorted.

**Computed values** (base scenario):
```
D9  (Y1 accretion):  23.6%
E9  (Y2):            60.9%  ← implausibly high — see H-2
F9  (Y3):            67.9%
G9  (Y4, WRONG):     74.4%  ← actually Y3 recomputed
H9  (Y5, WRONG):     80.6%  ← actually Y4
I9  (Y6):           None    ← formula breaks because ProForma!I27 not populated
```

**Fix**: regenerate with corrected column references in `modelforge/builder/sheets/accretion.py` (or equivalent). The formula pattern `=ProForma!{col}27/(21200 + D15)` must advance one column per year without repeating.

---

### H-2. Merger accretion is implausibly large (60–80%)

Even ignoring the off-by-one, a 60%+ accretion rate suggests either (a) standalone EPS is understated, (b) synergies are overstated, or (c) incremental interest is understated. A committee reader would flag this immediately. **Needs sanity-check against TIM's reported diluted EPS and Iliad's own FY25 numbers.** Current model has:

- Standalone acquirer NI = 0.0189 × 21200 shares ≈ €400M (plausible for TIM)
- Pro-forma NI per my back-of-envelope = €750M → accretion ≈ 30%
- Model's pro-forma NI (back-solved from 60% accretion at €0.03 EPS × 33.7k shares) ≈ €1,011M

Gap of €260M is unexplained. Likely sources:
1. Cost synergies compounded too aggressively (model uses `MIN(1, synergy_phase)` but default phase-in may be too fast)
2. Revenue synergies applied at EBITDA margin, not net margin
3. Incremental interest R24 references `DealStructure!$D$16` which is `=-D13*financing_rate` where D13 = cash consideration — if financing is 100% cash (cash_mix_pct=1), interest is on the full equity purchase, not the new debt net of existing cash

---

### H-3. 3-statement: debt row is flat hardcoded (no roll-forward)

**Files**: `three_statement_cdmo.xlsx`, `real_stevanato_3statement.xlsx`
**Sheet / cells**: `Model!D27:K27 = 8, 8, 8, 8, 8, 8, 8, 8` (for CDMO); similar for Stevanato

Debt is stored as a static scalar throughout the projection. Consequences:
- CFS has no line item for debt issuance or repayment — CFF is only dividends
- Interest expense R14 uses `$D$27` (same BOP forever), not a rolled BS debt balance
- BS debt is not reconciled to any debt schedule (there isn't one)
- Any scenario where the company actually pays down debt or refinances cannot be modeled

**WSP reference**: *"Every line item on the cash flow statement should be referenced from elsewhere in the model (it should not be hardcoded) as it is a reconciliation"* — [How the 3 Financial Statements Are Linked, Wall Street Prep](https://www.wallstreetprep.com/knowledge/how-are-the-financial-statements-linked/).

**Fix**: add a `DebtSchedule` sheet (or roll-forward lines within the Model sheet) so R27 becomes `=D27 + Et_draw - Et_repay`, and CFF picks up the delta.

---

### H-4. 3-statement: historical rows are synthesized from % assumptions

**Files**: same as above.
**Examples**:
```
R12 (D&A)       D: =-$D$9 * da_pct_revenue      ← historical D&A from assumed %
R21 (AR)        D: 7.5                           ← this one is a hardcoded opening
R22 (Inventory) D: 5.2                           ← hardcoded
R23 (PPE)       D: 12                            ← hardcoded
```

But D&A, AR, Inventory, PPE for historical years should be **real reported figures from the 10-K / CONSOB filing**, not synthesized from a % assumption that itself is calibrated to one historical year. This breaks the single-most-important property of a 3-statement model: that *history ties to published financials*.

**Stevanato real-deal check**: R9 (revenue) has real FY23/24/25 numbers (1104, 1181, etc.) hardcoded — ✅ correct. But R12 D&A for history col D = `-D9 * da_pct_revenue` = assumed. Stevanato's *reported* FY24 D&A was ~€131M (versus model's implied €110M at 10% of revenue). Gap of €21M on a company with €282M net income = ~7% error in EPS.

**Fix**: the YAML spec should support `historical: {revenue: [...], ebitda: [...], da: [...]}` arrays for every P&L and BS line, and the builder should emit hardcoded values only in the historical columns with a source comment citing the filing page.

---

### H-5. Fairness opinion: football field is entirely hardcoded

**File**: `fairness_amplifon.xlsx`
**Sheet**: `FootballField`

All 10 EV low/high values are raw numbers, not formulas. The football field is a **static picture**, not a live model. Sensitivity drives nothing. Changing a trading comparable's EV/EBITDA multiple does not move the football field.

**Bulge-bracket reference**: Macabacus and WSP fairness-opinion templates link the football field live to:
- Trading comps: `MEDIAN(TradingComps!B6:B9) × FY+1 EBITDA ± 1× multiple`
- Transaction comps: same pattern on the transaction comp sheet
- DCF: `MIN(WACC_down, g_down) … MAX(WACC_up, g_up)` range
- LBO: `DealAssumptions!... × target_IRR` inverted

**Impact on MF positioning**: the top-line claim that "every workbook is live-formula" is violated in the fairness template. This undermines the source-traceability moat.

**Fix**: regenerate `FootballField` with 5 formula patterns tying to the other sheets; also replace hardcoded 950/226/25 (net debt / shares / current price) with named ranges from Assumptions.

---

### H-6. Minibond: debt not fully amortized at maturity

**File**: `minibond_logistics.xlsx`
**Sheet / cells**: `BondStructure!L11` (maturity year, Y6)

Spec: 6-year bond, linear amortization from year 3.
Model implementation: amort starts at col J (Y4) and extends through col M (Y7).

**Closing debt trajectory** (computed via formulas engine):
```
G11 (Y1): 20.0  ← drawdown
H11 (Y2): 20.0
I11 (Y3): 20.0  ← spec says amort starts here; model says no
J11 (Y4): 15.0  ← -5 amort
K11 (Y5): 10.0  ← -5 amort
L11 (Y6):  5.0  ← MATURITY; model still shows €5M outstanding  ✗
M11 (Y7):  0.0  ← model pays off one year late
```

**Bulge-bracket implication**: a Banca Finint pricing committee reviewing this workbook would see €5M of principal outstanding at maturity and refuse to sign off. This is a one-line fix (`amortization_start_year = 3` not `4`) but it passes the existing audit because the audit only checks sign (non-negative) and doesn't require `L11 ≈ 0` at maturity.

The v0.2 validation report flagged this as a "false positive" of the audit script. **That conclusion was incorrect** — the audit script was right that closing debt is non-zero, and the model IS wrong.

---

### H-7. DCF: hardcoded magic numbers in the valuation bridge

**File**: `dcf_enel.xlsx`
**Sheet / cells**:
```
Valuation!D11 (Net debt):          =-60000.0   ← magic
Valuation!D15 (Implied price):     =D12/10166.0 ← magic (shares out)
Valuation!D16 (Current price):     6.45         ← magic
```

Internal audit didn't scan the `Valuation` sheet for hardcodes because `Valuation` isn't in the predefined "three-statement / debt / operating" set.

**Bulge-bracket rule** (Macabacus Model Check): every cell containing a computed value must trace to a named range or an input cell with a source comment. ModelForge emits sources for every assumption but breaks its own rule on the bridge that most committee readers look at first.

---

## MEDIUM findings — selected

### M-1. PF tax is on EBITDA proxy, not EBIT

**Files**: `project_finance_solar.xlsx`, `real_enfinity_solar_pf.xlsx`
**Cell**: `ProjectCashFlow!F14` and forward

```
Formula: =-MAX($F$13, 0) * effective_tax_rate    where F13 = EBITDA
```

Standard Italian SPV taxation:
- Taxable income = EBIT - Interest expense (IRES + IRAP applies on slightly different bases)
- EBIT = EBITDA - D&A
- Missing the D&A shield → **overstates tax by D&A × tax_rate each year**

**Numerical impact (Enfinity 276MW, real file)**:
- Total capex ≈ €316M → annualized D&A (20y straight-line) ≈ €15.8M/yr
- Interest Y1 ≈ €6.4M
- Tax rate 27.9%
- Overstatement per year: (15.8 + 6.4) × 0.279 = **€6.2M/yr**
- Over 20 operating years: **€124M NPV gap** (undiscounted)
- DSCR is materially understated; debt-sizing solver lands lower than it should

The row label says *"Taxes (on EBITDA proxy)"*, which acknowledges the simplification. But a committee reading this would not accept it for a final IC memo; this is initial-screening grade.

**Fix in v0.5/v0.6**: add an explicit D&A schedule (straight-line or tax-MACRS), compute EBIT, then tax = `MAX(EBIT - |Interest|, 0) × tax_rate`, plus NOL carry-forward (Italian tax law caps NOLs at 5 years for non-startups but allows 80% offset of current-year taxable income).

**Reference**: [Breaking Into Wall Street — DSCR full tutorial](https://breakingintowallstreet.com/kb/project-finance/debt-service-coverage-ratio/) — CFADS = EBITDA − cash taxes − Δ WC − maintenance capex; cash taxes computed on EBT.

---

### M-2. PF CFADS omits WC and maintenance capex

Same files. Standard CFADS formula (BIWS, Edward Bodmer):

```
CFADS = EBITDA − cash taxes − Δ working capital − maintenance capex
```

ModelForge defines CADS as just `EBITDA − tax`. For a merchant solar project with minimal WC and <0.5% revenue maintenance capex, the simplification is defensible but should be documented on the sheet itself. For a real-estate PF, minibond PF, or toll-road PF with material WC, this simplification over-states CFADS by 2-5% and overstates DSCR correspondingly.

---

### M-3. LBO FCF-to-debt does not subtract cash interest

**Files**: `unitranche_cdmo.xlsx`, `credit_memo_cdmo.xlsx`
**Cell**: `OperatingModel!D28` (Free cash flow to debt)

```
Formula: =$D$13 + $D$20 + $D$26 + $D$27
       = EBITDA + Tax(on EBT) + Capex + ΔNWC   (no interest subtraction)
```

Problem: the sweep formula R19 references this "FCF" and sweeps `cash_sweep_pct` of it. But the FCF doesn't deduct the interest the borrower must actually pay. So the sweep is calculated off an inflated cash base.

**Numerical impact** on a typical unitranche with €37M senior at 9.25%:
- Annual interest ≈ €3.4M
- EBITDA minus tax minus capex minus ΔNWC ≈ €10M
- "FCF" per model = €10M → sweep at 50% = €5M
- True FCF available to debt = €10M − €3.4M = €6.6M → sweep at 50% = €3.3M
- **Sweep overstated by €1.7M/yr; debt amortizes too fast; lender IRR inflated**

**Fix**: redefine R28 to include cash interest from DebtSchedule!Total cash interest row; or apply the sweep % to (FCF − interest) explicitly.

---

### M-4. Sensitivity tornado produces zero deltas for operating drivers

**File**: `unitranche_cdmo.xlsx`
**Sheet**: `SensitivityAnalysis`

The "shadow (fractional Δ)" method produces:
```
F-001 Revenue growth ±20%:    J10=0.0,   K10=0.0         ← no sensitivity
F-002 EBITDA margin ±25%:     J11=0.0,   K11=0.0         ← no sensitivity
F-003 Senior margin ±25%:     J12=-0.164, K12=+0.164     ← works
F-004 EURIBOR ±50bps:         J13=-0.147, K13=+0.147     ← works
F-005 Maint capex ±20%:       J14=0.0,   K14=0.0         ← no sensitivity
F-006 Growth capex ±25%:      (same)
```

Only debt-side drivers (interest margin, base rate) register an impact on the primary output (Lender IRR). Operating drivers (revenue, margin, capex) show zero elasticity, even though operationally they drive cash sweep which drives lender IRR.

**Root cause**: most likely the circular reference (C-1 / C-2) breaks the propagation chain: when the shadow calc perturbs a revenue driver, the debt-schedule cells are still `None`, so lender IRR doesn't move. Once C-1 is fixed, rerun the shadow and re-audit.

**Commercial impact**: a committee reading this tornado would conclude the lender IRR is insensitive to operating performance — *false*. It is very sensitive; the tornado is just broken.

---

### M-5. DCF does not support mid-year convention

**File**: `dcf_enel.xlsx`
**Sheet / cell**: `Valuation!D5`

Explicit-period PV uses end-year discounting only:
```
=SUMPRODUCT('FCFForecast'!G16:K16, (1+wacc_rate)^-ROW(INDIRECT("1:5")))
```

Macabacus best practice: mid-year convention is recommended for any company without strong seasonality or fiscal-year cash spikes. Reference: [Macabacus — DCF terminal value and discounting](https://macabacus.com/valuation/dcf-terminal-value).

**Fix**: add `mid_year_toggle` assumption; formula becomes
```
=SUMPRODUCT(G16:K16, (1+wacc_rate)^-(ROW(INDIRECT("1:5")) - 0.5 * mid_year_toggle))
```

Also: ModelForge uses `INDIRECT` which is a **volatile function** — bulge-bracket practice avoids volatile functions because they trigger a full-sheet recalc on every cell change. Replace with `SEQUENCE(5)` (Excel 365+) or explicit terms.

---

### M-6. DCF averages Gordon and Exit-Multiple terminal values

**File**: `dcf_enel.xlsx`
**Cell**: `Valuation!D8 = AVERAGE(D6, D7)`

Standard bulge-bracket practice: present both terminal values side-by-side in a football field, let the reader see the gap. Averaging them obscures the methodology assumption that drives most of the EV.

For this particular Enel model, if Gordon gives EV ≈ €100B and Exit Multiple gives ≈ €150B, averaging to €125B hides a €50B judgment call.

---

### M-7. Merger: 30+ hardcoded magic numbers

**File**: `merger_tim_iliad.xlsx`
**Sheets**: `DealStructure` and `ProForma`

Sampled issues:
- `DealStructure!D5 = 25.0` (target share price) — should be named
- `D8 = 200.0` (target shares) — should be named
- `D10 = 800.0` (target net debt) — should be named
- `D15 = D14 / 0.24` (acquirer share price embedded)
- `ProForma!D8..H8`: acquirer revenue hardcoded 15800, 16274, 16762, 17265, 17783 (historical + projected)
- `D9..H9`: target revenue hardcoded
- `D14..H14`: acquirer EBITDA margin = `D8 * 0.3987341772…` — **17-sig-fig literal** in formula
- `D15..H15`: target EBITDA margin = `D9 * 0.25`
- `D21..H21`: combined D&A hardcoded
- `D23..H23`: standalone interest hardcoded
- `D24..H24`: `='DealStructure'!$D$16` (OK reference, but D16 itself is `=-D13*rate` where D13 is "cash consideration" — conflates acquisition financing with existing debt)

Total hardcoded cells in `merger_tim_iliad.xlsx`: **60+** across the two sheets.

**Bulge-tier rule** (WSP, Macabacus): no magic numbers in the calculation engine; everything traces to `Assumptions` with a source ID. The merger template violates this pervasively.

---

### M-8. NPL waterfall has no priority ordering

**File**: `npl_mixed_portfolio.xlsx`
**Sheet**: `CollectionWaterfall`

R28 (Equity CF to fund) at final column N:
```
=$N$21 + $N$26 − $D$24 − $D$25
```

This simultaneously repays senior note principal AND mezz note principal at maturity out of the same collection pool. Real NPL tranched structures have a strict waterfall:
1. Senior interest
2. Senior principal amortization (or PV-sculpted)
3. Mezz interest (cash-pay or PIK)
4. Mezz principal
5. Residual to equity

The current model has no mechanism for:
- Senior prin paid before mezz prin
- Mezz PIKing interest if cash insufficient
- Senior loss coverage if collections < senior face

For a mixed NPL portfolio with 8% IRR target mezz notes, this is a **MEDIUM** structural gap — the IRR calcs reported to the investor are optimistic in stressed scenarios.

---

### M-9. Real Estate: LP/GP waterfall is proportionate only (no promote)

**File**: `real_estate_pbsa.xlsx`
**Sheet**: `Financing` row 19 onwards

Standard PE real-estate waterfall:
1. LP preferred return (typically 8%)
2. GP catchup (100% to GP until GP reaches promote share)
3. Promote split (typically 80/20 LP/GP above pref)

ModelForge's "waterfall (simplified)" just splits cash 90/10 (or whatever `lp_capital_commitment_pct`) proportionately. **GP's IRR ≡ LP's IRR** under this structure, which defeats the purpose of being a GP. A real RE sponsor model has the GP IRR materially higher due to the promote.

**Fix in v0.5**: implement a 3-tier waterfall with pref, catchup, and promote in a dedicated block. Same pattern reusable for PE fund models.

---

### M-10. Real Estate: exit cap applied to TTM NOI (not NTM)

**File**: `real_estate_pbsa.xlsx`
**Cell**: `DCF!D21 = D20 / exit_cap_rate`, `D20 = K15` (Year 7 NOI)

At sale in end-of-Y7, a buyer prices off *forward* (Y8) NOI, not *trailing* (Y7). Using Y7 is a minority convention and is conservative. Not a bug, but not industry-mode.

---

## LOW findings (not enumerated individually)

- `TradingComps` and `TransactionComps` in fairness opinion have only 4 and 3 comps respectively — thin vs. bulge-bracket 6-10 minimum
- `Comps` tables show only Median and Mean, missing Min/Q1/Q3/Max
- `AccretionDilution!R9` col I returns None (ProForma!I27 not populated — last-year accretion is indeterminate)
- `DCF Valuation!D5` uses volatile INDIRECT function
- 3-statement historical "Debt" row uses hardcoded 8 (not real Stevanato reported debt of ~€267M)
- `QC!C4 (ALL CHECKS PASS)` cell returns None in formulas library (nested SUM/AND pattern); in Excel itself this would compute, but it means the internal audit's headline check is unverifiable programmatically
- `NPL!R33 Gross recovery rate = $N$12` — labeled as "cum/GBV" but $N$12 is cumulative collection % GBV, not recovery % net of losses. Labels don't match what's computed.

---

## What the existing internal audit misses (and should start checking)

| # | Check | Why WSO/Macabacus requires it |
|---|-------|-------------------------------|
| 1 | Circular reference detection | Excel warns; broken values downstream |
| 2 | Iterative-calc flag is ON when sweep/revolver present | Without it, cash sweep is unresolvable |
| 3 | Hardcoded magic numbers scan in non-Assumption sheets | Bulge-tier: named ranges mandatory |
| 4 | Duplicate-formula detection across columns | Catches off-by-one year shifts |
| 5 | Debt amortizes to ~0 at tenor (`\|EOP debt\| < 0.01`) | Maturity ≠ tenor = investor loss |
| 6 | Mid-year convention toggle exists | Macabacus default; affects EV ±3% |
| 7 | WACC weights sum to 1.0 | Typo protection |
| 8 | Terminal growth < WACC | Gordon divergence |
| 9 | CFS line items are all references (no hardcodes) | WSP: CFS is a reconciliation |
| 10 | Retained earnings roll: RE_t = RE_{t-1} + NI - Div | CFI: fundamental BS tie |
| 11 | Football field cells are formulas, not raw numbers | Fairness opinion requires derivation |
| 12 | Comps tables have Min/Q1/Median/Mean/Q3/Max | Bulge standard |
| 13 | Accretion/dilution EPS is computed (NI/shares) | Not hardcoded |
| 14 | PF tax uses EBIT − Interest, not EBITDA | Otherwise understates CADS ~5-7% |
| 15 | CFADS includes WC and maintenance capex | Bodmer standard |

---

## What I verified clean (no issues)

These items passed the adversarial audit:

1. **Named-range coverage**: 25-59 named ranges per file, all resolvable
2. **Scenario CHOOSE propagation**: flipping `scenario_index` in Assumptions flips every `=CHOOSE(scenario_index, ...)` cell across sheets correctly
3. **3-statement BS tie**: `|Assets − Liabilities − Equity| ≈ 1e-15` (floating-point noise) every year, every scenario for both CDMO and Stevanato — genuine pass, not false pass
4. **Stevanato historical revenue / EBITDA margin**: matches reported FY24/25 figures within ±1%
5. **PF DSCR breach count = 0** for both solar templates in BASE after v0.3 sculpted-amort fix
6. **Enfinity solver sizing**: €163.76M @ 1.30x DSCR is a reproducible and defensible outcome
7. **Sign convention audit**: D&A, capex, tax, interest rows all negative in projection columns (zero violations)
8. **No `#DIV/0!`, `#VALUE!`, `#NUM!`** in any evaluated cell
9. **Sources sheet integrity**: every file has a populated Sources sheet with ID, publisher, page, date, URL
10. **Linkage graph (SQLite .graph.db)**: present for every workbook

---

## Recommended fix priority

Order by (severity × blast radius × fix effort):

| Priority | Finding | Effort | Blast radius |
|----------|---------|--------|--------------|
| **P0 (same day)** | C-1/C-2: set `calculation.iterate = True` in base_workbook.py | 1-line code change | Unblocks 2 of 13 files |
| **P0** | H-1: fix merger accretion col references (off-by-one) | 3-5 lines in sheets/accretion.py | One file, but material |
| **P0** | H-6: fix minibond `amortization_start_year` off-by-one | 1 number in spec or builder | One file, high visibility |
| **P1 (this week)** | H-5: link FootballField to TradingComps / TransactionComps / DCF / LBO | Rewrite fairness builder | Moat claim |
| **P1** | H-7: replace DCF hardcoded net debt / shares / current price with named ranges | Spec + builder | DCF template |
| **P1** | M-7: same treatment for merger hardcoded margins / D&A / interest | Bigger rewrite | Merger template |
| **P2 (v0.5)** | M-1: proper PF tax with D&A shield + NOL | New sheet section | All PF/credit files |
| **P2** | M-3: LBO FCF-to-debt to subtract interest | 1-cell formula change | 2 LBO files |
| **P2** | H-3/H-4: 3-statement needs debt schedule + real historical data | Spec expansion + builder | Core 3-stmt templates |
| **P3 (v0.6)** | M-9: RE waterfall with pref/catchup/promote | New block | RE template |
| **P3** | M-8: NPL tranched waterfall with priority | New block | NPL template |
| **P3** | Add all 15 audit checks above to `audit_compute.py` | 200 LoC | Whole suite |

---

## Sources

- [Common LBO errors — Wall Street Oasis](https://www.wallstreetoasis.com/forum/private-equity/common-lbo-errors)
- [LBO with Cash Flow Statement but no Balance Sheet — Wall Street Oasis](https://www.wallstreetoasis.com/forum/private-equity/lbo-with-cash-flow-statement-but-no-balance-sheet-help)
- [How Are the Three Financial Statements Linked? — Wall Street Prep](https://www.wallstreetprep.com/knowledge/how-are-the-financial-statements-linked/)
- [3-Statement Model Complete Guide — Wall Street Prep](https://www.wallstreetprep.com/knowledge/build-integrated-3-statement-financial-model/)
- [How the 3 Financial Statements are Linked — Corporate Finance Institute](https://corporatefinanceinstitute.com/resources/accounting/3-financial-statements-linked/)
- [Mastering Terminal Value Calculation in DCF — Macabacus](https://macabacus.com/valuation/dcf-terminal-value)
- [DCF Overview — Macabacus](https://macabacus.com/valuation/dcf-overview)
- [Model Check for Excel — Macabacus](https://macabacus.com/features/model-check)
- [Debt Service Coverage Ratio (DSCR) — Breaking Into Wall Street](https://breakingintowallstreet.com/kb/project-finance/debt-service-coverage-ratio/)
- [Loan Life Coverage Ratio (LLCR) — Breaking Into Wall Street](https://breakingintowallstreet.com/kb/project-finance/loan-life-coverage-ratio/)
- [LLCR and PLCR Complexities — Edward Bodmer](https://edbodmer.com/llcr-and-plcr-complexities-and-meaning-for-break-even/)
- [FAST Standard](https://fast-standard.org/)

---

## Appendix — audit artifacts

- `stress_test.py` — initial structural stress test (0 findings; heuristics too shallow)
- `adversarial_audit.py` — deeper formula / magic-number / circular-ref scan (98 findings)
- `adversarial_findings.json` — machine-readable output
- `stress_test_findings.json` — initial scan output

Run `python adversarial_audit.py` to reproduce.

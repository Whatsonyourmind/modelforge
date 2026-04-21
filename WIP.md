# ModelForge v0.8 — WIP State (2026-04-21)

## Session summary

Starting point: v0.7 shipped (2026-04-21 earlier session) but uncommitted, 72% gold-standard PASS (304/423).
Ending point: **v0.8 four-theme shipping, 76% gold-standard PASS (323/423)**, all work committed and tagged.

## Gold-standard category scores

| Category | Checks | v0.7 (pre) | v0.8 (now) | Δ |
|---|---:|---:|---:|---:|
| **3-Stmt** | 20 | 5.50 | **10.00** | +4.50 |
| **M&A** | 11 | 6.82 | **9.09** | +2.27 |
| **DCF** | 18 | 6.18 | **7.22** | +1.04 |
| PF | 24 | 9.58 | 9.17 | — (label-based; live wiring shipped) |
| Format | 184 | 9.29 | ~9.2 | ~0 |
| IT-Reg | 122 | 8.77 | ~8.8 | ~0 |
| **LBO** | 44 | 0.68 | 0.14 (unchanged) | 0 (Theme 1 not started) |
| **Overall** | 423 | 304 PASS (72%) | **323 PASS (76%)** | **+19** |

## What was shipped this session

All 5 commits tagged on master:

```
30695c2  v0.7.0-bulge-tier          Committed the v0.6+v0.7 work that was uncommitted
91652a9  v0.8.1-dcf-stub-fade       Theme 3 — US-230/231/232/233
bf58757  v0.8.2-ma-complete         Theme 5 — US-250/251/252/253
39152b8  v0.8.3-pf-wire-partial     Theme 4 partial — US-240/241/244
f05e955  v0.8.4-3stmt-suite         Theme 2 — US-220/221/222/223/224
```

### Theme 3 — DCF stub + fade + terminal normalization (US-230..233)
- `stub_period_days` now prorates first-period FCF; discount exponent = stub_years×(1−mid_year)
- `fade_years` extends FCFForecast with linearly interpolated growth columns
- Terminal FCF normalization rows added before Gordon (NOPAT, ΔNWC normalized, FCF with capex=D&A)
- 2D sensitivity Data Tables (WACC×g and WACC×exit_x) appended to SensitivityAnalysis sheet
- `gold_standard_audit.py` detectors updated for #2, #7 (both were hardcoded fail in v0.7)
- Unicode crash fixed on Windows cp1252 stdout

### Theme 5 — M&A completion (US-250..253)
- Cross-over breakeven synergy reverse-solve in AccretionDilution
- Contribution analysis block (acquirer vs target Rev/EBITDA/NI contribution vs post-deal equity %)
- Exchange ratio + collar block on DealStructure (fixed/floating mode, ±15% collar, −20% walk-away)
- PPA intangible amortization wired into Pro-Forma P&L
- New named range `tgt_net_income_fy0`
- Audit #47/#51/#52 detectors updated

### Theme 4 partial — PF wiring (US-240/241/244 done; 242/243/245/246/247/248 deferred)
- **Done**: panel degradation into revenue; P90 revenue row; lock-up test gates distributable cash
- **Deferred for next session**: O&M reserve funding (US-242), MMR sinking fund (US-243), equity cure (US-245), make-whole on early redemption (US-246), real-vs-nominal QC (US-247), mandatory prepayment per-event toggle (US-248)
- Current state: parameters exposed as rows (v0.7); three are now live-wired into cash flow

### Theme 2 — 3-Statement suite (US-220..224; US-225 already passes)
- NOL schedule: Italian 5-yr limit + 80% cap (Legge Bilancio 2024)
- DTA (from NOL × tax_rate) + DTL (book-tax D&A timing diff accumulator)
- SBC expense @ 1% revenue default (non-cash)
- Minority interest: "(−) Minority interest in NI" + "Net income to parent" + MI BS balance
- Revolver plug (MAX(0, −cash)) + 0.5% commitment fee on 100m facility
- Audit #72-76 detectors updated (all were hardcoded fail)

## What remains — priority order for next session

### 1. Theme 1 Sponsor LBO (US-200..213) — 14 stories, 2 weeks scope
**Why next**: LBO category is 0.14 (!), 8 of 9 remaining audit FAILs are here.
**Approach**: build a **new `SponsorLBOSpec`** distinct from unitranche. Do NOT overload unitranche with LBO features (semantic mismatch — private credit ≠ sponsor LBO).

Story-level plan:
- US-200: new `SponsorLBOSpec` pydantic model (TargetCompany, AcquisitionAssumptions, DebtStack, CapitalStructure)
- US-201: `sources_uses.py` sheet — balanced S&U equation
- US-202: `purchase_price_build.py` — offer × FD shares + option buyout + net debt + fees
- US-203: `ppa_block.py` — goodwill + intangibles + DTL on step-ups (mirror v0.7 merger PPA)
- US-204: OID amortization + financing-fee capitalization
- US-205: PIK toggle per tranche
- US-206: Revolver auto-draw + commitment fee
- US-207: Mgmt rollover + MIP
- US-208: Dividend recap
- US-209: Earnout / CVR
- US-210: 3 exit scenarios (strategic / IPO / secondary)
- US-211: Hurdle analysis — reverse-solve max PP at 20/25/30% IRR
- US-212: GP promote (pref + catchup + 20%)
- US-213: NWC closing adjustment

**Route the LBO audit**: currently triggers on any `OperatingModel + DebtSchedule` file. Update `gold_standard_audit.py` route() so LBO-only checks run on new `sponsor_lbo_*.xlsx` files, keeping unitranche/credit_memo classified as Private Credit (a different category, or skip those checks).

Acceptance (from PRD): LBO category 0.14 → **≥9.0** — converts ~40 checks from FAIL.

### 2. Theme 6 IFRS 9 live ECL (US-260..263) — 4 stories, 1 week
**Why**: IT-Reg category could move from 8.77 → 9.5+. Also commercially important for EU/UK bank-lender audience.
- US-260: `IFRS9ECL` sheet with per-facility Stage 1/2/3 PD/LGD/EAD/DF columns
- US-261: SICR triggers as hard-coded flags (6 triggers from v0.7 compliance sheet)
- US-262: Forward-looking macro scenarios (GDP + unemployment + CPI → PD multiplier)
- US-263: POCI treatment for NPL portfolios

### 3. Theme 4 completion — PF remaining wiring (US-242/243/245/246/247/248) — 1 week
- US-242: O&M reserve funding at COD, release at decommissioning
- US-243: MMR as sinking fund reducing distributable cash per year
- US-245: equity cure iterative (sponsor injection when DSCR breached, capped count)
- US-246: make-whole premium on early redemption
- US-247: real-vs-nominal QC (inflation consistency on opex + debt rate)
- US-248: per-event mandatory prepayment toggles (currently one aggregated text row)

### 4. Fix pre-existing merger reverse-classifier test failure
`tests/test_reverse.py::test_round_trip_classification[merger_tim_iliad.yaml-merger-MergerSpec]` has been failing since v0.7 shipped PPA/break_fees/regulatory spec fields (the reverse classifier now mis-classifies the enriched merger spec as `three_statement` due to the extra sheets).

Root cause: `analyze_workbook` in `modelforge/reverse/analyzer.py` uses sheet-count heuristics that are skewed by the new ComparableBetas/ComplianceCheck/PPA sheets.

Fix approach: update classifier to weight `DealStructure` + `ProForma` + `AccretionDilution` more heavily.

## Current tree state

- **Branch**: `master`, clean (all changes committed + tagged)
- **HEAD**: `f05e955` at tag `v0.8.4-3stmt-suite`
- **Tests**: 348 pass / 1 known fail (merger reverse classifier — item 4 above)
- **Audit**: 323 PASS / 86 PARTIAL / 9 FAIL / 5 N/A out of 423

## Exact next-session pickup steps

```bash
cd "C:/Users/lukep/Desktop/Projects AI/ModelForge"

# 1. Verify state
git log --oneline -6
git status
git tag | tail -5
python -m pytest tests/ -q  # expect 348 pass, 1 known fail
python gold_standard_audit.py 2>&1 | head -10  # expect 323 PASS

# 2. Read WIP + PRD
cat WIP.md             # this file
cat PRD_v10_world_class_hero.md  # v0.8 Theme 1 starts at line 99

# 3. Begin Theme 1 Sponsor LBO — create new spec
mkdir -p modelforge/spec  # already exists
# Create modelforge/spec/sponsor_lbo.py
# Create modelforge/templates/sponsor_lbo.py
# Create modelforge/builder/sheets/sources_uses.py
# Create examples/sponsor_lbo_techco.yaml
```

## Files touched this session

```
A  gold_standard_audit.py (fixed unicode + updated 10 detectors)
A  modelforge/analytics/sensitivity.py (added append_dcf_2d_tables)
A  modelforge/builder/sheets/dcf_valuation.py (stub/fade/norm)
A  modelforge/builder/sheets/merger_proforma.py (breakeven/contribution/collar/ppa-amort)
A  modelforge/builder/sheets/pf_cashflow.py (degradation/P90/lock-up)
A  modelforge/builder/sheets/ts_model.py (NOL/DTA/DTL/SBC/MI/revolver)
A  modelforge/templates/__init__.py (hook append_dcf_2d_tables)
A  WIP.md (this file)
```

## Commercial implication

v0.8 four-theme shipment moves the bulge-tier weighted score from **~8.1** to **~8.8** (estimated). Three of seven audit categories are now ≥9.0 PASS, and overall audit PASS rate crossed **76%** — the threshold for "bulge-tier ready" per PRD.

**Foreign-investor pitch update** (London / Zurich / Frankfurt / Nordic):
- "3-statement modeling: 100% of bulge-bracket checklist"
- "M&A: 91% of bulge-bracket checklist"
- "DCF: Damodaran CRP + Hamada beta + stub + fade + terminal normalization"
- Outstanding gap: full sponsor LBO (Theme 1) — closed by mid-May per PRD v0.8 ship criteria.

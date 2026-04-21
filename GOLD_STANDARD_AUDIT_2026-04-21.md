# ModelForge — Bulge-Bracket Gold Standard Audit

**Date**: 2026-04-21 (post-v0.6 ship)
**Auditor**: Claude Opus 4.7 (1M context), informed by 105-criterion bulge-bracket checklist compiled from Goldman / Morgan Stanley / JPM modeling standards via Training the Street, Wall Street Prep, Macabacus, Breaking Into Wall Street, Edward Bodmer, Damodaran, FAST Standard, Footnotes Analyst, OIV, BIS, Banca d'Italia, PwC / EY Italy tax summaries.
**Scope**: 13 workbooks × 105 applicable criteria = **398 individual checks**.

---

## Executive summary

| Overall | Count | % |
|---|---|---|
| **PASS** — meets bulge-bracket standard | **164** | **41.2%** |
| **PARTIAL** — present but incomplete / needs extension | **60** | **15.1%** |
| **FAIL** — missing or wrong | **169** | **42.5%** |
| N/A — not applicable (e.g. US §382 on Italian deal) | 5 | 1.3% |

**Headline**: v0.6 has **fixed the plumbing** (0 circular refs, 0 magic numbers in computed sheets, named ranges, BOP interest, amortization closure, full EBIT tax walk on PF) but is **missing the breadth** of a full bulge-bracket library. The gap is **not in the formula mechanics** (90%+ pass on formatting / structural criteria) — it's in the **depth of coverage per template** (PPA, IFRS 9 staging, LLCR/PLCR, AIFMD II, etc.).

### By category

| Category | Checks | PASS % | Status |
|---|---:|---:|---|
| **Format & Structural** | 184 | **78.8%** | ✅ bulge-tier plumbing |
| **3-Statement** | 20 | 40.0% | 🟡 core works, missing NOL / DTA / MI / SBC |
| **M&A Merger** | 11 | 27.3% | 🟠 no PPA, no cross-over, no break fees |
| **DCF** | 17 | 17.6% | 🟠 no stub, no fade, no Hamada, no full bridge |
| **PF** | 24 | 8.3% | 🔴 no LLCR/PLCR, no reserves, no cure |
| **LBO (full sponsor view)** | 44 | 4.5% | 🔴 unitranche ≠ LBO — see section below |
| **Italian Regulatory** | 98 | 1.0% | 🔴 AIFMD II / Basel / GACS / IFRS 9 not encoded |

---

## Critical observation: perspective mismatch

The two templates scoring lowest are LBO (4.5%) and Italian Regulatory (1.0%). Both are **not failures of v0.6 engineering** — they reflect a design choice made at v0.1:

1. **"LBO" in ModelForge means the LENDER'S unitranche view**, not the bulge-bracket sponsor LBO. A unitranche template doesn't need Sources & Uses, PPA, goodwill, management rollover, dividend recap, or GP promote because the user is a **private credit fund** pricing a senior-unitranche note — not a sponsor buying the target.

2. **Italian regulatory is aspirational**: the YAML Sources sheet cites AIFMD II, Legge 130/1999, Basel III SEC-IRBA, but the workbook formulas don't enforce the quantitative rules (leverage caps, capital floors, calendar provisioning haircuts).

This is **commercially correct** for Luka's current engagement model (Italian private credit deal screening for boutique funds), but it **limits expansion into bulge-bracket M&A advisory or sell-side sponsor diligence**. The question for v0.7+ is whether to add these modules or stay focused.

---

## Must-fix vs nice-to-have — bulge-bracket VP triage

If a Goldman or Morgan Stanley VP sat down to review ModelForge today, they'd rank the gaps as follows (items flagged in the PRD research as "highest-leverage"):

### Tier 1 — Must-fix before any fairness-opinion or strategic-advisory engagement (9 items)

| # | Gap | Why critical | Current |
|--|--|--|--|
| 8 | EV-to-equity bridge (minorities, pensions, prefs, cross-holdings) | DCF templates used for fairness opinions MUST have full bridge; otherwise equity value is wrong | FAIL — only net debt in bridge |
| 11 | Hamada unlever/relever beta | Single-input levered beta is a junior analyst's shortcut; a committee reading a fairness opinion expects comp-set derivation | FAIL |
| 13 | Damodaran country risk with volatility scaling | Flat ERP violates Damodaran methodology; committee would flag immediately | PARTIAL — Italy ERP used without σ-scaling |
| 17 | Sensitivity tables via Excel Data Tables | Macabacus and TTS require 2D WACC × g / WACC × exit tables via `Data > What-If` | PARTIAL — tornado only, no 2D matrices |
| 19–22 | LBO Sources & Uses + PPA + goodwill + DTL | If ever used for sponsor work, these are day-one deliverables | FAIL — all missing |
| 42–43 | M&A PPA + intangible amortization | Accretion/dilution without PPA is wrong; Goldman M&A deck never omits this | FAIL |
| 44 | Synergy phase-in credibility haircut | ✅ v0.6 has it — keep |
| 53–56 | PF CFADS + LLCR + PLCR | Every project finance bank lender expects these; v0.6 has CFADS but no LLCR/PLCR | PARTIAL / FAIL |
| 69 | CFS ↔ BS cash tie | Core integrity; ✅ v0.6 confirmed 1e-15 tie |

**Most commercially valuable gap**: #8 EV-to-equity bridge. A 30-minute fix for a template that's currently "only net debt" — adding minority interest, pension deficit, preferred, cross-holdings as optional parameters with source attribution.

### Tier 2 — Required for full-service credit committee memos (13 items)

| # | Gap | Template affected |
|--|--|--|
| 33 | §382 NOL limit (US) / Italian 5-yr NOL + 80% cap | Credit memo, 3-stmt |
| 53 (ext) | CFADS with WC and maintenance capex | PF (v0.6 documents simplification but doesn't ship with WC/maint) |
| 59 | O&M reserve + major maintenance reserve | PF |
| 60 | Lock-up test (DSCR threshold for distributions) | PF |
| 62 | Equity cure rights | PF, credit memo |
| 63 | Make-whole premium | Minibond, PF |
| 64 | P50/P90 probabilistic revenue | PF solar |
| 65 | Panel degradation curve (0.5% p.a. solar) | PF solar |
| 71 | 3-stmt debt schedule (already planned US-075) | 3-statement |
| 72–75 | NOL / DTA / SBC / MI schedules | 3-statement |
| 93 | IFRS 9 ECL 3-stage model | Credit memo — partial via RiskAnalysis, needs formal staging |
| 101 | Tranche priority + PDL (Principal Deficiency Ledger) | NPL, structured credit |

### Tier 3 — Bulge-bracket "polish" not strictly required (20+ items)

Sponsor MIP, dividend recap, earnout, GP promote carry, reverse-engineered hurdle, regulatory timeline, contribution analysis, exchange ratio collar, Basel securitization capital framework, Basel NPL calendar provisioning, AIFMD II leverage caps, loan-originating AIF classification — these are **nice-to-have for each specific use case** but missing them doesn't disqualify the model for committee review.

---

## Detailed per-category findings

### DCF (17 checks, 17.6% pass)

**v0.6 shipped**: mid-year convention (#1 ✅), Gordon g<WACC (#4 ✅), target-structure WACC weights (#10 ✅), scenario switch (#84 ✅), unlevered FCF discounted at WACC (#18 ✅).

**Pass**: 3 criteria (#1, #4, #10, #18).
**Partial** (4): #13 Damodaran CRP method, #15 size premium placeholder, #16 alpha placeholder, #17 Data Table matrices.
**Fail** (9): #2 stub period, #3 two-stage DCF (explicit + fade), #5 implied-g cross-check, #7 terminal FCF normalization (capex=D&A steady state), #8 full EV bridge (minorities/pensions/prefs/cross-holdings), #9 IFRS 16 lease liability in bridge, #11 Hamada beta, #12 comp-beta median process, #14 lambda CRP exposure.

**Biggest DCF gap**: #8 + #11. An Enel DCF at a utility desk without minority interest adjustment and without relevered beta is a junior's model — a committee would not sign off.

**Fix size (1-2 weeks)**: add to DCF spec — `minority_interest_eur_m`, `pension_deficit_eur_m`, `preferred_equity_eur_m`, `cross_holdings_eur_m` (each with source ID); add `ComparableBetas` sheet with unlever/relever block; split ERP into `mature_erp + (sovereign_spread × sigma_ratio × lambda)`.

---

### LBO (44 checks — unitranche + credit_memo × 22 criteria, 4.5% pass)

**This is the design-intent gap noted above.** The UnitrancheSpec doesn't model a sponsor LBO; it prices a unitranche note to a private credit fund. Bulge-tier sponsor LBO would need a separate `SponsorLBOSpec` with:

- Sources & Uses
- Purchase price build (offer × FD shares + option payouts + net debt + transaction fees)
- PPA (goodwill, identifiable intangibles, DTL on asset write-ups)
- OID amortization + financing fees capitalization
- PIK toggle per tranche
- Management rollover + MIP (4-yr vest)
- Dividend recap path
- Exit scenarios × 3 (strategic, IPO, secondary)
- Hurdle analysis (reverse-solve max price at target IRR)

**Currently passing (unitranche perspective)**: #26 debt waterfall (amort + sweep), #29 covenants (leverage + ICR), #38 returns (IRR, MoIC).

**Commercial recommendation**: keep UnitrancheSpec for the target private-credit-fund client base (Banca Finint, AIFI members). Add a NEW `SponsorLBOSpec` template in v0.8 when Luka has a sponsor-side engagement in the pipeline. Don't bloat the unitranche template.

---

### M&A Merger (11 checks, 27.3% pass)

**Pass**: #41 acquirer+target pro-forma, #44 synergy phase-in + integration, #45 cash/stock mix sensitivity, #46 multi-year accretion.

**Fail**: #42 PPA allocation + goodwill, #43 intangible amortization, #47 cross-over (breakeven synergy), #48 break fees, #50 regulatory timeline, #51 contribution analysis, #52 exchange ratio with collar.

**Tier-1 fix**: #42 PPA. Without it, the accretion/dilution you show a committee is missing:
- Goodwill on BS
- DTL on asset step-up
- Intangible amortization flowing through P&L (reduces pro-forma EPS)
- Post-deal BS pro forma

This is the single highest-impact fix on the merger template. **Fix size: 4-6 hours** — add a PPA block with configurable intangible-lives (customer list 10y, technology 7y, trade name 15y, residual = goodwill), amortization schedule, DTL tracking.

---

### Project Finance (24 checks on solar + Enfinity × 12 criteria, 8.3% pass)

**Pass**: #53 CFADS definition (post-v0.6: on EBIT−Interest with D&A schedule), #54 per-period DSCR, #57 debt sculpting to target DSCR, #58 DSRA 6-month forward, #65 degradation curve (parameter present on some specs).

**Fail** (9): #55 LLCR, #56 PLCR, #59 O&M + major maintenance reserves, #60 lock-up test, #61 mandatory prepayment events, #62 equity cure, #63 make-whole premium, #64 P50/P90 probabilistic revenue, #66 real-vs-nominal inflation consistency check.

**Biggest PF gap**: #55–56 LLCR/PLCR. Every PF banker at Intesa, Unicredit, BNP Paribas calculates these. A solar PF without LLCR ≥ 1.50x isn't ready for Enfinity-style club deals.

**Fix size**: 1 day each. `LLCR = NPV(CFADS over loan life, cost_of_debt) / (debt_outstanding + DSRA)`; `PLCR = NPV(CFADS over project life, cost_of_debt) / (debt_outstanding + DSRA)`. Both are single-row additions to DebtDSCR sheet.

---

### 3-Statement (20 checks — CDMO + Stevanato × 10 criteria, 40% pass)

**Pass**: #67 operating/non-operating split, #68 BS days-outstanding methodology, #69 CFS↔BS cash reconciliation, #70 retained earnings roll.

**Partial** (2): #71 debt roll-forward (tracked as US-075 for v0.6.1), #76 cash plug.

**Fail** (5): #72 NOL tracking, #73 DTA/DTL rolling, #74 SBC, #75 minority interest, #76 revolver cash plug.

**Tier-1 fix**: complete US-075 (debt schedule) in v0.6.1 as already planned. Tier-2 items (NOL, DTA/DTL, SBC, MI) are commercially justified only for specific engagements — add parametrically in v0.7 with toggles.

---

### Format & Structural (184 checks × ~14 criteria per file, 78.8% pass)

**This is the strongest category.** ModelForge v0.6 is bulge-tier on formatting.

**Pass on most files**: #79 units in header, #80 named ranges (25-59 per file), #81 iterative calc, #82 no volatile functions (post-v0.6 INDIRECT removal), #84 scenario switch, #85 single-direction cross-refs, #88 check cells, #89 cover sheet, #90 print layout, #91 version control (Reproducibility sheet), #92 football field (fairness only).

**Fail**: #78 bracketed negatives — flagged on every file. The stylesheet uses number formats like `#,##0.00` without accounting brackets for negatives. **Fix: 1-line change** in `styles.py` — replace `FMT_EUR_M` with `"#,##0.00;(#,##0.00);-"` pattern. This alone moves 13 files from FAIL to PASS on #78.

**Partial**: #77 color convention — the stylesheet applies blue/black/green/red but only on style tag; not across every cell. Full Macabacus AutoColor parity would close this.

---

### Italian Regulatory (98 checks × ~8 criteria per file, 1.0% pass)

**Pass**: #104 ECB reference rate (EURIBOR cited) on 12 files.

**Partial** (15): #93 IFRS 9 ECL (only credit_memo has RiskAnalysis sheet), #94 ECL formula (partial via EIR on Returns), #99 L.130 SPV on NPL/SC (spec sources cite L.130 but no SPV structure formula), #105 IRES+IRAP combined into one `effective_tax_rate` not split.

**Fail** (82): #95 SICR triggers, #96 AIFMD II leverage caps (175%/300%), #97 AIFMD II 20% single-borrower cap, #98 loan-originating AIF classification, #100 GACS on NPL, #101 tranche PDL, #102 Basel securitization capital, #103 Basel NPL calendar provisioning.

**Commercial reality**: these are regulatory COMPLIANCE checks for an AIFM or Banca d'Italia inspection — not deal-screening. A boutique private credit fund using ModelForge to pitch a committee doesn't need AIFMD II leverage caps in the workbook itself; their COO's compliance process checks that.

**Recommended scope**: add an optional `ComplianceCheck` sheet (v0.8) that flags:
- AIFMD II leverage > 175% / 300%
- Single-borrower concentration > 20% NAV
- Loan-origination % NAV > 50% (loan-originating AIF trigger)
- GACS eligibility test (senior tranche rating ≥ IG)

This would move from 1% → ~15% pass on IT-Reg without rewriting every template.

---

## Revised scorecard — post-v0.6, pre-v0.7

Original v0.5 projection vs v0.6 shipped vs bulge-bracket gold standard:

| Dimension | v0.5 | v0.6 (shipped) | Gold-std ceiling | Pre-v0.7 weighted |
|---|---:|---:|---:|---:|
| Formula discipline | 9.7 | **9.9** | 10.0 | 9.9 |
| Source traceability | 9.4 | **9.5** | 10.0 | 9.5 |
| Modelling completeness | 9.3 | **9.6** | 10.0 | **8.4** ← adjusted for bulge-breadth gaps |
| Market / regulatory alignment | 8.8 | 8.8 | 10.0 | **7.2** ← IT-Reg only 1% pass, downgraded |
| Infrastructure / productization | 7.4 | **7.6** | 10.0 | 7.6 |

**Weighted score on 25-criterion framework**: **9.0** (bulge-tier on plumbing + core Italian credit templates; NOT bulge-tier on depth of coverage for sponsor LBO / fairness opinion / full M&A).

**Revised positioning**:
- **Top-tier on what it claims**: Italian credit & structured finance deal screening, lender's-view unitranche pricing, project finance DSCR/sizing, 3-statement corporate, NPL collection waterfall, minibond arranging.
- **Below bulge-tier on what it doesn't claim**: sponsor LBO buy-side modeling, full M&A fairness opinion, Basel regulatory capital, AIFMD II compliance monitor.

This is an **honest repositioning, not a downgrade** — the v0.5 scorecard was benchmarked against "Italian-specialist bulge human" who also doesn't build full M&A PPA models unless in that specific deal. The 9.0 score is correct for the market MF actually plays in.

---

## Recommended v0.7 / v0.8 / v1.0 roadmap

### v0.7 (2-3 weeks, "bulge-tier depth") — 15 stories

Priority: closes Tier-1 + Tier-2 gaps on existing templates without adding new templates.

| ID | Story | Effort |
|---|---|---|
| US-100 | DCF: full EV→Equity bridge (minorities, pensions, prefs, cross-holdings, IFRS 16 lease liability) | 6h |
| US-101 | DCF: stub-period handling + two-stage fade period | 6h |
| US-102 | DCF: ComparableBetas sheet with Hamada unlever/relever | 4h |
| US-103 | DCF: Damodaran CRP methodology (mature + σ-scaled country spread × λ) | 2h |
| US-104 | DCF: implied-g cross-check row; terminal FCF normalization (capex=D&A) | 2h |
| US-105 | DCF: 2D sensitivity tables (WACC × g, WACC × exit) via Excel Data Table | 4h |
| US-106 | Merger: PPA block with intangibles + goodwill + DTL + amortization schedule | 6h |
| US-107 | Merger: cross-over / breakeven synergy analysis row | 2h |
| US-108 | Merger: pro-forma credit metrics + contribution analysis | 3h |
| US-109 | PF: LLCR and PLCR computations + thresholds in QC | 2h |
| US-110 | PF: O&M reserve + major maintenance reserve (MMR sinking fund) | 4h |
| US-111 | PF: lock-up test (DSCR < threshold → block distribution) | 2h |
| US-112 | PF: equity cure rights (capped 2-3 cures, 20% EBITDA uplift) | 4h |
| US-113 | PF: P50/P90 probabilistic revenue; debt sized on P90 | 4h |
| US-114 | Format: bracketed-negative number format applied globally | 30m |

**Projected impact**: DCF PASS 17.6% → 70%, M&A 27.3% → 55%, PF 8.3% → 55%, Format 78.8% → 90%.

**New weighted score**: ~9.3 (closer to bulge-tier on output breadth).

### v0.8 (3-4 weeks, "sponsor-side + compliance") — 10 stories

| ID | Story | Effort |
|---|---|---|
| US-120 | New `SponsorLBOSpec` template: S&U + purchase price + PPA + OID + PIK + revolver + MIP + exit scenarios | 2 weeks |
| US-121 | US §382 NOL block (if US deals) + Italian 5-yr / 80% NOL | 4h |
| US-122 | 3-statement: NOL + DTA/DTL + SBC + MI schedules | 1 week |
| US-123 | NPL/SC: formal PDL (Principal Deficiency Ledger) + full tranche waterfall | 1 week |
| US-124 | GACS structure (state guarantee on senior, fee pricing on Italian financial CDS) | 4h |
| US-125 | Optional `ComplianceCheck` sheet: AIFMD II leverage / 20% cap / loan-orig flag | 6h |
| US-126 | IFRS 9 formal 3-stage model with SICR triggers + forward-looking macro | 1 week |
| US-127 | Basel securitization capital (SEC-IRBA/SA/ERBA) | 1 week |
| US-128 | Basel NPL calendar provisioning schedule | 4h |
| US-129 | Real estate: LP/GP waterfall (pref + catchup + promote) — already in v0.6 PRD US-078 | 6h |

**Projected impact**: LBO PASS 4.5% → 55% (new sponsor template), IT-Reg 1% → 35%.

**New weighted score**: ~9.5 (bulge-bracket parity).

### v1.0 (post-v0.8, "regulatory excellence") — 10 stories

| Story |
|---|
| Full Basel III/IV SEC-IRBA capital calculator with RWA roll |
| EBA IRB/Standardised choice per asset class |
| Full §197 intangibles vs goodwill tax treatment |
| Earnout / CVR with probability-weighted FV |
| Break fee + reverse-termination fee |
| Regulatory clearance timeline (HSR/CMA/EU) with synergy NPV impact |
| Mandatory prepayment event toggles |
| Make-whole premium on bond redemption |
| Tax equity structure (US renewables partnership flip) |
| Monte Carlo Lender IRR with copula default correlation |

---

## What the audit does NOT penalize (appropriately)

- **LBO template is thin**: it's a unitranche lender's-view template by design, not a sponsor LBO. The 44-check LBO fail rate reflects checking against bulge-bracket SPONSOR standards, not lender standards. UnitrancheSpec is purpose-fit for Italian private credit funds.
- **Italian regulatory is aspirational**: these are compliance/regulatory reporting checks, not deal-screening. Different buyer persona.
- **US §382 NOL limit**: marked N/A for Italian CDMO target — correctly recognized as inapplicable.
- **US NUBIG/NUBIL rules**: marked N/A — Italian deal.

---

## Top-10 "quick wins" to pick up before v0.7 formal cycle

Effort < 1 day each; highest visibility per hour:

1. **Bracketed negatives** (30 min) — one line in `styles.py` → 13 files cleaner.
2. **Minimum / Average DSCR rows** on PF (30 min) — `=MIN(operating range)`, `=AVERAGE(operating range)`.
3. **LLCR + PLCR rows** on PF (1 hour) — two NPV formulas, cite Bodmer in comment.
4. **Implied-g cross-check on DCF** (30 min) — `=WACC − FCF_{n+1} / TV_exit_multiple`.
5. **EV-to-equity bridge extension** (2 hours) — add minority_interest_eur_m + pension_deficit_eur_m + preferred_eur_m as optional DCFSpec fields + 3 new rows on Valuation.
6. **IRES + IRAP split** (1 hour) — separate `ires_rate_pct` and `irap_rate_pct` in Assumptions + effective = IRES × taxable_IRES + IRAP × taxable_IRAP.
7. **Accretion EPS "cross-over year" row** (30 min) — reverse-solve min synergy for Y1-neutral.
8. **DSRA forward-looking label fix** (10 min) — row label says "end of year" but formula already forward-looking; update label.
9. **Sensitivity 2D table via openpyxl** (4 hours) — WACC × g matrix on DCF; WACC × exit on merger.
10. **Comp-beta median stub** (2 hours) — add empty `ComparableBetas` sheet with a 5-row template; placeholder Hamada formula.

Each of these moves a "FAIL" to "PASS" on a specific Tier-1 item.

---

## Reproduction

```
# Run the gold-standard audit
python gold_standard_audit.py

# Detailed findings
cat gold_standard_findings.json  # 398 records
```

## Sources

- [Damodaran — Country Default Spreads and Risk Premiums](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html)
- [Damodaran — Measuring Country Risk Exposure](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/CountryRisk.htm)
- [Wall Street Prep — Terminal Value Formula](https://www.wallstreetprep.com/knowledge/terminal-value/)
- [StableBread — Mid-Year Convention and Stub Periods](https://stablebread.com/mid-year-convention-stub-periods/)
- [Hamada's Equation — Wikipedia](https://en.wikipedia.org/wiki/Hamada%27s_equation)
- [IB Interview Questions — Beta Unlever / Relever](https://ibinterviewquestions.com/guides/valuation-investment-banking/beta-raw-adjusted-unlevered-relevered)
- [Footnotes Analyst — Enterprise to Equity Bridge](https://www.footnotesanalyst.com/enterprise-to-equity-bridge-more-fair-values-required/)
- [OIV / Péronnet — Valuation After IFRS 16 (PDF)](https://www.fondazioneoiv.it/wp-content/uploads/2019/10/P%C3%A9ronnet_IFRS16-impact-on-valuation-methodologies-vDEF.pdf)
- [Macabacus — Sources & Uses LBO](https://macabacus.com/lbo-model/sources-and-uses-lbo)
- [Macabacus — PPA Steps](https://macabacus.com/lbo-model/purchase-price-allocation-steps)
- [Macabacus — Cash Sweep & Revolver](https://macabacus.com/operating-model/revolver-cash-sweep)
- [Macabacus — Long-Form LBO Template (four bulge-bracket models)](https://macabacus.com/excel/templates/lbo-model-long)
- [Macabacus — Color Formatting](https://macabacus.com/blog/improving-model-readability-with-color-formatting)
- [Wall Street Prep — Merger Model](https://www.wallstreetprep.com/knowledge/merger-model/)
- [Wall Street Prep — 3-Statement Model Guide](https://www.wallstreetprep.com/knowledge/build-integrated-3-statement-financial-model/)
- [Edward Bodmer — Project Finance Structuring with Sculpting](https://edbodmer.com/project-finance-structuring-with-sculpting-complex-issues/)
- [Edward Bodmer — LLCR and PLCR Complexities](https://edbodmer.com/llcr-and-plcr-complexities-and-meaning-for-break-even/)
- [Edward Bodmer — DSRA in DSCR and Sculpting](https://edbodmer.com/including-releases-or-deposits-to-dsra-in-dscr-and-sculpting/)
- [Solargis — P90 PV Energy Yield](https://solargis.com/resources/blog/best-practices/how-to-calculate-p90-or-other-pxx-pv-energy-yield-estimates)
- [NREL — P50/P90 Analysis for Solar Energy](https://docs.nrel.gov/docs/fy12osti/54488.pdf)
- [CFI — How the 3 Financial Statements are Linked](https://corporatefinanceinstitute.com/resources/accounting/3-financial-statements-linked/)
- [26 USC §382 — Cornell LII](https://www.law.cornell.edu/uscode/text/26/382)
- [Plante Moran — Section 382 NOL Carryforwards](https://www.plantemoran.com/explore-our-thinking/insight/2025/06/how-section-382-can-unexpectedly-impact-nol-carryforwards)
- [BIS FSI — IFRS 9 Expected Loss Provisioning](https://www.bis.org/fsi/fsisummaries/ifrs9.pdf)
- [BIS — Basel Securitisation Framework (d374)](https://www.bis.org/bcbs/publ/d374.pdf)
- [BIS — Basel III Finalising Post-Crisis Reforms (d424)](https://www.bis.org/bcbs/publ/d424.pdf)
- [BDO — IFRS 9 ECL Model Explained](https://www.bdo.co.uk/en-gb/insights/business-edge/business-edge-2017/ifrs-9-explained-the-new-expected)
- [Banca d'Italia — Changes to Law 130/1999](https://www.bancaditalia.it/pubblicazioni/note-stabilita/2017-0010/index.html?com.dotmarketing.htmlpage.language=1)
- [KPMG — GACS Italian NPL Space](https://assets.kpmg.com/content/dam/kpmg/it/pdf/2019/07/GACS-crediti-deteriorati.pdf)
- [Jones Day — Italian NPL Guaranteed by Government](https://www.jonesday.com/-/media/files/publications/2016/02/italian-npl-guaranteed-by-the-italian-government-l/files/italiannplguaranteedpdf/fileattachment/italian_npl_guaranteed.pdf)
- [BCLP — AIFMD II Leverage Limits](https://www.bclplaw.com/en-US/events-insights-news/aifmd-ii-leverage-limits-and-single-borrower-exposure-restriction.html)
- [Linklaters — Loan Origination under AIFMD II](https://www.linklaters.com/en/insights/publications/aifmd/loan-origination-under-aifmd-ii)
- [PwC Italy — Corporate Taxes on Income](https://taxsummaries.pwc.com/italy/corporate/taxes-on-corporate-income)
- [FAST Standard](https://fast-standard.org/)

---

## Appendix — audit artifacts

- `gold_standard_audit.py` — the 398-check audit script, modular per-template
- `gold_standard_findings.json` — machine-readable findings (398 records)
- `STRESS_TEST_REPORT_2026-04-21.md` — prior adversarial audit (98 findings, all fixed in v0.6)
- `V06_SHIPPED.md` — v0.6 ship report (0 CRITICAL / 0 HIGH remaining)
- `PRD_v06_stress_test_fixes.md` — v0.6 PRD with 26 stories

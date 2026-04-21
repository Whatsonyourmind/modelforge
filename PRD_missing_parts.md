# PRD — ModelForge Missing Parts (v0.8.7 → v1.0+ and beyond)

**Status**: drafted 2026-04-22 (supersedes and complements `PRD_v10_world_class_hero.md`)
**Owner**: Luka Stanisljevic
**Horizon**: 6-9 months, split across v0.8.7 polish → v0.9 → v1.0 → v1.5 stretch
**Baseline**: v0.8.6 (`713728e`) — 369 PASS / 53 PARTIAL / 0 FAIL / 3 N/A on 425-check bulge-bracket gold-standard audit (86.8%). Weighted score ~9.1/10. v1.0 target 9.65/10.

---

## Executive summary — the remaining gap

v0.8 closed every criterion-level FAIL. The shape of what remains is:

1. **53 PARTIALs to close** (one week of surgical work). Cluster into 9 specific issues with file-level fixes; drives PASS rate 86.8% → ~95%.
2. **1 pre-existing test failure** (`test_reverse.py` merger classifier) blocks `pytest -q` cleanliness.
3. **Live-compute polish on v0.8 Theme 4/6 stubs** (~2 weeks). Rows exist, values need to live-compute not just be placeholder-labelled.
4. **v0.9 "Beyond Italy"** — 5 new jurisdictions, multi-currency / FX, live market data, Excel add-in (6-8 weeks).
5. **v1.0 "Enterprise hero"** — Multi-tenant SaaS, deliverable export (PPT/Word/PDF), regulatory reporting (AIFMD Annex IV + COREP/FINREP), AI co-pilot, ingestion v2, SOC 2 + Big 4 attestation (10-12 weeks).
6. **v1.5+ horizon** — APAC jurisdictions, FRTB market-risk stack, ESG/SFDR, template marketplace.

Total: **~140 user stories**, delivered across 4 versions, 6-9 months, ending at 9.65/10 weighted + €600K-1.2M ARR.

---

# Part 0 — v0.8.7 Audit-Gap Polish (1 week, May 2026)

**Goal**: convert 53 PARTIAL → 0 PARTIAL (or N/A where policy dictates). Reach ≥92% gold-standard PASS, the v0.8 PRD ship gate. Ship as `v0.8.7-audit-clean`.

## Theme 0.A — The 53 PARTIAL clusters

### Cluster A — 2D Data Tables universal (13 files × check #83)

v0.8.1 added `append_dcf_2d_tables()` (WACC×g and WACC×exit_x) to DCF sheet. Audit flags it as PARTIAL on **every non-DCF template** because the detector expects Data Table presence in each workbook's sensitivity sheet, and tornado-only is marked `~`.

| ID | Story | Acceptance |
|---|---|---|
| US-500 | Extract `append_2d_tables()` into `modelforge/analytics/sensitivity.py` as generic helper taking (row_var_range, col_var_range, output_cell). Wire into every template's SensitivityAnalysis sheet. Templates: unitranche, credit_memo, minibond, npl, structured_credit, project_finance, real_estate, three_statement, merger, fairness, sponsor_lbo. | Check #83 PASS for all 13 files; 2 axes per template as per §US-501 matrix below. |
| US-501 | Per-template axis selection matrix: <br>• unitranche/credit_memo: Leverage × Spread; Leverage × Exit Multiple <br>• minibond: Coupon × Senior Leverage <br>• npl: Haircut × Recovery Timing <br>• structured_credit: Attachment × Detachment <br>• project_finance: DSCR × Tariff; DSCR × Capex <br>• real_estate: Cap Rate × Exit Yield <br>• three_statement: Revenue Growth × EBITDA Margin <br>• merger: Synergy × Accretion/(Dilution) <br>• fairness: WACC × g; EV/EBITDA × EBITDA <br>• sponsor_lbo: Purchase Multiple × Exit Multiple; Leverage × Hold Period | Each workbook has ≥2 Data Tables; audit #83 green. |
| US-502 | Unit tests: open built workbook via openpyxl, assert each SensitivityAnalysis sheet has ≥1 CELL with `.data_validation` or table formula hash resolving a 2D array. Add to `tests/test_sensitivity_tables.py`. | pytest green. |

### Cluster B — Macabacus AutoColor full parity (14 files × check #87)

Currently `styles.py` tags hard-coded blues/blacks but not greens for cross-references. Macabacus AutoColor distinguishes: **input (blue)**, **formula (black)**, **link to other sheet (green)**, **link to other workbook (red)**, **reserved/warning (orange)**.

| ID | Story | Acceptance |
|---|---|---|
| US-505 | Extend `modelforge/builder/styles.py` with `GREEN_XREF_FONT` and `apply_xref_color(cell)` helper that inspects formula for `!` or external-range refs and tags green. Integrate into `BaseWorkbook._write_formula()`. | Every cross-sheet formula tagged green; every external-workbook link (rare in templates) tagged red. |
| US-506 | Add orange tagging for any row flagged as `warning=True` in its spec (e.g., negative NPV, covenant breach, DSCR<1.0x). Currently these rows exist in QC sheet with `fill_yellow`; promote orange for the driver cell too. | Audit #87 PASS for all 14 templates. |

### Cluster C — Basel securitization capital framework (13 files × check #102)

Check #102 expects each credit/structured model to include a Basel-III capital computation either as a dedicated sheet or as a row in Covenants/Compliance referencing RWA × capital ratio.

| ID | Story | Acceptance |
|---|---|---|
| US-510 | New sheet `BaselCapital` (hidden by default; user toggles via `spec.include_basel_capital: True`). Four rows: EAD (Exposure at Default from debt outstanding), Risk Weight (spec input + default matrix), RWA = EAD × RW, Capital Requirement = RWA × 8%. CET1 / Tier 1 / Total Capital breakdown. | Check #102 PASS on all 13 non-equity templates. |
| US-511 | Risk-weight default matrix in `modelforge/risk/basel_rw.py`: senior secured → 50%, mezz unrated → 100%, equity tranche → 1,250% (deduct), NPL Stage 3 → 150%, PF DSCR≥1.5x → 70%, unrated corporate → 100%. Spec override via `spec.risk_weight_override: float`. | All templates pull RW correctly; unit test covers override. |
| US-512 | Basel securitization framework (SEC-SA / SEC-ERBA) for structured_credit + npl: implement look-up tables for senior/mezz/equity-like tranches. | #102 PASS specifically on structured_credit + npl. |

### Cluster D — Legge 130/1999 SPV structure (2 files × check #99)

| ID | Story | Acceptance |
|---|---|---|
| US-515 | Add `SPVStructure` block to NPL + SC templates: SPV name, servicer, master servicer, sub-servicer, trustee, calculation agent, paying agent, Legge 130/1999 compliance flag, segregation statement. Outputs on StructureOverview sheet. | #99 PASS on npl + structured_credit. |

### Cluster E — CFADS maint capex split (2 files × check #53)

| ID | Story | Acceptance |
|---|---|---|
| US-520 | In `modelforge/builder/sheets/pf_cashflow.py`, split capex into `maintenance_capex` vs `growth_capex` in the CFADS row. CFADS = EBITDA − taxes − ΔWC − maintenance_capex (growth capex funded separately from equity/debt). | #53 PASS on project_finance + real_estate_pbsa PF variant. |

### Cluster F — M&A pro-forma credit metrics (1 file × check #49)

| ID | Story | Acceptance |
|---|---|---|
| US-525 | On AccretionDilution sheet, add Pro-forma Credit Metrics block: combined Net Debt / EBITDA, Net Debt / EBITDA pre-synergy, Net Debt / EBITDA year-3 post-synergy, Interest Coverage, Fixed-Charge Coverage. Tag breaches red. | #49 PASS on merger. |

### Cluster G — DCF Enel-specific gaps (4 checks on dcf_enel.xlsx: #9, #10, #15, #16)

| ID | Story | Acceptance |
|---|---|---|
| US-530 | #9 IFRS 16 lease treatment — add operating-lease liability add-back to EV bridge and lease-interest in WACC. Dedicated row on BridgeToEquity sheet. | #9 PASS. |
| US-531 | #10 WACC target capital structure — expose `target_de_ratio` input; unlever-relever beta using target D/E rather than current. | #10 PASS. |
| US-532 | #15 Size premium — add Duff & Phelps / Kroll size premium row ramping 0% for >$20B equity to 500bps for <$100M. Read from `modelforge/feeds/duff_phelps.py` static table. | #15 PASS. |
| US-533 | #16 Company-specific alpha — expose `spec.alpha_bps` as WACC add-on (default 0; override for Italian boutiques / illiquid names). | #16 PASS. |

### Cluster H — Sponsor LBO live compute (3 checks: #24, #27, #28)

v0.8.5 added rows but compute is static. Live compute needed:

| ID | Story | Acceptance |
|---|---|---|
| US-540 | #24 Financing fees capitalization — wire `financing_fee_pct × debt_raised` → CapitalizedFees line; amortize over weighted-avg tenor; add-back to CFS as non-cash. | #24 PASS. |
| US-541 | #27 Revolver + commitment fee live draw — currently revolver balance is manual input; implement auto-draw: `revolver_t = MAX(0, min_cash − cash_before_revolver_t)`; commitment fee = `0.5% × (facility_size − avg_balance_t)`. | #27 PASS. |
| US-542 | #28 Cash sweep step-down by leverage — 75% sweep if Net Debt/EBITDA ≥ 5.0x, 50% if 4.0-5.0x, 25% if 3.0-4.0x, 0% below. Step-function row on DebtSchedule. | #28 PASS. |

### Cluster I — Fairness named ranges (1 check on fairness_amplifon.xlsx: #80)

| ID | Story | Acceptance |
|---|---|---|
| US-545 | Add `equity_value_midpoint`, `football_low`, `football_high`, `wacc_base`, `g_terminal` named ranges to FootballField + DCFValuation sheets. | #80 PASS. |

## Theme 0.B — Reverse classifier fix

| ID | Story | Acceptance |
|---|---|---|
| US-550 | `modelforge/reverse/analyzer.py` weight fix: bump DealStructure + ProForma + AccretionDilution sheet weights to 3× vs ComparableBetas / ComplianceCheck / PPA. Classifier should detect merger when these sheets are present even with the new v0.7 enrichment sheets. | `tests/test_reverse.py::test_round_trip_classification[merger_tim_iliad.yaml-merger-MergerSpec]` PASS. Add regression test for false-positive merger-from-three_statement scenario. |

## Theme 0.C — v0.8 Theme 4 & 6 live-compute residuals

v0.8 shipped Theme 4 partial (US-240/241/244 live; US-242/243/245/246/247/248 row-only). Ship full:

| ID | Story | Acceptance |
|---|---|---|
| US-560 | US-242 live compute — O&M reserve funding at COD, monthly deposit to target `om_reserve_months × monthly_opex`, release at decommissioning. Add `OMReserveBalance` roll row. | PF workbook shows positive O&M reserve balance during ops, draw-down at terminal. |
| US-561 | US-243 MMR sinking fund — accumulate `major_maintenance_reserve_eur_m / mmr_build_years` per year until target reached; draw per event schedule (default every 5y). | MMR balance row live; audit detector pattern updated. |
| US-562 | US-245 equity cure — iterative Excel calc (enable `wb.iterative_calculation = True`): if DSCR_t < min_dscr, sponsor injects `equity_cure_t = covenant_shortfall × (1 + haircut)`; subject to `equity_cure_cap_count` limit. | Cure column populates when breach simulated; cap enforcement tested. |
| US-563 | US-246 make-whole on early redemption — make-whole premium = `MAX(0, PV_remaining_coupons_at_treasury+spread − principal_outstanding)` triggered by `early_redemption_flag`. | Make-whole row computes positive value on early redemption scenario. |
| US-564 | US-247 real-vs-nominal QC — add `inflation_consistency_check` row: flag red if tariff escalator inflation assumption ≠ opex inflation assumption ≠ discount-rate inflation assumption. | Check red on inconsistent spec; green on consistent. |
| US-565 | US-248 mandatory prepayment per-event toggle — 5 boolean flags (insurance proceeds, asset sale, change of control, illegality, excess CF sweep); each gates a prepayment row. | Flags togglable via spec; each gate tested. |
| US-566 | Theme 6 US-260 full IFRS9ECL sheet — dedicated sheet per-facility with columns: Facility ID, Stage (1/2/3/POCI), 12m PD, Lifetime PD, LGD, EAD, Discount Factor, ECL = PD × LGD × EAD × DF. Roll-up to portfolio ECL. | Sheet exists on all credit templates; audit detector #260 implemented. |
| US-567 | Theme 6 US-261 SICR trigger flags — hard-coded cells: absolute PD threshold (spec input), relative doubling vs origination, rating downgrade ≥ 2 notches, watchlist flag, forbearance flag, 30+ DPD flag. Stage migration logic: any flag → Stage 2; 90+ DPD → Stage 3. | Triggers all togglable; stage migration live via SUMPRODUCT formula. |
| US-568 | Theme 6 US-262 forward-looking macro scenarios — 3 scenarios (Upside/Base/Downside) weighted (25/50/25). Each scenario has GDP growth, unemployment rate, CPI inflation → PD multiplier via linear coefficient. Weighted PD = Σ(weight_s × PD_base × multiplier_s). | Scenarios on separate rows; weighted PD flows into ECL formula. |
| US-569 | Theme 6 US-263 POCI treatment — for NPL portfolios, mark Stage POCI; LGD applied to gross carrying value; no 12m/lifetime switch (always lifetime); recognize interest on net of ECL. | POCI toggle in NPL spec; ECL computed on gross. |
| US-570 | Theme 1 sponsor-LBO live compute polish — PIK accrual compounding (not straight-line), revolver auto-draw (done US-541), dividend-recap refinance flow with new debt placement fees + redemption premium, earnout accretion through P&L (time-value unwind), exit IRR via XIRR on actual sponsor CF series (not approximation). | All 5 items live-compute in `sponsor_lbo_techco.xlsx`; audit category LBO 77% → ≥90%. |

## Theme 0.D — Sponsor LBO ingest + sensitivity + reverse

| ID | Story | Acceptance |
|---|---|---|
| US-575 | Curate `modelforge/ingest/prompts/template_sponsor_lbo.md` for sponsor-side signals (CIM, IC memo, purchase agreement, subscription doc, ESG screen, financing commitment letter, lender presentation). Remove inherited unitranche cues. | `modelforge ingest` on sample CIM → sponsor_lbo YAML with ≥80% field coverage. |
| US-576 | Sponsor LBO sensitivity factor list in `modelforge/analytics/factors.py` → primary: offer premium, exit multiple, hold period, sponsor equity contribution, cost of debt, EBITDA margin; secondary: tax rate, working-capital efficiency, transaction fees. | Tornado for sponsor_lbo shows 6-8 primary factors by default. |
| US-577 | Sponsor LBO reverse-engineer from external Excel — extend `modelforge/reverse/engine.py` to classify Sources&Uses + DebtSchedule + Returns patterns as sponsor_lbo. | Existing Macabacus LBO template parses to SponsorLBOSpec round-trip. |

**v0.8.7 ship gate**: gold standard ≥ **95%** PASS (conservative: ≥92% PASS); 0 FAIL; 0 PARTIAL on Clusters A/B/C; `pytest -q` 100% clean.

---

# Part 1 — v0.9 "Beyond Italy" (6-8 weeks, Jun-Jul 2026)

**Goal**: Remove the Italian-centricity. Ship 5 new jurisdictions, multi-currency, live market data, and the long-deferred Excel add-in. Tag `v0.9-beyond-italy`.

## Theme 1.A — Jurisdictional coverage (4 weeks)

| ID | Story |
|---|---|
| US-600 | Introduce `modelforge/jurisdictions/` package. Each jurisdiction = pydantic `Jurisdiction` model with: ISO code, tax rates (federal + state/regional breakdown), regulatory regime list, accounting standard (IFRS / US GAAP / UK GAAP / German HGB), fiscal year convention, corporate tax loss carryforward rules, statutory depreciation schedules, default comps set, sovereign risk-free curve ticker, default ERP, withholding tax matrix. |
| US-601 | Refactor existing `modelforge/finance/italy_corp_tax.py` as `modelforge/jurisdictions/italy.py` conforming to new Jurisdiction protocol. IRES 24% + IRAP 3.9% + PEX / SIIQ / participation exemptions preserved. |
| US-602 | `modelforge/jurisdictions/uk.py` — UK corp tax 25% (main) / 19% (small), IFRS as standard, PRA leverage ratio 3.25%, FCA AIFM + BMR regimes, SONIA as risk-free, CMA merger regime, UK Takeover Panel rules for M&A. Share-based consideration tax neutrality rules. |
| US-603 | `modelforge/jurisdictions/germany.py` — Körperschaftsteuer 15% + Solidaritätszuschlag 5.5% + Gewerbesteuer ~14% (municipality-varying) = ~29.9% combined, HGB/IFRS dual, BaFin + KAGB, thin-cap + interest barrier rules, German trade-tax add-backs (25% of interest). |
| US-604 | `modelforge/jurisdictions/france.py` — IS 25% (standard) / 15% (small), AMF oversight, 4% financial-sector surcharge, CVAE (territorial economic contribution), IFRS + French GAAP dual. |
| US-605 | `modelforge/jurisdictions/spain.py` — IS 25%, CNMV, IFRS, capital gains rules for PE/RE, Law 19/2017 on alternative investment funds. |
| US-606 | `modelforge/jurisdictions/usa.py` — federal 21% + avg state ~5% (blended ~25-27%), US GAAP, SEC '40 Act for RICs + Investment Advisers Act, §382 NOL limit (ownership-change studies), GILTI / FDII / BEAT for cross-border, ASC 842 leases, ASC 805 business combinations, §197 15yr goodwill amortization (vs IFRS impairment-only), §162(m) executive comp limit. |
| US-607 | Jurisdiction-aware WACC builder: reads risk-free curve ticker → fetches current yield from feeds; applies country ERP from Damodaran; country-specific tax shield; unlevers beta using local avg D/E. |
| US-608 | Jurisdiction-aware accounting policies — GAAP-vs-IFRS switchboard covering: revenue recognition (ASC 606 vs IFRS 15 — very similar post-convergence), leases (ASC 842 vs IFRS 16), goodwill (US §197 amortization for tax only; IFRS/GAAP both impairment-only for books), business combinations (ASC 805 vs IFRS 3 — fair value), intangible amortization lives. |
| US-609 | Jurisdiction-aware labels / i18n pass #2 — extend `modelforge/builder/i18n.py` with DE + FR + ES + UK-English strings. User-selectable default language via spec `display_language: "en"\|"it"\|"de"\|"fr"\|"es"`. |
| US-610 | Cross-jurisdiction tests: build identical 3-stmt DCF model under IT / UK / DE / FR / ES / US; assert tax expense matches expected post-tax shield differential within 50bps. |

## Theme 1.B — Multi-currency + FX (2 weeks)

| ID | Story |
|---|---|
| US-620 | `modelforge/fx/` package: `spot_rates.py` (ECB reference rates), `forward_rates.py` (covered interest parity using short-rate differential), `historical.py` (time-series). |
| US-621 | Currency roll across periods: each cash-flow row tagged with currency code; workbook displays in presentation currency with live FX conversion footer row showing FX assumption per period. |
| US-622 | Cross-border M&A support: target EBITDA in currency A, acquirer multiples in currency B, financing raised in currency C. Three-currency FX block on DealStructure sheet. |
| US-623 | FX sensitivity 2D table: ±10% / ±20% FX shock on deal-date spot → post-close IRR / MoIC (LBO) or accretion/dilution (M&A). |
| US-624 | Natural-hedge detection row on Covenants / QC: if revenue ≥ 60% in same currency as senior debt, flag "naturally hedged" green; else orange. |
| US-625 | Multi-currency debt tranches: senior in EUR, mezz in USD, each with own reference rate (EURIBOR / SOFR) and margin. Interest schedule computes each tranche in local currency then converts. |
| US-626 | FX translation-adjustment CTA (cumulative translation adjustment) row on 3-stmt equity bridge for cross-border subs. |

## Theme 1.C — Live market data (1 week)

| ID | Story |
|---|---|
| US-630 | ECB SDW (Statistical Data Warehouse) connector in `modelforge/feeds/ecb.py` extended: EURIBOR 1M/3M/6M/12M, euro-area swap curve (OIS + EUR swap), TLTRO stock, ECB deposit rate, inflation HICP. Cache policy: 1-hour TTL, last-known-good fallback. |
| US-631 | BoE connector — Bank Rate, SONIA, UK swap curve, gilt yield curve. |
| US-632 | Fed / FRED connector — Fed Funds target, SOFR, UST yield curve 1M→30Y, CPI, unemployment, GDP growth, recession probability (NY Fed). |
| US-633 | Damodaran data refresh cron — monthly auto-fetch of Country ERP + Total ERP + Industry Beta + WACC datasets; pin snapshot to git for reproducibility. Already partial via `modelforge/feeds/damodaran.py`; extend with industry beta + mature ERP + country default spreads. |
| US-634 | CDS spreads via Markit RED or free IHS proxy — sovereign CDS + top 100 corporate CDS; use for GACS-style guarantee fee pricing + credit-spread analytics. |
| US-635 | Static FX snapshot connector — ECB daily reference rates for top 20 pairs (EUR/USD, EUR/GBP, EUR/CHF, EUR/JPY, GBP/USD, etc.). |
| US-636 | Live-data drift watcher integration — `modelforge drift` command (already exists for feeds) extended to flag workbook as "stale" if any referenced rate has moved >25bps since build. Add to Excel add-in (US-650). |

## Theme 1.D — Excel add-in (1 week)

| ID | Story |
|---|---|
| US-650 | Office.js add-in scaffolding in new `modelforge/addin/` directory: manifest.xml, taskpane.html + react UI, Office runtime integration. Ribbon group: "ModelForge" with buttons: Build from Spec, QC, Drift Check, Dossier, Lineage Walk. |
| US-651 | Build from Spec — user drops YAML into taskpane, add-in POSTs to local `modelforge serve` daemon or hosted API, receives .xlsx binary, replaces current workbook. |
| US-652 | Lineage side-pane — on cell selection, query linkage graph (SQLite .graph.db served via HTTP), show "Upstream drivers" + "Source doc / page" + "Downstream dependents". |
| US-653 | Drift badge — cell turns yellow if market data has moved ≥25bps since workbook was built; hover shows "Was 3.25% on 2026-04-15, now 3.50%". |
| US-654 | One-click Update — re-fetch all feeds, rebuild specific cells that depend on feeds (not full rebuild — targeted recompute). |
| US-655 | AppSource publish prep — manifest validation, privacy policy, support URL, test tenant. Submission to Microsoft review (allow 4-6 weeks). |

**v0.9 ship gate**: 5 new jurisdictions build clean workbooks; Excel add-in distributed to 3 external pilot users; FX roll works on one real cross-border deal; market-data lag ≤1 hour verified in production; no audit regression (still ≥95% PASS).

---

# Part 2 — v1.0 "Enterprise Hero" (10-12 weeks, Aug-Oct 2026)

**Goal**: Multi-tenant SaaS with deliverable export, regulatory reporting, AI co-pilot, data-room ingestion v2, and SOC 2 Type II + Big 4 attestation.

## Theme 2.A — Multi-tenant SaaS (3 weeks)

| ID | Story |
|---|---|
| US-700 | FastAPI + Next.js app in `modelforge/web/` extended: Auth (OIDC via Auth0 or WorkOS), tenant isolation (row-level PostgreSQL policies), workbook versioning (every build tagged with user + timestamp + spec hash), S3-compatible object storage for built XLSX + PDF dossiers. |
| US-701 | Spec-editor UI — YAML form with live validation (pydantic error messages inline), inline docs from `modelforge/spec/` docstrings, drag-drop PDF attach → linked to Source ID in spec. |
| US-702 | Build-and-browse UI — server builds workbook on submit; client renders via luckysheet or react-spreadsheet-grid; cells clickable → side-panel shows lineage. |
| US-703 | Lineage visual graph — cytoscape.js rendering of linkage graph SQLite; click cell → upstream / downstream walk; filters by sheet / driver type. |
| US-704 | Commenting + @mentions + review-approval workflow — like a PR for a model. Analyst submits, senior reviews, MD approves before "finalizing" a workbook (locks spec hash). |
| US-705 | Deal library + comp library — searchable by sector / country / year / EV / deal-type; one-click "add to comps" pulls multiples into new DCF/fairness workbook. |
| US-706 | Stripe billing — tiered seats per tenant + per-deal surcharge at Pro / Team tier; metered usage for Enterprise. |
| US-707 | PostgreSQL migration — move SQLite `.graph.db` + spec store to Postgres with multi-tenant row-level security. `alembic` migrations. |
| US-708 | Tenant admin UI — SSO provisioning (SCIM via WorkOS), role assignments (Admin / MD / Analyst / View-only), API key issuance, usage dashboard. |

## Theme 2.B — Deliverable export (2 weeks)

| ID | Story |
|---|---|
| US-720 | PPTX export via python-pptx: auto-generate IC deck with slides for exec summary, football field, LBO returns, credit covenants, sensitivity, QC. Templates per deal type (credit memo, LBO, PF, M&A, fairness). Branded via tenant logo + color scheme. |
| US-721 | Word export via python-docx: credit memo (Italian + English variants) with auto-filled deal summary, risk factors, covenant schedule, recommendation. Template per deal type. |
| US-722 | PDF dossier v2 — existing `modelforge/dossier/generator.py` enhanced: DCF waterfall chart, LBO returns attribution waterfall, PF DSCR curve chart, comp football field chart (matplotlib → embedded). |
| US-723 | Regulator filing pack — "how was this model built" PDF with: full spec dump, git hash, source-doc attestation (page-level citations), every formula with its linkage chain, QC report. Designed to satisfy auditor + regulator self-review under SOC 2 / Big 4 attestation. |
| US-724 | Branded export templates — Enterprise tier customization of PPTX/Word/PDF templates via `branding.yaml` per tenant. |

## Theme 2.C — Regulatory reporting (3 weeks)

| ID | Story |
|---|---|
| US-740 | AIFMD Annex IV output — from any credit / PF / NPL workbook, generate ESMA-mandated XML filing per ESMA Implementing Regulation. Sections: general (AIFM ID, AIF ID, reporting period, NAV), risk (exposures by asset type + country + currency), leverage (gross + commitment methods), liquidity (investor + portfolio), concentration (top-5 + top-10). |
| US-741 | Basel COREP templates — generate C 01.00 (OWN FUNDS), C 02.00 (OWN FUNDS REQUIREMENTS), C 08.01 (CREDIT RISK IRB) / C 13.00 (CREDIT RISK STANDARDISED) populated from NPL / SC / bank-book credit workbooks. XBRL output compatible with EBA DPM. |
| US-742 | Basel FINREP templates — F 01.01 (BALANCE SHEET), F 02.00 (P&L), F 18.00 (NON-PERFORMING EXPOSURES per ITS 2020/429). |
| US-743 | EBA risk dashboard feed — quarterly NPL ratio, Texas ratio, coverage ratio, concentration-risk indicators computed from NPL portfolio + output as CSV + chart for board-pack consumption. |
| US-744 | Banca d'Italia supervisory return (Matrice dei Conti / SegnalaRIO-equivalent) for AIF loans — Italian-specific credit register filing. |
| US-745 | FRTB standardized approach (SA) for market-risk capital — BCBS d457 full implementation: sensitivities (delta, vega, curvature), correlations per risk class (GIRR, CSR-NonSec, CSR-Sec, Equity, Commodity, FX), default risk charge, residual risk add-on. **Stretch** — ship as v1.1 if v1.0 scope full. |
| US-746 | Calendar provisioning (EU 2019/630) — NPE prudential backstop schedule: 3y for unsecured → 100% / 7y for secured → 100%. Auto-populate from NPL workbook origination dates. |

## Theme 2.D — AI co-pilot (2 weeks)

| ID | Story |
|---|---|
| US-760 | `modelforge chat` (already exists) v2: propose fixes — "DSCR low at Y3, would you like me to sculpt the amortization?" Patch spec in-place with user approval; rebuild workbook; show diff. |
| US-761 | Red-flag detection — LLM reads workbook + linkage graph output + source docs; flags anomalies via 20-rule ruleset: covenant headroom <10%, goodwill > market cap, exit multiple implies negative terminal g, debt cost < risk-free rate, industry beta outside 0.5-2.0 range, revenue growth inconsistent with sector, etc. Output as orange-annotated QC rows. |
| US-762 | Deal-comp search — given a new deal spec, query deal library for 5 most-similar historical deals (sector + country + year + size vector cosine similarity); explain differences in 3 sentences per comp. |
| US-763 | Narrative generator — given a workbook, generate executive summary in IT/EN/DE/FR/ES, 3 paragraphs, committee-tone. Uses workbook-derived facts + spec inputs; never hallucinates numbers. |
| US-764 | Peer-review simulator — LLM plays "Goldman MD" role and critiques model; returns 5-10 punch-list items ranked by severity. Output as Markdown for review. |
| US-765 | Model-memory — assumption drift agent (already scaffolded in `modelforge/drift/`) extended: rebuild last-known-good spec; diff current spec; flag drift with blast-radius analysis (which cells moved by >X%). |
| US-766 | Voice MD-review (stretch) — upload audio of verbal MD critique; Whisper transcribe; chat agent converts to punch-list items. |

## Theme 2.E — Data-room ingestion v2 (2 weeks)

| ID | Story |
|---|---|
| US-780 | OCR for scanned PDFs — `modelforge/ingest/readers/pdf_reader.py` extended with Tesseract fallback; if digital text extraction yields <10 words/page, invoke OCR. Alternative: Claude vision API for higher-accuracy OCR when budget permits. |
| US-781 | Cross-doc reconciliation — detect discrepancies: FY2024 revenue per CIM vs per FY24 audited statements vs per IC memo. Flag via new IngestionReconciliation sheet. |
| US-782 | Embedding-based retrieval — for data rooms >50 docs, chunk + embed (OpenAI ada or Anthropic embedding model if available); store in pgvector; retrieve top-k per query during ingestion. |
| US-783 | Intralinks / Datasite / Dealcloud API integrations — where partner APIs available, scan VDR directly via authenticated API. Ship as Enterprise-tier connector. |
| US-784 | Virtual data room UI — per-deal folder viewer in SaaS app; upload docs, auto-classify, tag to Source IDs. |
| US-785 | Financial-statements extractor — structured LLM-call prompt that returns P&L + BS + CFS in three JSON arrays from audited-statement PDFs; validate against accounting identities; surface inconsistencies. |

## Theme 2.F — Attestation & compliance (1 week orchestration; 3-month SOC 2 calendar)

| ID | Story |
|---|---|
| US-800 | SOC 2 Type II observation — via Sprinto (started 2026-05-18 per action plan); complete observation Q3 2026; report issued Q1 2027. Ongoing security-controls evidence capture automated. |
| US-801 | Big 4 independent attestation of deterministic-build property — "same spec + same code = same output". Engage PwC or KPMG Italy Q3 2026; scope: 5 representative spec→workbook builds, reproduced on clean environment; attestation letter by Q1 2027. |
| US-802 | ISO 27001 info security certification — for multi-tenant SaaS; 12-18 month program via BSI or DNV; kick off Q3 2026. |
| US-803 | GDPR / Italian Data Protection audit — client-data handling review via external counsel (BonelliErede or Chiomenti); produce DPIA; update ToS + DPA. |
| US-804 | Anthropic API EU residency verification — confirm data does not leave EU region for any LLM-powered ingestion / chat / co-pilot feature; document DPA signed with Anthropic. |

**v1.0 ship criteria**:
- Multi-tenant SaaS live with ≥2 paid pilot customers
- Excel add-in in production use for ≥5 external users
- AIFMD Annex IV output validated against ESMA schema for ≥1 real AIF
- Basel COREP / FINREP outputs cross-checked against ≥1 real bank internal process
- SOC 2 Type II observation complete (report pending issuance)
- Gold-standard audit ≥ **97%** PASS
- Overall weighted score: **9.65 / 10**

---

# Part 3 — v1.5+ Horizon (Q1 2027 → Q4 2027)

## v1.5 "APAC" (Q1 2027)

| ID | Story |
|---|---|
| US-900 | Singapore MAS jurisdiction — Securities and Futures Act, SFA Schedule, GST, 17% corp tax. |
| US-901 | Hong Kong SFC jurisdiction — Securities and Futures Ordinance, 16.5% profits tax. |
| US-902 | Japan FSA jurisdiction — JGAAP + IFRS dual, 30% effective corp tax, FIEA. |
| US-903 | CNY/JPY/SGD/HKD FX curves + CNH offshore. |
| US-904 | APAC market-data feeds — BOJ JGB curve, HK HIBOR, SG SORA. |
| US-905 | Asia-specific templates — Hong Kong pre-IPO PF structures, Japan REIT with TK-GK, Singapore S-REIT with stapled securities. |

## v1.6 "Market-Risk Stack" (Q2 2027)

| ID | Story |
|---|---|
| US-910 | FRTB SA full implementation (US-745 if not delivered in v1.0). |
| US-911 | CVA (credit valuation adjustment) computation — bilateral counterparty exposure; integrate with swap / bond portfolios. |
| US-912 | SA-CCR (standardized approach for counterparty credit risk) — BCBS d279. |
| US-913 | Economic capital model — internal VaR + tail-risk measures for credit portfolios (separate from regulatory RWA). |

## v1.7 "ESG / SFDR" (Q3 2027)

| ID | Story |
|---|---|
| US-920 | SFDR Article 8 / Article 9 pre-contractual + periodic disclosure outputs from any fund-level workbook. |
| US-921 | EU Taxonomy Regulation alignment computation — OpEx / CapEx / turnover KPIs per activity. |
| US-922 | GRI / SASB / TCFD output tabs. |
| US-923 | Carbon accounting — Scope 1/2/3 per portfolio company; weighted-avg carbon intensity roll-up for fund-level. |
| US-924 | PAI (Principal Adverse Impacts) statement — the 14 mandatory + opt-in indicators. |

## v2.0 "Marketplace" (Q4 2027)

| ID | Story |
|---|---|
| US-930 | Template marketplace — any user can publish a spec + optional custom sheet builder; 70/30 rev-share (author 70%). |
| US-931 | Template browser + search — filter by sector / geo / year / popularity. |
| US-932 | Template version control + backward compatibility policies. |
| US-933 | Community ratings + review workflow. |
| US-934 | Partner showcase — boutique banks / funds publish templates as thought-leadership. |

## v2.5 "Native integrations" (2028)

| ID | Story |
|---|---|
| US-940 | Bloomberg Terminal native connector — pull live quotes, comps, ratings. |
| US-941 | FactSet integration — comp sets, industry screens, estimates. |
| US-942 | Dealcloud / Intralinks / Datasite deeper integrations — deal-level sync of metadata. |
| US-943 | Salesforce / HubSpot — map ModelForge deal library to CRM pipeline. |

---

# Part 4 — Commercial tie-in (reference, not new stories)

The v1.0 PRD already specifies commercial tiering (Pro €499/mo → Team €2,499/mo → Enterprise €50-200K/yr → Bulge €500K-2M/yr) and revenue ramp (€100K ARR Q3 2026 → €3M Q4 2027). Story-level gates below:

**Commercial gate at v0.8.7 ship**: first boutique Italian credit fund pilot signed (€25-50K) — single-deal engagement to validate UX + deliverables.

**Commercial gate at v0.9 ship**: 2 foreign-investor Pro seats (London / Zurich / Frankfurt) active, paying for 30 days. Validates jurisdiction breadth commercially.

**Commercial gate at v1.0 ship**: 2 Enterprise pilots paying ≥€100K/yr; 1 Big-4 attestation engagement confirmed (not issued).

**Commercial gate at v2.0**: 10 active marketplace templates; first marketplace revenue €5K/mo run-rate; 3 published case studies.

---

# Part 5 — Technical debt & hygiene

Continuous work in parallel, no version-gate:

| ID | Story |
|---|---|
| US-950 | Pytest reaches 500+ tests by v1.0 (currently 430). Add integration tests per new template + per jurisdiction + per deliverable export format. Coverage ≥85% by v1.0. |
| US-951 | CI pipeline — GitHub Actions: lint (ruff), typecheck (mypy strict), pytest, gold-standard audit, build-time regression check (<5s per workbook). Block merges on red. |
| US-952 | Performance profiling — target <5s per workbook build, <30s per audit, <500ms per API call at p95. Profile hotspots per release. |
| US-953 | Documentation v2 — `docs/` currently has 7 files; expand to: 15-template cookbook, jurisdiction-switching guide, SaaS admin guide, API reference, linkage-graph guide. Hosted on mkdocs + GitHub Pages. |
| US-954 | Packaging + distribution — pip-installable `modelforge-cli`, Docker image for `modelforge serve`, conda-forge channel, Homebrew formula (Mac). |
| US-955 | Telemetry — opt-in anonymous usage reporting via posthog: which templates used, avg build time, error frequencies. Informs roadmap prioritization. |
| US-956 | Error-message UX — every pydantic validation failure returns user-actionable message with example; CLI `--hint` flag explains next step. |
| US-957 | Reproducibility CI — monthly reproducibility job: rebuild every pinned-git-hash published example workbook; assert byte-identical output. Alert on drift. |
| US-958 | Cost tracking — LLM spend per tenant attributable for Enterprise billing; per-tenant cost P&L in admin UI. |

---

# Risks & mitigations (additive to v1.0 PRD risk register)

### New risks in the missing-parts scope

1. **53 PARTIALs expand under deeper audit** — closing today's PARTIALs may surface tomorrow's. Mitigation: include 1 buffer week in v0.8.7.
2. **Jurisdiction tax-rule churn** — UK / DE / FR / ES / US rules change annually (e.g., Autumn Statement, Jahressteuergesetz, PLF, PGE, TCJA expirations). Mitigation: versioned jurisdiction snapshots (`jurisdictions/italy_2026.py`, `italy_2027.py`); user pins snapshot for reproducibility.
3. **AppSource review delays** (US-655) — Microsoft review times variable 4-12 weeks. Mitigation: start submission during v0.9 dev, not at ship.
4. **Regulatory reporting accuracy risk** — if ModelForge AIFMD / COREP output is wrong and client files it, ModelForge could be named. Mitigation: clear disclaimers in export, "pre-submission review by qualified person required" banner, Big 4 attestation as shared responsibility.
5. **SaaS operational risk** — downtime during paying-customer pilots. Mitigation: 99.5% SLA stated (not 99.9% until mature); status page; automated failover to last-known-good workbook snapshots.
6. **LLM cost inflation** — red-flag detection + narrative generator run on every workbook; at €0.015 / 1K tokens blended and ~50K tokens per review, €0.75/review × 500 reviews/month = €375/mo/tenant. Mitigation: cache common prompts; offer "LLM features" as Team+ tier upsell, not Pro.

---

# Decision gates — augmented from v1.0 PRD

**v0.8.7 gate (early May 2026)** — NEW:
- 53 PARTIALs → 0? Ship.
- `pytest -q` 100% clean? Ship.
- First Italian boutique pilot accepted engagement? Triggers BeBeez exclusive whitepaper (already scheduled for 2026-05-02 per action plan).

**v0.9 gate (Jul 2026)**: unchanged from v1.0 PRD — Excel add-in 3 external pilots + UK/DE/US jurisdiction working + FX on real cross-border deal.

**v1.0 gate (Oct 2026)**: unchanged — Multi-tenant SaaS ≥2 paid + SOC 2 observation complete + AIFMD Annex IV validated + gold std ≥95%.

**v1.5 gate (Q1 2027)**: ≥1 APAC paid customer (Singapore family-office OR Hong Kong PE fund).

**v2.0 gate (Q4 2027)**: ≥3 marketplace authors publishing ≥10 templates total; first author payout processed.

---

# Appendix A — Full PARTIAL inventory (v0.8.6 → v0.8.7 scope)

| Check # | Description | File count | Remediation story |
|---:|---|---:|---|
| #83 | Sensitivity via Data Table | 13 | US-500/501/502 |
| #87 | Macabacus AutoColor | 14 | US-505/506 |
| #102 | Basel securitization capital | 13 | US-510/511/512 |
| #99 | Legge 130/1999 SPV | 2 | US-515 |
| #53 | CFADS maint capex split | 2 | US-520 |
| #49 | Pro-forma credit metrics | 1 | US-525 |
| #9 | IFRS 16 lease treatment | 1 | US-530 |
| #10 | WACC target capital structure | 1 | US-531 |
| #15 | Size premium | 1 | US-532 |
| #16 | Company-specific alpha | 1 | US-533 |
| #24 | Financing fees capitalized | 1 | US-540 |
| #27 | Revolver + commitment fee | 1 | US-541 |
| #28 | Cash sweep step-down | 1 | US-542 |
| #80 | Named ranges fairness | 1 | US-545 |
| **Total** | | **53** | 18 stories cover all |

---

# Appendix B — v0.8 Theme residuals mapped to new stories

| v0.8 story | Status | New story in this PRD |
|---|---|---|
| US-242 O&M reserve funding | Deferred | US-560 |
| US-243 MMR sinking fund | Deferred | US-561 |
| US-245 equity cure iterative | Deferred | US-562 |
| US-246 make-whole on early redemption | Deferred | US-563 |
| US-247 real-vs-nominal QC | Deferred | US-564 |
| US-248 mandatory prepayment toggle | Deferred | US-565 |
| US-260 IFRS9ECL dedicated sheet | Deferred | US-566 |
| US-261 SICR trigger flags | Deferred | US-567 |
| US-262 forward-looking macro | Deferred | US-568 |
| US-263 POCI treatment | Deferred | US-569 |
| Sponsor LBO live compute polish | Deferred | US-570 |
| Sponsor LBO ingest curation | Deferred | US-575 |
| Sponsor LBO sensitivity list | Deferred | US-576 |
| Sponsor LBO reverse | Deferred | US-577 |
| Merger reverse classifier | Failing | US-550 |

---

# Appendix C — Effort estimate

| Version | Duration | Stories | Peak people | Calendar dates |
|---|---:|---:|---:|---|
| v0.8.7 polish | 1 week | 23 | 1 FTE (Luka) | 2026-05-01 → 2026-05-08 |
| v0.9 beyond Italy | 6-8 weeks | 37 | 1-2 FTE | 2026-05-15 → 2026-07-15 |
| v1.0 enterprise | 10-12 weeks | 52 | 2-3 FTE | 2026-07-15 → 2026-10-15 |
| v1.5 APAC | 6 weeks | 6 | 2 FTE | 2027-01-15 → 2027-03-01 |
| v1.6 market-risk | 6 weeks | 4 | 2 FTE | 2027-03-01 → 2027-04-15 |
| v1.7 ESG/SFDR | 6 weeks | 5 | 2 FTE | 2027-06-01 → 2027-07-15 |
| v2.0 marketplace | 8 weeks | 5 | 2 FTE | 2027-09-01 → 2027-11-01 |
| v2.5 integrations | 8 weeks | 4 | 2 FTE | 2028-02-01 → 2028-04-01 |
| **Total** | **~50 weeks** | **136 stories** | | 2026-05 → 2028-04 |

Assumes 1 primary owner (Luka) with surge capacity (contractors / partnerships) on v1.0 SaaS + SOC 2.

---

# Appendix D — Out-of-scope clarifications

Explicitly **not** included in this PRD (for future consideration):

- Mobile apps (iOS / Android) — not a target user segment for institutional modeling
- Excel Online / Google Sheets native builder — add-in is the Office-native experience; Sheets has too small an institutional footprint
- Real-time collaborative editing in built workbooks — Excel + OneDrive already provides this
- Generative text→workbook without a spec — architectural invariant (v0.1) requires deterministic spec; relax only if proven at customer scale
- Decentralized / crypto / DeFi modeling — not in core target market
- Agent-based autonomous "run the whole deal" — chat + co-pilot is the ceiling until v2.0+; full autonomy breaks deterministic invariant

---

# Appendix E — Source traceability

This PRD sources from:
- `WIP.md` (v0.8 session state 2026-04-22)
- `PRD_v10_world_class_hero.md` (2026-04-21 v1.0 master)
- `gold_standard_audit.py` output as of 2026-04-22 HEAD 713728e (369 PASS / 53 PARTIAL / 0 FAIL / 3 N/A)
- `GOLD_STANDARD_AUDIT_2026-04-21.md` (105-criterion checklist)
- `PRD_v07_bulge_tier_breadth.md` (48-story v0.7 source)
- `STRESS_TEST_REPORT_2026-04-21.md` (98-finding adversarial audit)
- `../freelance-edge/memory/competitor_landscape_2026q2.md` (v3 refresh)
- `../freelance-edge/memory/modelforge_action_plan_may2026.md` (30-day sprint)
- `../freelance-edge/memory/modelforge_v08_shipped.md` (v0.8 FINAL recap)

All file paths relative to `C:/Users/lukep/Desktop/Projects AI/ModelForge/`.

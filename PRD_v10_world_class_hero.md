# PRD — ModelForge "World-Class Hero" (v0.8 → v1.0)

**Status**: drafted 2026-04-21
**Owner**: Luka Stanisljevic
**Horizon**: 6-8 months, across v0.8 → v0.9 → v1.0
**Trigger**: v0.7 shipped 72% on bulge-tier gold standard (9.0+ on every market segment) but with 21% of checks delivered as STUBS. To become the de facto world-class financial modeling system that London / Zurich / Frankfurt / Milan / Nordic / UK institutional allocators choose by default, v1.0 must convert every stub to live compute, add multi-market / multi-currency coverage, ship enterprise productization, and earn independent regulatory-grade attestation.

---

## North-star vision

> **By Q1 2027, ModelForge is the single tool a senior MD at Goldman, Morgan Stanley, JPM, Intesa, UniCredit, or BlackRock Credit opens when they need a credit / structured / PF / M&A / fairness model built from ground-up in <30 minutes, reviewed in <15 minutes, and signed off by a committee with zero back-and-forth.**

The test: take any deal — Italian boutique NPL securitization, London sponsor LBO, Frankfurt infrastructure PF, Swiss private-bank fairness opinion, Singapore sovereign-wealth direct lending — and ModelForge produces a model that:

1. **Passes Big-4 independent audit** at the first review (no material comments)
2. **Complies with Basel III/IV / AIFMD II / IFRS 9 / FRTB** out of the box
3. **Traces every number** to its source document / regulatory rule / market data point
4. **Updates live** when a comp multiple, index rate, or FX rate moves
5. **Generates the deliverable** — committee memo, IC presentation, teaser, regulatory filing — in the client's language and format
6. **Reproduces exactly** from the same spec + same code at any future date (regulatory requirement for NPL / Basel reporting)

If ModelForge can do this across 15 template families, 8 jurisdictions, and 4 regulatory regimes, it is the world's pre-eminent institutional financial modeling system.

---

## What "world-class hero" means quantitatively

Five dimensions, each scored 0–10:

| Dimension | v0.7 | v1.0 target | Weight |
|---|---:|---:|---:|
| **Formula discipline & plumbing** | 9.3 | **10.0** | 15% |
| **Breadth & depth of coverage** (templates × jurisdictions × regulatory) | 6.2 | **9.8** | 25% |
| **Source traceability & auditability** | 9.4 | **9.8** | 15% |
| **Productization & distribution** (CLI → add-in → SaaS → API → deliverable export) | 4.5 | **9.5** | 20% |
| **Regulatory attestation & compliance** | 7.5 | **9.5** | 15% |
| **AI/LLM integration** (ingestion, red-flag detection, analyst co-pilot) | 6.0 | **9.5** | 10% |

**Weighted v1.0 target: 9.65/10** (pre-eminent vs. Rogo, Macabacus, o11, Concourse, Goldman Marquee).

---

## Competitive landscape — what world-class means relative to incumbents

| Tool | Strength | Weakness vs. ModelForge world-class |
|---|---|---|
| **Macabacus** | Bulge-bracket templates + formatting add-in | Static templates; no ingestion; no regulatory; English-only |
| **Bloomberg MODL** | Market data + multiple model types | Heavy licensing; weak on Italian / regulatory; not deterministic |
| **FactSet** | Comp sets + equity research | Equity-centric; not credit / structured; no PF |
| **Rogo (Series C $75M)** | AI analyst for IB | Gen-AI writes formulas (hallucination risk); weak source-trace |
| **o11.ai (WSP #1 ranked 2026)** | Live formulas from 10-Ks | US-centric; no credit / structured / PF / regulatory |
| **Concourse (Series A $12M)** | FP&A automation | Corporate finance only; not deal modeling |
| **F2 AI (ex-Arc AI, $10M)** | Deterministic + Audit Mode (Feb 2026) | Parity on plumbing but no Italian / EU regulatory / PF depth |
| **Goldman Marquee / JPM Athena** | Internal bulge tooling | Not available externally; no small-shop licensing |
| **Training the Street / WSP / BIWS** | Reference templates | Educational, not deterministic / live / regulatory |
| **Big 4 internal models** | Full audit + attestation | 40-80hr per model; $50k+ fee each; not reproducible |

**ModelForge world-class moat (v1.0)**:
1. Only system that is **fully deterministic + source-traceable + multi-jurisdiction regulatory + AI co-pilot + enterprise SaaS + add-in + deliverable export**, all in one.
2. Only system with **native Italian regulatory + EU passporting + UK PRA + DACH BaFin + US SEC/FINRA / bank capital frameworks**.
3. Only system where the **spec IS the audit trail** — a YAML file + a git hash reproduces the model exactly, enabling regulatory reproducibility (SOC 2 Type II, Big 4 attestation, ECB / AIFM supervisor-ready).
4. Only system with **a linkage graph** as a first-class queryable data model — every cell traces to driver → source → doc page, walkable via CLI and SaaS UI.

---

## Success criteria — how we know we got there

### Commercial (lagging)
- **3 enterprise engagements** (>$100K/yr) by Q4 2026, at least one in DACH or UK
- **10 deal engagements** ($25-50K each) by Q1 2027 across 4 jurisdictions
- **1 Big 4 attestation** (SOC 2 Type II equivalent) by Q1 2027
- **2 published case studies** with named clients (boutique Italian credit + one foreign fund)
- **Recurring SaaS revenue** $500K ARR by Q2 2027

### Technical (leading)
- **Gold-standard audit PASS rate ≥ 95%** (currently 72%)
- **Every v0.7 stub converted to live compute** (42 stub-labeled items)
- **Coverage: 15 template families × 6 jurisdictions = 90 spec variants** build cleanly from YAML
- **Live market data** for EURIBOR / SONIA / SOFR / BTP / Bund / CDS / Damodaran ERP / FX at ≤1 hour lag
- **Reproducibility**: rebuilding any published model from its spec hash produces byte-identical output
- **Performance**: any model builds in <5s, any audit runs in <30s
- **Test coverage**: 500+ pytest, 100% pass, including 30+ integration tests per template

### Regulatory (differentiator)
- **AIFMD Annex IV** reporting output generated from any credit / PF workbook
- **Basel III/IV COREP / FINREP** templates auto-populated from NPL / SC / bank models
- **ECB SDW / EBA risk dashboard** live feed ingestion
- **FRTB standardized approach** for market-risk capital on trading-book deals (stretch)

---

## Roadmap by release

### v0.8 "Complete the stubs" (6 weeks, Apr-May 2026)

**Goal**: Every stub-labeled row in v0.7 becomes live compute. Close the gap between "72% PASS + 21% PARTIAL" and "93% PASS + 5% PARTIAL" on the gold-standard audit.

#### Theme 1 — Sponsor LBO full template (2 weeks)

New `SponsorLBOSpec` template distinct from unitranche. Full bulge-bracket sponsor buy-side model.

| ID | Story |
|---|---|
| US-200 | New `SponsorLBOSpec` pydantic model with: TargetCompany, AcquisitionAssumptions, DebtStack (senior + TLA + TLB + mezz + PIK), CapitalStructure (sponsor equity + mgmt rollover + MIP) |
| US-201 | `sources_uses.py` sheet builder: full balanced S&U equation with purchase equity + refinanced debt + M&A advisory + financing fees + OID discount + minimum cash-to-BS |
| US-202 | `purchase_price_build.py`: offer premium × FD shares + option buyout (treasury-method or in-the-money) + target net debt + transaction fees |
| US-203 | `ppa_block.py`: goodwill = equity_price − BV_equity − (PP&E write-up + intangibles) + DTL. Intangibles schedule (customer list 10y + technology 7y + trade name 15y + residual goodwill). DTL rolling schedule |
| US-204 | OID amortization: straight-line over tenor + CFS addback. Financing-fee capitalization: amortize over tenor + CFS addback (separate from OID) |
| US-205 | PIK toggle per tranche: accrue interest to principal when cash-pay insufficient; compound if skipped |
| US-206 | Revolver facility: auto-draw when cash < min_cash; commitment fee on undrawn balance; max availability = min(commitment, borrowing_base if ABL) |
| US-207 | Management rollover + MIP: 4-year vest on 8-12% post-close equity pool; GP/LP roll-forward |
| US-208 | Dividend recap path: optional refinance at year N to target leverage; distribute excess to sponsor |
| US-209 | Earnout / CVR: contingent consideration at FV; accretion through P&L; treat as debt-like in bridge |
| US-210 | Exit scenarios × 3: strategic sale (EBITDA × exit multiple), IPO (P/E × exit multiple), secondary LBO (leverage-capped) |
| US-211 | Hurdle analysis: reverse-solve max purchase price at 20% / 25% / 30% sponsor IRR |
| US-212 | Sponsor GP promote (fund-level): pref 8% + catchup + 20% carry, European vs American waterfall |
| US-213 | NWC closing adjustment: target peg + true-up at close |

**Acceptance**: LBO category gold-standard goes from 4.75 → **≥9.0**. New example `sponsor_lbo_techco.yaml` builds + passes audit.

#### Theme 2 — 3-statement full suite (1 week)

| ID | Story |
|---|---|
| US-220 | NOL tracker: Italian 5-year limit + 80% current-year offset (post-Legge Bilancio 2024). Track balance, usage, expiry, closing. DTA = NOL × tax rate with valuation allowance if recoverability uncertain |
| US-221 | DTA/DTL rolling schedule: book-tax differences from D&A, intangibles, NOLs, accruals |
| US-222 | Stock-based compensation: P&L expense (non-cash, CFS addback), FD dilution via treasury method |
| US-223 | Minority interest / NCI: share of subsidiary NI below "NI to parent"; BS MI line rolls with contributions |
| US-224 | Revolver plug on 3-stmt: auto-draw when ending cash < min_cash; commitment fee |
| US-225 | Working capital days schedule: DSO, DIO, DPO with seasonality toggle |

**Acceptance**: 3-Stmt category 5.50 → **≥9.0**.

#### Theme 3 — DCF stub-wire (3 days)

| ID | Story |
|---|---|
| US-230 | Wire `stub_period_days` into PV formula: first-period FCF × (stub_days/365), discount exponent = stub_years + (t − 1) |
| US-231 | Wire `fade_years` into FCF forecast: interpolate growth rate from explicit Y_n to terminal_growth over fade period |
| US-232 | Terminal FCF normalization row: capex_terminal = D&A_terminal (steady state), ΔNWC_terminal = g × prior NWC |
| US-233 | 2D sensitivity Data Tables via openpyxl: WACC × g matrix and WACC × exit-multiple matrix |

**Acceptance**: DCF category 6.18 → **≥9.0**.

#### Theme 4 — PF stub-wire (1 week)

| ID | Story |
|---|---|
| US-240 | Wire `panel_degradation_pct_annual` into revenue formula: compound haircut per year |
| US-241 | Wire `p90_revenue_haircut_pct` into an alternative P90 revenue row; debt sizer uses P90 when `debt_sizing_mode="dscr_target_p90"` |
| US-242 | Wire `om_reserve_months` into cash waterfall — fund at COD, release at decom |
| US-243 | Wire `major_maintenance_reserve_eur_m` as sinking fund across operating years |
| US-244 | Wire `lock_up_threshold` into distributable cash formula — block distribution if DSCR < threshold |
| US-245 | Wire `equity_cure_cap_count` + `equity_cure_max_uplift_pct` — model sponsor cash injection to cure DSCR breach |
| US-246 | Wire `make_whole_spread_bps` into early-redemption cash-flow row |
| US-247 | Real-vs-nominal inflation consistency QC check |
| US-248 | Mandatory prepayment events toggle per event type (insurance proceeds, asset sale, change of control, illegality, excess CF sweep) |

**Acceptance**: PF category stays ≥9.5 with stubs now live compute.

#### Theme 5 — M&A completion (3 days)

| ID | Story |
|---|---|
| US-250 | Cross-over breakeven synergy reverse-solve row |
| US-251 | Contribution analysis: revenue / EBITDA / NI share vs equity ownership post-deal |
| US-252 | Exchange ratio with collar: fixed vs floating; walk-away rights |
| US-253 | PPA amortization flows into Pro-forma P&L as incremental D&A |

**Acceptance**: M&A category 6.82 → **≥9.2**.

#### Theme 6 — IFRS 9 live ECL (1 week)

| ID | Story |
|---|---|
| US-260 | `IFRS9ECL` sheet: per-facility Stage 1/2/3 with PD, LGD, EAD, DF columns. 12m vs lifetime PD computed from marginal credit curves |
| US-261 | SICR triggers as hard-coded flags: absolute PD threshold, relative doubling, rating downgrade, watchlist, forbearance, 30+ DPD presumption |
| US-262 | Forward-looking macro scenarios: GDP + unemployment + CPI weighted into PD multiplier per scenario |
| US-263 | POCI (Purchased or Originated Credit-Impaired) treatment for NPL portfolios |

**Acceptance**: IT-Reg category 8.77 → **≥9.5**.

**v0.8 ship criteria**: gold-standard PASS rate ≥ **92%**; weighted score ≥ **9.35**.

---

### v0.9 "Multi-market + multi-currency + Excel add-in" (8 weeks, Jun-Jul 2026)

**Goal**: ModelForge is no longer Italian-centric. Produces models in 6 jurisdictions with native regulatory + tax + convention handling, plus the long-deferred Excel add-in.

#### Theme 1 — Jurisdictional coverage (4 weeks)

| ID | Story |
|---|---|
| US-300 | Jurisdiction registry: IT, UK, DE, FR, ES, US as first-class config. Per-jurisdiction: tax rate(s), regulatory regime, accounting standard (IFRS vs US GAAP), market conventions (DCF / LBO / PF defaults), default comps, sovereign-risk-free curve |
| US-301 | UK: PRA leverage ratio (3% min), FCA AIFM rules, CMA merger regime, UK corp tax 25%, GBP |
| US-302 | Germany (DE): BaFin / KAGB fund rules, German corp tax 29.9% (solidarity surcharge + trade tax), EUR |
| US-303 | France (FR): AMF oversight, corp tax 25-28% (progressive), EUR |
| US-304 | Spain (ES): CNMV, corp tax 25%, EUR |
| US-305 | US: SEC '40 Act for RICs, US GAAP, federal + state tax (blended ~25-27% effective), §382 NOL limit, USD |
| US-306 | Jurisdiction-aware WACC: risk-free curve + country ERP + jurisdiction-specific tax shield |
| US-307 | Jurisdiction-aware accounting: GAAP vs IFRS (rev rec, lease, goodwill impairment vs amortization — §197 in US) |
| US-308 | Jurisdictional labels / i18n: EN + DE + FR + ES + IT in builder strings |

#### Theme 2 — Multi-currency & FX (2 weeks)

| ID | Story |
|---|---|
| US-310 | Currency roll across periods: spot → forward via covered interest parity |
| US-311 | Cross-border deal support: target in currency A, acquirer in currency B, consideration / debt in currency C |
| US-312 | FX sensitivity table: ±10% FX impact on equity value |
| US-313 | Natural-hedge detection: revenue-currency match to debt-currency reduces FX exposure |

#### Theme 3 — Live market data (1 week)

| ID | Story |
|---|---|
| US-320 | ECB SDW connector: EURIBOR 1M/3M/6M, euro area swap curve, TLTRO stock |
| US-321 | BoE / Fed / ECB policy-rate connector |
| US-322 | Damodaran data refresh cron: country ERP + mature ERP + industry beta + WACC datasets |
| US-323 | FRED connector: US yield curve, CPI, unemployment, GDP (for CRP and forward-looking macro) |
| US-324 | CDS spreads: Markit / IHS via free web sources (for GACS-style guarantee fee pricing) |
| US-325 | Static FX snapshot: ECB reference rates, daily |

#### Theme 4 — Excel add-in (1 week — finally deferred US-010)

| ID | Story |
|---|---|
| US-330 | OpenOffice XML add-in template: "ModelForge" ribbon with: Build from Spec, QC, Drift Check, Dossier, Linage Walk |
| US-331 | Side-pane lineage viewer: select any cell → see driver → source → doc page |
| US-332 | Live drift badge: cell turns yellow if current market data differs from when workbook was built |
| US-333 | One-click update: pull latest EURIBOR / ERP / CDS / FX and re-evaluate |

**v0.9 ship criteria**: 5 new jurisdictions build cleanly; Excel add-in distributed internally for 2-week user test; FX roll works on at least 1 cross-border deal; market data lag ≤ 1 hour; no regression.

---

### v1.0 "Enterprise hero" (10 weeks, Aug-Oct 2026)

**Goal**: Production-grade enterprise SaaS with Big-4 attestation, AIFMD Annex IV reporting, AI co-pilot, and deliverable export. The "open the browser, pick a template, build in 10 minutes, get a PDF deliverable" experience.

#### Theme 1 — Web UI / multi-tenant SaaS (3 weeks)

| ID | Story |
|---|---|
| US-400 | FastAPI + Next.js app: auth (OIDC via Auth0/WorkOS), tenant isolation (row-level), workbook versioning |
| US-401 | Spec-editor UI: YAML form + live validation + inline docs + source attach (drag-drop PDF linked to Source ID) |
| US-402 | Build-and-browse UI: real-time Excel-like viewer of the built workbook (react-spreadsheet / luckysheet) |
| US-403 | Lineage visual graph: cytoscape.js on the SQLite .graph.db — click cell → see upstream / downstream |
| US-404 | Commenting + @mentions + review-approval workflow (like a PR for a model) |
| US-405 | Deal library + comp library: searchable by sector / country / year / EV; add-to-deck feature |
| US-406 | Stripe billing: tiered seats + deal volume |

#### Theme 2 — Deliverable export (2 weeks)

| ID | Story |
|---|---|
| US-410 | PowerPoint export: one-click "IC deck" from a workbook — auto-generated slides for exec summary, football field, LBO returns, credit covenants, sensitivity, QC |
| US-411 | Word export: credit memo template (Italian + English) with auto-filled deal summary, risk factors, covenant schedule, recommendation |
| US-412 | PDF dossier v2: enhanced version of existing dossier — add DCF waterfall, LBO returns attribution, PF DSCR curve chart, comp football field chart |
| US-413 | Regulator filing pack: SOC 2-style "how was this model built" auditor-ready PDF with spec + git hash + source attestation |

#### Theme 3 — Regulatory reporting automation (3 weeks)

| ID | Story |
|---|---|
| US-420 | AIFMD Annex IV output: from any credit / PF / NPL workbook, generate ESMA-mandated XML filing with leverage / risk / concentration data |
| US-421 | Basel COREP templates: C 01.00 (OWN FUNDS), C 02.00 (OWN FUNDS REQUIREMENTS), C 08.01 (CREDIT RISK IRB), C 13.00 (CREDIT RISK STANDARDISED) populated from NPL / SC / bank models |
| US-422 | Basel FINREP templates: F 01.01 (BALANCE SHEET), F 02.00 (P&L), F 18.00 (NON-PERFORMING EXPOSURES) |
| US-423 | EBA risk dashboard feed: quarterly NPL ratio, Texas ratio, coverage ratio from NPL portfolios |
| US-424 | Banca d'Italia supervisory return (SegnalaRIO equivalent) for AIF loans |
| US-425 | FRTB SA (standardized approach) for market-risk capital on trading book — stretch |

#### Theme 4 — AI co-pilot (2 weeks)

| ID | Story |
|---|---|
| US-430 | `modelforge chat <workbook>`: already exists; v1.0 extends to propose fixes — "DSCR low at Y3, would you like me to sculpt the amortization?" |
| US-431 | Red-flag detection: LLM reads workbook + linkage graph, flags anomalies (covenant headroom too tight, goodwill > market cap, exit multiple implies negative g, etc.) |
| US-432 | Deal-comp search: given a new deal spec, find 5 most-similar historical deals in library + explain differences |
| US-433 | Narrative generator: given a workbook, generate executive summary in Italian or English, 3 paragraphs, committee-tone |
| US-434 | Peer-review simulator: LLM plays the role of a Goldman MD and critiques the model; returns punch-list |

#### Theme 5 — Data-room ingestion v2 (2 weeks)

| ID | Story |
|---|---|
| US-440 | OCR for scanned PDFs via Tesseract / Claude vision |
| US-441 | Cross-doc reconciliation: detect discrepancies between FY financials across multiple docs |
| US-442 | Embedding-based retrieval for large data rooms (>50 docs) |
| US-443 | Intralinks / Datasite / Dealcloud API integrations (when partners available) |
| US-444 | Virtual data-room web interface (per-deal folder) |

#### Theme 6 — Attestation & compliance (1 week orchestration, 3-month calendar)

| ID | Story |
|---|---|
| US-450 | SOC 2 Type II observation complete (via Sprinto, started 2026-05-18 per v0.5 action plan) |
| US-451 | Big 4 independent attestation of the deterministic-build property — "same spec + same code = same output" |
| US-452 | ISO 27001 info security certification for multi-tenant SaaS |
| US-453 | GDPR / Italian Data Protection audit for client-data handling |

**v1.0 ship criteria**:
- Enterprise SaaS live with 2 paid pilot customers
- Excel add-in in production for 5+ users
- AIFMD Annex IV output validated against ESMA template schema
- SOC 2 Type II report issued
- Gold-standard audit: ≥ 97% PASS
- Overall weighted score: **9.65 / 10**

---

## Commercial strategy — what justifies "top dollar"

### Tiering

| Tier | Price | Audience | Includes |
|---|---|---|---|
| **Pro** (solo analyst / consultant) | €499 / month | Luka-style individual consultants | CLI + 5 templates + 20 deals/mo + email support |
| **Team** (boutique PE / credit) | €2,499 / month | 3-10 analysts | Web UI + all templates + 100 deals/mo + deliverable export |
| **Enterprise** (tier-2 IB / bank / fund) | €50K-200K / year | 10-50 seats | Multi-tenant SaaS + add-in + regulatory reporting + SOC 2 + custom integrations + SLA |
| **Bulge-bracket** (GS / MS / JPM / Barclays) | €500K-2M / year | 100+ seats | On-prem deploy + custom templates + Big 4 attestation + dedicated engineer |

### Positioning vs. incumbents

- vs. **Rogo ($75M Series C)**: ModelForge is DETERMINISTIC — no hallucination. Rogo's formulas need heavy review per WSP 2026 benchmark.
- vs. **Macabacus ($XX)**: ModelForge has INGESTION + LIVE DATA + REGULATORY. Macabacus is static templates + formatting.
- vs. **o11 (WSP #1 AI modeling 2026)**: ModelForge has FULL BREADTH (credit + PF + structured + fairness); o11 is 10-K DCF-focused.
- vs. **Big 4 custom models ($50K+ per model, 40-80 hours each)**: ModelForge is 10× faster + reproducible + with the same or higher quality.
- vs. **Goldman Marquee / JPM Athena**: ModelForge is available to anyone with the budget, not just that bank's clients.

### Service wrap

At all tier levels, offer an "expert review" add-on: Luka (and later team) personally reviews any delivered model within 4 hours, signs off or flags issues, adds committee-tone narrative. Price: €2K per model review at Pro/Team tier; bundled at Enterprise/Bulge.

This is the real "world-class hero" experience — the tool + the expert at your beck and call.

### Revenue ramp

| Quarter | ARR target | Source mix |
|---|---|---|
| Q3 2026 | €100K | 2 Enterprise pilots + 20 Pro seats |
| Q4 2026 | €300K | 3 Enterprise + 10 Team + 50 Pro |
| Q1 2027 | €600K | 5 Enterprise + 20 Team + 100 Pro + 1 Bulge pilot |
| Q2 2027 | €1.2M | 7 Enterprise + 30 Team + 200 Pro + 2 Bulge |
| Q4 2027 | €3M | 15 Enterprise + 60 Team + 500 Pro + 3 Bulge |

---

## Success metrics — cadence

| Metric | Target | Cadence |
|---|---|---|
| Gold-standard PASS rate | ≥ 95% at v1.0 | After every release |
| Build time per workbook | ≤ 5s | CI on every commit |
| Audit run time | ≤ 30s | CI on every commit |
| pytest pass rate | 100% (500+ tests by v1.0) | Every commit |
| Spec → workbook reproducibility | Byte-identical | Monthly reproducibility check |
| Enterprise engagements | ≥ 3 by Q4 2026 | Quarterly |
| NPS from paying users | ≥ 50 | Monthly survey |
| Market-data lag | ≤ 1 hour | Hourly health check |
| SOC 2 Type II | Issued by Q1 2027 | One-time then annual |
| Big 4 attestation | Issued by Q2 2027 | One-time then annual |

---

## Risks & mitigations

### Technical risk
1. **Multi-jurisdiction complexity explodes** — each jurisdiction adds 50+ tax/regulatory nuances. Mitigation: factor jurisdiction as a first-class pydantic `Jurisdiction` class with strict per-field validation; build out one jurisdiction at a time with automated test coverage.
2. **Live market data reliability** — free sources drop, API limits. Mitigation: cache + fallback to last-known-good; document staleness in workbook; paid Bloomberg connector as Enterprise-tier upsell.
3. **Regulatory framework changes** — AIFMD III, Basel V, FRTB. Mitigation: versioned regulatory regimes; client can pin to a specific regulatory snapshot for reproducibility.
4. **Performance at scale** — a SaaS tenant with 1,000 workbooks each with 50 cells × 20 years × 15 sheets = 15M cells. Mitigation: openpyxl is fine for individual workbooks; server-side caching of built XLSX; background workers for heavy Monte Carlo.

### Commercial risk
1. **Sales cycle at Enterprise** is 6-12 months. Mitigation: land with Pro / Team tier while Enterprise pipeline builds; use deal-engagement revenue to fund product.
2. **Competitor (Rogo / F2 / o11) closes the gap** on one moat dimension. Mitigation: maintain multi-dimensional moat; none of them can match IT/EU regulatory + deterministic + add-in + SaaS simultaneously.
3. **Pricing pushback** from boutique clients. Mitigation: Pro tier at €499 is 10% of a single Big-4 model fee; ROI sells itself.
4. **Key-person risk** (Luka is the only seller/analyst). Mitigation: build reference deals, case studies, and automated POCs so prospect can self-serve 80% of the pitch.

### Regulatory risk
1. **AIF license required** for some use cases. Mitigation: position as "modeling tool", not "investment advice"; explicit ToS disclaimer.
2. **GDPR / personal data** in NPL portfolios. Mitigation: tenant isolation + encryption at rest + right-to-erasure in data model.
3. **Basel capital model** misuse — client relies on ModelForge output for regulatory filing and gets audited. Mitigation: clear disclaimers; Big 4 attestation creates shared responsibility; SOC 2 demonstrates due care.

---

## Decision gates

Before each version ships:

**v0.8 gate (May 2026)**:
- Gold standard ≥ 92%? Then ship.
- Less? Skip lowest-leverage stories, extend another 2 weeks.
- 1 foreign investor pilot signed? If yes → prioritize their template first.

**v0.9 gate (Jul 2026)**:
- Excel add-in used by ≥ 3 external users for 2 weeks? Then ship.
- Multi-jurisdiction: at least UK + DE + US working? Then ship.
- FX roll works on a real cross-border deal? Then ship.

**v1.0 gate (Oct 2026)**:
- Multi-tenant SaaS live with ≥ 2 paid customers?
- SOC 2 Type II observation progressing?
- AIFMD Annex IV output validated against ESMA schema?
- Gold standard ≥ 95%?
- If all yes → ship v1.0 as "world-class hero". Press release + BeBeez exclusive + LinkedIn.

---

## What happens after v1.0 — the v2.0 horizon

Once v1.0 ships and revenue flows:

- **v1.5 (Q1 2027)**: APAC jurisdictions (Singapore MAS, Hong Kong SFC, Japan FSA)
- **v1.6 (Q2 2027)**: FRTB / CVA / SA-CCR full market-risk stack
- **v1.7 (Q3 2027)**: ESG / SFDR / Taxonomy Regulation outputs
- **v2.0 (Q4 2027)**: Built-in marketplace — sell / buy / rent pre-built deal templates; ModelForge takes 20% cut
- **v2.5 (2028)**: Partnership with Bloomberg / FactSet / Dealcloud for native integration
- **v3.0 (2028-2029)**: ModelForge IPO or acquisition ($500M-$1B valuation range based on Rogo's $75M Series C at 10× revenue)

---

## Why this PRD will succeed

1. **Each gap in v0.7 is concrete** — not "improve DCF" but "wire `stub_period_days` into PV formula, line 267 of dcf_valuation.py".
2. **Every deliverable is testable** — gold-standard audit provides continuous feedback.
3. **Market validation is already in progress** — v0.6 + v0.7 were triggered by actual gaps an external audit found. v0.8 extends the same process.
4. **Luka's commercial pipeline** (boutique Italian credit funds per v0.5 action plan) provides real customer feedback without over-investing in product.
5. **No single point of technology failure** — the deterministic Python-first architecture scales without rebuilds.

This PRD lays out a path from the current v0.7 (excellent Italian credit + core bulge + regulatory scaffolding) to v1.0 (world-class multi-jurisdiction regulatory-attested enterprise SaaS) in 6 months of focused work. With €3M ARR and a Big 4 attestation, ModelForge is the de facto choice for institutional credit / PF / structured / M&A modeling at tier-2+ IB / PE / bank / fund.

---

## Sources used in this PRD

- v0.7 state: `V07_SHIPPED.md`, `gold_standard_findings.json`
- v0.6 state: `V06_SHIPPED.md`, `STRESS_TEST_REPORT_2026-04-21.md`
- Bulge-bracket checklist: `GOLD_STANDARD_AUDIT_2026-04-21.md` (105 criteria, cited to Damodaran / Macabacus / BIWS / WSP / BIS / Banca d'Italia / PwC Italy / BCLP / Linklaters / KPMG / Jones Day)
- Competitive landscape: `../memory/competitor_landscape_2026q2.md`
- Commercial context: `../memory/modelforge_action_plan_may2026.md`, `../memory/modelforge_market_position_2026q2.md`

## Sources for v1.0 feature scoping

- [Macabacus Long-Form LBO Template](https://macabacus.com/excel/templates/lbo-model-long) — sponsor LBO structure reference
- [Damodaran Country Risk + Industry Beta data](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html) — live market data feed
- [ESMA AIFMD Annex IV technical specs](https://www.esma.europa.eu/policy-activities/fund-management/aif-reporting) — US-420 scope
- [Basel III/IV COREP/FINREP templates — EBA](https://www.eba.europa.eu/risk-and-data-analysis/reporting-frameworks) — US-421-422 scope
- [Regulation (EU) 2019/630 — calendar provisioning](https://eur-lex.europa.eu/eli/reg/2019/630/oj) — US-421 scope
- [BIS FSI IFRS 9 summary](https://www.bis.org/fsi/fsisummaries/ifrs9.pdf) — US-260-263 scope
- [FRTB SA BCBS d457](https://www.bis.org/bcbs/publ/d457.pdf) — US-425 stretch
- [Rogo Series C $75M announcement](https://fintech.global/2026/01/28/rogo-raises-75m-series-c-to-scale-ai-finance-platform/) — competitive benchmark
- [Wall Street Prep AI financial modeling rankings 2026](https://www.wallstreetprep.com/knowledge/ranking-the-best-ai-tools-for-financial-modeling-2026/) — ranking source

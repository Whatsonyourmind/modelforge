# PRD: ModelForge v0.4 → v1.0 — "#1 in the World" SOTA Track

**Status:** Draft, 2026-04-17
**Owner:** Luka Stanisljevic
**Horizon:** 6 months (v0.4 ships ~6 weeks; v1.0 ships ~24 weeks)
**Strategic intent:** Move ModelForge from credible niche tool (8.3/10 weighted SOTA, behind Italian bulge specialist 9.4) to the **defensible #1 modelling platform for finance professionals globally**, with three structural moats Rogo and Macabacus cannot copy: source-traced live formulas, regulator-grade audit dossier, and model-memory + reverse-engineering agents.

---

## 1. Introduction / Overview

ModelForge today is a CLI that emits bulge-tier Excel workbooks with every cell live-formulated and every number traceable to a data-room page. v0.3 closed the two biggest commercial gaps (PF sculpted amortization and project-finance data-room ingestion). It is now production-usable for Luka's freelance bridge but **not yet indispensable** to a typical finance professional, and not yet defensible against Rogo's distribution moat (Series C, 25k users, GPT-5 + Gemini 3 stack, Offset model-memory agents).

This PRD specifies the work to:

1. **Close every remaining quality gap** versus the Italian bulge specialist baseline (9.4 → ModelForge ≥ 9.5).
2. **Open three structural moats** Rogo cannot replicate without rewriting their architecture: (a) regulator-grade audit dossier export, (b) competitor-model reverse-engineering, (c) probabilistic credit engine with backtested IFRS 9 ECL.
3. **Live where finance professionals work** with an Excel add-in (Macabacus's distribution territory) plus a web SaaS thin layer for committee sharing (Rogo's territory).
4. **Become enterprise-ready** with SOC 2 Type II, SAML/SSO, multi-tenancy, and an on-prem option for banks.
5. **Globalize** beyond Italian credit — US (EDGAR / 10-K/Q ingest), UK (PRA), and APAC packs — without losing the Italian niche advantage.
6. **Add an agentic and marketplace layer** — data-room watcher agents, voice MD-review mode, and a template marketplace with revenue share — to create network and switching-cost moats.

Target: **9.6 / 10 weighted SOTA** by v1.0, top-1 across 22 of 25 scorecard criteria.

---

## 2. Goals

### Quality
- Reach 9.5+ weighted SOTA score by v0.4; 9.6+ by v1.0
- All 8 existing templates rated ≥ 9/10 on bulge-bracket criteria
- Three new templates (M&A merger, DCF-WACC, fairness opinion) shipped at ≥ 9/10
- Data-room ingestion criterion: 7/10 → 9/10 (all 8 templates + OCR)
- Sensitivity / Monte Carlo criterion: 5/10 → 9/10
- Probabilistic credit / IFRS 9 ECL criterion: 6/10 → 10/10 (new SOTA)

### Distribution
- Excel add-in published to Microsoft AppSource by v0.5
- Web app live at modelforge.app by v0.5; SOC 2 Type II audit complete by v1.0
- 50 paying seats by v0.5; 200 by v1.0
- 5 design-partner banks/funds by v1.0 (target: 1 boutique credit fund, 1 mid-market PE, 1 BB credit desk pilot, 1 EU regulator-facing infra fund, 1 Italian rating agency)

### Defensibility
- Audit dossier export is the only product on the market that produces a regulator-ready PDF where every number traces to a data-room page (verified by external counsel review)
- Model reverse-engineer correctly extracts spec from a public Macabacus / Wall Street Prep template with ≥ 90% formula coverage
- Template marketplace launches with ≥ 50 community templates by v1.0

### Commercial
- Per-engagement pricing supports €15-25k average (vs €5-10k pre-v0.4)
- Enterprise contracts: 3 signed at €100k+/yr by v1.0
- Italian rating agency adopts audit dossier as "preferred format" (qualitative goal)

---

## 3. User Stories

User stories are grouped by release. Each is sized to one focused session unless explicitly marked "epic" (multi-session).

### Release v0.4 — "SOTA parity" (Weeks 1-6)

**Goal:** Close every remaining v0.3 roadmap item, ship Excel add-in MVP and audit dossier export. Scorecard target: 9.5/10.

#### US-001: Sensitivity tornado on every template
**Description:** As a credit analyst, I want a one-click tornado chart on revenue ±20%, margin ±300bps, EUR rate ±100bps so I can present sensitivity to committee.
**Acceptance Criteria:**
- [ ] `SensitivityAnalysis` sheet generated for all 8 templates
- [ ] 6 factors swept at ±low / ±high; output IRR or DSCR delta
- [ ] Tornado chart rendered as native Excel chart (not image)
- [ ] Sensitivity factors driven by named ranges on Assumptions sheet
- [ ] QC gate passes 8/8

#### US-002: Monte Carlo simulation on IRR / DSCR
**Description:** As a fund manager, I want a 1000-run Monte Carlo distribution on the deal IRR so I can quote P5/P50/P95 in IC memos.
**Acceptance Criteria:**
- [ ] `MonteCarlo` sheet with distribution stats (mean, std, P5, P25, P50, P75, P95)
- [ ] Histogram chart embedded
- [ ] Configurable distributions per factor (normal, triangular, lognormal) via YAML
- [ ] Runs in < 5s for 1000 iterations on a 5-year deal
- [ ] Numpy-based; results written as values into output sheet (not live formulas)

#### US-003: Template 9 — M&A merger model
**Description:** As an M&A analyst, I want a pro-forma merger model with accretion-dilution and synergies so I can run quick deal screens.
**Acceptance Criteria:**
- [ ] Spec class `MergerSpec` in `spec/merger.py`
- [ ] Sheets: Cover, Sources, Assumptions, Acquirer, Target, Pro Forma, Synergies, Accretion-Dilution, Returns
- [ ] Deal structure: cash / stock / mix toggle
- [ ] Accretion-dilution by year, EPS bridge waterfall
- [ ] QC gate passes 8/8 on sample deal

#### US-004: Template 10 — DCF-WACC standalone
**Description:** As an equity analyst, I want a clean DCF with explicit WACC build (Damodaran Italy ERP 6.7% baseline) so I can defend valuations.
**Acceptance Criteria:**
- [ ] Spec class `DCFSpec` in `spec/dcf.py`
- [ ] WACC build sheet: risk-free, ERP, beta, debt cost, tax rate, target capital structure
- [ ] Terminal value: Gordon growth + exit multiple, both shown
- [ ] Sensitivity tornado on WACC × terminal growth
- [ ] Damodaran 2026 Italy ERP cited inline (§Damodaran ctryprem.html)

#### US-005: Template 11 — Fairness opinion football field
**Description:** As an IB associate, I want a football-field valuation chart aggregating trading comps, transaction comps, DCF, and LBO so I can produce fairness opinion exhibits.
**Acceptance Criteria:**
- [ ] Spec class `FairnessSpec` in `spec/fairness.py`
- [ ] 4 valuation methodologies in separate sheets, summary on Football Field sheet
- [ ] Native Excel bar chart with low/high ranges per method
- [ ] Premium / discount columns vs current price
- [ ] QC gate passes 8/8

#### US-006: Ingestion expanded to all 8 templates
**Description:** As a deal team lead, I want `modelforge ingest` to work for unitranche / minibond / credit memo / RE / NPL / structured credit / 3-statement so I can onboard any deal type from a data room.
**Acceptance Criteria:**
- [ ] Per-template prompt files in `modelforge/ingest/prompts/template_*.md`
- [ ] Schema derivation works on all 8 + 3 new templates
- [ ] End-to-end test for each template with a synthetic data-room fixture
- [ ] Cache hit rate ≥ 80% across runs (≥ 3 ingestions in test suite)
- [ ] All 11 templates round-trip QC 8/8 from ingested YAML

#### US-007: OCR layer for scanned PDFs
**Description:** As an analyst, I want scanned PDFs in a data room to be OCR'd so I do not need to manually retype Italian notary docs.
**Acceptance Criteria:**
- [ ] Optional `[ingest-ocr]` extras: tesseract or Azure Document Intelligence (configurable)
- [ ] PDF reader auto-detects when text layer is empty and falls back to OCR
- [ ] Italian language pack included; English, French, German, Spanish optional
- [ ] OCR-extracted chunks tagged `source: ocr` in DocChunk
- [ ] Test fixture with one scanned PDF passes ingestion E2E

#### US-008: `modelforge chat` lineage Q&A
**Description:** As a senior MD, I want to ask "why is Y3 revenue growth 7%?" against a generated workbook and get a sourced answer in plain English.
**Acceptance Criteria:**
- [ ] CLI `modelforge chat <model.xlsx>` opens REPL
- [ ] Claude Opus + linkage-graph walker; system prompt cached
- [ ] Answers cite assumption IDs and source pages (e.g., "A-012, sourced from S-005 page 14")
- [ ] Handles questions about: assumption provenance, formula derivation, scenario impact, covenant headroom, sensitivity
- [ ] Conversation export to markdown for committee transcripts

#### US-009: Audit dossier export — regulator-grade PDF
**Description:** As a credit committee chair, I want a single PDF that contains every assumption, every source citation, every formula, and a QC sign-off page so I can hand it to auditors and rating agencies.
**Acceptance Criteria:**
- [ ] CLI `modelforge dossier <model.xlsx> -o dossier.pdf`
- [ ] PDF sections: Cover (deal name, date, version hash), Executive Summary, Assumptions Register (every named range + source page), Source Registry (every doc with page-level citations), Formula Inventory (every unique formula by sheet), Lineage Graph (key cells walked back to sources), QC Sign-off (8 checks + auditor name field), Glossary (EN+IT)
- [ ] Cryptographic hash of source workbook on cover (SHA-256)
- [ ] Reproducibility statement: lists ModelForge version + Python version + spec YAML hash
- [ ] External counsel review by end of v0.4 (acceptance gate: counsel confirms it would be acceptable to Banca d'Italia / Consob)
- [ ] `modelforge dossier --format html` alternative for web review

#### US-010: Excel add-in MVP — ribbon, lineage walker, scenario flipper (epic)
**Description:** As an analyst editing a ModelForge workbook in Excel, I want a sidebar that shows lineage of the selected cell, lets me flip scenarios, and explains formulas in plain English so I never leave Excel.
**Acceptance Criteria:**
- [ ] Office.js add-in scaffold in `add-in/` directory
- [ ] Manifest passes Microsoft validation
- [ ] Sidebar shows: selected cell address, formula, named-range expansion, lineage walk back to source pages, scenario value comparison (Worst/Base/Best)
- [ ] One-click scenario flip writes to scenario toggle cell
- [ ] "Explain this formula" calls modelforge chat backend; result rendered in sidebar
- [ ] Works against local linkage-graph SQLite (no cloud required for MVP)
- [ ] Side-loaded distribution acceptable for v0.4; AppSource publication is v0.5

#### US-011: Versioned spec hash + reproducibility
**Description:** As an auditor, I want every workbook to embed the spec YAML hash and ModelForge version so I can verify it was not tampered with.
**Acceptance Criteria:**
- [ ] Cover sheet shows: spec_yaml_sha256, modelforge_version, python_version, build_timestamp
- [ ] `modelforge verify <model.xlsx>` recomputes the spec hash and confirms match
- [ ] Tamper detection: if any non-input cell changed since build, verify reports diff

#### US-012: Documentation & website refresh
**Description:** As a prospective customer, I need a clean docs site explaining what ModelForge does, with code examples and a quickstart.
**Acceptance Criteria:**
- [ ] mkdocs-material site at docs.modelforge.app (or modelforge.app/docs)
- [ ] Quickstart, Architecture, CLI reference, Template gallery, FAQ, Comparison vs Rogo/Macabacus
- [ ] All 11 templates with sample YAML and rendered xlsx download
- [ ] CI deploys on tag

---

### Release v0.5 — "Defensibility moats" (Weeks 7-14)

**Goal:** Ship the three structural moats Rogo cannot replicate: probabilistic credit engine, competitor reverse-engineer, model diff/version control. Web SaaS thin layer goes live. Live data feeds (stub-level). Scorecard target: 9.55/10.

#### US-013: Probabilistic credit engine — Merton structural model
**Description:** As a credit risk analyst, I want a Merton structural default model on the borrower so I can quote PD with theoretical grounding.
**Acceptance Criteria:**
- [ ] New module `modelforge/risk/merton.py`
- [ ] Inputs: equity value, equity volatility, debt face value, risk-free rate, tenor
- [ ] Outputs: asset value, asset volatility, distance-to-default, PD
- [ ] Newton iteration solver for asset value/vol; convergence test
- [ ] Unit tests with textbook examples (Hull 11e, ch 24)
- [ ] Optional sheet `MertonPD` in credit memo and unitranche templates

#### US-014: KMV-style PD calibration with empirical mapping
**Description:** As a fund risk officer, I want distance-to-default mapped to empirical PD via a Moody's-style table so my numbers are committee-defensible.
**Acceptance Criteria:**
- [ ] Bundled empirical DD→PD table (KMV public-paper basis) in `modelforge/risk/kmv_table.csv`
- [ ] Calibration function with linear interpolation
- [ ] Citations in code (Moody's RiskCalc whitepaper, year)
- [ ] Sheet shows both Merton-theoretical PD and KMV-empirical PD side-by-side

#### US-015: IFRS 9 ECL staging engine with backtesting
**Description:** As an IFRS 9 reporter, I want stage 1/2/3 ECL computed on a portfolio with backtesting against historical defaults so I can defend the provision.
**Acceptance Criteria:**
- [ ] `modelforge/risk/ifrs9_ecl.py`: PD × LGD × EAD × discount with stage transition matrix
- [ ] 12-month and lifetime ECL
- [ ] Stage transitions: 30 dpd / SICR proxy / 90 dpd thresholds (configurable)
- [ ] Backtesting CLI: `modelforge backtest ecl --history <csv> --predicted <csv>` → reports prediction vs realized loss with Hosmer-Lemeshow test
- [ ] Sheet `IFRS9ECL` integrated into NPL and structured credit templates
- [ ] Citations: IFRS 9 §B5.5.17, EBA GL 2017/06

#### US-016: Competitor model reverse-engineer (epic)
**Description:** As a new ModelForge user with a legacy Excel model from Macabacus or a previous bank job, I want to ingest it and produce a ModelForge spec so my switching cost is near-zero.
**Acceptance Criteria:**
- [ ] CLI `modelforge reverse <legacy.xlsx> -o spec.yaml`
- [ ] Reads workbook with openpyxl; classifies sheets (cover/assumptions/IS/BS/CF/debt/returns) via Claude classifier
- [ ] Extracts named ranges and inputs into Pydantic spec
- [ ] Detects template type from sheet pattern (LBO / DCF / merger / 3-statement / PF)
- [ ] Reports `REVERSE_REPORT.md`: % of formulas covered by emitted spec, list of unmatched cells, suggested manual review queue
- [ ] Acceptance test: round-trip on a public Macabacus LBO long-form template with ≥ 90% formula coverage

#### US-017: Model diff / Git-style version control
**Description:** As a deal-team lead, I want to compare two versions of a model and see exactly which assumptions and formulas changed, with provenance.
**Acceptance Criteria:**
- [ ] CLI `modelforge diff <v1.xlsx> <v2.xlsx>` → markdown report
- [ ] Diff dimensions: input values changed, formula changes, structural changes (sheets/named ranges added/removed), source citations changed
- [ ] Each change references the assumption ID and (if available) source page
- [ ] HTML output option with side-by-side cell view
- [ ] Integrates with `modelforge dossier` so audit dossier can show "changes since v1"
- [ ] Performance: < 10s on a 50-sheet workbook

#### US-018: Web SaaS thin layer — read & share (epic)
**Description:** As a credit committee chair, I want to view a ModelForge workbook in a browser without needing Excel installed, with the lineage walker and scenario flipper available.
**Acceptance Criteria:**
- [ ] FastAPI backend in `web/api/`, Next.js frontend in `web/app/`
- [ ] Upload xlsx + linkage SQLite → render read-only view
- [ ] Sheet navigator with frozen-pane preserved
- [ ] Click any cell → lineage walker panel (same UX as Excel add-in)
- [ ] Scenario toggle live-recomputes via numpy backend (not just static render)
- [ ] Magic-link sharing for committee distribution (no login required for read-only)
- [ ] Hosted at modelforge.app; auth: NextAuth + magic links for v0.5; SSO in v1.0

#### US-019: Live data feeds — Bloomberg / Refinitiv / S&P CIQ adapters (stubs + 1 live)
**Description:** As a credit analyst, I want EURIBOR / ECB rate / Italy ERP to auto-refresh in my workbook on open so my models never use stale data.
**Acceptance Criteria:**
- [ ] `modelforge/feeds/` module with adapter interface
- [ ] Adapters (stubs): Bloomberg Server API, Refinitiv RDP, S&P CIQ
- [ ] One live adapter end-to-end: ECB Statistical Data Warehouse (free, public) for EURIBOR + main refinancing rate + EONIA/€STR
- [ ] One live adapter for Damodaran country risk (scraped weekly, cached)
- [ ] Excel add-in "Refresh feeds" button updates relevant named ranges
- [ ] Audit dossier records feed timestamps and source URLs

#### US-020: Sensitivity → tornado on probabilistic outputs
**Description:** As a fund manager, I want sensitivity tornado on PD / ECL / IRR jointly so I can see which assumption drives risk-adjusted return most.
**Acceptance Criteria:**
- [ ] Extension of US-001 to risk metrics (PD, ECL, EL, RAROC)
- [ ] Joint sensitivity table: factor × output matrix
- [ ] QC: integration test on credit memo template

#### US-021: Excel add-in v1 — published to AppSource
**Description:** As any Excel user, I want to install the ModelForge add-in from the Office store with one click.
**Acceptance Criteria:**
- [ ] Privacy policy + terms of service + support email at modelforge.app
- [ ] Microsoft Partner Center submission packaged
- [ ] Office.js manifest validates against latest schema
- [ ] Free tier: lineage walker + formula explainer; Pro tier (subscription): scenario flipper + dossier export + reverse-engineer
- [ ] Stripe subscription wiring; license check on Pro features

#### US-022: Multi-tenant data model migration
**Description:** As a platform engineer, I need to migrate the SQLite linkage graph to a per-tenant Postgres schema so the SaaS can host multiple firms safely.
**Acceptance Criteria:**
- [ ] Schema migration scripts: SQLite → Postgres (per-tenant database or schema)
- [ ] Tenant ID propagated through every query
- [ ] Row-level security (RLS) policies in Postgres
- [ ] Existing SQLite path remains supported for solo / on-prem mode
- [ ] CI matrix runs both backends

---

### Release v1.0 — "Enterprise-ready and #1" (Weeks 15-24)

**Goal:** SOC 2 Type II, SAML/SSO, multi-tenant SaaS at GA, US/UK/Asia regulatory packs, model-memory agents + data-room watcher, voice MD-review mode, template marketplace. Scorecard target: 9.6/10, top-1 on 22 of 25 criteria.

#### US-023: SAML / OIDC SSO + RBAC
**Description:** As a bank IT admin, I need SAML SSO and role-based access control so I can deploy ModelForge to the credit team.
**Acceptance Criteria:**
- [ ] SAML 2.0 via SP-initiated and IdP-initiated flows; tested against Okta, Azure AD, Ping
- [ ] OIDC alternative for Google Workspace / Auth0
- [ ] Roles: Viewer / Analyst / Reviewer / Admin
- [ ] Audit log of every model build, dossier export, scenario flip with user identity

#### US-024: SOC 2 Type II audit complete
**Description:** As a procurement gate, I need a SOC 2 Type II report so I can sell to regulated firms.
**Acceptance Criteria:**
- [ ] Engage Vanta / Drata; complete Type I in v0.5; Type II observation period bridges into v1.0
- [ ] Controls: encryption at rest + in transit, vulnerability scanning, access reviews, incident response runbook
- [ ] Report available to enterprise prospects under NDA
- [ ] Trust center page at modelforge.app/trust

#### US-025: On-prem / private-VPC deployment
**Description:** As a BB credit desk, I need to deploy ModelForge inside our VPC with no outbound internet (model files do not leave the bank).
**Acceptance Criteria:**
- [ ] Docker compose + Helm chart for k8s
- [ ] Air-gapped install path: pre-pulled container images, offline license activation
- [ ] LLM backend pluggable: Bedrock / Azure OpenAI / on-prem (OpenAI-compatible endpoint)
- [ ] Documentation: network diagram, data-flow diagram, threat model
- [ ] Pilot install at 1 design-partner bank by v1.0

#### US-026: US regulatory pack — EDGAR / 10-K/Q ingest
**Description:** As a US equity analyst, I want to point ModelForge at an EDGAR ticker and have it pre-fill a 3-statement spec from the latest 10-K/Q.
**Acceptance Criteria:**
- [ ] `modelforge ingest --edgar AAPL --years 2022-2025` pulls XBRL-tagged financials
- [ ] Spec emitted: 3-statement template with historicals filled and forecast assumptions templated
- [ ] Citations point to specific SEC filing URL + accession number
- [ ] US tax rates (federal + state weighted) included as named range
- [ ] Test: round-trip on 5 large-cap tickers

#### US-027: UK / EU regulatory packs
**Description:** As a UK / EU analyst, I want regional regulatory data sources (PRA returns, ESMA filings) supported.
**Acceptance Criteria:**
- [ ] PRA / Companies House adapter for UK PLC ingestion
- [ ] ESMA register adapter for EU funds
- [ ] EBA stress test scenarios bundled (2024 + 2026)
- [ ] FR / DE / ES regulatory cite stubs for v1.0; full FR/DE pack deferred to v1.1

#### US-028: APAC regulatory pack — HKEX / SGX / TSE
**Description:** As an Asia-Pacific analyst, I want HKEX / SGX / TSE filing ingestion.
**Acceptance Criteria:**
- [ ] HKEX HKEXnews adapter
- [ ] SGX SGXNet adapter
- [ ] TSE EDINET (Japan) adapter — minimal viable
- [ ] FX handling: report currency vs functional currency reconciliation
- [ ] Test: round-trip on 3 tickers across 3 exchanges

#### US-029: Model-memory agent — assumption drift watcher
**Description:** As a portfolio manager, I want an agent that watches my models, notices when an assumption is no longer current (e.g., EURIBOR moved, comparable EBITDA multiple shifted), and proposes updates.
**Acceptance Criteria:**
- [ ] Background worker (Celery / Temporal) iterates active models
- [ ] For each input named range, queries relevant data feed; flags if delta > configurable threshold
- [ ] Generates a `ProposedUpdate` record with: assumption ID, current value, proposed value, source citation, blast-radius (impacted output cells)
- [ ] User reviews in web UI: approve → applies as a new spec version (with diff dossier auto-generated)
- [ ] This is the Rogo Offset parity feature

#### US-030: Data-room watcher agent
**Description:** As a deal lead, I want an agent that monitors a data-room folder and proposes spec updates whenever new docs land (Q3 trading update arrives → revenue growth assumption refreshed).
**Acceptance Criteria:**
- [ ] Watches a folder path (local), Google Drive folder, or SharePoint folder (1 cloud connector for v1.0)
- [ ] On new doc: classify → extract relevant fields → produce ProposedUpdate
- [ ] Notifications: web UI inbox + optional email digest
- [ ] Test: synthetic Q3 update added to data-room fixture triggers correct ProposedUpdate

#### US-031: Voice + chat MD-review mode
**Description:** As an MD reviewing a junior's model on the phone before committee, I want to ask questions out loud and get audio answers grounded in the lineage graph.
**Acceptance Criteria:**
- [ ] Web UI mic button; OpenAI Whisper or Azure Speech for ASR
- [ ] Same chat backend as US-008
- [ ] TTS via Azure / ElevenLabs with conservative voice
- [ ] Conversation transcript exportable to dossier (becomes "MD review" appendix)
- [ ] Latency target: end-of-question to start-of-audio-answer < 4s on a 100-cell question

#### US-032: Template marketplace — publish, install, revenue share
**Description:** As a community contributor, I want to publish my template (e.g., "EU PBSA waterfall v2") and earn revenue when others install it.
**Acceptance Criteria:**
- [ ] `modelforge publish <template-dir>` → marketplace.modelforge.app
- [ ] `modelforge install <template-id>` from CLI; one-click install in Excel add-in
- [ ] Templates sandboxed: cannot execute arbitrary code outside the spec emitter
- [ ] Stripe Connect for payouts; 70 / 30 revenue split (publisher / platform)
- [ ] Quality gates: required QC test fixture, version semver, deprecation policy
- [ ] 50 templates by v1.0 launch (10 first-party seed + 40 community)

#### US-033: Template marketplace — quality scoring & reputation
**Description:** As a marketplace user, I want to see which templates are reliable so I do not install something that breaks committee review.
**Acceptance Criteria:**
- [ ] Templates rated on: QC pass rate across installs, downloads, user star rating, last-update recency
- [ ] Verified-publisher badge for KYC'd contributors
- [ ] Auto-flagging of templates that fail QC after a ModelForge core update

#### US-034: Comparison shoot-out — "ModelForge vs Rogo on the same deal"
**Description:** As marketing, I want a public benchmark study where ModelForge and Rogo build the same deal from the same data room and the outputs are graded.
**Acceptance Criteria:**
- [ ] 5 anonymized public deals (1 LBO, 1 PF, 1 NPL, 1 RE, 1 minibond)
- [ ] Scorecard methodology published; external grader (an ex-MD)
- [ ] Whitepaper at modelforge.app/benchmark
- [ ] Press release; pitch to Bloomberg / FT / Sifted

#### US-035: Pricing & billing — Stripe + enterprise quoting
**Description:** As a SaaS operator, I need a working billing system supporting solo / boutique / enterprise tiers.
**Acceptance Criteria:**
- [ ] Tiers: Solo (€99/mo, 5 models/mo), Boutique (€499/seat/mo, unlimited), Enterprise (quoted, includes on-prem + SSO)
- [ ] Stripe checkout + customer portal for self-serve
- [ ] Enterprise: HubSpot quote-to-cash flow; invoice + ACH/SEPA
- [ ] Usage metering: model builds, dossier exports, agent invocations

#### US-036: Documentation, sales collateral, pitch deck
**Description:** As GTM, I need a polished pitch deck, ROI calculator, and security questionnaire pre-filled to close enterprise deals.
**Acceptance Criteria:**
- [ ] 15-slide pitch deck (DeckForge-built, of course)
- [ ] ROI calculator (Excel + web): saves X hours per deal × Y deals/yr × analyst loaded cost
- [ ] Pre-filled SIG Lite security questionnaire
- [ ] 2 case studies from design-partner customers (with quotes, anonymized if needed)

---

## 4. Functional Requirements

### Core engine
- FR-1: All 11 templates (8 existing + M&A merger + DCF-WACC + fairness opinion) emit QC-8/8 workbooks from valid YAML.
- FR-2: Every workbook embeds spec_yaml_sha256, modelforge_version, build_timestamp on the Cover sheet.
- FR-3: Every workbook supports `modelforge verify` for tamper detection.
- FR-4: Sensitivity tornado and Monte Carlo are first-class sheets on every template.

### Ingestion & reverse-engineering
- FR-5: `modelforge ingest` works for all 11 templates with per-template prompt files.
- FR-6: OCR fallback activates automatically when a PDF has no text layer.
- FR-7: `modelforge reverse` extracts spec from a legacy xlsx with ≥ 90% formula coverage on Macabacus reference templates.
- FR-8: `modelforge ingest --edgar / --hkex / --sgx / --edinet / --pra / --companies-house` work for the listed regulators.

### Auditability
- FR-9: `modelforge dossier` produces a regulator-grade PDF with every section in US-009.
- FR-10: `modelforge diff` produces markdown and HTML diff between two model versions.
- FR-11: Audit dossier embeds spec hash, source URLs, feed timestamps, and reproducibility statement.

### Risk engine
- FR-12: Merton structural model produces PD with documented numerical convergence.
- FR-13: KMV-style empirical mapping bundled with citations.
- FR-14: IFRS 9 ECL engine supports stage 1/2/3 with configurable transition thresholds.
- FR-15: ECL backtesting CLI reports Hosmer-Lemeshow goodness-of-fit.

### Surfaces
- FR-16: CLI remains the canonical interface; everything else wraps the same engine.
- FR-17: Excel add-in installs from AppSource and works against local SQLite linkage graph.
- FR-18: Web app at modelforge.app supports upload, view, share, scenario flip, lineage walk.
- FR-19: Voice mode end-to-end latency < 4s on standard questions.

### Data & feeds
- FR-20: ECB SDW and Damodaran adapters live; Bloomberg / Refinitiv / S&P CIQ adapters with documented config.
- FR-21: Feeds refresh on workbook open in Excel add-in (with user opt-in).

### Agents
- FR-22: Assumption drift watcher generates ProposedUpdate records with blast-radius analysis.
- FR-23: Data-room watcher monitors local + 1 cloud connector and proposes spec updates.

### Marketplace
- FR-24: Templates can be published, installed, rated, and revenue-shared via Stripe Connect.
- FR-25: Templates are sandboxed and run a quality gate before publication.

### Enterprise
- FR-26: SAML 2.0 SSO works against Okta, Azure AD, Ping; OIDC supported.
- FR-27: RBAC enforces Viewer / Analyst / Reviewer / Admin roles.
- FR-28: Multi-tenant Postgres backend with row-level security.
- FR-29: On-prem deployment via docker compose and Helm chart.
- FR-30: SOC 2 Type II report available under NDA.
- FR-31: Audit log records every privileged action with user identity and timestamp.

### Quality / non-regression
- FR-32: 95%+ test coverage on engine; 80%+ on add-in and web; CI gates on coverage drop.
- FR-33: Every release ships a SOTA scorecard update.

---

## 5. Non-Goals (Out of Scope)

- **Building a research / pitchbook generator to compete with Rogo on breadth.** ModelForge wins on depth in modelling; Rogo wins on breadth of artefacts. Stay in lane.
- **Replacing Bloomberg / Refinitiv as a data terminal.** Adapters consume their data; we never become the source of market data.
- **Mobile-native app.** Web is responsive; no iOS/Android binary in this horizon.
- **Realtime collaborative editing of cells (Google-Docs-style).** Conflicts with deterministic-spec philosophy. Collaboration is at the spec/YAML level via Git.
- **AI that writes formulas freely into cells.** Hard rule: deterministic Python writes cells, LLM writes spec. Violates the moat.
- **Crypto / DeFi / token modelling.** Scope creep; revisit only if a paying customer demands it.
- **Replacing accounting systems.** Ingest from QuickBooks / NetSuite is acceptable; becoming the GL is not.
- **Free unlimited tier.** Trial yes (14 days, full features); free forever no.
- **Open source the engine.** Add-in and CLI client may be source-available; the deterministic builder + risk engine + dossier exporter remain proprietary.
- **Italian-only positioning post-v1.0.** Italy stays the niche advantage but global is now the goal.

---

## 6. Design Considerations

### Architectural invariants (do not break)
- LLM never writes numbers into cells. Spec → deterministic emitter → workbook.
- Linkage graph is the canonical artifact; Excel and PDF dossier are renders.
- Costs negative; English primary, Italian secondary; scenarios Worst/Base/Best.
- Color code: Blue input / Black formula / Green link / Red warning.
- Named ranges mandatory; no magic numbers.

### Surface design
- CLI: stays terse, scriptable, the engine's truth source.
- Excel add-in: minimal chrome, Office.js sidebar, never blocks Excel's own UX.
- Web app: read-and-share first; editing is via spec upload, not in-browser cell edits.
- Voice mode: optional, behind a feature flag; never default.

### Brand / positioning
- Tagline: "Bulge-tier Excel models. Every cell live. Every number sourced. Every assumption defended."
- Keep DeckForge / ModelForge / "Forge" line consistent.
- Avoid LLM-marketing tropes ("AI-powered"); lead with audit and source-traceability.

### Re-use
- Audit dossier reuses linkage-graph queries; do not duplicate logic.
- Web app reuses CLI engine via Python subprocess or library import; do not reimplement.
- Excel add-in reuses chat backend; one chat service serves CLI + web + add-in + voice.

---

## 7. Technical Considerations

### Dependencies
- Python 3.11+ (current 3.14)
- New: psycopg[binary], sqlalchemy 2 (multi-tenant), celery or temporal-py (agents), reportlab or weasyprint (dossier PDF), pytesseract or azure-ai-documentintelligence (OCR), formulas (already), pdfplumber (already)
- Web: Next.js 15 + tRPC + tailwindcss + shadcn/ui
- Add-in: Office.js + React (vite-react template), TypeScript
- Auth: NextAuth + SAML strategy, optional WorkOS for SSO orchestration
- Billing: Stripe SDK (Python) + Stripe Connect for marketplace

### Performance budgets
- CLI build of any template: < 2s (current ~1.2s)
- Ingestion of 10-doc data room: < 60s (current ~45s)
- Reverse-engineer of 50-sheet workbook: < 30s
- Dossier PDF for 8-template workbook: < 10s
- Monte Carlo 1000 runs: < 5s
- Voice question round-trip: < 4s

### Compliance & security
- SOC 2 Type II (Vanta or Drata-mediated)
- GDPR: data processing addendum, EU hosting option
- Data residency: EU default, US optional
- Encryption: TLS 1.3 in transit, AES-256 at rest, KMS-managed keys
- LLM data handling: zero-data-retention via Anthropic enterprise API; on-prem option for banks who refuse cloud LLM

### Testing strategy
- Unit + integration test suites already at 34 tests; target ~250 by v1.0
- Round-trip tests per template: spec → build → QC → re-spec → re-build → equal
- Property-based tests on the risk engine (hypothesis library)
- E2E tests on web app via Playwright
- Monthly regression run against 5 anonymized real-deal fixtures

### Scaling
- Stateless CLI workers behind a queue
- Per-tenant Postgres schema (tenancy isolation > shared-table efficiency at this scale)
- Object storage for workbooks (S3 / R2); not in DB
- LLM call budget per tier; abuse limits

---

## 8. Success Metrics

### Quality (engine-side)
- Weighted SOTA scorecard ≥ 9.5 by v0.4; ≥ 9.6 by v1.0
- Top-1 on ≥ 22 of 25 scorecard criteria by v1.0
- Audit dossier accepted by ≥ 1 Italian rating agency as preferred format
- Zero formula errors across 100% of templates in CI

### Usage
- 50 paid seats by v0.5; 200 by v1.0
- 5 design-partner banks/funds by v1.0
- 50 marketplace templates at v1.0 launch
- ≥ 80% Claude API cache hit rate on ingestion runs

### Commercial
- ARR €500k by v0.5; €2M by v1.0
- 3 enterprise contracts ≥ €100k/yr by v1.0
- Per-engagement freelance pricing supports €15-25k
- Customer NPS ≥ 50 (industry benchmark for finance SaaS: 30)

### Time-to-deliverable for finance professionals
- New deal from data room to committee-ready model: 2 hours (vs 2 days legacy)
- Audit dossier generation: 30 seconds (vs 2-4 hours hand-built)
- Senior MD review via chat / voice: 15 minutes (vs 2-hour walkthrough)

### Defensibility / moat
- Reverse-engineer covers ≥ 90% of formulas on public Macabacus reference template
- Model diff catches 100% of input/formula changes in adversarial test
- ECL backtesting Hosmer-Lemeshow p-value > 0.05 on bundled historical NPL dataset
- External counsel review confirms dossier acceptable to Banca d'Italia / Consob
- Public benchmark whitepaper shows ModelForge ≥ Rogo on source-traceability and ≥ Italian bulge on output quality across 5 deals

---

## 9. Open Questions

1. **Voice MD-review:** is this a feature MDs actually want, or vanity? Validate with 3 MD interviews before US-031.
2. **Marketplace revenue split:** is 70 / 30 right? Stripe Connect benchmarks suggest 80 / 20 for premium creators; revisit before US-032.
3. **On-prem LLM:** which open model is good enough for ingestion + chat at bank-grade quality? Llama 4 / Qwen 3 / DeepSeek? Evaluation needed before US-025.
4. **EDGAR vs Pitchbook for US deals:** EDGAR is free but limited; should we partner with Pitchbook / S&P CIQ for richer US deal flow? Cost analysis needed.
5. **AppSource gating:** Microsoft review can take 2-6 weeks. Submit early in v0.5 to derisk.
6. **GDPR data residency:** EU customers may demand "no data leaves EU" — is Anthropic API EU-resident in 2026? Confirm.
7. **Template marketplace IP:** what license do contributors grant? Need legal review before US-032.
8. **Pricing anchor:** is €499/seat/mo right for boutique? Macabacus is ~$150/seat; Rogo is rumored $1k+/seat. Test with 5 design partners.
9. **SOC 2 Type II observation period:** typically 6+ months. Start in v0.4 to land the report by v1.0.
10. **How much ahead does the Italian bulge specialist stay?** They get 9.4 on the human baseline; if we reach 9.6 the gap is real but small. Is a 9.7 target realistic for v1.1?

---

## 10. Sequencing & Milestones

| Release | Weeks | Headline | Scorecard target |
|---------|-------|----------|------------------|
| v0.4 | 1-6 | SOTA parity + add-in MVP + audit dossier | 9.5 |
| v0.5 | 7-14 | Defensibility moats + web SaaS + risk engine | 9.55 |
| v1.0 | 15-24 | Enterprise + agents + marketplace + global | 9.6 |

### v0.4 critical path (build order recommendation)
US-001/002 (sensitivity + MC) → US-006 (ingest-wide) → US-007 (OCR) → US-003/004/005 (M&A + DCF + fairness) → US-008 (chat) → US-009 (dossier) → US-010 (add-in MVP) → US-011 (verify) → US-012 (docs).

### v0.5 critical path
US-013/014/015 (risk engine) → US-016 (reverse-engineer) → US-017 (diff) → US-019 (feeds, ECB live) → US-018 (web SaaS) → US-022 (multi-tenant) → US-021 (AppSource) → US-020 (probabilistic sensitivity).

### v1.0 critical path
US-023 (SSO) → US-026/027/028 (regional packs) → US-024 (SOC 2 Type II) → US-025 (on-prem) → US-029/030 (agents) → US-032/033 (marketplace) → US-035 (billing) → US-031 (voice) → US-034 (benchmark whitepaper) → US-036 (sales collateral).

---

## 11. Closing Note

The strategic premise of this PRD is that **#1 in modelling for finance professionals is not won by being the best at any single dimension** — Rogo will likely win on raw output breadth and distribution, Macabacus will keep its Excel-add-in incumbency, and the Italian bulge specialist will keep producing one extraordinary model at a time. ModelForge wins by being the **only product where every cell is live, every number is sourced, every change is diffed, every assumption is defended, every model is auditable, and every professional can install it where they already work**. The combination is the moat. This PRD is the build plan to get there.

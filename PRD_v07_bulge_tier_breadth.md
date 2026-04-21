# PRD — ModelForge v0.7 "Bulge-Tier Breadth Across All Markets"

**Status**: drafted 2026-04-21, immediate execution
**Owner**: Luka Stanisljevic
**Trigger**: v0.6 gold-standard audit (398 checks) shows 41% pass against bulge-bracket / Italian regulatory standards. Foreign institutional investors (family offices, sovereign wealth, pension funds, direct-lending funds in London / Zurich / Frankfurt) demand 9+ on **all three** dimensions: core plumbing, bulge depth, regulatory compliance.

---

## Goal

Ship **one consolidated v0.7** release that lifts weighted score from 9.0 → **≥9.5** on **every market segment** ModelForge could plausibly serve:

| Market | v0.6 score | v0.7 target |
|---|---:|---:|
| Italian private credit / PF / NPL / structured credit (current base) | 9.0 | **9.6** |
| Bulge-bracket sponsor LBO / M&A advisory / fairness opinion | 8.4 | **9.2** |
| Regulatory compliance (AIFMD II / Basel / IFRS 9 for institutional allocators) | 7.2 | **9.0** |

Foreign institutional investors — family offices, Swiss private banks, DACH direct-lending funds, UK DB pension trustees, Nordic sovereign wealth arms — use standards beyond the Italian boutique baseline. They demand:

1. **Macabacus-grade formula discipline** — already there (v0.6).
2. **Goldman/Morgan Stanley-grade breadth** — EV bridge, PPA, sculpted sensitivities, full sponsor LBO stack, stub periods, Hamada beta, Damodaran CRP methodology.
3. **BaFin / ECB / FCA-grade regulatory plumbing** — IFRS 9 three-stage ECL, AIFMD II leverage / loan-origination / single-borrower compliance, Basel III/IV securitisation capital, GACS structure for Italian NPL.

v0.7 closes all three.

---

## Success criteria

Ship when:

1. `gold_standard_audit.py` reports **≥75% PASS** across 398 checks (currently 41%).
2. Within each category: DCF ≥75%, M&A ≥70%, PF ≥80%, LBO (unitranche) ≥70% + a new **SponsorLBO** template at ≥60%, 3-Stmt ≥70%, Format ≥90%, IT-Reg ≥65%.
3. `adversarial_audit.py` still reports 0 CRITICAL / 0 HIGH (no regression from v0.6).
4. `audit_compute.py` 0 computational errors.
5. `pytest` all existing tests pass + ≥30 new test cases.
6. Every new feature has a working example in `examples/` YAML that builds successfully.

---

## Scope — 48 stories across 6 waves

### Wave A — Quick wins (8 stories, ~4 hours total)

| ID | Story | Effort |
|---|---|---|
| US-090 | Apply accounting number format `#,##0.00;(#,##0.00);-` globally in `styles.py` | 15 min |
| US-091 | Add LLCR + PLCR rows to `pf_debt.py` | 1 hr |
| US-092 | Add min / average DSCR summary rows to `pf_debt.py` | 30 min |
| US-093 | Add implied-g cross-check row to DCF Valuation | 20 min |
| US-094 | Split `effective_tax_rate` into `ires_rate_pct` + `irap_rate_pct`; compute effective combination | 45 min |
| US-095 | Extend `_write_comp_table` (fairness): add Min / Q1 / Q3 / Max rows | 30 min |
| US-096 | Fix DSRA row label to match forward-looking formula | 5 min |
| US-097 | Add accretion "cross-over year" row on merger `AccretionDilution` | 30 min |

### Wave B — DCF depth (9 stories, ~20 hours total)

| ID | Story | Effort |
|---|---|---|
| US-100 | Extend DCFSpec with `minority_interest_eur_m`, `pension_deficit_eur_m`, `preferred_equity_eur_m`, `cross_holdings_eur_m`, `lease_liability_ifrs16_eur_m` as optional Assumptions. Emit as separate bridge rows on Valuation | 2 hr |
| US-101 | Stub-period handling: add `stub_period_days` (default 365); multiply first-period FCF by `stub_days/365`; compound discount factor by `stub_years` | 3 hr |
| US-102 | Two-stage DCF: add `fade_years` (default 3); FCF converges linearly from Y_{n} growth rate to terminal_growth over fade period; inserted between explicit and terminal in Valuation | 4 hr |
| US-103 | `ComparableBetas` sheet — list of comp companies with levered beta + D/E + tax; Hamada unlever per row; median; relever to target | 4 hr |
| US-104 | Damodaran CRP methodology: decompose ERP = mature_erp + sovereign_default_spread × (σ_equity/σ_bond) × λ_country_exposure | 2 hr |
| US-105 | Terminal-FCF normalization block: capex_terminal = D&A_terminal; ΔNWC_terminal = g × prior NWC | 1 hr |
| US-106 | 2D sensitivity Data Tables on DCF (WACC × g; WACC × exit multiple) via openpyxl | 3 hr |
| US-107 | Remove ERP as flat input; derive from risk_free + mature_ERP_damodaran + country_spread + lambda | 1 hr |
| US-108 | Size premium optional row (Duff & Phelps decile), auto-skip if mkt cap > $2B | 30 min |

### Wave C — PF rigor (8 stories, ~22 hours total)

| ID | Story | Effort |
|---|---|---|
| US-110 | O&M reserve: 3-6 months of opex, funded at COD, released at decommissioning | 3 hr |
| US-111 | Major Maintenance Reserve (MMR): sinking fund for turbine/inverter replacement | 3 hr |
| US-112 | Lock-up test: distributable cash = 0 if DSCR < `dscr_lockup_threshold` (1.10x default) | 2 hr |
| US-113 | Equity cure rights: cap 2-3 cures, max 20% EBITDA uplift per cure | 4 hr |
| US-114 | Make-whole premium: T+50bps on early bond redemption | 2 hr |
| US-115 | P50/P90 revenue: base = P50, downside = P90; solver debt sizes against P90 | 4 hr |
| US-116 | Panel degradation curve: 0.5% p.a. compounding revenue haircut | 2 hr |
| US-117 | Real-vs-nominal inflation consistency check — QC sheet flags mix | 2 hr |

### Wave D — M&A rigor (7 stories, ~18 hours total)

| ID | Story | Effort |
|---|---|---|
| US-120 | PPA block: goodwill = equity price − BV − write-ups + DTL; identifiable intangibles with useful lives | 6 hr |
| US-121 | Intangible amortization schedule: tax-deductible (customer/tech) vs non-deductible (trade name in some jurisdictions) | 3 hr |
| US-122 | Cross-over / breakeven synergy reverse-solve row | 1 hr |
| US-123 | Break fees: target reverse-termination (1-4% equity); asymmetric with acquirer walk fees | 2 hr |
| US-124 | Regulatory timeline: HSR / CMA / EU merger reg; delay synergy start months accordingly | 2 hr |
| US-125 | Contribution analysis: revenue / EBITDA / NI share vs equity ownership post-deal | 2 hr |
| US-126 | Exchange ratio with collar: fixed vs floating; walk-away rights | 2 hr |

### Wave E — Italian regulatory compliance (9 stories, ~28 hours total)

| ID | Story | Effort |
|---|---|---|
| US-130 | IFRS 9 three-stage ECL: Stage 1 (12m ECL on gross), Stage 2 (lifetime on gross + 30 DPD backstop), Stage 3 (lifetime on net). Add dedicated `IFRS9ECL` sheet | 6 hr |
| US-131 | SICR triggers: absolute PD, relative PD doubling, rating downgrade, watchlist, forbearance | 3 hr |
| US-132 | Forward-looking macro scenarios (GDP, unemployment, CPI) weighted into PD | 4 hr |
| US-133 | AIFMD II leverage check: open-ended ≤175%, closed-ended ≤300% commitment method | 2 hr |
| US-134 | AIFMD II single-borrower cap: 20% NAV | 1 hr |
| US-135 | Loan-originating AIF flag: if >50% NAV in originated loans | 1 hr |
| US-136 | GACS structure for NPL: state guarantee on senior tranche, fee priced on Italian financial CDS | 4 hr |
| US-137 | Formal tranche waterfall + PDL (Principal Deficiency Ledger) for NPL/SC | 5 hr |
| US-138 | Basel calendar provisioning for NPL: unsecured 100% after 3y, secured 7-9y | 2 hr |

### Wave F — RE promote + NPL priority + 3-stmt depth (7 stories, ~22 hours)

| ID | Story | Effort |
|---|---|---|
| US-140 | RE LP/GP waterfall: pref (8%) + catchup + 80/20 promote | 6 hr |
| US-141 | NPL strict waterfall: senior int → senior prin → mezz int → mezz prin → equity (replaces simultaneous bullet) | 5 hr |
| US-142 | 3-statement debt schedule roll-forward (US-075 redux): opening + draws − repay = closing; interest on average | 4 hr |
| US-143 | 3-statement NOL tracker: Italian 5-year limit, 80% current-year offset | 2 hr |
| US-144 | 3-statement stock-based compensation: P&L expense + CFS addback + FD shares dilution | 2 hr |
| US-145 | 3-statement minority interest: MI share of NI below NI-to-parent; MI BS line rolls | 2 hr |
| US-146 | Revolver plug: auto-draw when ending cash < min cash; commitment fee on undrawn | 3 hr |

**Total**: **48 stories**, **~115 engineering hours**. Target compressed delivery via parallel development per wave.

---

## Acceptance criteria

Per-wave:
- Wave A → 100% of quick-win checks PASS
- Wave B → DCF PASS rate 17.6% → ≥75%
- Wave C → PF PASS rate 8.3% → ≥80%
- Wave D → M&A PASS rate 27.3% → ≥70%
- Wave E → IT-Reg PASS rate 1% → ≥65%
- Wave F → RE/NPL waterfalls PASS; 3-stmt PASS rate 40% → ≥70%

Per-story: working example in `examples/` YAML; all existing tests pass; new test case covers the feature.

---

## Risks & mitigations

1. **Spec surface explosion** — adding 30+ new Assumption fields risks making YAML specs unwieldy. Mitigation: all new fields default-off or optional; existing specs continue to build without change.
2. **Performance regression** — Hamada comp-beta sheet, Data Tables, Monte Carlo could slow builds. Mitigation: profile; target <2s per workbook build.
3. **Numerical instability** — Data Tables + iterative calc + new sculpting solver could diverge. Mitigation: unit test each solver convergence separately.
4. **Breaking changes** — field renames in DCFSpec (ERP decomposition) will require migrating dcf_enel.yaml. Mitigation: backwards-compatible wrappers where possible; clean migration note in `V07_MIGRATION.md`.

---

## Sources

- Damodaran — country risk + Hamada + terminal FCF normalization
- Macabacus — LBO S&U + PPA + long-form templates
- Wall Street Prep — merger model + terminal value
- Edward Bodmer — LLCR/PLCR/DSRA/cure
- BIS FSI — IFRS 9 summaries
- Banca d'Italia — L.130/1999
- KPMG / Jones Day — GACS
- Clifford Chance / Linklaters / BCLP — AIFMD II
- PwC Italy — IRES/IRAP
- Footnotes Analyst — EV bridge

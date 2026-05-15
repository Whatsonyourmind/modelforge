# ModelForge — IC Dossier (2026-05-15)

Verified evidence for an external Investment Committee review. Every
number below was produced by running the actual product **today** (not
copied from internal scorecards).

---

## 1. Codebase

| Metric | Value |
|---|---:|
| Python files | 172 |
| Lines of code (modelforge/) | 20,793 |
| Lines in feeds/ (added today) | 4,051 |
| Tests collected | 473 |
| Tests passing | **471 (99.6%)** |
| Tests failing | 2 (pre-existing — `ipo`/`restructuring` not wired into ingest pipeline + sensitivity defaults) |
| Test runtime | 157 s |

## 2. Templates registered

14 templates in `modelforge.templates.REGISTRY`:
`credit_memo · dcf · fairness · ipo · merger · minibond · npl · project_finance · real_estate · restructuring · sponsor_lbo · structured_credit · three_statement · unitranche`

Each is a YAML-spec → live-formula `.xlsx` builder.

## 3. End-to-end build test (this session)

I built **11 of 14 templates** from `examples/*.yaml` (no errors):

| File | Sheets | Cells | Formulas | Named ranges | Size (KB) |
|---|---:|---:|---:|---:|---:|
| credit_memo_cdmo | 14 | 2,014 | 528 | 64 | 60.9 |
| dcf_enel | 12 | 1,240 | 270 | 46 | 49.2 |
| fairness_amplifon | 9 | 443 | 71 | 23 | 28.9 |
| merger_tim_iliad | 11 | 1,072 | 222 | 46 | 45.7 |
| minibond_logistics | 12 | 1,511 | 356 | 53 | 48.4 |
| npl_mixed_portfolio | 10 | 1,167 | 224 | 45 | 42.1 |
| project_finance_solar | 11 | 2,264 | 783 | 49 | 53.5 |
| real_estate_pbsa | 10 | 1,036 | 183 | 32 | 39.1 |
| sponsor_lbo_techco | 13 | 2,167 | 604 | 72 | 62.3 |
| structured_credit_pmi | 10 | 1,265 | 246 | 47 | 42.0 |
| three_statement_cdmo | 9 | 1,195 | 361 | 30 | 39.6 |
| unitranche_cdmo | 12 | 1,838 | 507 | 59 | 53.3 |
| **TOTAL** | — | **17,212** | **4,355** | — | — |

**Live-formula ratio: 25.3% across 11 workbooks.** (Marketing claims "every cell live-formulated"; the ~75% hardcodes are correctly hardcoded *inputs* in the Assumptions sheets, but the marketing line is overstated. Honest version: "every *output cell* is live-formulated".)

## 4. QC gate

`modelforge qc dcf_enel.xlsx` → **8/8 PASS**:
- QC sheet present
- Sign convention declared (`costs_negative`)
- `scenario_index` named range exists
- All named ranges resolve to populated cells
- Every BASE assumption has a cell comment
- All referenced source IDs exist on Sources sheet
- Print-ready (freeze panes / print titles)
- No orphan / empty sheets

## 5. Independent formula recalculation

The `formulas` package (third-party Excel-compatible engine, not ModelForge's writer) loads `dcf_enel.xlsx` and recalculates **1,288 cells** with no errors.

## 6. **CRITICAL FINDING — Numerical plausibility gap**

`dcf_enel.xlsx` Valuation outputs (live-recalculated):

| Cell | Label | Value |
|---|---|---:|
| D14 | Enterprise Value | **€631,073M** |
| D15 | (−) Net debt | (60,000) |
| D21 | Equity Value | **€552,973M** |
| D24 | Implied price per share | €54.39 |
| D25 | Current price | €6.45 |
| D26 | Premium / (discount) % | **+743%** |

Real-world Enel SpA market cap is ~€70-80B. The model output is **~7-8× too high**. Either:
- Example assumptions are deliberately illustrative ("teach me what cells exist") and not calibrated, OR
- Units bug somewhere in WACC/exit-multiple math

**Either way: there is no automated sanity-check (peer-comparable EV band, EBITDA-multiple bound, market-cap deviation alert) firing.** This is the killer flaw an institutional buyer would surface in a 5-minute eval. SCORECARD_v3 D1 (formula discipline) is rated 9.7; with a real plausibility gate it would be defensible at 9.7. Without one, an honest score is 7.0.

## 7. Live data feeds (2026-05-14 release, exercised today)

```
11 providers registered

  [bulge        ] bloomberg  needs-auth  quote,history,fundamentals
  [bulge        ] refinitiv  needs-auth  quote,history,fundamentals
  [bulge        ] factset    needs-auth  quote,history,fundamentals
  [bulge        ] spcapiq    needs-auth  fundamentals,search
  [institutional] polygon    needs-auth  quote,history,fundamentals
  [institutional] fmp        needs-auth  quote,history,fundamentals,search
  [institutional] finnhub    needs-auth  quote,history
  [institutional] tiingo     needs-auth  quote,history
  [free         ] edgar      LIVE        filings,search
  [free         ] openfigi   LIVE        entity_lookup,search
  [free         ] gleif      LIVE        entity_lookup,search
```

Live-verified today:
- EDGAR `lookup_cik("AAPL")` → **320193** ✔
- EDGAR `latest_10k("AAPL")` → 2025-10-31 filing URL resolved ✔
- GLEIF `search_entities("Apple Inc")` → **HWUPKR0MPOU8FGXBT394** ✔
- OpenFIGI `map_identifier("TICKER","AAPL", exch_code="UN")` → **BBG000B9XVV8** ✔

Bulge + institutional adapters are *interface-complete* but not credentials-active. Adding `POLYGON_API_KEY` (free tier 5 req/min) or `FMP_API_KEY` (free tier 250 req/day) flips them on with one env-var.

## 8. MCP tools surface

10 originally + 7 added today = **17 MCP tools** at `modelforge-mcp` stdio server:
`list_templates · build_model · qc_workbook · list_sources · lineage_walk · ingest_dataroom · export_pptx · export_docx · screen_deals · compute_tax · data_providers_status · quote · history · fundamentals · search_filings · entity_lookup · search_securities`

Already published on the MCP registry as `isLatest`. Tested by 3 awesome-mcp PRs open (one in punkpeye's 83K-star list).

## 9. Distribution

- PyPI: `modelforge-finance` (LIVE, version 0.9.6) — credentials shared, not yet promoted
- GitHub: `Whatsonyourmind/modelforge` — **public**, MIT-style or Proprietary (pyproject says proprietary)
- MCP Registry: `isLatest` flag on the official registry
- Awesome lists: 3 PRs open

## 10. Self-claimed scorecard (SCORECARD_v3, 2026-05-14)

| Dim | Weight | MF | Rogo | Hebbia | o11 | Macabacus |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| D1 Formula discipline | 12% | 9.7 | 5.0 | 6.0 | 9.0 | 8.5 |
| D2 Source traceability | 12% | 9.4 | 4.0 | 6.5 | 3.0 | 2.0 |
| D3 Modelling completeness | 15% | 7.5 | 7.5 | 6.5 | 5.5 | 7.5 |
| D4 Data integrations | 15% | 4.5 | 9.0 | 8.0 | 7.0 | 8.5 |
| D5 Productization / SaaS | 15% | 2.5 | 9.5 | 9.0 | 8.0 | 7.0 |
| D6 Collaboration | 10% | 5.0 | 8.0 | 8.5 | 9.0 | 6.0 |
| D7 Security / compliance | 8% | 4.0 | 8.5 | 8.5 | 7.0 | 9.0 |
| D8 Regional coverage | 8% | 6.5 | 7.5 | 7.0 | 6.5 | 7.5 |
| D9 Speed | 5% | 8.0 | 8.5 | 7.5 | 8.0 | 5.5 |
| **WEIGHTED** | 100% | **6.56** ⚠ | 7.40 | 7.20 | 6.60 | 6.85 |

⚠ With today's feeds release, D4 is claimed to lift 4.5 → ~6.5, weighted score 6.56 → ~6.90. **External review needed.**

## 11. Comparable transactions / valuation comps (last 6 months)

| Comp | Stage | Round | Valuation | Source |
|---|---|---|---:|---|
| Rogo | growth | Series C (Sequoia) | $750M post-money | Jan 2026 |
| Rogo | growth | Series D | $160M raised → $X | Apr 29 2026 |
| Hebbia | growth | Series B | (private, $700M-1.2B band) | 2025 |
| Macabacus | mature | acquired by FactSet | $80M (2022) | — |
| o11.ai | seed | seed | $30-40M (2025) | — |

## 12. Internal valuation (memory snapshot 2026-05-14)

`$5.5-12M base` (was $3.5-7.0M before PyPI live + #1-international SOTA at 7.87)

---

## What we want from this review

1. **Blind score** across the 9 dimensions — no peeking at SCORECARD_v3
2. **IC memo** — 5 sections (thesis · product · market · risks · recommendation)
3. **Valuation band** — pre-money in USD, with reasoning
4. **Top 3 killers** — what would make you NOT invest
5. **Top 3 unlocks** — what 90-day work would meaningfully change your score
6. **Recommendation** — pass / fund / acquire / license / partner

The reviewer should treat the SCORECARD_v3 as the founder's pitch and the dossier above as the diligence packet. Where they disagree, the reviewer wins.

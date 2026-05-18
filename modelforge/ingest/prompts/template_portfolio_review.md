# Portfolio Review template — extractor guidance (v0.10 PREVIEW)

Target spec class: `modelforge.spec.portfolio_review.PortfolioReviewSpec`.

⚠️ v0.10 PREVIEW — automated extraction of a portfolio review across N
portcos from raw dataroom documents is NOT recommended. Portfolio reviews
are typically built from existing internal portfolio-monitoring systems
(Allvue, Investran, eFront) which export per-portco data in a structured
form. Use the manual YAML build path.

If you must ingest, point at a single document containing the quarterly
portfolio review committee deck (PDF). The LLM extracts per-portco lines.

## A-id allocation

Portfolio review uses no `Assumption` objects — every value is a
historical or quarter-end fact about a portfolio company.

## Field → source

Per `PortcoLine`:

| Field | Source |
|---|---|
| `portco_id` | Internal fund accounting system (assign PC-001..) |
| `name` | Portco company name (anonymize if external publication) |
| `entry_date`, `entry_leverage`, `entry_ev`, `entry_ebitda` | Original underwriting model |
| `current_leverage`, `current_ebitda_ltm`, `current_revenue_ltm` | Most recent quarterly reporting |
| `plan_ebitda_q`, `actual_ebitda_q` | Original budget vs Q-end actual |
| `covenant_cushion_pct` | Most binding covenant — lowest cushion across the package |
| `next_covenant_test_date` | Loan documentation |
| `cash_trap_active` | Boolean from credit agreement compliance check |
| `rating_internal` | Fund's internal portfolio rating 1-5 |
| `narrative` | Brief MD commentary for IC |

## When to use this template

- Quarterly portfolio committee preparation
- LP quarterly reporting (high-level rollup)
- Annual portfolio review across vintage

## When NOT to use

- New deal underwriting (use sponsor_lbo, unitranche, credit_memo)
- Single-deal monitoring (use the original deal template + revision logs)
- Cross-fund consolidation (build a wrapper — out of v0.10 scope)

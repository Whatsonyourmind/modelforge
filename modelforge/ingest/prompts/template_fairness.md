# Fairness Opinion template — extractor guidance

Target spec class: `modelforge.spec.fairness.FairnessSpec`.

## Shape differs from other templates

Fairness has **lists of structured items** rather than sub-models:

- `trading_comps: list[CompItem]` — public comparables table
- `transaction_comps: list[CompItem]` — precedent transactions table
- `valuation_ranges: list[ValuationRange]` — one row per methodology

The extractor should locate two tables in the data room (analyst
research decks, league-table databases, banker exhibits) and emit them
as item lists. A `target_ebitda_eur_m` assumption is required.

## A-id allocation

- `A-001` — target EBITDA (run-rate used for multiple applications)

## Field → source

| Field | Source |
|---|---|
| `trading_comps[].ev_ebitda_x` | Analyst reports (Goldman / JPM / BAML research) or Bloomberg |
| `transaction_comps[].*` | Dealogic / Mergermarket / FactSet |
| `valuation_ranges[].ev_low / ev_high` | Banker's working footings |
| `current_price_eur` | Market quote at valuation date |

## Football-field conventions

Each methodology's range plus optional implied price + premium.
The sheet sorts methodologies in the order they appear in the spec —
typically: Trading comps, Transaction comps, DCF, LBO, 52-week range.

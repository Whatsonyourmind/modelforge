# IPO template — extractor guidance

Target spec class: `modelforge.spec.ipo.IPOSpec`.

## A-id allocation

- `A-001 – A-049` — DCF inputs (WACC, growth, margins, terminal)
- `A-101 – A-149` — Comparable trading multiples (P/E, EV/EBITDA, EV/Sales)
- `A-201 – A-249` — Precedent transaction multiples
- `A-301 – A-349` — IPO mechanics (offer size, primary/secondary split, greenshoe, discount)

## Canonical IPO conventions

- `ipo_discount_pct`: typical 10-25% discount to fair value at offer
- `primary_secondary_split`: primary funds new growth; secondary cashes out existing holders
- `greenshoe_pct`: typically 15% over-allotment option for stabilizing manager
- `lock_up_days`: typical 180 days for insiders, 90 days for institutional

## Comp set hygiene

Comparable trading multiples must include at least 3 names from the same sector,
similar size band (±50% revenue), and same listing market (or comparable disclosure regime).

Precedent transactions: prefer announced/closed deals from last 24 months; document if
older. Strip out outliers (>2σ from median) with a note.

## Section types to extract

- `target` (Target shape — name, sector, country, currency, last-FY revenue/EBITDA)
- `dcf` (DCFInputs — for the income-approach valuation triangulation)
- `comps` (list of CompTradingMultiple — handled as LLM-table)
- `precedents` (list of PrecedentTransaction — handled as LLM-table)

# 3-Statement Corporate template — extractor guidance

Target spec class: `modelforge.spec.three_statement.ThreeStatementSpec`.

## A-id allocation

- `A-001 – A-019` — P&L drivers (revenue growth y1-y5, EBITDA margin y1-y5, D&A %, interest %, tax rate)
- `A-020 – A-039` — BS drivers (DSO, DIO, DPO, capex % revenue, dividend payout)

Opening balance sheet (not assumptions) populated from last historical year audited accounts.

## Field → source

| Field | Source |
|---|---|
| `historical_revenue_eur_m[]` | Audited income statement |
| `historical_ebitda_eur_m[]` | Audited IS + non-cash adjustments |
| `revenue_growth_y{n}` | Management case / equity research |
| `ebitda_margin_y{n}` | Management case |
| `receivables_days`, `inventory_days`, `payables_days` | Historical WC turnover |
| `capex_pct_revenue` | Management guidance or sector benchmark |
| `opening_bs.*` | Last historical year audited BS |

BS tie: `TOTAL ASSETS = TOTAL L&E` must hold every year. QC check automatic.

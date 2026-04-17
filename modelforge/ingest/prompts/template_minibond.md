# Minibond template — extractor guidance

Target spec class: `modelforge.spec.minibond.MinibondSpec`.

## A-id allocation

- `A-001 – A-029` — issuer operating drivers (revenue, margin, D&A, capex, NWC, tax)
- `A-030 – A-049` — bond structure (notional, coupon, tenor, amort, arrangement, make-whole)
- `A-050 – A-069` — covenants (leverage, ICR thresholds by year)
- `A-070 – A-079` — investor adjustments (withholding tax, transaction costs)

## Field → typical source

| Field | Source |
|---|---|
| `bond_notional` | Press release, term sheet, ExtraMOT Pro listing |
| `fixed_coupon` | Term sheet |
| `arrangement_fee_pct`, `make_whole_pct` | Term sheet |
| `withholding_tax_pct` | Italian tax code (12.5% for minibond unlisted, 26% otherwise) |
| `transaction_cost_bps` | Investor fee schedule |

Italian minibond norm: 5-7y tenor, 5-7% coupon, €5-25M notional, ExtraMOT Pro.

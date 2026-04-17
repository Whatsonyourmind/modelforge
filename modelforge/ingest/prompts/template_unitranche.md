# Unitranche LBO template — extractor guidance

Target spec class: `modelforge.spec.unitranche.UnitrancheSpec`.

## A-id allocation

- `A-001 – A-029` — operating drivers (revenue growth / EBITDA margin by year, D&A %, tax rate, capex splits, NWC)
- `A-030 – A-049` — debt (amount, margin bps, floor, arrangement fee, commitment fee, OID, reference rate)
- `A-050 – A-059` — cash sweep + covenants
- `A-060 – A-079` — covenant thresholds by year (leverage + ICR, one each per projection year)
- `A-080 – A-089` — exit (multiple, hold period, target equity IRR)

## Field → typical source type

| Field | Typical source |
|---|---|
| `revenue_growth_y{n}` | Management case in IM / CIM |
| `ebitda_margin_y{n}` | FY actuals + management case |
| `senior_unitranche_amount` | Term sheet |
| `senior_unitranche_margin_bps` | Term sheet or BB private-credit pricing survey |
| `euribor_6m_rate` | ECB SDW or Bloomberg |
| `cash_sweep_pct` / `cash_sweep_trigger` | Term sheet |
| `leverage_threshold_y{n}` | Covenant schedule |
| `icr_threshold_y{n}` | Covenant schedule |
| `effective_tax_rate` | PwC/EY Italy tax guide (~0.28) |

## Notes

- Sign convention: costs NEGATIVE. `opex_pct_revenue` is POSITIVE (the downstream formula applies the minus).
- `margin_bps` always a positive integer.
- Unitranche = single senior tranche; multi-tranche spec uses a list of tranches.

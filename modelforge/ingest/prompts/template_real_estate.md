# Real Estate template — extractor guidance

Target spec class: `modelforge.spec.real_estate.RealEstateSpec`.

## A-id allocation

- `A-001 – A-019` — property (acquisition price, lettable area, rent, vacancy, indexation, opex, capex)
- `A-020 – A-039` — financing (LTV, senior rate, arrangement fee, covenant ICR)
- `A-040 – A-049` — exit (cap rate, transaction costs)
- `A-050 – A-079` — LP/GP waterfall (tier hurdles + shares, typically 4 tiers)

## Field → source mapping

| Field | Source |
|---|---|
| `acquisition_price_eur_m` | SPA or offering document |
| `lettable_area_sqm` | Building technical docs |
| `rent_eur_sqm_year1` | Rent roll or appraiser valuation |
| `exit_cap_rate` | Market cap rate surveys (CBRE / JLL / Savills) |
| `ltv_pct`, `senior_interest_rate` | Term sheet |
| `tier{n}_hurdle`, `tier{n}_lp_share` | Waterfall in SPA / JV agreement |

Italian PBSA / build-to-rent common exit caps: 4.5-5.5%.

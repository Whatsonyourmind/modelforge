# NPL template — extractor guidance

Target spec class: `modelforge.spec.npl.NPLSpec`.

## A-id allocation

- `A-001 – A-009` — portfolio (GBV, purchase price % GBV, secured/unsecured split)
- `A-010 – A-029` — collection curves (cumulative % by year, typically 10y)
- `A-030 – A-049` — servicing fees (servicing %, setup, legal, data tape)
- `A-050 – A-069` — capital stack (senior/mezz note %, rates)
- `A-070` — effective tax rate

## Field → source

| Field | Source |
|---|---|
| `gbv_eur_m`, `purchase_price_pct_gbv` | Data tape + offer letter |
| `secured_pct_gbv`, `unsecured_pct_gbv` | Data tape |
| `cum_col_y{n}` | Underwriting model or servicer track record |
| `servicing_fee_pct_collections`, `setup_fee_pct_gbv` | Servicing agreement |
| `senior_note_rate`, `mezz_note_rate` | Term sheet |

Italian NPL market: typical secured/unsecured split 60/40; recovery 30-40% of GBV on secured.

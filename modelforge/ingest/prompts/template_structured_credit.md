# Structured Credit template — extractor guidance

Target spec class: `modelforge.spec.structured_credit.StructuredCreditSpec`.

## A-id allocation

- `A-001 – A-009` — collateral pool (face value, WAL)
- `A-010 – A-019` — default / recovery / prepayment assumptions
- `A-020 – A-039` — tranche structure (senior/mezz/junior/equity attach/detach/coupon)
- `A-040` — servicing fee
- `A-050` — effective tax rate

## Field → source

| Field | Source |
|---|---|
| `face_value_eur_m`, `wal_years` | Transaction prospectus |
| `def_y{n}` | Rating-agency base case or issuer stress |
| `recovery_pct_on_default` | Historical servicer data |
| `prepayment_rate_annual` | CPR assumption in prospectus |
| `senior_attach` / `senior_detach` / `senior_coupon` | Term sheet |

GACS-compliant Italian NPL securitizations: senior usually 50-75% detach, minimum BBB rating.

# Project Finance template — extractor guidance

Target spec class: `modelforge.spec.project_finance.ProjectFinanceSpec`.

## A-id allocation

Assign Assumption IDs from these ranges so they don't collide:

- `A-001 – A-009` — construction (capex, phasing, commitment fee)
- `A-010 – A-019` — operating (revenue, opex, indexation, MMRA)
- `A-020 – A-029` — debt (amount, rate, margin, fees)
- `A-030 – A-059` — covenant thresholds by year (one per operating year)
- `A-060 – A-069` — covenant lock-up + misc
- `A-070 – A-079` — equity (target IRR, tax rate)
- `A-080 – A-089` — DSCR target sizing (v0.3 fields)

## Horizon rules

- `construction_years`: 1-5. Most Italian solar PF deals are 2 years (site prep + installation/COD).
- `operating_years`: 5-30. Italian FER X solar typically 20 years.

## Debt sizing — v0.3 capability

If the data room contains a term sheet with explicit DSCR covenants and amortization profile, set:

```yaml
debt:
  amortization_profile: sculpted_dscr_target   # or sculpted_level_debt_service / linear / bullet
  debt_sizing_mode: dscr_target                 # or fixed_amount
  target_dscr_base:
    { id: A-080, name: target_dscr_base, ..., base: 1.30, ... }
```

The downstream solver will back-solve senior amount from the target DSCR. The `amount` field is treated as a CAP in dscr_target mode.

## Sign conventions for PF

- `opex_pct_revenue` must be POSITIVE (e.g. 0.22 for 22% — the downstream formula applies the minus).
- `commitment_fee_bps` positive integer.
- `margin_bps` positive integer.

## Common field → source mappings

| Field | Typical source type |
|---|---|
| `total_capex_eur_m` | Press release / IM |
| `capex_phasing_pct_y{n}` | IM section on phasing |
| `revenue_yr1` | IM + tariff report + irradiation benchmark |
| `revenue_indexation_pct` | IM (usually 1.5-2.0% for CPI-linked tariffs) |
| `opex_pct_revenue` | IM operations section or industry benchmark |
| `senior_amount` | Press release or term sheet |
| `reference_rate` | ECB SDW / Bloomberg |
| `margin_bps` | Term sheet or PF pricing survey |
| `arrangement_fee_pct` | Term sheet |
| `dscr_op{n}` | Term sheet covenant schedule |
| `effective_tax_rate` | PwC/EY Italian tax guide (usually 0.279 = IRES+IRAP) |
| `target_irr` | IM equity section or sector benchmark |

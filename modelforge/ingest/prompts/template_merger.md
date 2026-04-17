# M&A Merger template — extractor guidance

Target spec class: `modelforge.spec.merger.MergerSpec`.

## A-id allocation

- `A-001 – A-009` — deal structure (offer premium, cash mix, financing rate, tax rate)
- `A-100 – A-109` — synergies (revenue run-rate, cost run-rate, Y1 realization %, integration cost)

## Field → source

| Field | Source |
|---|---|
| `acquirer.*` | Acquirer 10-K / annual report |
| `target_financials.*` | Target 10-K / annual report |
| `offer_premium_pct` | Press release on deal announcement |
| `cash_mix_pct` | Deal press release / Joint proxy statement |
| `financing_rate_pct` | Acquisition facility term sheet |
| `revenue_synergies_eur_m`, `cost_synergies_eur_m` | Deal presentation (usually disclosed run-rate) |
| `synergy_realization_y1_pct` | Deal presentation / consensus synergy ramp |
| `integration_cost_eur_m` | Deal presentation or sector benchmark (5-15% of deal value) |

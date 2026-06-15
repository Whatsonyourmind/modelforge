# Development RE template — extractor guidance

Target spec class: `modelforge.spec.development_re.DevelopmentRESpec`.

Ground-up development underwriting: phased capex, a permit / construction /
lease-up timeline (in MONTHS), an S-curve lease-up to stabilisation, a
forward-NOI cap-rate exit, pro-rata loan-to-cost senior debt with construction
interest capitalised, and a European whole-fund LP/GP promote waterfall. Two
revenue kinds are supported: `pbsa` (beds × rent_per_bed_year) and `generic`
(lettable_sqm × rent_sqm_year × (1 − vacancy)).

## A-id allocation

- `A-001 – A-009` — capex (acquisition, hard, soft, FF&E, other dev charges, contingency %)
- `A-010 – A-019` — revenue (beds + rent/bed + operator floor occ, OR lettable_sqm + rent/sqm + vacancy; plus opex/unit and NOI growth)
- `A-020 – A-029` — capital (equity %, senior all-in rate, arrangement fee %, optional public grant amount)
- `A-030 – A-039` — exit (cap rate on forward NOI, selling costs %)
- `A-040 – A-049` — LP/GP waterfall (lp_capital_commitment_pct + tier hurdles/shares, typically 4 tiers)
- `A-050` — discount rate (equity NPV)

## Field → source mapping

| Field | Source |
|---|---|
| `capex.acquisition_eur_m`, `hard_costs_eur_m`, `soft_costs_eur_m`, `ffe_eur_m` | Development appraisal / cost plan / QS report |
| `capex.contingency_pct` | Cost plan (development standard ~6%) |
| `timeline.permit_months`, `construction_months`, `leaseup_months`, `hold_total_months` | Programme / development schedule |
| `revenue.beds`, `rent_per_bed_year` (PBSA) | Rent roll / operator nominations agreement |
| `revenue.lettable_sqm`, `rent_sqm_year`, `vacancy_pct` (generic) | Letting schedule / valuation |
| `revenue.rev_growth_pct` | Market rent-growth note |
| `exit.exit_cap_rate` | Market cap rate surveys (CBRE / JLL / Savills) |
| `capital.equity_pct`, `senior_rate_all_in`, `arrangement_fee_pct` | Development finance term sheet |
| `capital.public_grant_amount`, `grant_name` | Grant award letter (keep `grant_name` generic) |
| `tier{n}` hurdles / shares | Waterfall in JV / LPA |

## Notes

- The timeline is expressed in MONTHS; delivery = permit_months + construction_months and the asset is sold (exit) at hold_total_months (must exceed delivery).
- Prime living / PBSA exit caps are commonly 4.5–5.5%; development senior all-in typically 5–6% at 50–60% loan-to-cost.
- `grant_name` is a GENERIC display string (e.g. "Public development grant") — never a jurisdiction-specific programme name.

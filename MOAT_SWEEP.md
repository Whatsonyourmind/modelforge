# MOAT_SWEEP — moat-gate scoreboard across 14 templates

**Generated**: 2026-05-15  
**Tool**: `scripts/moat_sweep.py`  
**Pass rate**: **8/14** templates pass all 4 moat gates

## Per-template scoreboard

| File | Template | All Pass | Density | Magic# | No Orphans | Recalc | Avg core density | Failing sheets | # orphans |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|---|:-:|
| credit_memo_cdmo | credit_memo | n | n | Y | n | Y | 94% | DebtSchedule: 74% | 8 |
| dcf_enel | dcf | Y | Y | Y | Y | Y | 96% | — | 0 |
| fairness_amplifon | fairness | Y | Y | Y | Y | Y | — | — | 4 |
| merger_tim_iliad | merger | n | n | Y | n | Y | 79% | DealStructure: 69%; ProForma: 89% | 9 |
| minibond_logistics | minibond | Y | Y | Y | Y | Y | 98% | — | 0 |
| npl_mixed_portfolio | npl | n | n | Y | Y | Y | 84% | CollectionWaterfall: 84% | 5 |
| project_finance_solar | project_finance | Y | Y | Y | Y | Y | 100% | — | 2 |
| real_enfinity_solar_pf | project_finance | Y | Y | Y | Y | Y | 100% | — | 3 |
| real_estate_pbsa | real_estate | n | Y | Y | n | Y | — | — | 8 |
| real_stevanato_3statement | three_statement | Y | Y | Y | Y | Y | — | — | 0 |
| sponsor_lbo_techco | sponsor_lbo | n | n | Y | n | Y | 91% | DebtSchedule: 71% | 10 |
| structured_credit_pmi | structured_credit | Y | Y | Y | Y | Y | — | — | 5 |
| three_statement_cdmo | three_statement | Y | Y | Y | Y | Y | — | — | 0 |
| unitranche_cdmo | unitranche | n | n | Y | n | Y | 92% | DebtSchedule: 74% | 7 |

## Per-template gap details

### credit_memo_cdmo (credit_memo)
- **Density gaps**: DebtSchedule: 74%
- **Orphan named ranges** (8): `advisory_fees_eur_m`, `expected_hold_years`, `legal_fees_eur_m`, `make_whole_pct`, `other_fees_eur_m`, `recovery_timeline_years`, `senior_unitranche_commitment_fee`, `senior_unitranche_oid`

### merger_tim_iliad (merger)
- **Density gaps**: DealStructure: 69%, ProForma: 89%
- **Orphan named ranges** (9): `asset_writeup_ppe`, `asset_writeup_ppe_eur_m`, `intangibles_customer_list`, `intangibles_customer_list_eur_m`, `intangibles_technology`, `intangibles_technology_eur_m`, `intangibles_trade_name`, `intangibles_trade_name_eur_m`, `target_bv_equity_eur_m`

### npl_mixed_portfolio (npl)
- **Density gaps**: CollectionWaterfall: 84%
- **Orphan named ranges** (5): `ecl_gdp_growth_base`, `ecl_gdp_growth_downside`, `ecl_gdp_growth_upside`, `effective_tax_rate`, `unsecured_pct_gbv`

### real_estate_pbsa (real_estate)
- **Orphan named ranges** (8): `arrangement_fee_pct`, `tier1_hurdle`, `tier1_lp_share`, `tier2_hurdle`, `tier2_lp_share`, `tier3_hurdle`, `tier3_lp_share`, `tier4_lp_share`

### sponsor_lbo_techco (sponsor_lbo)
- **Density gaps**: DebtSchedule: 71%
- **Orphan named ranges** (10): `advisory_fees_eur_m`, `cash_sweep_trigger`, `exit_year_input`, `expected_hold_years`, `legal_fees_eur_m`, `make_whole_pct`, `other_fees_eur_m`, `purchase_price_eur_m`, `senior_unitranche_commitment_fee`, `senior_unitranche_oid`

### unitranche_cdmo (unitranche)
- **Density gaps**: DebtSchedule: 74%
- **Orphan named ranges** (7): `advisory_fees_eur_m`, `expected_hold_years`, `legal_fees_eur_m`, `make_whole_pct`, `other_fees_eur_m`, `senior_unitranche_commitment_fee`, `senior_unitranche_oid`

---

## How to use this report

1. **Density gaps** mean a core output sheet has hardcoded numeric cells where the analyst expects formulas. Fix by replacing literals with formula references to named ranges.
2. **Orphan named ranges** mean assumptions are defined in the spec but no formula uses them. Fix by either wiring the assumption into a formula or removing it from the spec.
3. **Magic-number** failures mean a formula contains a numeric literal that's not 0/1/12/100/1000-class. Fix by extracting the literal to a named-range assumption.
4. **Recalculation** failures mean the third-party `formulas` engine can't reproduce the workbook's cached values — usually a cross-sheet reference or named-range scope issue.

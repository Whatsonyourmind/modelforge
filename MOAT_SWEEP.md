# MOAT_SWEEP — moat-gate scoreboard across 14 templates

**Generated**: 2026-05-15  
**Tool**: `scripts/moat_sweep.py`  
**Pass rate**: **14/14** templates pass all 4 moat gates

## Per-template scoreboard

| File | Template | All Pass | Density | Magic# | No Orphans | Recalc | Avg core density | Failing sheets | # orphans |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|---|:-:|
| credit_memo_cdmo | credit_memo | Y | Y | Y | Y | Y | 99% | — | 3 |
| dcf_enel | dcf | Y | Y | Y | Y | Y | 96% | — | 0 |
| fairness_amplifon | fairness | Y | Y | Y | Y | Y | — | — | 4 |
| merger_tim_iliad | merger | Y | Y | Y | Y | Y | 96% | — | 0 |
| minibond_logistics | minibond | Y | Y | Y | Y | Y | 98% | — | 0 |
| npl_mixed_portfolio | npl | Y | Y | Y | Y | Y | 100% | — | 5 |
| project_finance_solar | project_finance | Y | Y | Y | Y | Y | 100% | — | 2 |
| real_enfinity_solar_pf | project_finance | Y | Y | Y | Y | Y | 100% | — | 3 |
| real_estate_pbsa | real_estate | Y | Y | Y | Y | Y | — | — | 0 |
| real_stevanato_3statement | three_statement | Y | Y | Y | Y | Y | — | — | 0 |
| sponsor_lbo_techco | sponsor_lbo | Y | Y | Y | Y | Y | 97% | — | 5 |
| structured_credit_pmi | structured_credit | Y | Y | Y | Y | Y | — | — | 5 |
| three_statement_cdmo | three_statement | Y | Y | Y | Y | Y | — | — | 0 |
| unitranche_cdmo | unitranche | Y | Y | Y | Y | Y | 98% | — | 2 |

## Per-template gap details

---

## How to use this report

1. **Density gaps** mean a core output sheet has hardcoded numeric cells where the analyst expects formulas. Fix by replacing literals with formula references to named ranges.
2. **Orphan named ranges** mean assumptions are defined in the spec but no formula uses them. Fix by either wiring the assumption into a formula or removing it from the spec.
3. **Magic-number** failures mean a formula contains a numeric literal that's not 0/1/12/100/1000-class. Fix by extracting the literal to a named-range assumption.
4. **Recalculation** failures mean the third-party `formulas` engine can't reproduce the workbook's cached values — usually a cross-sheet reference or named-range scope issue.

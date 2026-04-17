# Reverse-engineering report — unitranche_cdmo.xlsx

**Detected template type:** `unitranche` (confidence 100%)

## Template-match scores

| Template | Score |
|---|---|
| unitranche | 100% |
| credit_memo | 100% |
| minibond | 100% |
| project_finance | 100% |
| structured_credit | 100% |
| three_statement | 100% |
| merger | 100% |
| real_estate | 86% |
| dcf | 83% |
| npl | 80% |
| fairness | 80% |

## Sheet analysis

| Sheet | Kind | Rows × Cols | Formulas | Inputs |
|---|---|---|---|---|
| Cover | `cover` | 32 × 12 | 1 | 1 |
| Sources | `sources` | 14 × 8 | 0 | 9 |
| Assumptions | `assumptions` | 52 × 12 | 47 | 141 |
| OperatingModel | `operating` | 44 × 13 | 140 | 10 |
| DebtSchedule | `debt` | 23 × 13 | 96 | 25 |
| Covenants | `covenants` | 20 × 13 | 64 | 0 |
| Returns | `returns` | 11 × 12 | 12 | 0 |
| QC | `qc` | 18 × 13 | 103 | 0 |
| SensitivityAnalysis | `sensitivity` | 16 × 11 | 23 | 36 |
| MonteCarlo | `monte_carlo` | 51 × 3 | 11 | 99 |
| Reproducibility | `metadata` | 11 × 3 | 1 | 0 |

## Named ranges (54)

| Name | Attr |
|---|---|
| `advisory_fees_eur_m` | `'Assumptions'!$I$49` |
| `cash_sweep_pct` | `'Assumptions'!$I$32` |
| `cash_sweep_trigger` | `'Assumptions'!$I$33` |
| `da_pct_revenue` | `'Assumptions'!$I$20` |
| `ebitda_margin_y1` | `'Assumptions'!$I$13` |
| `ebitda_margin_y2` | `'Assumptions'!$I$14` |
| `ebitda_margin_y3` | `'Assumptions'!$I$15` |
| `ebitda_margin_y4` | `'Assumptions'!$I$16` |
| `ebitda_margin_y5` | `'Assumptions'!$I$17` |
| `ebitda_margin_y6` | `'Assumptions'!$I$18` |
| `ebitda_margin_y7` | `'Assumptions'!$I$19` |
| `effective_tax_rate` | `'Assumptions'!$I$24` |
| `euribor_6m_rate` | `'Assumptions'!$I$31` |
| `expected_hold_years` | `'Assumptions'!$I$51` |
| `growth_capex_pct_revenue` | `'Assumptions'!$I$22` |
| `icr_threshold_y1` | `'Assumptions'!$I$41` |
| `icr_threshold_y2` | `'Assumptions'!$I$42` |
| `icr_threshold_y3` | `'Assumptions'!$I$43` |
| `icr_threshold_y4` | `'Assumptions'!$I$44` |
| `icr_threshold_y5` | `'Assumptions'!$I$45` |
| `icr_threshold_y6` | `'Assumptions'!$I$46` |
| `icr_threshold_y7` | `'Assumptions'!$I$47` |
| `legal_fees_eur_m` | `'Assumptions'!$I$48` |
| `leverage_threshold_y1` | `'Assumptions'!$I$34` |
| `leverage_threshold_y2` | `'Assumptions'!$I$35` |
| `leverage_threshold_y3` | `'Assumptions'!$I$36` |
| `leverage_threshold_y4` | `'Assumptions'!$I$37` |
| `leverage_threshold_y5` | `'Assumptions'!$I$38` |
| `leverage_threshold_y6` | `'Assumptions'!$I$39` |
| `leverage_threshold_y7` | `'Assumptions'!$I$40` |
| `maintenance_capex_pct_revenue` | `'Assumptions'!$I$21` |
| `make_whole_pct` | `'Assumptions'!$I$52` |
| `mf_build_timestamp` | `'Reproducibility'!$B$8` |
| `mf_python_version` | `'Reproducibility'!$B$7` |
| `mf_spec_sha256` | `'Reproducibility'!$B$5` |
| `mf_spec_source` | `'Reproducibility'!$B$9` |
| `mf_version` | `'Reproducibility'!$B$6` |
| `nwc_pct_revenue_delta` | `'Assumptions'!$I$23` |
| `other_fees_eur_m` | `'Assumptions'!$I$50` |
| `primary_output` | `'Returns'!$D$9` |
| ... | *(+14 more)* |

## Extracted inputs (56)

| Sheet | Cell | Label | Value |
|---|---|---|---|
| Assumptions | F6 | A-001 | 0.03 |
| Assumptions | F7 | A-002 | 0.02 |
| Assumptions | F8 | A-003 | 0.02 |
| Assumptions | F9 | A-004 | 0.01 |
| Assumptions | F10 | A-005 | 0.01 |
| Assumptions | F11 | A-006 | 0.01 |
| Assumptions | F12 | A-007 | 0.01 |
| Assumptions | F13 | A-011 | 0.18 |
| Assumptions | F14 | A-012 | 0.19 |
| Assumptions | F15 | A-013 | 0.19 |
| Assumptions | F16 | A-014 | 0.19 |
| Assumptions | F17 | A-015 | 0.19 |
| Assumptions | F18 | A-016 | 0.18 |
| Assumptions | F19 | A-017 | 0.18 |
| Assumptions | F20 | A-020 | 0.06 |
| Assumptions | F21 | A-021 | 0.045 |
| Assumptions | F22 | A-022 | 0.02 |
| Assumptions | F23 | A-023 | 0.18 |
| Assumptions | F24 | A-024 | 0.28 |
| Assumptions | F25 | A-031 | 38.0 |
| Assumptions | F26 | A-032 | 675.0 |
| Assumptions | F27 | A-033 | 0.0 |
| Assumptions | F28 | A-034 | 0.025 |
| Assumptions | F29 | A-035 | 0.0 |
| Assumptions | F30 | A-036 | 0.0 |
| Assumptions | F31 | A-030 | 0.036 |
| Assumptions | F32 | A-080 | 0.75 |
| Assumptions | F33 | A-081 | 3.0 |
| Assumptions | F34 | A-040 | 5.25 |
| Assumptions | F35 | A-041 | 5.0 |
| Assumptions | F36 | A-042 | 4.75 |
| Assumptions | F37 | A-043 | 4.5 |
| Assumptions | F38 | A-044 | 4.25 |
| Assumptions | F39 | A-045 | 4.0 |
| Assumptions | F40 | A-046 | 4.0 |
| Assumptions | F41 | A-050 | 1.75 |
| Assumptions | F42 | A-051 | 1.85 |
| Assumptions | F43 | A-052 | 2.0 |
| Assumptions | F44 | A-053 | 2.0 |
| Assumptions | F45 | A-054 | 2.0 |
| Assumptions | F46 | A-055 | 2.0 |
| Assumptions | F47 | A-056 | 2.0 |
| Assumptions | F48 | A-060 | 0.35 |
| Assumptions | F49 | A-061 | 0.2 |
| Assumptions | F50 | A-062 | 0.15 |
| Assumptions | F51 | A-070 | 5.0 |
| Assumptions | F52 | A-071 | 0.02 |
| OperatingModel | D9 | Revenue | 35.0 |
| OperatingModel | D12 | EBITDA margin % | 0.2 |
| OperatingModel | D13 | EBITDA | 7.0 |
| ... | *(+6 more — see spec skeleton)* |

## Next steps

1. Review the spec skeleton output (write via `--spec-out`).
2. Fill in sources, meta, target from the original workbook's cover.
3. Run `modelforge build <spec.yaml>` to emit a ModelForge-native workbook.
4. Compare with original using `modelforge diff original.xlsx new.xlsx`.
# ModelForge Public Benchmark — Results

Scored 12 artifact(s). Protocol: benchmarks/PROTOCOL.md (pre-registered). Ground truth: benchmarks/harness/ground_truth.py.

ModelForge version (arm A): `0.11.4`

## dcf_industrial

| artifact | arm | m1 errors | m2 headline acc | m3 hardcode | m5 lineage | m6 complete | recalc |
|---|---|---|---|---|---|---|---|
| dcf_industrial__armA__run1.xlsx | A | 0 | 100% | 42.1% | yes | 100% | ok |
| dcf_industrial__armB__run1.xlsx | B | 0 | 100% | 0.5% | yes | 100% | ok |
| dcf_industrial__armB__run2.xlsx | B | 0 | 100% | 0.0% | yes | 100% | ok |
| dcf_industrial__armB__run3.xlsx | B | 0 | 100% | 0.5% | yes | 100% | ok |

<details><summary>headline detail</summary>

| artifact | headline | got | expected | pass |
|---|---|---|---|---|
| dcf_industrial__armA__run1.xlsx | wacc | 0.0811875 | 0.0811875 | PASS |
| dcf_industrial__armA__run1.xlsx | enterprise_value | 1509.97 | 1509.97 | PASS |
| dcf_industrial__armA__run1.xlsx | equity_value | 1259.97 | 1259.97 | PASS |
| dcf_industrial__armA__run1.xlsx | implied_price_per_share | 8.39979 | 8.39979 | PASS |
| dcf_industrial__armB__run1.xlsx | wacc | 0.0811875 | 0.0811875 | PASS |
| dcf_industrial__armB__run1.xlsx | enterprise_value | 1509.97 | 1509.97 | PASS |
| dcf_industrial__armB__run1.xlsx | equity_value | 1259.97 | 1259.97 | PASS |
| dcf_industrial__armB__run1.xlsx | implied_price_per_share | 8.39979 | 8.39979 | PASS |
| dcf_industrial__armB__run2.xlsx | wacc | 0.0811875 | 0.0811875 | PASS |
| dcf_industrial__armB__run2.xlsx | enterprise_value | 1509.97 | 1509.97 | PASS |
| dcf_industrial__armB__run2.xlsx | equity_value | 1259.97 | 1259.97 | PASS |
| dcf_industrial__armB__run2.xlsx | implied_price_per_share | 8.39979 | 8.39979 | PASS |
| dcf_industrial__armB__run3.xlsx | wacc | 0.0811875 | 0.0811875 | PASS |
| dcf_industrial__armB__run3.xlsx | enterprise_value | 1509.97 | 1509.97 | PASS |
| dcf_industrial__armB__run3.xlsx | equity_value | 1259.97 | 1259.97 | PASS |
| dcf_industrial__armB__run3.xlsx | implied_price_per_share | 8.39979 | 8.39979 | PASS |

</details>

## lbo_us_saas

| artifact | arm | m1 errors | m2 headline acc | m3 hardcode | m5 lineage | m6 complete | recalc |
|---|---|---|---|---|---|---|---|
| lbo_us_saas__armA__run1.xlsx | A | 0 | 100% | 22.3% | yes | 100% | ok |
| lbo_us_saas__armB__run1.xlsx | B | 0 | 100% | 10.0% | yes | 100% | ok |
| lbo_us_saas__armB__run2.xlsx | B | 0 | 100% | 0.0% | yes | 100% | ok |
| lbo_us_saas__armB__run3.xlsx | B | 0 | 100% | 8.8% | yes | 100% | ok |

<details><summary>headline detail</summary>

| artifact | headline | got | expected | pass |
|---|---|---|---|---|
| lbo_us_saas__armA__run1.xlsx | sponsor_irr | 0.154606 | 0.154606 | PASS |
| lbo_us_saas__armA__run1.xlsx | sponsor_moic | 2.05196 | 2.05196 | PASS |
| lbo_us_saas__armA__run1.xlsx | exit_equity_proceeds | 358.067 | 358.067 | PASS |
| lbo_us_saas__armA__run1.xlsx | sponsor_equity_cheque | 174.5 | 174.5 | PASS |
| lbo_us_saas__armB__run1.xlsx | sponsor_irr | 0.154606 | 0.154606 | PASS |
| lbo_us_saas__armB__run1.xlsx | sponsor_moic | 2.05196 | 2.05196 | PASS |
| lbo_us_saas__armB__run1.xlsx | exit_equity_proceeds | 358.067 | 358.067 | PASS |
| lbo_us_saas__armB__run1.xlsx | sponsor_equity_cheque | 174.5 | 174.5 | PASS |
| lbo_us_saas__armB__run2.xlsx | sponsor_irr | 0.154606 | 0.154606 | PASS |
| lbo_us_saas__armB__run2.xlsx | sponsor_moic | 2.05196 | 2.05196 | PASS |
| lbo_us_saas__armB__run2.xlsx | exit_equity_proceeds | 358.067 | 358.067 | PASS |
| lbo_us_saas__armB__run2.xlsx | sponsor_equity_cheque | 174.5 | 174.5 | PASS |
| lbo_us_saas__armB__run3.xlsx | sponsor_irr | 0.154606 | 0.154606 | PASS |
| lbo_us_saas__armB__run3.xlsx | sponsor_moic | 2.05196 | 2.05196 | PASS |
| lbo_us_saas__armB__run3.xlsx | exit_equity_proceeds | 358.067 | 358.067 | PASS |
| lbo_us_saas__armB__run3.xlsx | sponsor_equity_cheque | 174.5 | 174.5 | PASS |

</details>

## three_statement_mfg

| artifact | arm | m1 errors | m2 headline acc | m3 hardcode | m5 lineage | m6 complete | recalc |
|---|---|---|---|---|---|---|---|
| three_statement_mfg__armA__run1.xlsx | A | 0 | 100% | 34.6% | yes | 100% | ok |
| three_statement_mfg__armB__run1.xlsx | B | 0 | 67% | 0.0% | yes | 100% | ok |
| three_statement_mfg__armB__run2.xlsx | B | 0 | 67% | 0.0% | yes | 100% | ok |
| three_statement_mfg__armB__run3.xlsx | B | 0 | 100% | 7.9% | no | 100% | ok |

<details><summary>headline detail</summary>

| artifact | headline | got | expected | pass |
|---|---|---|---|---|
| three_statement_mfg__armA__run1.xlsx | final_net_income | 49.3059 | 49.3059 | PASS |
| three_statement_mfg__armA__run1.xlsx | final_total_assets | 529.362 | 529.362 | PASS |
| three_statement_mfg__armA__run1.xlsx | final_total_liabilities_equity | 529.362 | 529.362 | PASS |
| three_statement_mfg__armA__run1.xlsx | final_balance_check | 1.13687e-13 | 1.13687e-13 | PASS |
| three_statement_mfg__armA__run1.xlsx | final_cash | 26.4834 | 26.4834 | PASS |
| three_statement_mfg__armA__run1.xlsx | final_debt | 40 | 40 | PASS |
| three_statement_mfg__armB__run1.xlsx | final_net_income | 49.3059 | 49.3059 | PASS |
| three_statement_mfg__armB__run1.xlsx | final_total_assets | 529.362 | 529.362 | PASS |
| three_statement_mfg__armB__run1.xlsx | final_total_liabilities_equity | 529.362 | 529.362 | PASS |
| three_statement_mfg__armB__run1.xlsx | final_balance_check | 0 | 1.13687e-13 | PASS |
| three_statement_mfg__armB__run1.xlsx | final_cash | 40 | 26.4834 | FAIL |
| three_statement_mfg__armB__run1.xlsx | final_debt | 180 | 40 | FAIL |
| three_statement_mfg__armB__run2.xlsx | final_net_income | 49.3059 | 49.3059 | PASS |
| three_statement_mfg__armB__run2.xlsx | final_total_assets | 529.362 | 529.362 | PASS |
| three_statement_mfg__armB__run2.xlsx | final_total_liabilities_equity | 529.362 | 529.362 | PASS |
| three_statement_mfg__armB__run2.xlsx | final_balance_check | 0 | 1.13687e-13 | PASS |
| three_statement_mfg__armB__run2.xlsx | final_cash | 40 | 26.4834 | FAIL |
| three_statement_mfg__armB__run2.xlsx | final_debt | 180 | 40 | FAIL |
| three_statement_mfg__armB__run3.xlsx | final_net_income | 49.3059 | 49.3059 | PASS |
| three_statement_mfg__armB__run3.xlsx | final_total_assets | 529.362 | 529.362 | PASS |
| three_statement_mfg__armB__run3.xlsx | final_total_liabilities_equity | 529.362 | 529.362 | PASS |
| three_statement_mfg__armB__run3.xlsx | final_balance_check | 0 | 1.13687e-13 | PASS |
| three_statement_mfg__armB__run3.xlsx | final_cash | 26.4834 | 26.4834 | PASS |
| three_statement_mfg__armB__run3.xlsx | final_debt | 40 | 40 | PASS |

</details>

## m4 — reproducibility

### dcf_industrial
- arm A byte-identical double build: **True**
- arm B structural identical across 3 runs: **False**
  - `wacc` cross-run range: 0.00%
  - `enterprise_value` cross-run range: 0.00%
  - `equity_value` cross-run range: 0.00%
  - `implied_price_per_share` cross-run range: 0.00%

### lbo_us_saas
- arm A byte-identical double build: **True**
- arm B structural identical across 3 runs: **False**
  - `sponsor_irr` cross-run range: 0.00%
  - `sponsor_moic` cross-run range: 0.00%
  - `exit_equity_proceeds` cross-run range: 0.00%
  - `sponsor_equity_cheque` cross-run range: 0.00%

### three_statement_mfg
- arm A byte-identical double build: **True**
- arm B structural identical across 3 runs: **False**
  - `final_net_income` cross-run range: 0.00%
  - `final_total_assets` cross-run range: 0.00%
  - `final_total_liabilities_equity` cross-run range: 0.00%
  - `final_balance_check` cross-run range: n/a
  - `final_cash` cross-run range: 38.08%
  - `final_debt` cross-run range: 105.00%

---
*Arm B is a raw frontier-agent + openpyxl baseline — NOT a measurement of any commercial Excel product. See PROTOCOL.md §3 for all honesty caveats.*

*Conflict of interest: the arm-A specs were authored by the ModelForge project, which also built and scored this benchmark (PROTOCOL.md §3.4, §3.6). Arm-B model: claude-opus-4-8 (PROTOCOL.md Deviations D-003). three_statement arm-B m2 sub-100% scores are headline LOCATABILITY under the frozen label-search, not wrong math (D-004). Scorer numpy-coercion fix applied post-arms, coercion-only (D-001).*

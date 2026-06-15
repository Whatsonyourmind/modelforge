# Bank / FIG ingestion guidance

Extract the inputs for a single-entity **bank / financial-institution** model
(Basel III/IV + EU CRR/CRD framework, Standardised-approach fidelity). Source
documents are typically an annual report, a Pillar 3 disclosure, and an
investor presentation.

Map the data room into these spec blocks:

- **target** — bank name (anonymise if required), sector label, country,
  reporting currency, last full-year end date.
- **nii** (net interest income drivers, decimal rates): `loan_yield` (gross
  yield on customer loans), `securities_yield`, `deposit_cost` (blended),
  `wholesale_cost` (senior/MREL funding), `risk_free_rate` (policy anchor).
- **pnl**: `fee_income_growth`, `trading_income_eur_m` (net trading/FV result),
  `cost_income_ratio` (opex / total operating income), `cost_of_risk_bps`
  (impairment charge in bps of gross loans), `tax_rate`, `at1_coupon_eur_m`.
- **balance**: `loan_growth`, `deposit_growth`, `securities_growth`,
  `writeoff_pct_opening_allowance` (annual utilisation of the allowance stock).
- **capital**: `rwa_density` (RWA / risk-bearing assets), `cet1_requirement_ratio`
  (OCR = Pillar 1 + P2R + combined buffers), `target_cet1_ratio`,
  `mda_buffer_pct`, `leverage_min_ratio`, `dividend_payout_ratio`,
  `buyback_target_eur_m`.
- **opening_bs** (last reported balance sheet, EUR m; MUST balance
  A = L + E where common equity = `cet1_eur_m` + `intangibles_eur_m` and the
  loan-loss `allowance_eur_m` is **negative**): gross loans, allowance,
  securities, cash, intangibles, other assets; deposits, wholesale funding,
  other liabilities, CET1, AT1.

Notes:
- The loan-loss `allowance_eur_m` is a contra-asset — record it as a **negative**
  number (e.g. −210 for a 1.5% coverage on €14bn gross loans).
- `cet1_eur_m` is the **regulatory CET1**, not book equity: book common equity
  = CET1 + intangibles. If the report quotes book equity, subtract goodwill &
  intangibles (and any CRR Art. 26-36 deductions) to recover CET1, or put the
  residual in `cet1_regulatory_adjustments_eur_m`.
- Cost of risk is in **basis points** of gross loans (e.g. 45 = 0.45%).
- Sign convention is costs-negative.

Every hardcoded value should be tagged to a Source (S-id) or, where it is an
analyst judgment, an Assumption (A-id) with a non-empty rationale.

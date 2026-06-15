# Loan-tape cash securitization (CLO / RMBS / ABS) ingestion guidance

Extract the inputs for a **cash securitization** driven by a granular,
stratified **loan tape**. Typical source documents are the originator's loan
data tape / stratification report, the offering circular / prospectus (capital
structure, triggers, fees), a rating-agency pre-sale, and a servicer report.

Map the data room into these spec blocks:

- **target** — issuer / SPV name (anonymise if required), collateral-sector
  label, country, currency, last reporting date. Revenue / EBITDA are 0 for an
  SPV.
- **tape** — a list of representative **strata** of the loan tape (group the
  data tape into homogeneous lines; 2–5 strata is typical for a deal cashflow
  model). For each stratum: `balance_eur_m` (current UPB), `wac_pct`
  (weighted-average gross coupon, decimal), `wam_years` (weighted-average
  remaining maturity), `cdr_pct` (annualised constant default rate for that
  stratum, decimal).
- **pool** (pool-wide cashflow drivers, decimals): `cpr_pct` (annual constant
  prepayment rate), `recovery_pct` (recovery on defaulted balance = 1 −
  severity), `servicing_fee_pct` (on the performing balance), `senior_fees_eur_m`
  (fixed trustee / admin fee per period).
- **notes** — the capital structure, ordered **senior → mezzanine → … →
  residual**. The LAST note MUST be the first-loss residual / equity
  certificate (`rating: Equity`, `coupon_pct` base 0). For each note:
  `advance_pct` (initial balance as a % of the initial pool UPB) and
  `coupon_pct`. The `advance_pct` values (debt notes + residual) MUST sum to
  1.0 — the residual note closes the structure to 100% of the pool.
- **enhancement** — `oc_trigger_pct` (required overcollateralisation ratio;
  a breach diverts excess interest to a senior turbo paydown), `ic_trigger_pct`
  (required interest-coverage ratio), `reserve_pct_initial` (cash reserve as a
  % of the initial **pool** balance, funded at close from the residual; at
  maturity it cures any outstanding debt before returning capital to the residual).
- **effective_tax_rate** — SPV tax (Italian legge 130/1999 SPVs are
  tax-neutral → 0).

Notes:
- Rates (WAC, CDR, CPR, recovery, coupons, triggers) are **decimals**
  (0.045 = 4.5%); CDR/CPR are annualised. WAM is in **years**.
- The model amortizes each stratum straight-line to its own WAM with a clean-up
  sweep at the deal's final period, defaults on its own CDR, prepays at the
  pool CPR, and collects recoveries one period after default.
- Sign convention is costs-negative.

Every hardcoded value should be tagged to a Source (S-id) or, where it is an
analyst / agency judgment, an Assumption (A-id) with a non-empty rationale.

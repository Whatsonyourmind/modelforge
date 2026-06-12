# Deal Brief BM-DCF-001 — DCF Valuation of a Generic US Industrial

> **Synthetic benchmark deal.** "IndustrialCo" is a fictional company. All
> numbers are frozen benchmark inputs — they do not describe any real
> company, transaction, or counterparty.
>
> **Task:** build a complete, audit-ready enterprise DCF in Excel from this
> brief alone. Every parameter needed to compute the headline outputs is
> stated below; the brief is solvable unambiguously.

## 1. Target

| Item | Value |
|---|---|
| Company | IndustrialCo (fictional US diversified industrial) |
| Currency / units | USD, millions |
| Last FY revenue (FY0) | 1,000.0 |
| Last FY EBITDA | 180.0 (18.0% margin) |
| Net debt | 250.0 |
| Shares outstanding | 150.0 m |
| Reference share price (for premium/discount display) | $8.00 |

## 2. Forecast (5 explicit years, revenue fade)

| Year | Revenue growth | EBITDA margin |
|---|---|---|
| 1 | 4.0% | 18.0% |
| 2 | 3.5% | 18.0% |
| 3 | 3.0% | 18.0% |
| 4 | 2.5% | 18.0% |
| 5 | 2.0% | 18.0% |

Other drivers (every projection year):

| Driver | Value |
|---|---|
| D&A | 6.0% of revenue (so EBIT margin = 12.0%) |
| Capex | 6.5% of revenue |
| ΔNWC | 10% of Δrevenue (vs prior year; year 1 vs FY0 = 1,000.0) |
| Cash tax rate | 25% on EBIT (EBIT is positive every year) |

Free cash flow to the firm, per year:

```
FCFF_t = EBIT_t × (1 − 25%) + D&A_t − capex_t − ΔNWC_t
```

## 3. WACC build (plain CAPM — no extra premia)

| Component | Value |
|---|---|
| Risk-free rate (10Y UST) | 4.25% |
| Equity risk premium | 5.00% |
| Beta (levered) | 1.10 |
| Cost of equity | 4.25% + 1.10 × 5.00% = **9.75%** |
| Pre-tax cost of debt | 5.75% |
| Tax rate | 25% → after-tax Kd = **4.3125%** |
| Target D/(D+E) | 30% |
| **WACC** | 0.70 × 9.75% + 0.30 × 4.3125% = **8.11875%** |

No country risk premium, no size premium, no company-specific alpha, no
comparable-beta relevering — the CAPM inputs above are final.

## 4. Discounting and terminal value

- **End-of-year discounting.** Full first year. PV exponents are 1, 2, 3, 4, 5.
  No mid-year convention, no stub period, no fade block beyond the explicit
  growth path above.
- **Terminal value: Gordon growth** on a NORMALIZED terminal cash flow with
  terminal growth **g = 2.0%** (note g < risk-free 4.25% < WACC):

```
norm_FCF = NOPAT_5 − ΔNWC_5 × (1 + g)        # capex = D&A in perpetuity
TV       = norm_FCF × (1 + g) / (WACC − g)
PV(TV)   = TV / (1 + WACC)^5
```

## 5. Headline outputs

```
enterprise_value        = Σ_t FCFF_t/(1+WACC)^t  +  PV(TV)
equity_value            = enterprise_value − 250.0 net debt
implied_price_per_share = equity_value / 150.0
wacc                    = 8.11875%
```

No minority interest, pension deficit, preferred equity, leases, or
cross-holdings — the EV→equity bridge is net debt only.

**Headline outputs the model must show (labels required, see PROTOCOL.md):**

1. `wacc` (decimal)
2. `enterprise_value` ($m)
3. `equity_value` ($m)
4. `implied_price_per_share` ($)

## 6. Required model components (completeness checklist)

- Explicit WACC build (component by component)
- FCFF forecast (revenue → EBITDA → EBIT → NOPAT → FCFF)
- Terminal value section (Gordon, with the normalization shown)
- At least one sensitivity table (e.g. WACC × terminal growth)

Ground truth: `benchmarks/harness/ground_truth.py::dcf_industrial()`.

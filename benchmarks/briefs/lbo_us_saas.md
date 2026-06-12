# Deal Brief BM-LBO-001 — Sponsor LBO of a US Enterprise SaaS Company

> **Synthetic benchmark deal.** "SaaSCo" is a fictional company. All numbers
> are frozen benchmark inputs — they do not describe any real company,
> transaction, or counterparty.
>
> **Task:** build a complete, audit-ready sponsor LBO model in Excel from this
> brief alone. Every parameter needed to compute the headline outputs is
> stated below; the brief is solvable unambiguously.

## 1. Target

| Item | Value |
|---|---|
| Company | SaaSCo (fictional US enterprise SaaS) |
| Currency / units | USD, millions |
| Historical revenue (FY-2, FY-1, FY0) | 81.0 / 90.0 / 100.0 |
| Historical EBITDA (FY-2, FY-1, FY0) | 26.7 / 30.6 / 35.0 |
| Entry (LTM) EBITDA | **35.0** (= last historical FY) |
| Target net debt at close (refinanced) | 20.0 |

## 2. Purchase price and entry valuation

| Item | Value |
|---|---|
| Current share price | $4.40 |
| Offer premium | 25% → offer price **$5.50**/share |
| Fully diluted shares | 60.0 m |
| Option/RSU buyout | 0.0 |
| Equity purchase price | 5.50 × 60.0 = **330.0** |
| Entry enterprise value | 330.0 + 20.0 net debt = **350.0** |
| Implied entry EV/EBITDA | 350.0 / 35.0 = **10.0×** |

## 3. Financing (sources & uses)

**Uses** (all funded at close):

| Use | Amount |
|---|---|
| Equity purchase price | 330.0 |
| Refinance target net debt | 20.0 |
| M&A advisory fees | 7.0 |
| Financing fees | 5.0 |
| Minimum cash funded to balance sheet | 5.0 |
| **Total uses** | **367.0** |

**Sources:**

| Tranche | Amount | Pricing | Terms |
|---|---|---|---|
| Senior Term Loan | 157.5 (4.5× EBITDA) | SOFR 4.00% + 350 bps = **7.50%** all-in | bullet, 7-year tenor, no floor, no OID |
| Mezzanine Notes | 35.0 (1.0× EBITDA) | SOFR 4.00% + 700 bps = **11.00%** all-in | bullet, 8-year tenor, no floor, no OID |
| Sponsor equity | **balancing plug = 367.0 − 192.5 = 174.5** | | new money; no management rollover |

Conventions: **no cash sweep**, no revolver, no dividend recap, no earnout,
no PIK. Interest accrues on the opening balance of each year. Because both
tranches are bullet with no sweep, **debt outstanding at exit = 192.5**
(face value). Free cash flow accumulates as balance-sheet cash and is
**excluded from the exit equity bridge** (stated conservative convention —
see §5).

## 4. Operating plan (projection years 1–5, the hold period)

| Year | Revenue growth | EBITDA margin |
|---|---|---|
| 1 | 12.0% | 35.0% |
| 2 | 11.0% | 36.0% |
| 3 | 10.0% | 36.0% |
| 4 | 9.0% | 37.0% |
| 5 | 8.0% | 38.0% |

Revenue compounds from FY0 = 100.0. EBITDA_t = revenue_t × margin_t.
(For completeness of the model: D&A 4.0% of revenue, maintenance capex 3.0%,
growth capex 1.0%, ΔNWC = 5% of Δrevenue, cash tax rate 25%. These drive the
FCF/covenant schedules but — given bullet debt, no sweep, and the exit
convention below — they do **not** change the headline IRR/MoIC.)

## 5. Exit (year 5) and headline outputs

| Item | Value |
|---|---|
| Exit year | end of projection year 5 |
| Exit multiple (strategic sale) | **9.0× EV/EBITDA** |
| Exit EBITDA basis | **projected year-5 EBITDA** (NOT entry LTM) |
| Exit enterprise value | 9.0 × EBITDA_5 |
| **Exit equity proceeds** | **exit EV − debt outstanding at exit (192.5)** |

Sponsor cash-flow series: `[−174.5, 0, 0, 0, 0, +exit equity]` (no interim
distributions).

**Headline outputs the model must show (labels required, see PROTOCOL.md):**

1. `sponsor_irr` — IRR of the sponsor cash-flow series (annual, decimal)
2. `sponsor_moic` — exit equity proceeds / 174.5
3. `exit_equity_proceeds` — as defined above ($m)
4. `sponsor_equity_cheque` — the 174.5 plug ($m)

## 6. Required model components (completeness checklist)

- Sources & uses table (balanced)
- Debt schedule (per-tranche roll-forward with interest)
- Returns section (IRR + MoIC on a visible cash-flow series)
- At least one sensitivity table (e.g. exit multiple × growth or leverage)

Ground truth: `benchmarks/harness/ground_truth.py::lbo_us_saas()`.

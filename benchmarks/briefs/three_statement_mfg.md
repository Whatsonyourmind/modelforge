# Deal Brief BM-3S-001 — 3-Statement Model of a Generic US Manufacturer

> **Synthetic benchmark deal.** "MfgCo" is a fictional company. All numbers
> are frozen benchmark inputs — they do not describe any real company,
> transaction, or counterparty.
>
> **Task:** build a fully integrated 3-statement model (P&L, balance sheet,
> cash flow statement) in Excel from this brief alone. The balance sheet must
> tie (Assets = Liabilities + Equity) in **every** year purely through the
> model's mechanics — no plugs into equity, no balancing hacks. Every
> parameter needed is stated below; the brief is solvable unambiguously.

## 1. Timeline and historicals

8 annual columns: 3 historical (t = 0, 1, 2) + 5 projection (t = 3..7).
The opening balance sheet below anchors column t = 0; working-capital and
PP&E lines are restated from the days/percentage drivers from t = 1 onward
(stated convention — keeps the model fully driver-linked).

| Item | FY t=0 | FY t=1 | FY t=2 |
|---|---|---|---|
| Revenue | 540.0 | 570.0 | 600.0 |
| EBITDA | 70.2 | 76.95 | 84.0 |

Currency / units: USD, millions. 365-day year.

## 2. Opening balance sheet (anchors t = 0)

| Assets | | Liabilities & Equity | |
|---|---|---|---|
| Cash | 40.0 | Accounts payable | 55.0 |
| Accounts receivable | 90.0 | Debt | 180.0 |
| Inventory | 75.0 | Equity | 220.0 |
| Net PP&E | 250.0 | | |
| **Total** | **455.0** | **Total** | **455.0** |

## 3. Drivers (projection years t = 3..7)

| Year (proj) | Revenue growth | EBITDA margin |
|---|---|---|
| 1 (t=3) | 5.0% | 14.0% |
| 2 (t=4) | 4.5% | 14.5% |
| 3 (t=5) | 4.0% | 15.0% |
| 4 (t=6) | 3.5% | 15.0% |
| 5 (t=7) | 3.0% | 15.0% |

Constant drivers (apply to ALL columns t = 0..7 unless stated):

| Driver | Value | Convention |
|---|---|---|
| D&A | 5.5% of revenue | |
| Interest rate on debt | 6.0% | charged on the **opening** debt balance of the year (t=0 uses the t=0 balance) |
| Tax rate | 25% | on positive EBT only (EBT is positive every year here) |
| Receivables days (DSO) | 55 | AR_t = revenue_t × 55/365, from t = 1 onward |
| Inventory days | 60 | on **revenue** (stated simplification), from t = 1 onward |
| Payables days | 40 | on **revenue** (stated simplification), from t = 1 onward |
| Capex | 6.0% of revenue | |
| Dividend payout | 30% of positive net income | |
| Debt amortization | **20.0 per year**, floored at 0 | scheduled; financing outflow in the CFS |

No stock-based compensation, no revolver, no deferred taxes, no NOLs, no
minority interest — keep those at zero.

## 4. Model mechanics (all stated, no discretion)

- P&L: revenue → EBITDA (margin) → − D&A → EBIT → − interest → EBT →
  − tax (25% of positive EBT) → **net income**.
- Debt roll: debt_t = max(debt_{t−1} − 20.0, 0). t=0 = 180.0.
- PP&E roll: PPE_t = PPE_{t−1} + capex_t − D&A_t (from t = 1).
- Equity roll: equity_t = equity_{t−1} + NI_t − dividends_t (from t = 1).
- CFS (indirect): CFO = NI + D&A − ΔNWC, where
  ΔNWC_t = (AR_t − AR_{t−1}) + (Inv_t − Inv_{t−1}) − (AP_t − AP_{t−1});
  CFI = −capex; CFF = −dividends − debt repayment.
- Cash roll: cash_t = cash_{t−1} + CFO_t + CFI_t + CFF_t (from t = 1).
- Balance check each year: (cash + AR + Inv + PP&E) − (AP + debt + equity) = 0.

## 5. Headline outputs (final projection year, t = 7)

**Headline outputs the model must show (labels required, see PROTOCOL.md):**

1. `final_net_income` — net income, final year ($m)
2. `final_total_assets` — total assets, final year ($m)
3. `final_total_liabilities_equity` — total liabilities + equity, final year ($m)
4. `final_balance_check` — assets − (liabilities + equity), final year (must be ~0)
5. `final_cash` — ending cash, final year ($m)
6. `final_debt` — ending debt, final year ($m) (= 180 − 7×20 = 40.0)

## 6. Required model components (completeness checklist)

- All three statements present and labeled (P&L, balance sheet, CFS)
- Balance sheet tie (|A − L − E| ≤ 0.01 in the final year)
- A visible balance-check row (or equivalent)

Ground truth: `benchmarks/harness/ground_truth.py::three_statement_mfg()`.

# DCF-WACC template — extractor guidance

Target spec class: `modelforge.spec.dcf.DCFSpec`.

## A-id allocation

- `A-001 – A-019` — WACC (risk-free, ERP, beta, cost of debt, tax, target debt weight)
- `A-101 – A-105` — revenue growth Y1..Y5
- `A-201 – A-205` — EBITDA margin Y1..Y5
- `A-301 – A-303` — D&A %, capex %, ΔNWC %
- `A-401 – A-402` — terminal (growth %, exit EV/EBITDA x)

## Canonical Italy benchmarks to cite

- `equity_risk_premium`: 0.067 (Damodaran 2026, country risk table).
- `risk_free_rate`: 10Y BTP yield at valuation date (MTS).
- `effective_tax_rate`: 0.279 (IRES 24% + IRAP 3.9%).

## Terminal value reconciliation

Emitted sheet computes BOTH Gordon growth and exit EV/EBITDA — the
valuation uses their average. If they diverge > 20%, flag in rationale
(either terminal_growth or exit_x is implausible).

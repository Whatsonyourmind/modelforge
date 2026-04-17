# ModelForge ROI — Banca Finint Credit Fund

One-page business case. All numbers are computed from the assumptions below; edit any of them and re-run `modelforge roi` to refresh.

## Assumptions

| Field | Value |
|---|---|
| Deals per year | 30 |
| Hours per deal — legacy | 50.0 |
| Hours per deal — ModelForge | 7.0 |
| Legacy error rate | 15% |
| ModelForge error rate | 3% |
| Rework multiplier | 50% |
| Audit hours — legacy | 20.0 |
| Audit hours — ModelForge | 4.0 |
| Loaded analyst rate (€/hr) | 180 |
| Seats | 3 |
| Monthly price per seat (€) | 499 |

## Headline numbers

| Metric | Value |
|---|---|
| Hours saved per deal | 43.0 |
| Annual time savings | €232,200 |
| Rework reduction savings | €19,683 |
| Audit time savings | €86,400 |
| **Gross annual savings** | **€338,283** |
| Subscription cost | €17,964 |
| **Net annual savings** | **€320,319** |
| 1-year ROI | 1783.1% |
| Payback period | 0.6 months |

Prepared for Banca Finint Credit Fund · ModelForge v0.5. The numbers above are driven by your stated assumptions; every calculation is computed deterministically by the Python module `modelforge.roi.calculator` and can be audited line-by-line.
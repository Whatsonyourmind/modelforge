# Template Gallery

Eleven templates ship with ModelForge today. Each has an example spec at `examples/<name>.yaml` and builds into a QC-passing workbook in `output/<name>.xlsx`.

| Template | model_type | Example spec | Sheets |
|---|---|---|---|
| Unitranche LBO | `unitranche` | `unitranche_cdmo.yaml` | Cover, Sources, Assumptions, OperatingModel, DebtSchedule, Covenants, Returns, QC + SensitivityAnalysis + MonteCarlo + Reproducibility |
| Credit Memo | `credit_memo` | `credit_memo_cdmo.yaml` | Unitranche + CreditOpinion |
| Minibond | `minibond` | `minibond_logistics.yaml` | Cover, Sources, Assumptions, IssuerFinancials, BondStructure, Covenants, InvestorReturns, QC + analytics |
| Project Finance | `project_finance` | `project_finance_solar.yaml` | Cover, Sources, Assumptions, ProjectCashFlow, DebtDSCR, EquityReturns, QC + analytics |
| Real Estate | `real_estate` | `real_estate_pbsa.yaml` | Cover, Sources, Assumptions, DCF, Financing, QC + analytics |
| NPL Portfolio | `npl` | `npl_mixed_portfolio.yaml` | Cover, Sources, Assumptions, CollectionWaterfall, QC + analytics |
| Structured Credit | `structured_credit` | `structured_credit_pmi.yaml` | Cover, Sources, Assumptions, Tranches, QC + analytics |
| 3-Statement | `three_statement` | `three_statement_cdmo.yaml` | Cover, Sources, Assumptions, Model, QC + analytics |
| DCF-WACC | `dcf` | `dcf_enel.yaml` | Cover, Sources, Assumptions, WACCBuild, FCFForecast, Valuation, QC + analytics |
| M&A Merger | `merger` | `merger_tim_iliad.yaml` | Cover, Sources, Assumptions, DealStructure, ProForma, AccretionDilution, QC + analytics |
| Fairness Opinion | `fairness` | `fairness_amplifon.yaml` | Cover, Sources, Assumptions, TradingComps, TransactionComps, FootballField, QC |

## Primary outputs (what sensitivity / MC / dossier highlight)

| Template | Primary output | Sheet location |
|---|---|---|
| Unitranche / Credit Memo | Blended Lender IRR (or single Lender IRR) | `Returns!D9` |
| Minibond | Investor Net YTM (after WHT) | `InvestorReturns!D…` |
| Project Finance | Sponsor Equity IRR | `EquityReturns!D11` |
| Real Estate | Equity IRR | `Financing!D…` |
| NPL | Equity IRR | `CollectionWaterfall!D…` |
| Structured Credit | Senior Tranche IRR (AAA) | `Tranches!D22` |
| 3-Statement | Net income Y1 projected | `Model!D17` |
| DCF-WACC | Implied EV | `Valuation!D…` |
| M&A Merger | Y1 Accretion / Dilution % | `AccretionDilution!D…` |
| Fairness | (no single output — football field *is* the output) | — |

## Each template carries

- **Assumptions sheet** as the single source of truth. Every driver has a named range.
- **Sources sheet** with every doc, page, publisher, URL, verified flag.
- **QC sheet** with in-sheet checks.
- **SensitivityAnalysis** — tornado on primary_output, ≥ 6 factors, native Excel chart.
- **MonteCarlo** — 1000-run histogram with P5/P25/P50/P75/P95 stats.
- **Reproducibility** — spec SHA-256, ModelForge version, Python version, build timestamp.

## Extending

New templates:

1. Add a Pydantic spec class in `modelforge/spec/<name>.py` with `model_type: Literal["..."]`.
2. Add a template builder in `modelforge/templates/<name>.py` that calls `build_base_workbook()` and emits template-specific sheets via `modelforge/builder/sheets/`.
3. Register in `REGISTRY` (`modelforge/templates/__init__.py`) and in the CLI's `_load_spec_class`.
4. Add an example YAML in `examples/` and an ingest prompt in `modelforge/ingest/prompts/template_<name>.md`.
5. Add default sensitivity factors in `modelforge/analytics/factors.py` and a primary-output locator in `modelforge/analytics/sensitivity.py` if it has a single key metric.
6. Run `pytest tests/ -q` — all green.

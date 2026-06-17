# Architecture

## The invariant

**LLMs never write numbers into cells. A deterministic Python builder emits the workbook from a typed Pydantic spec.**

Everything else follows from that rule.

## Flow

```
YAML spec ─► Pydantic validation ─► template.build()
                                        │
                   ┌────────────────────┼────────────────────┐
                   ▼                    ▼                    ▼
               base_workbook       template-specific     post-processors
               (Cover / Sources /  sheets               (sensitivity tornado,
                Assumptions / QC)                         Monte Carlo,
                                                          reproducibility,
                                                          optional dossier)
                                        │
                                        ▼
                              .xlsx  +  .graph.db
```

Every step is deterministic. Given the same spec bytes, you get the same workbook (modulo build timestamp, which is recorded in the Reproducibility sheet).

## Core packages

| Package | Role |
|---|---|
| `modelforge.spec` | Pydantic spec classes — one per template. Each has its own `SpecClass.model_fields` describing the inputs. |
| `modelforge.templates` | Template builders. Each registers in `REGISTRY` and is dispatched by `model_type`. |
| `modelforge.builder` | Shared sheet builders (Cover, Sources, Assumptions, QC) + style / layout / formula helpers. |
| `modelforge.builder.sheets` | Per-template sheet emitters (operating, debt, covenants, returns, etc.). |
| `modelforge.graph` | SQLite-backed linkage graph — every CELL, DRIVER, SOURCE node + edge between them. |
| `modelforge.analytics` | Sensitivity tornado, Monte Carlo, reproducibility metadata (spec SHA-256 + version). |
| `modelforge.dossier` | Regulator-grade PDF generator. |
| `modelforge.chat` | Lineage Q&A REPL backed by Claude with a deterministic workbook-summary system prompt. |
| `modelforge.ingest` | Data-room ingestion pipeline — readers / classifier / extractor / pipeline / reporter. |
| `modelforge.qc` | External 8-check gate. |
| `modelforge.cli` | Click-based CLI: build, qc, sources, lineage, stats, ingest, chat, verify, dossier. |

## Cell-level rules

1. **Named ranges mandatory.** Every driver on the Assumptions sheet gets a workbook-level named range. No magic numbers in any other sheet.
2. **Colour discipline.** Blue = hardcoded input, Black = formula, Green = cross-sheet link, Red = warning / external.
3. **Scenario toggle.** `Cover!C17` holds `scenario_index` (1 = Worst, 2 = Base, 3 = Best). Every driver's Active column reads `CHOOSE(scenario_index, Worst, Base, Best)`; every downstream formula reads the Active cell via its name.
4. **Sign convention.** Costs NEGATIVE. Not parenthesis-positive. Declared on Cover; QC gate enforces.
5. **Language.** EN primary in column A / B; IT secondary label on each row.

## Linkage graph

Every cell that holds a hardcoded input or formula becomes a node:

- `CELL:Sheet!D15` — cell-level node, links to a driver
- `DRIVER:revenue_growth_y1` — logical driver, links to an assumption or source
- `SOURCE:S-003` — documented source (doc + page + publisher)
- `ASSUMPTION:A-012` — analyst judgment (rationale + confidence)

The graph is a first-class artifact persisted to SQLite next to the workbook. Walk it with `modelforge lineage <graph.db> CELL:Returns!D9` to see every upstream dependency.

## Post-processors

After the core template emits its sheets, ModelForge layers three optional analytics:

### Sensitivity tornado

For each factor (driver + ±shock), computes output delta using per-factor elasticity coefficients. Renders a native Excel BarChart sorted by spread.

### Monte Carlo

1000-run (configurable) simulation using per-factor elasticities and a distribution (triangular / normal / lognormal). Histogram + P5/P25/P50/P75/P95 stats. Seeded deterministic by default.

### Reproducibility

Computes SHA-256 of the spec YAML bytes, writes it + ModelForge version + Python version + build timestamp to a `Reproducibility` sheet with matching named ranges (`mf_spec_sha256`, `mf_version`, `mf_python_version`, `mf_build_timestamp`).

## QC gate

Eight external checks:

1. QC sheet present
2. Sign convention declared = costs_negative
3. `scenario_index` named range exists
4. All named ranges resolve to populated cells
5. Every BASE assumption has a cell comment (source / assumption id / rationale)
6. Every source referenced in Assumptions exists on the Sources sheet
7. Print-ready (freeze panes or print titles set on every sheet)
8. No orphan / empty sheets

Pass all 8 → deliverable-ready.

## Roadmap

v0.4 ships the multi-template suite (now 19: 17 shipped + 2 preview) + sensitivity/MC + reproducibility + audit dossier + chat + ingest-wide + OCR. v0.5 brings probabilistic credit (Merton/KMV/IFRS 9 ECL), model diff, and a web SaaS thin layer. v1.0 brings SSO/SOC 2, on-prem, EDGAR/HKEX/PRA packs, model-memory agents, and a template marketplace. See `PRD_v04_to_v10_sota.md` for the full plan.

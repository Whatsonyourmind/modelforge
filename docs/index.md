# ModelForge

> Bulge-tier Excel financial models. Every cell live. Every number sourced. Every assumption defended.

ModelForge is a deterministic Excel model factory for credit, structured finance, and corporate-finance workflows. An LLM writes the spec; a typed Python builder writes the workbook. Every cell is a live formula; every input cites a source page or an analyst rationale; every model ships with a linkage graph auditable via CLI or PDF dossier.

## Why it exists

The bar for deliverables at a credit committee or rating agency is different from what a generic LLM produces. Rogo and similar tools generate workbooks where cells are values (not live formulas), and numbers can drift from the specific opportunity. ModelForge solves that specific gap:

- **Live formulas.** Flip the scenario toggle on the Cover sheet and every sheet recomputes.
- **Source traceability.** Every hardcoded input carries an `S-###` (sourced) or `A-###` (assumption) tag that traces back to a documented rationale and, where applicable, a specific page in the data room.
- **Deterministic emitter.** Claude produces the YAML spec; Python writes the cells. The LLM never writes numbers into the workbook.
- **Audit dossier.** `modelforge dossier <xlsx>` emits a regulator-grade PDF that embeds the spec hash, every assumption, every source, every formula shape, and a QC sign-off page.

## 11 templates ship today

Credit & structured finance: **Unitranche LBO · Credit Memo · Minibond · Project Finance · Real Estate · NPL waterfall · Structured Credit · 3-Statement**.

M&A and valuation: **M&A Merger (accretion/dilution) · DCF-WACC · Fairness Opinion football field**.

See the [Template Gallery](templates.md) for spec and output details.

## Installing

```bash
pip install 'modelforge-finance[ingest]'
```

Optional extras:

- `[ingest-ocr]` — OCR fallback for scanned PDFs (requires system tesseract + Poppler).

## 30-second quickstart

```bash
modelforge list-templates                                   # see all 11 templates
modelforge build examples/unitranche_cdmo.yaml             # build workbook + linkage graph
modelforge qc output/unitranche_cdmo.xlsx                   # 8/8 QC gate
modelforge dossier output/unitranche_cdmo.xlsx              # regulator-grade PDF
modelforge chat output/unitranche_cdmo.xlsx                 # lineage Q&A REPL
```

See the [Quickstart](quickstart.md) for a deeper walkthrough, the [Architecture](architecture.md) page for how the pieces fit, and the [Comparison](comparison.md) page for how ModelForge differs from Rogo, Macabacus, and FAST Standard.

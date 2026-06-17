# Quickstart

A 5-minute tour of ModelForge.

## 1. Install

```bash
pip install 'modelforge-finance[ingest]'
```

Verify:

```bash
modelforge list-templates
```

## 2. Build your first workbook

ModelForge ships with an anonymized example spec for every shipped template (see `examples/`). Let's build the Italian CDMO unitranche:

```bash
modelforge build examples/unitranche_cdmo.yaml
# → Built: output/unitranche_cdmo.xlsx (unitranche)
# → Graph: output/unitranche_cdmo.graph.db
```

Open `output/unitranche_cdmo.xlsx` in Excel. Every cell is a live formula; flip `Cover!C17` between 1 / 2 / 3 to switch Worst / Base / Best scenarios and watch every sheet respond.

## 3. Run the 8-check QC gate

```bash
modelforge qc output/unitranche_cdmo.xlsx
```

QC verifies: sign convention declared, scenario_index exists, every named range resolves, every BASE assumption has a cell comment, every source referenced exists on Sources, print-ready layout, no orphan sheets, and the QC sheet itself is present.

## 4. Generate the audit dossier

```bash
modelforge dossier output/unitranche_cdmo.xlsx
# → Dossier: output/unitranche_cdmo.dossier.pdf
```

Open the PDF. You'll see: cover + reproducibility metadata (spec SHA-256), executive summary, assumptions register, source registry, formula inventory, lineage graph summary, QC sign-off with signature lines, bilingual glossary.

## 5. Ask lineage questions

```bash
export ANTHROPIC_API_KEY=sk-ant-...
modelforge chat output/unitranche_cdmo.xlsx
# You › why is Y3 revenue growth 7%?
# ModelForge › That's driven by A-003 (revenue_growth_y3, confidence M),
#   sourced from S-001 p.14 (data room IM Section 4.2). The analyst's
#   rationale is "Management case aligned with sector benchmark".
```

## 6. Verify spec hash

Later, to confirm a workbook matches a given spec:

```bash
modelforge verify output/unitranche_cdmo.xlsx --spec examples/unitranche_cdmo.yaml
# → PASS spec hash matches: 5eb6bf7a62a4f46fb0bfa6423a8636cfb808aea71db7bee24016c754b2a9282d
```

## 7. Data-room ingestion

To generate a spec from a folder of PDFs / XLSX / CSV:

```bash
modelforge ingest path/to/dataroom/ -t project_finance -o out.yaml
```

This classifies each document, extracts relevant fields via Claude, and writes a validated YAML you can then `modelforge build`.

## Next steps

- Read [Architecture](architecture.md) to understand how the pieces fit.
- Browse the [Template Gallery](templates.md) for all 19 templates.
- See [Comparison](comparison.md) for how ModelForge differs from Rogo / Macabacus / FAST Standard.

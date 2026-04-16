# ModelForge

Bulge-tier Excel financial model factory for credit & structured finance. Every cell live-formulated. Every number traceable back to the source document page it came from.

Built for Italian private capital (unitranche, minibond, project finance, RE, NPL, structured credit) — extensible to any asset class.

## The architectural principle

> **LLMs produce specs + sources + narrative. Deterministic Python produces the workbook.**

The LLM never writes a number into a cell. It writes a typed YAML spec with source IDs. A deterministic builder emits the Excel via openpyxl. A QC gate validates before export. Excel is a render of a linkage graph; the graph is persisted to SQLite and is the canonical artifact.

## Quality standards (bulge-tier, non-negotiable)

**Formatting**
- Blue = hardcoded input. Black = formula. Green = cross-sheet link. Red = warning.
- No mixed formulas (no magic numbers embedded). Named ranges for every driver.
- Costs NEGATIVE (sign convention enforced and checked).
- EN primary labels, IT secondary.
- Historical vs Projected column separator, obvious.
- Check row at top of every sheet (BS balance, CFS tie, covenant headroom — TRUE or 0).

**Sourcing**
- Every hardcoded cell has a comment with source ID (S-001, S-002, ...).
- `Sources` sheet lists each source: doc, page, publisher, date, URL, verified-flag.
- Assumptions (not sourced) tagged A-001 with rationale + confidence H/M/L.

**Scenarios**
- WORST / BASE / BEST toggle on Assumptions. Drives every sheet via CHOOSE.
- Every sheet respects the toggle — no orphan assumptions.

**Audit**
- `QC` sheet with 12 automated checks, all must pass.
- Revision log on Cover.
- Named ranges mandatory.
- Print areas set. Print-ready on every sheet.

## Quick start

```bash
cd "C:/Users/lukep/Desktop/Projects AI/ModelForge"
pip install -e .
modelforge build examples/unitranche_cdmo.yaml
modelforge qc output/unitranche_cdmo.xlsx
```

## Package layout

```
modelforge/
├── graph/            # First-class linkage graph (nodes, edges, SQLite persistence)
├── spec/             # Pydantic schemas per template
│   ├── base.py       # Source, Assumption, Scenario, Target (shared types)
│   └── unitranche.py # Template 1: Unitranche LBO
├── builder/          # Deterministic openpyxl writer
│   ├── styles.py     # Bulge-tier formatting library
│   ├── formulas.py   # Formula string builders
│   ├── i18n.py       # EN/IT label dictionary
│   ├── workbook.py   # Top-level builder
│   └── sheets/       # One module per sheet (cover, sources, assumptions, ...)
├── qc/               # Quality gate (12 checks + PDF report)
├── data/             # Market data loaders (Damodaran, ECB, Borsa minibond)
└── cli.py            # modelforge build|qc|sources|inspect
```

## Template roadmap

1. ✅ Unitranche LBO (Italian mid-market direct lending)
2. Minibond pricing + investor returns
3. Credit memo + covenant headroom
4. Project Finance (infra, RE, energy)
5. Real Estate DCF + waterfall
6. NPL portfolio recovery waterfall + IRR
7. Structured Credit tranche allocation
8. 3-statement corporate

## The pitch

> Bulge-tier Excel models, every cell live-formulated, every number traceable back to the data room page it came from.

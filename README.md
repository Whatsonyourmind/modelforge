# ModelForge

<!-- mcp-name: io.github.Whatsonyourmind/modelforge -->

[![Status](https://img.shields.io/badge/version-0.9.3-blue)](./CHANGELOG.md) [![Tests](https://img.shields.io/badge/tests-431%2F431-brightgreen)](./tests) [![Audit](https://img.shields.io/badge/audit-0%20FAIL%20%2F%200%20PARTIAL-brightgreen)](./GOLD_STANDARD_AUDIT_2026-04-21.md) [![SOTA](https://img.shields.io/badge/SOTA-9.40%20Italian%20%2F%207.42%20International-blueviolet)](./SCORECARD_v3.md) [![MCP](https://img.shields.io/badge/MCP-native-orange)](./modelforge/mcp_server.py) [![Templates](https://img.shields.io/badge/templates-14-blue)](./modelforge/templates/) [![Public](https://img.shields.io/badge/repo-public-brightgreen)](https://github.com/Whatsonyourmind/modelforge)

Bulge-tier Excel financial model factory for credit & structured finance. Every cell live-formulated. Every number traceable back to the source document page it came from.

Built for Italian private capital (unitranche, minibond, project finance, RE, NPL, structured credit) — extensible to any asset class.

## Use it inside Claude Code, Cursor, ChatGPT Enterprise (MCP-native)

**PyPI name**: `modelforge-finance` (the unscoped `modelforge` was taken by source{d}'s ML library). **Import name** stays `modelforge`.

```bash
pip install "modelforge-finance[mcp,export]"

# wire into your MCP client config:
{
  "mcpServers": {
    "modelforge": { "command": "modelforge-mcp" }
  }
}
```

Then in your AI assistant:
> *"Build me a unitranche LBO model from this YAML spec, export the committee deck."*

Tools available: `list_templates` · `build_model` · `qc_workbook` · `list_sources` · `lineage_walk` · `ingest_dataroom` · `export_pptx` · `export_docx`.

See [GTM_STRATEGY.md](./GTM_STRATEGY.md) and [SCORECARD_v2.md](./SCORECARD_v2.md) for the full GTM thesis and competitor comparison (vs Rogo / Hebbia / Macabacus / o11).

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

## Data-room ingestion (v0.3.1)

Turn a directory of PDFs, XLSXs and CSVs into a validated ModelForge YAML spec using Claude Opus. Every extracted number traces back to a doc page via the auto-built Sources registry.

```bash
pip install -e .[ingest]                # installs anthropic, pdfplumber, pypdf
export ANTHROPIC_API_KEY=sk-ant-...      # required

modelforge ingest path/to/dataroom/ \
    --template project_finance \
    -o output/my_deal.yaml --verbose

# Review output/my_deal.yaml + output/my_deal.ingestion.md
# (INGESTION_REPORT.md lists every extracted field, S-id, confidence)

modelforge build output/my_deal.yaml     # produces the workbook
modelforge qc output/my_deal.xlsx        # 8/8 quality gate
```

Supported template: `project_finance` (MVP). Templates 1, 3, 5-8 queued for v0.3.2. See `PRD_v03_dataroom_ingestion.md` for the full spec.

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

## Templates (all shipped)

1. ✅ **Unitranche LBO** — Italian mid-market direct lending (Cash sweep + IFRS 9 EIR)
2. ✅ **Minibond** — Banca Finint territory (Gross YTM + Net YTM + Italian WHT)
3. ✅ **Credit Memo** — Extends Unitranche with recovery waterfall + PD×LGD×EAD
4. ✅ **Project Finance** — Construction + operating phases, DSCR-driven
5. ✅ **Real Estate** — NOI build, exit cap, LP/GP promote waterfall
6. ✅ **NPL Portfolio** — Collection curves, servicing fees, senior/mezz capital structure
7. ✅ **Structured Credit** — Tranche waterfall with attachment/detachment points
8. ✅ **3-Statement** — P&L + BS + CFS with BS balance integrity check

Run `modelforge list-templates` to see them all. Each ships with an anonymized Italian example YAML in `examples/`.

## The pitch

> Bulge-tier Excel models, every cell live-formulated, every number traceable back to the data room page it came from.

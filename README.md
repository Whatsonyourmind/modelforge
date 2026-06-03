# ModelForge

<!-- mcp-name: io.github.Whatsonyourmind/modelforge -->

[![Version](https://img.shields.io/pypi/v/modelforge-finance?label=version&color=blue)](https://pypi.org/project/modelforge-finance/) [![Tests](https://img.shields.io/badge/tests-679%2F679-brightgreen)](./tests) [![Trust](https://img.shields.io/badge/trust--layer-v1%20(14%2F14%20FAIL--clean)-brightgreen)](./AUDIT_REPORT.md) [![MCP](https://img.shields.io/badge/MCP-native-orange)](./modelforge/mcp_server.py) [![Templates](https://img.shields.io/badge/templates-14-blue)](./modelforge/templates/) [![SBOM](https://img.shields.io/badge/SBOM-CycloneDX%201.5-purple)](./.github/workflows/ci.yml)

Bulge-tier Excel financial model factory for credit & structured finance. Every cell live-formulated. Every number traceable back to the source document page it came from.

A developer tool for analysts and engineers who build credit and corporate-finance models programmatically. Covers unitranche, sponsor-backed LBO, project finance, real estate credit, NPL, structured credit, restructuring, M&A, DCF and IPO templates. Extensible to any asset class.

---

> **🚀 Using ModelForge in production — or want managed features, priority support, or a specific template/connector?**
> [**Tell me about your use case →**](https://github.com/Whatsonyourmind/modelforge/issues/new?template=early-access.yml) — I read every one.

---

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

Tools available: `list_templates` · `build_model` · `qc_workbook` · `list_sources` · `lineage_walk` · `ingest_dataroom` · `screen_deals` · `compute_tax` · `export_pptx` · `export_docx` · plus 7 unified-feed tools (`get_fundamentals`, `get_prices`, `lookup_lei`, etc.) across an 11-provider data stack.

## The architectural principle

> **LLMs produce specs + sources + narrative. Deterministic Python produces the workbook.**

The LLM never writes a number into a cell. It writes a typed YAML spec with source IDs. A deterministic builder emits the Excel via openpyxl. A QC gate validates before export. Excel is a render of a linkage graph; the graph is persisted to SQLite and is the canonical artifact.

## Quality standards (bulge-tier, non-negotiable)

**Formatting**
- Blue = hardcoded input. Black = formula. Green = cross-sheet link. Red = warning.
- No mixed formulas (no magic numbers embedded). Named ranges for every driver.
- Costs NEGATIVE (sign convention enforced and checked).
- EN primary labels, multi-language secondary (DE / ES / IT shipped; SV / NO / DA / NL on the v0.10 roadmap as design-partner asks).
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
pip install "modelforge-finance[mcp,export,data]"

# Build any of 14 templates from a YAML spec
modelforge build examples/unitranche_cdmo.yaml

# QC the workbook (12 checks + Trust Layer plausibility)
modelforge qc output/unitranche_cdmo.xlsx --trust-strict

# Audit every example (CI uses the same gate)
modelforge audit-all examples/ --report AUDIT_REPORT.md
```

## Trust Layer v1 (new in v0.9.7)

> Why should a buyer trust the number in cell `B42`?

The Trust Layer is a **semantic** gate (separate from the structural QC gate). It answers the question every IC asks in the first five minutes: *is this number plausible?* It catches issues like a DCF EV that's 8× the company's real market cap before the model ever leaves QA.

25+ built-in rules cover all 14 templates:

- **DCF**: WACC band (3-25%), terminal growth ≤ GDP + 1%, EV vs market-cap deviation, terminal-value share, sensitivity-table monotonicity
- **Three-statement**: balance-sheet integrity, cash reconciliation, retained-earnings link
- **NPL**: cumulative recovery ≤ 100%, vintage staircase monotone
- **Project finance**: DSCR floor, wire degradation > 0, P90 < P50
- **Sponsor LBO**: XIRR plausibility, multiple expansion vs entry
- **M&A / fairness / structured credit / unitranche / credit memo**: per-template plausibility

Each violation produces a `RedFlags` worksheet inside the built workbook with severity (`info` / `warn` / `fail`), the rule that fired, expected-vs-actual, and the recommended remediation.

```bash
modelforge audit-all examples/   # 14/14 templates, 0 FAIL violations in current ship
```

See [AUDIT_REPORT.md](./AUDIT_REPORT.md) for the current ship's audit.

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

Supported template: `project_finance` (MVP). Templates 1, 3, 5-8 queued for v0.3.2.

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

## Templates (14, all shipped)

1. ✅ **Unitranche LBO** — Mid-market direct lending (Cash sweep + IFRS 9 EIR + covenant package)
2. ✅ **Minibond / Private Placement Bond** — Direct private debt instrument (Gross YTM + Net YTM + jurisdiction-specific WHT)
3. ✅ **Credit Memo** — Extends Unitranche with recovery waterfall + PD×LGD×EAD
4. ✅ **Project Finance** — Construction + operating phases, DSCR-driven
5. ✅ **Real Estate** — NOI build, exit cap, LP/GP promote waterfall
6. ✅ **NPL Portfolio** — Collection curves, servicing fees, senior/mezz capital structure
7. ✅ **Structured Credit** — Tranche waterfall with attachment/detachment points
8. ✅ **3-Statement** — P&L + BS + CFS with BS balance integrity check
9. ✅ **DCF** — WACC build, fade, terminal normalization, 2D sensitivity (Trust Layer protected)
10. ✅ **Merger** — Accretion/dilution, breakeven, contribution, collar, PPA
11. ✅ **Fairness Opinion** — Selected comps, regression, premium analysis
12. ✅ **Sponsor LBO** — Returns waterfall, debt schedule, 14-story block
13. ✅ **IPO** — Float build, lock-up, stabilization, fee schedule
14. ✅ **Restructuring** — Going-concern recovery, plan-feasibility, creditor classes

Run `modelforge list-templates` to see them all. Each ships with an anonymized example YAML in `examples/`.

## Tax jurisdictions (7)

```
US  · Federal CIT + state + NOL + R&D credit + GILTI + BEAT + ASC 740
UK  · FRS 102 + main rate + marginal relief + RDEC + AIA + WDA + group relief
DE  · KSt + SolZ + GewSt (Hebesatz + § 8 add-backs + min-tax loss CF) — HGB roadmap v0.10
FR  · IS + small-profits + social surcharge + CVAE + CIR + 88% participation
ES  · IS + SME 23% + newly-created 15% + 95% participation + R&D + min-tax 15%
JP  · NCT + LCT + Enterprise Tax + Special Local Corp Tax + R&D credit
IT  · IRES / IRAP / SIIQ / PEX
```

## Data providers (11, unified `Provider` Protocol)

**Tier-0 (free, live today)**: EDGAR · OpenFIGI · GLEIF
**Tier-1 (low-cost paid)**: Polygon ($29/mo) · FMP ($19/mo) · Finnhub · Tiingo
**Tier-2 (institutional)**: Bloomberg · Refinitiv · FactSet · S&P Capital IQ

Tier-1 and Tier-2 are interface-complete — paid keys activate them via env vars. Local TTL cache prevents rate-limit blow-ups.

## Security & SBOM

- **CycloneDX 1.5 SBOM** auto-generated by CI on every push and attached to every GitHub release (`scripts/generate_sbom.py`)
- **CI gates**: pytest across Python 3.11 + 3.12, ruff lint, SBOM structure validation (`.github/workflows/ci.yml`)
- **Audit log** with append-only SQLite (`modelforge/audit_log.py`)
- **Trust Layer** semantic gates auto-injected into every built workbook
- **Security policy**: see [SECURITY.md](./SECURITY.md)

Procurement-grade controls (SOC 2 Type II, ISO 27001, pen-test, multi-tenant SaaS with SSO/SCIM) are Phase-B work.

## The pitch

> Bulge-tier Excel models, every cell live-formulated, every number traceable back to the data room page it came from.

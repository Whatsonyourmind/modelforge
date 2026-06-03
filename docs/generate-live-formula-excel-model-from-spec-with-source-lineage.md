# How do I generate a live-formula Excel financial model from a spec, with every number traceable to its source?

Most "AI builds your spreadsheet" tools have the same flaw: the model writes numbers straight into cells. You get a workbook that looks finished but is actually a static dump — no formulas, no scenario toggles, and no way to answer the one question every reviewer asks: *where did this number come from?*

ModelForge takes a different route. The architectural rule is simple:

> LLMs produce specs, sources, and narrative. Deterministic Python produces the workbook.

The language model never writes a value into a cell. It writes a typed YAML spec where each hardcoded input carries a source ID. A deterministic builder (openpyxl) renders that spec into Excel — every cell a real formula — and persists the underlying linkage graph to SQLite. The workbook is just a render of that graph; the graph is the canonical artifact.

## The pipeline in four steps

1. **Pick a template.** ModelForge ships builders for DCF, three-statement, M&A merger, sponsor LBO, unitranche, project finance, NPL portfolio, structured credit, IPO, restructuring, and more.
2. **Write (or ingest) a YAML spec.** Specs are Pydantic-validated. Inputs are tagged with source IDs (S-001, S-002, ...); unsourced numbers are flagged as assumptions with a rationale and confidence.
3. **Build the workbook.** A deterministic builder emits the `.xlsx` plus a `.graph.db` linkage store. Cells are formulas, with named ranges, enforced sign conventions, and WORST/BASE/BEST scenario toggles that propagate across sheets.
4. **QC and export.** An automated structural QC gate checks the workbook (QC sheet present, named ranges populated, source references resolve, print areas set, no orphan sheets) and returns a per-check pass/fail report. Optional exporters produce a PowerPoint summary or a Word memo.

## Minimal usage

Install with the MCP and export extras:

```bash
pip install "modelforge-finance[mcp,export]"
```

Build and QC a model from the command line:

```bash
# Build any template from a YAML spec
modelforge build examples/dcf_example.yaml

# Run the structural QC gate on the result
modelforge qc output/dcf_example.xlsx
```

Or drive it from an AI agent. ModelForge is an MCP server, so it plugs into Claude Code, Cursor, Cline, or ChatGPT Enterprise:

```json
{
  "mcpServers": {
    "modelforge": { "command": "modelforge-mcp" }
  }
}
```

The agent then has tools like `list_templates`, `build_model`, `qc_workbook`, and `lineage_walk`. A natural request — *"Build a DCF from this spec and tell me where the WACC assumption came from"* — maps directly onto `build_model` followed by a lineage trace.

## Why the lineage matters

The linkage graph is what separates an auditable model from a black box. Because every hardcoded cell is linked to a source ID, and every source ID resolves to a document and page, you can walk a result back to its origin: output cell -> driver(s) -> source -> doc page. That trail is the difference between a number you can defend in a review and one you have to take on faith.

It also makes the model honest about what is *not* sourced. Anything that isn't backed by a document is tagged as an assumption with an explicit confidence level, so a reviewer can see exactly which inputs are evidence and which are judgment.

## Data-room ingestion

If you start from raw documents rather than a hand-written spec, the optional ingestion path reads a directory of PDFs, spreadsheets, and CSVs and produces a validated YAML spec, plus an ingestion report tracing each extracted field back to its source. You review the spec, then build the workbook from it — the deterministic pipeline is unchanged.

## When to reach for this

ModelForge is a developer tool for analysts and engineers who build corporate-finance and credit models programmatically and need them to be live, scenario-driven, and audit-ready — not a one-click consumer spreadsheet generator. If you want a workbook a reviewer can interrogate cell by cell, that is exactly the gap it fills.

Try it:

```bash
pip install "modelforge-finance[mcp,export]"
```

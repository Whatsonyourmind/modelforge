"""ModelForge MCP server.

Exposes ModelForge as an MCP tool catalog for AI agents (Claude Code, Cursor, Cline,
ChatGPT Enterprise, etc.). Distribution lever per GTM_STRATEGY.md §4 Channel A.

Usage::

    pip install modelforge-finance[mcp]
    modelforge-mcp                       # stdio server
    npx -y @modelforge/mcp-server@latest # via Node wrapper (Phase B)

Tools exposed:

    build_model       — YAML spec → live-formula Excel workbook
    qc_workbook       — run 12-check QC gate
    list_sources      — enumerate source citations
    lineage_walk      — trace cell → driver → source → doc page
    list_templates    — which deal templates are available
    ingest_dataroom   — auto-extract YAML spec from a directory of PDFs
    export_pptx       — generate executive presentation from a model
    export_docx       — generate IC/credit memo from a model
    sensitivity_run   — 2D sensitivity tornado on key drivers
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "MCP server requires `pip install modelforge[mcp]` "
        "(adds `mcp>=1.12.0` to your environment)."
    ) from e

from modelforge.templates import REGISTRY, build_model
from modelforge.qc import run_qc

log = logging.getLogger("modelforge.mcp")

server = FastMCP(
    name="modelforge",
    instructions=(
        "ModelForge is a deterministic bulge-tier financial model factory. "
        "Every cell is live-formulated, every number traces to a source doc page, "
        "every change is diffed. Use `list_templates` to see what's available, "
        "`build_model` to produce a workbook from a YAML spec, `qc_workbook` to run "
        "the 12-check audit gate, and `export_pptx`/`export_docx` for committee "
        "deliverables. Source traceability is the moat — every output cell can be "
        "walked back to the underlying document via `lineage_walk`."
    ),
)


# ---- Helper -----------------------------------------------------------------


def _resolve_path(p: str | Path) -> Path:
    """Resolve a user-supplied path, expanding ~ and making absolute."""
    return Path(os.path.expanduser(str(p))).resolve()


# ---- Tools ------------------------------------------------------------------


@server.tool()
def list_templates() -> dict[str, Any]:
    """Enumerate available ModelForge deal templates.

    Returns the active template registry — names, asset classes, and a one-line
    description of each. Use this to discover what kinds of models can be built
    before invoking ``build_model``.
    """
    return {
        "templates": [
            {"name": name, "registered": True}
            for name in sorted(REGISTRY.keys())
        ],
        "count": len(REGISTRY),
    }


@server.tool()
def build_model(spec_path: str, output_dir: str | None = None) -> dict[str, Any]:
    """Build an Excel model from a YAML spec.

    Args:
        spec_path: Path to a ModelForge YAML spec (see ``examples/`` in the repo).
        output_dir: Where to write the .xlsx + .graph.db (default: ``output/``).

    Returns:
        Paths to the generated artifacts and high-level model stats.
    """
    spec = _resolve_path(spec_path)
    if not spec.exists():
        return {"error": f"spec file not found: {spec}"}

    out_dir = _resolve_path(output_dir) if output_dir else Path("output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        xlsx, graph = build_model(spec, out_dir)
    except Exception as e:
        log.exception("build_model failed")
        return {"error": f"build failed: {e!r}"}

    return {
        "xlsx": str(xlsx),
        "graph_db": str(graph),
        "spec": str(spec),
        "ok": True,
    }


@server.tool()
def qc_workbook(xlsx_path: str) -> dict[str, Any]:
    """Run the 12-check QC gate on a ModelForge workbook.

    Checks: balance sheet ties, CFS reconciliation, named-range coverage,
    sign-convention enforcement, formula vs hardcoded-value ratio, source-citation
    coverage, scenario-toggle propagation, and 5 others.

    Args:
        xlsx_path: Path to a .xlsx file produced by ``build_model``.

    Returns:
        Per-check pass/fail/partial dict + summary score.
    """
    xlsx = _resolve_path(xlsx_path)
    if not xlsx.exists():
        return {"error": f"workbook not found: {xlsx}"}

    try:
        report = run_qc(xlsx)
    except Exception as e:
        log.exception("qc failed")
        return {"error": f"qc failed: {e!r}"}

    return {"xlsx": str(xlsx), "report": report}


@server.tool()
def list_sources(graph_db: str) -> dict[str, Any]:
    """List every source citation in the model's linkage graph.

    Returns the Sources sheet content (doc, page, publisher, date, URL,
    verified-flag) for each S-001…S-NNN entry.

    Args:
        graph_db: Path to the SQLite graph store (output of ``build_model``).
    """
    db = _resolve_path(graph_db)
    if not db.exists():
        return {"error": f"graph_db not found: {db}"}

    try:
        from modelforge.graph.store import GraphStore
        store = GraphStore(db)
        sources = store.list_sources()
    except Exception as e:
        return {"error": f"failed to read sources: {e!r}"}

    return {"graph_db": str(db), "sources": sources, "count": len(sources)}


@server.tool()
def lineage_walk(graph_db: str, cell: str) -> dict[str, Any]:
    """Trace a cell back to its source documents.

    Walks: cell → driver(s) → source(s) → doc page. The defining moat of ModelForge —
    every output number is queryable back to where it came from.

    Args:
        graph_db: Path to the SQLite graph store.
        cell: Cell reference (e.g. "Returns!E45" or "IS!Revenue_2026").

    Returns:
        Ordered list of upstream cells/drivers/sources for ``cell``.
    """
    db = _resolve_path(graph_db)
    if not db.exists():
        return {"error": f"graph_db not found: {db}"}

    try:
        from modelforge.graph.store import GraphStore
        store = GraphStore(db)
        path = store.lineage(cell)
    except Exception as e:
        return {"error": f"lineage walk failed: {e!r}"}

    return {"graph_db": str(db), "cell": cell, "lineage": path}


@server.tool()
def ingest_dataroom(
    dataroom_path: str,
    template: str = "project_finance",
    output_spec: str | None = None,
) -> dict[str, Any]:
    """Auto-extract a YAML spec from a directory of PDFs/XLSXs/CSVs.

    Uses Claude (via the Anthropic SDK) to classify each document, then
    structured extraction produces a Pydantic-validated YAML ready for
    ``build_model``. Generates an INGESTION_REPORT.md listing every extracted
    field, source ID, and confidence level.

    Args:
        dataroom_path: Directory containing the data room.
        template: Which template to ingest into (default: project_finance).
                  Use ``list_templates`` to enumerate options.
        output_spec: Where to write the resulting YAML (default: auto-name).

    Returns:
        Paths to generated YAML + ingestion report + extraction stats.
    """
    dr = _resolve_path(dataroom_path)
    if not dr.exists() or not dr.is_dir():
        return {"error": f"dataroom not a directory: {dr}"}

    try:
        from modelforge.ingest.pipeline import ingest as run_ingest
    except ImportError:
        return {
            "error": "ingest requires `pip install modelforge[ingest]` "
            "(adds anthropic + pdfplumber + pypdf)."
        }

    out = _resolve_path(output_spec) if output_spec else dr.parent / f"{dr.name}.yaml"

    try:
        result = run_ingest(dr, template=template, output=out)
    except Exception as e:
        log.exception("ingest failed")
        return {"error": f"ingest failed: {e!r}"}

    return {
        "dataroom": str(dr),
        "spec": str(out),
        "report": str(out.with_suffix(".ingestion.md")),
        "template": template,
        "extracted_fields": result.get("extracted_fields", 0) if isinstance(result, dict) else 0,
    }


@server.tool()
def export_pptx(xlsx_path: str, output_path: str | None = None) -> dict[str, Any]:
    """Generate an executive PPTX from a ModelForge workbook.

    Produces a 5-slide deck: Cover · Assumptions · Sources · Key Outputs · QC Pass.
    Branded with the bulge-tier color convention.

    Args:
        xlsx_path: ModelForge workbook to summarize.
        output_path: Output .pptx (default: ``<xlsx>.pptx``).
    """
    xlsx = _resolve_path(xlsx_path)
    if not xlsx.exists():
        return {"error": f"workbook not found: {xlsx}"}

    try:
        from modelforge.exporters.pptx import build_committee_deck
    except ImportError:
        return {
            "error": "pptx export requires `pip install modelforge[export]` "
            "(adds python-pptx)."
        }

    out = _resolve_path(output_path) if output_path else xlsx.with_suffix(".pptx")
    try:
        build_committee_deck(xlsx, out)
    except Exception as e:
        log.exception("pptx export failed")
        return {"error": f"pptx export failed: {e!r}"}

    return {"xlsx": str(xlsx), "pptx": str(out), "ok": True}


@server.tool()
def export_docx(xlsx_path: str, output_path: str | None = None) -> dict[str, Any]:
    """Generate an IC/credit-memo DOCX from a ModelForge workbook.

    Produces a structured Word document with sections: Executive Summary,
    Transaction Overview, Key Assumptions (cited), Risk Analysis, Recommendation.

    Args:
        xlsx_path: ModelForge workbook to summarize.
        output_path: Output .docx (default: ``<xlsx>.docx``).
    """
    xlsx = _resolve_path(xlsx_path)
    if not xlsx.exists():
        return {"error": f"workbook not found: {xlsx}"}

    try:
        from modelforge.exporters.docx import build_ic_memo
    except ImportError:
        return {
            "error": "docx export requires `pip install modelforge[export]` "
            "(adds python-docx)."
        }

    out = _resolve_path(output_path) if output_path else xlsx.with_suffix(".docx")
    try:
        build_ic_memo(xlsx, out)
    except Exception as e:
        log.exception("docx export failed")
        return {"error": f"docx export failed: {e!r}"}

    return {"xlsx": str(xlsx), "docx": str(out), "ok": True}


# ---- Entry point ------------------------------------------------------------


def main() -> None:
    """Stdio MCP server entry point — invoked by `modelforge-mcp`."""
    server.run()


if __name__ == "__main__":
    main()

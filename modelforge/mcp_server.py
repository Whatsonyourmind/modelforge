"""ModelForge MCP server.

Exposes ModelForge as an MCP tool catalog for AI agents (Claude Code, Cursor, Cline,
ChatGPT Enterprise, etc.).

Usage::

    pip install modelforge-finance[mcp]
    modelforge-mcp                       # stdio server

Tools exposed (17):

    list_templates       — discover available financial-model templates
    build_model          — YAML spec → live-formula Excel workbook + SQLite linkage graph
    qc_workbook          — run automated structural QC gate (8 checks)
    list_sources         — enumerate source citations from the linkage graph
    lineage_walk         — trace cell → driver → source → doc page
    ingest_dataroom      — auto-extract validated YAML spec from a directory of PDFs/XLSXs/CSVs
    export_pptx          — generate executive PPTX from a model workbook
    screen_deals         — filter and rank deal spec YAMLs by criteria without building
    compute_tax          — corporate income tax across 7 jurisdictions
    export_docx          — generate IC/credit memo DOCX from a model workbook
    data_providers_status — list every market-data provider and its availability
    quote                — latest price quote for a ticker
    history              — historical OHLCV bars for a ticker
    fundamentals         — reported financial statements for a ticker
    search_filings       — list recent SEC EDGAR filings for a US ticker
    entity_lookup        — resolve an entity by LEI, FIGI, or ticker
    search_securities    — free-text search across reference-data providers
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

from modelforge.templates import REGISTRY, PREVIEW_TEMPLATES, build_model
from modelforge.qc import run_qc

log = logging.getLogger("modelforge.mcp")

server = FastMCP(
    name="modelforge",
    instructions=(
        "ModelForge is a deterministic financial model factory. "
        "Every cell is live-formulated, every number traces to a source doc page. "
        "Use `list_templates` to see what's available, "
        "`build_model` to produce a workbook from a YAML spec, `qc_workbook` to run "
        "the automated structural QC gate, and `export_pptx`/`export_docx` for committee "
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
    """List every financial-model template the server can build, with a count.

    Use this FIRST to discover which model types are available (e.g. DCF,
    three-statement, M&A merger, LBO, project finance, NPL portfolio, structured
    credit, IPO, restructuring) before calling build_model or ingest_dataroom.
    Returns {templates: [{name, registered, preview}], count} from the live REGISTRY.
    """
    return {
        "templates": [
            {"name": name, "registered": True, "preview": name in PREVIEW_TEMPLATES}
            for name in sorted(REGISTRY.keys())
        ],
        "count": len(REGISTRY),
    }


@server.tool()
def build_model(spec_path: str, output_dir: str | None = None) -> dict[str, Any]:
    """Generate a live-formula Excel workbook (.xlsx) plus its SQLite linkage graph (.graph.db) from a typed YAML spec.

    Use when the user has (or has just produced) a ModelForge YAML spec and wants
    the actual workbook — formulas in every cell, scenario toggles, and
    source-tagged inputs. Takes spec_path and optional output_dir; returns
    {xlsx, graph_db, spec, ok} or {error}.
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
    """Run the automated structural QC gate on a ModelForge workbook and return a per-check pass/fail report.

    Use after build_model (or on any ModelForge .xlsx) to verify it is
    audit-ready before exporting or sharing. Runs 8 checks: QC-sheet presence,
    sign-convention declaration, scenario-toggle named range, named-range
    population, comments on hardcoded cells, source references resolving, print
    areas, and no orphan sheets. Takes xlsx_path; returns {xlsx, report} or {error}.
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
    """Enumerate the source citations recorded in a model's linkage graph.

    Returns the doc, page, publisher, date and URL behind each S-NNN reference.
    Use when an agent needs the provenance list for a built model (e.g. to render
    a citations table or verify every input is sourced). Takes graph_db (the
    .graph.db from build_model); returns {graph_db, sources, count} or {error}.
    """
    db = _resolve_path(graph_db)
    if not db.exists():
        return {"error": f"graph_db not found: {db}"}

    try:
        from modelforge.graph.store import GraphStore
        store = GraphStore(db)
        sources = store.list_sources()
    except AttributeError:
        # Fallback: query source nodes directly from SQLite when list_sources
        # is not yet present on this version of GraphStore.
        try:
            import sqlite3, json as _json
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, label, payload FROM nodes WHERE kind = 'source' ORDER BY id"
            ).fetchall()
            conn.close()
            sources = [
                {"id": r["id"], "label": r["label"], **_json.loads(r["payload"])}
                for r in rows
            ]
        except Exception as e2:
            return {"error": f"failed to read sources: {e2!r}"}
    except Exception as e:
        return {"error": f"failed to read sources: {e!r}"}

    return {"graph_db": str(db), "sources": sources, "count": len(sources)}


@server.tool()
def lineage_walk(graph_db: str, cell: str) -> dict[str, Any]:
    """Trace a single output cell back through its drivers to the underlying source document and page.

    Use when the user asks 'where does this number come from?' or 'show the
    audit trail for cell X' on a built model. Takes graph_db and a cell
    reference (e.g. "Returns!E45"); returns an ordered list of upstream hops
    cell -> driver -> source -> doc page.
    """
    db = _resolve_path(graph_db)
    if not db.exists():
        return {"error": f"graph_db not found: {db}"}

    try:
        import sqlite3 as _sqlite3
        from modelforge.graph.store import GraphStore
        store = GraphStore(db)
        # Discover the first model_id persisted in this database.
        conn = _sqlite3.connect(db)
        _row = conn.execute("SELECT DISTINCT model_id FROM nodes LIMIT 1").fetchone()
        conn.close()
        if _row is None:
            return {"error": "graph_db contains no model data"}
        model_id = _row[0]
        path = store.lineage(model_id, cell)
    except Exception as e:
        return {"error": f"lineage walk failed: {e!r}"}

    return {"graph_db": str(db), "cell": cell, "lineage": path}


@server.tool()
def ingest_dataroom(
    dataroom_path: str,
    template: str = "project_finance",
    output_spec: str | None = None,
) -> dict[str, Any]:
    """Read a folder of PDFs/XLSXs/CSVs and produce a Pydantic-validated ModelForge YAML spec plus an ingestion report.

    Use when the user has a directory of raw deal documents and wants to turn
    them into a buildable spec without hand-coding it. Each extracted field is
    traced to its source. Requires the [ingest] extra and an Anthropic API key.
    Takes dataroom_path, template (default project_finance), optional
    output_spec; returns paths to the YAML + ingestion report + extracted_fields
    count.
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
    """Generate an executive PowerPoint deck (.pptx) summarizing a built ModelForge workbook.

    Use when the user wants a presentation-ready summary of a model for a
    committee or stakeholder review. Requires the [export] extra (python-pptx).
    Takes xlsx_path and optional output_path; returns {xlsx, pptx, ok} or
    {error}.
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
def screen_deals(
    spec_dir: str,
    filters: dict[str, Any] | None = None,
    rank_by: dict[str, float] | None = None,
    top_n: int = 25,
) -> dict[str, Any]:
    """Filter and rank a directory of deal spec YAMLs by quantitative criteria without building each workbook.

    Use when the user wants to triage many candidate deals — e.g. 'rank all
    specs with EBITDA margin >= 20% and leverage <= 5x by base-case IRR'.
    Filter keys support _min (>=), _max (<=), _in (membership), or bare key
    (equality); rank_by weights are positive (higher better) or negative (lower
    better). Takes spec_dir, filters, rank_by, top_n (default 25); returns a
    ranked list of {deal_id, spec_path, summary, score}.
    """
    try:
        from modelforge.screening import screen
    except ImportError as e:
        return {"error": f"screening unavailable: {e!r}"}

    results = screen(
        spec_dir=spec_dir,
        filters=filters or {},
        rank_by=rank_by or {},
        top_n=top_n,
    )
    return {
        "spec_dir": spec_dir,
        "count": len(results),
        "results": [
            {
                "deal_id": r.deal_id,
                "spec_path": str(r.spec_path),
                "summary": r.summary,
                "score": r.score,
            }
            for r in results
        ],
    }


@server.tool()
def compute_tax(
    jurisdiction: str,
    pretax_book_income: float,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compute corporate income tax (effective rate + total tax) for one of seven jurisdictions from pretax book income.

    Use when a model or analysis needs a quick jurisdiction-aware tax figure.
    US, UK, DE, FR, ES, JP are fully wired; IT returns a pointer to the
    dedicated italian_tax module for full IRES/IRAP inputs. Takes jurisdiction
    code, pretax_book_income, and optional jurisdiction-specific kwargs; returns
    {jurisdiction, etr, total_tax} or an error for an unknown code.
    """
    from decimal import Decimal
    pti = Decimal(str(pretax_book_income))

    j = jurisdiction.upper()
    if j == "IT":
        from modelforge.finance_core import italian_tax as t
        return {"jurisdiction": "IT", "note": "use italian_tax module for full IRES/IRAP/SIIQ/PEX inputs"}
    if j == "US":
        from modelforge.finance_core.us_gaap_tax import compute_us_tax, USTaxInputs
        out = compute_us_tax(USTaxInputs(pretax_book_income=pti))
        return {"jurisdiction": "US", "etr": float(out.effective_rate), "total_tax": float(out.total_current_tax)}
    if j == "UK":
        from modelforge.finance_core.uk_corp_tax import compute_uk_tax, UKTaxInputs
        out = compute_uk_tax(UKTaxInputs(pretax_book_income=pti))
        return {"jurisdiction": "UK", "etr": float(out.effective_rate), "total_tax": float(out.corporation_tax)}
    if j == "DE":
        from modelforge.finance_core.german_corp_tax import compute_german_tax, GermanTaxInputs
        out = compute_german_tax(GermanTaxInputs(pretax_book_income=pti))
        return {"jurisdiction": "DE", "etr": float(out.effective_rate), "total_tax": float(out.total_tax)}
    if j == "FR":
        from modelforge.finance_core.french_corp_tax import compute_french_tax, FrenchTaxInputs
        out = compute_french_tax(FrenchTaxInputs(pretax_book_income=pti))
        return {"jurisdiction": "FR", "etr": float(out.effective_rate), "total_tax": float(out.total_tax)}
    if j == "ES":
        from modelforge.finance_core.spanish_corp_tax import compute_spanish_tax, SpanishTaxInputs
        out = compute_spanish_tax(SpanishTaxInputs(pretax_book_income=pti))
        return {"jurisdiction": "ES", "etr": float(out.effective_rate), "total_tax": float(out.total_tax)}
    if j == "JP":
        from modelforge.finance_core.japanese_corp_tax import compute_japanese_tax, JapaneseTaxInputs
        out = compute_japanese_tax(JapaneseTaxInputs(pretax_book_income=pti, capital=Decimal(str(kwargs.get("capital", 200000000)))))
        return {"jurisdiction": "JP", "etr": float(out.effective_rate), "total_tax": float(out.total_tax)}
    return {"error": f"unknown jurisdiction {jurisdiction!r}. Use one of IT/US/UK/DE/FR/ES/JP."}


@server.tool()
def export_docx(xlsx_path: str, output_path: str | None = None) -> dict[str, Any]:
    """Generate a structured Word memo (.docx) from a built ModelForge workbook.

    Sections: Executive Summary, Transaction Overview, cited Key Assumptions,
    Risk Analysis, Recommendation. Use when the user wants a written
    investment/credit memo derived from a model. Requires the [export] extra
    (python-docx). Takes xlsx_path and optional output_path; returns
    {xlsx, docx, ok} or {error}.
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


# ---- Market data tools ------------------------------------------------------


@server.tool()
def data_providers_status() -> dict[str, Any]:
    """List every registered market-data provider with its tier and an availability flag.

    Use this FIRST before quote/history/fundamentals/search_filings to see
    which providers are actually usable in the current environment (free
    providers work out of the box; paid/institutional ones activate only when
    their API keys are set). Returns {providers, available_count, total_count}.
    """
    from modelforge.feeds import status
    rows = status()
    return {
        "providers": rows,
        "available_count": sum(1 for r in rows if r["available"]),
        "total_count": len(rows),
    }


@server.tool()
def quote(symbol: str, prefer: str | None = None) -> dict[str, Any]:
    """Fetch the latest price quote for a ticker, auto-routed to the best available market-data provider.

    Use when the user needs a current price for a symbol. Takes a vendor-native
    symbol (e.g. AAPL, BNP.PA) and an optional ``prefer`` provider to try first;
    returns the quote fields, or an {error, hint} if no provider is configured.
    """
    from dataclasses import asdict
    from modelforge.feeds import quote as _quote, NoProviderAvailable
    try:
        q = _quote(symbol, prefer=prefer)
    except NoProviderAvailable as e:
        return {"error": str(e), "hint": "Set provider env vars (POLYGON_API_KEY, FMP_API_KEY, etc.)."}
    return asdict(q)


@server.tool()
def history(
    symbol: str,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    limit: int = 250,
    prefer: str | None = None,
) -> dict[str, Any]:
    """Fetch historical OHLCV price bars for a ticker over a date range and interval.

    Use when the user needs a price series (e.g. daily bars for the last year,
    or intraday bars). Takes symbol, interval (1m/5m/1h/1d/1wk/1mo), optional
    start/end ISO dates, limit, and optional prefer provider; returns
    {symbol, interval, bars: [...]} or {error}.
    """
    from dataclasses import asdict
    from modelforge.feeds import history as _history, NoProviderAvailable
    try:
        bars = _history(symbol, interval=interval, start=start, end=end, limit=limit, prefer=prefer)
    except NoProviderAvailable as e:
        return {"error": str(e)}
    return {"symbol": symbol, "interval": interval, "bars": [asdict(b) for b in bars]}


@server.tool()
def fundamentals(
    symbol: str,
    statement: str = "income",
    period: str = "annual",
    limit: int = 5,
    prefer: str | None = None,
) -> dict[str, Any]:
    """Fetch reported financial statements (income, balance, or cashflow) for a ticker, newest first.

    Use when the user needs historical fundamentals to seed or sanity-check a
    model. Takes symbol, statement (income/balance/cashflow), period
    (annual/quarter), limit, optional prefer provider; returns
    {symbol, statement, period, data: [...]} or {error}.
    """
    from dataclasses import asdict
    from modelforge.feeds import fundamentals as _fund, NoProviderAvailable
    try:
        rows = _fund(symbol, statement=statement, period=period, limit=limit, prefer=prefer)  # type: ignore[arg-type]
    except NoProviderAvailable as e:
        return {"error": str(e)}
    return {
        "symbol": symbol,
        "statement": statement,
        "period": period,
        "data": [asdict(r) for r in rows],
    }


@server.tool()
def search_filings(ticker: str, form: str | None = None, limit: int = 20) -> dict[str, Any]:
    """List recent SEC EDGAR filings (10-K, 10-Q, 8-K, etc.) for a US ticker.

    Use when the user wants to find or link a company's primary filings for
    due diligence or sourcing. Takes ticker, optional form filter (e.g. 10-K),
    and limit; returns {ticker, filings: [...]} or {error}.
    """
    from dataclasses import asdict
    from modelforge.feeds import filings as _filings, NoProviderAvailable
    try:
        rows = _filings(ticker, form=form, limit=limit, prefer="edgar")
    except NoProviderAvailable as e:
        return {"error": str(e)}
    return {"ticker": ticker.upper(), "filings": [asdict(r) for r in rows]}


@server.tool()
def entity_lookup(
    lei: str | None = None,
    figi: str | None = None,
    ticker: str | None = None,
) -> dict[str, Any]:
    """Resolve a legal entity by LEI, FIGI, or ticker and return its canonical legal name plus any cross-reference IDs.

    Use to disambiguate a counterparty or issuer before building a model spec
    or wiring market data. Takes any one of lei / figi / ticker; returns the
    resolved Entity record or {error}.
    """
    from dataclasses import asdict
    from modelforge.feeds import entity_lookup as _entity, NoProviderAvailable
    try:
        e = _entity(lei=lei, figi=figi, ticker=ticker)
    except NoProviderAvailable as err:
        return {"error": str(err)}
    return asdict(e)


@server.tool()
def search_securities(query: str, limit: int = 20) -> dict[str, Any]:
    """Free-text search for securities/entities across configured reference data providers, returning the first non-empty result set.

    Use when the user has a company name or fragment and needs to find the
    matching ticker/identifier. Takes a query string and limit (default 20);
    returns {query, results} or {error}.
    """
    from modelforge.feeds import search as _search, NoProviderAvailable
    try:
        rows = _search(query, limit=limit)
    except NoProviderAvailable as e:
        return {"error": str(e)}
    return {"query": query, "results": rows}


# ---- Entry point ------------------------------------------------------------


def main() -> None:
    """Stdio MCP server entry point — invoked by `modelforge-mcp`."""
    server.run()


if __name__ == "__main__":
    main()

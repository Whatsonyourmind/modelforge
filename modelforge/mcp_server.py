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
def screen_deals(
    spec_dir: str,
    filters: dict[str, Any] | None = None,
    rank_by: dict[str, float] | None = None,
    top_n: int = 25,
) -> dict[str, Any]:
    """Screen a directory of deal YAMLs by criteria, ranking the top N matches.

    Mirrors Rogo's Screenings feature: filter 1,000+ deals by sector, geography,
    deal size, IRR threshold, leverage ceiling, EBITDA margin — without building
    each model. Works on spec YAMLs with a ``screening:`` block.

    Args:
        spec_dir: Directory containing deal spec YAML files (walked recursively).
        filters: e.g. ``{"sector": "industrials", "ebitda_margin_min": 0.20,
                  "leverage_x_max": 5.0, "geography_in": ["EU/IT","EU/ES"]}``.
                  Suffixes: ``_min`` (gte), ``_max`` (lte), ``_in`` (membership),
                  no suffix = equality.
        rank_by: Weights for sort key. Positive = higher better, negative = lower better.
                  e.g. ``{"irr_base": 0.5, "leverage_x": -0.3, "deal_size_eur_m": 0.2}``.
        top_n: Max results returned (default 25).

    Returns:
        Ranked list of {deal_id, spec_path, summary, score}.
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
    """Compute corporate tax for a given jurisdiction.

    Args:
        jurisdiction: One of "IT" (Italy), "US" (federal+state), "UK" (FRS 102),
                       "DE" (Germany), "FR" (France), "ES" (Spain), "JP" (Japan).
        pretax_book_income: Pretax book income in local currency.
        **kwargs: Additional jurisdiction-specific parameters (NOL CF, R&D,
                  state rate, Hebesatz, capital, etc.). See finance_core module
                  for each jurisdiction's full input dataclass.

    Returns:
        Effective rate + total tax + per-component breakdown.
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


# ---- Market data tools ------------------------------------------------------


@server.tool()
def data_providers_status() -> dict[str, Any]:
    """List every registered market data provider and its availability.

    Returns adapter name, tier (bulge/institutional/free), required-auth
    flag, capability list, and an `available` flag (True if creds + SDK
    are present). Use this first to see what's wired up before calling
    `quote`/`fundamentals`/`filings`.
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
    """Latest quote for a symbol, auto-routed to the best available provider.

    Args:
        symbol: Vendor-native ticker (e.g. ``AAPL``, ``BNP.PA``, ``IBM US Equity``).
        prefer: Optional provider name to try first (``bloomberg``, ``polygon``,
                ``fmp``, ``finnhub``, ``tiingo``, ``refinitiv``, ``factset``).
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
    """OHLCV bars for a symbol over a date range.

    Args:
        symbol: Ticker.
        interval: ``1m``, ``5m``, ``1h``, ``1d``, ``1wk``, ``1mo``.
        start: ISO date inclusive (default: limit-derived).
        end: ISO date inclusive (default: today).
        limit: Max bars returned.
        prefer: Optional provider override.
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
    """Income / balance / cashflow fundamentals for a ticker.

    Args:
        symbol: Ticker (vendor-native).
        statement: ``income``, ``balance``, or ``cashflow``.
        period: ``annual`` or ``quarter``.
        limit: How many periods back, newest first.
        prefer: Optional provider override.
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
    """List recent SEC filings (10-K, 10-Q, 8-K) for a US ticker.

    Args:
        ticker: US ticker (resolved to CIK via the SEC ticker file).
        form: Optional form filter, e.g. ``10-K``.
        limit: Max filings.
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
    """Cross-reference an entity by LEI (GLEIF), FIGI (OpenFIGI), or ticker.

    Resolves the canonical legal name and any other available IDs.
    Use this before any model spec to disambiguate counterparties.
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
    """Free-text search across the available reference universes.

    Tries every available provider's search() (FMP, EDGAR, OpenFIGI,
    GLEIF) and returns the first non-empty result set.
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

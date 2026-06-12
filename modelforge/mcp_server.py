"""ModelForge MCP server.

Exposes ModelForge as an MCP tool catalog for AI agents (Claude Code, Cursor, Cline,
ChatGPT Enterprise, etc.).

Usage::

    pip install modelforge-finance[mcp]
    modelforge-mcp                       # stdio server

Tools exposed (22):

    list_templates       — discover available financial-model templates
    spec_guide           — authoring guide for one model_type (blocks, ID rules, example)
    get_spec_schema      — JSON Schema for a model_type's YAML spec
    validate_spec        — validate a draft spec WITHOUT building (friendly errors)
    build_model          — YAML spec → live-formula Excel workbook + SQLite linkage graph
    certify              — build from spec YAML (or audit a workbook) → CERTIFIED/WARN/FAIL
    qc_workbook          — run automated structural QC gate (8 checks)
    list_sources         — enumerate source citations from the linkage graph
    lineage_walk         — trace cell → driver → source → doc page
    ingest_dataroom      — auto-extract validated YAML spec from a directory of PDFs/XLSXs/CSVs
    export_pptx          — generate executive PPTX from a model workbook
    export_deck          — certified, hash-stamped board deck (fail-closed: manifest + CERTIFIED audit)
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

Conversational authoring loop (for LLM clients such as Claude Desktop/Code):

    1. list_templates                — what can be built
    2. spec_guide / get_spec_schema  — how to author the chosen model_type
    3. draft the YAML spec           — start from spec_guide's example_yaml
    4. validate_spec                 — fix friendly errors, repeat until valid
    5. build_model or certify(spec_yaml=...) — produce the workbook
    6. certify / qc_workbook         — audit the delivered artifact
    7. list_sources + lineage_walk   — walk any number back to its source
    8. export_pptx / export_docx     — committee deliverables
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "MCP server requires `pip install modelforge[mcp]` "
        "(adds `mcp>=1.12.0` to your environment)."
    ) from e

# NOTE: the template builder is imported under an alias so the global name
# `build_model` is NOT shadowed by the `build_model` *tool* defined below.
# Without the alias the tool would recursively call itself instead of the
# real template factory.
from modelforge.templates import REGISTRY, PREVIEW_TEMPLATES, build_model as _build_model
from modelforge.qc import run_qc

log = logging.getLogger("modelforge.mcp")

server = FastMCP(
    name="modelforge",
    instructions=(
        "ModelForge is a deterministic financial model factory. "
        "Every cell is live-formulated, every number traces to a source doc page. "
        "Conversational authoring loop: `list_templates` (discover) -> "
        "`spec_guide`/`get_spec_schema` (learn the model_type) -> draft a YAML spec -> "
        "`validate_spec` (fix friendly errors WITHOUT building, repeat until valid) -> "
        "`build_model` or `certify(spec_yaml=...)` (build) -> `certify`/`qc_workbook` "
        "(audit) -> `list_sources`/`lineage_walk` (provenance) -> "
        "`export_pptx`/`export_docx` (committee deliverables). "
        "Source traceability is the moat — every output cell can be "
        "walked back to the underlying document via `lineage_walk`."
    ),
)


# ---- Helper -----------------------------------------------------------------


def _resolve_path(p: str | Path) -> Path:
    """Resolve a user-supplied path, expanding ~ and making absolute."""
    return Path(os.path.expanduser(str(p))).resolve()


# ---- Conversational-authoring helpers ---------------------------------------
#
# These mirror the CLI's friendly validation chain (cli._load_and_validate_spec
# / _warn_unknown_top_keys / _check_dangling_sources) but COLLECT messages into
# structured lists instead of printing to a console and sys.exit()-ing, so an
# MCP client gets machine-readable {errors, warnings} it can act on.


def _read_spec_input(spec_yaml: str) -> tuple[bytes, Path | None]:
    """Accept either literal YAML text or a path to an existing .yaml/.yml file.

    Returns (spec_bytes, source_path_or_None). LLM clients sometimes pass a
    file path where text is expected — treating a single-line existing
    ``*.yaml``/``*.yml`` path as a file read makes both shapes Just Work.
    """
    candidate = spec_yaml.strip()
    if "\n" not in candidate and candidate.lower().endswith((".yaml", ".yml")):
        p = _resolve_path(candidate)
        if p.exists() and p.is_file():
            return p.read_bytes(), p
    return spec_yaml.encode("utf-8"), None


def _friendly_pydantic_errors(exc: Exception) -> list[str]:
    """Render a Pydantic ValidationError as the CLI's plain-language one-liners.

    Same ordering contract as ``modelforge.spec.errors.format_validation_error``
    (missing fields first, then sorted by dotted path) but returned as a list so
    the MCP payload stays structured.
    """
    try:
        from modelforge.spec.errors import _dotted, _friendly_line
        raw = list(exc.errors())  # type: ignore[attr-defined]
        raw.sort(key=lambda e: (0 if e.get("type") == "missing" else 1,
                                _dotted(e.get("loc", ()))))
        return [_friendly_line(e) for e in raw]
    except Exception:
        return [str(exc)]


def _unknown_top_keys(raw: dict, spec_class) -> list[str]:
    """Mirror cli._warn_unknown_top_keys: unknown TOP-LEVEL keys as warnings.

    Pydantic silently drops unknown keys, so a fat-fingered field name would
    otherwise build with the default — a silent wrong-number risk.
    """
    extras = sorted(set(raw) - set(spec_class.model_fields))
    return [f"unknown top-level field ignored (typo?): {k}" for k in extras]


def _dangling_source_ids(spec) -> list[str]:
    """Mirror cli._check_dangling_sources: referenced-but-undefined source ids.

    A ``*_source_id`` pointing at a Source that is not in ``sources`` plants a
    fabricated "Source: S-xxx" citation on the workbook — an integrity defect,
    so callers must treat any returned id as a hard error.
    """
    from pydantic import BaseModel as _BM
    from modelforge.spec.base import Source

    defined: set[str] = set()
    referenced: set[str] = set()
    seen: set[int] = set()

    def walk(o):
        if id(o) in seen:
            return
        if isinstance(o, _BM):
            seen.add(id(o))
            if isinstance(o, Source) and isinstance(o.id, str) and o.id.strip():
                defined.add(o.id)
            for fname, fval in o.__dict__.items():
                if ((fname == "source_id" or fname.endswith("_source_id"))
                        and isinstance(fval, str) and fval.strip()):
                    referenced.add(fval)
                walk(fval)
        elif isinstance(o, (list, tuple)):
            for it in o:
                walk(it)
        elif isinstance(o, dict):
            for it in o.values():
                walk(it)

    walk(spec)
    return sorted(referenced - defined)


def _validate_spec_chain(spec_yaml: str, model_type: str | None = None) -> dict[str, Any]:
    """Run the CLI's full friendly validation chain on YAML text, no build.

    Chain (same order as ``cli._load_and_validate_spec``): YAML parse →
    mapping check → model_type resolution → Pydantic field validation →
    unknown top-level keys (warnings) → dangling source ids (errors).

    Returns {valid, model_type, errors, warnings} plus private ``_spec`` /
    ``_spec_bytes`` / ``_spec_path`` keys for internal reuse by ``certify``.
    """
    result: dict[str, Any] = {
        "valid": False, "model_type": None, "errors": [], "warnings": [],
        "_spec": None, "_spec_bytes": None, "_spec_path": None,
    }

    spec_bytes, src_path = _read_spec_input(spec_yaml)
    result["_spec_path"] = src_path

    try:
        raw = yaml.safe_load(spec_bytes)
    except yaml.YAMLError as e:
        result["errors"].append(f"YAML parse error: {e}")
        return result
    if not isinstance(raw, dict):
        result["errors"].append(
            "spec is not a YAML mapping (expected a document with "
            "`model_type: ...` plus the template's blocks)."
        )
        return result

    declared = raw.get("model_type")
    effective = declared or model_type or "unitranche"
    if declared and model_type and declared != model_type:
        result["warnings"].append(
            f"spec declares model_type {declared!r} but {model_type!r} was "
            f"requested; validating as {declared!r}."
        )
    result["model_type"] = effective

    try:
        from modelforge.cli import _load_spec_class
        spec_class = _load_spec_class(effective)
    except ValueError as e:
        result["errors"].append(str(e))
        return result
    except Exception as e:  # pragma: no cover - defensive
        result["errors"].append(f"spec loader unavailable: {e!r}")
        return result

    from pydantic import ValidationError
    try:
        spec = spec_class.model_validate(raw)
    except ValidationError as e:
        result["errors"].extend(_friendly_pydantic_errors(e))
        return result

    result["warnings"].extend(_unknown_top_keys(raw, spec_class))

    dangling = _dangling_source_ids(spec)
    if dangling:
        result["errors"].append(
            f"source id(s) referenced but not defined in `sources`: "
            f"{', '.join(dangling)}. Add them to the sources list (or fix the "
            f"reference) — a dangling source_id plants a citation for a source "
            f"that isn't in the workbook."
        )
        return result

    result["valid"] = True
    result["_spec"] = spec
    result["_spec_bytes"] = bytes(spec_bytes)
    return result


def _manifest_sha(xlsx: Path) -> str | None:
    """workbook_sha256 from the build manifest sidecar, or None if unreadable."""
    try:
        from modelforge.analytics.manifest import read_manifest
        return read_manifest(xlsx.with_suffix(".manifest.json")).workbook_sha256
    except Exception:
        return None


# ---- Tools ------------------------------------------------------------------


@server.tool()
def list_templates() -> dict[str, Any]:
    """List every financial-model template the server can build, with a count.

    Use this FIRST to discover which model types are available (e.g. DCF,
    three-statement, M&A merger, LBO, project finance, NPL portfolio, structured
    credit, IPO, restructuring) before calling build_model or ingest_dataroom.
    Returns {templates: [{name, registered, preview}], count} from the live REGISTRY.

    Conversational loop: STEP 1 — pick a model_type here, then call
    spec_guide(model_type) to learn how to author its spec.
    """
    return {
        "templates": [
            {"name": name, "registered": True, "preview": name in PREVIEW_TEMPLATES}
            for name in sorted(REGISTRY.keys())
        ],
        "count": len(REGISTRY),
    }


@server.tool()
def spec_guide(model_type: str) -> dict[str, Any]:
    """Return a concise authoring guide for one model_type: required blocks, Source/Assumption ID rules, a starter example, and the most common validation errors.

    Use BEFORE drafting a spec so the first draft validates. The
    ``example_yaml`` is seeded from a shipped, build-ready example (or an
    honest required-field stub when ``example_is_stub`` is true — currently
    ipo/restructuring); edit its placeholder values rather than authoring from
    a blank page. ``required_blocks``/``optional_blocks`` are the legal
    top-level YAML keys. Returns {model_type, required_blocks, optional_blocks,
    id_discipline, example_yaml, example_is_stub, common_errors, workflow} or
    {error} for an unknown model_type.

    Conversational loop: STEP 2 — after list_templates, before drafting.
    Call get_spec_schema for the full field-level JSON Schema.
    """
    try:
        from modelforge.cli import _load_spec_class
        spec_class = _load_spec_class(model_type)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # pragma: no cover - defensive
        return {"error": f"spec loader unavailable: {e!r}"}

    from modelforge.spec.scaffold import _SEED_EXAMPLE, scaffold_yaml
    try:
        example_yaml: str | None = scaffold_yaml(model_type, spec_class)
    except KeyError:
        example_yaml = None

    fields = spec_class.model_fields
    required = sorted(n for n, f in fields.items() if f.is_required())
    optional = sorted(n for n, f in fields.items() if not f.is_required())

    return {
        "model_type": model_type,
        "required_blocks": required,
        "optional_blocks": optional,
        "id_discipline": (
            "Sources are declared ONCE in the top-level `sources:` block with "
            "ids S-001, S-002, ... Every fact-bearing input cites one via a "
            "`source_id` / `*_source_id` field; a referenced id that is not "
            "defined in `sources` is a HARD validation error (it would plant a "
            "fabricated citation on the workbook). Assumptions carry ids "
            "A-001, A-002, ... with name/label/unit/base (optionally "
            "worst/best, rationale, confidence H/M/L, and a source_id). Keep "
            "ids unique and stable across spec revisions."
        ),
        "example_yaml": example_yaml,
        "example_is_stub": model_type not in _SEED_EXAMPLE,
        "common_errors": [
            {
                "error": "Missing required field: <block>.<field>",
                "fix": "Start from example_yaml and keep every required "
                       f"top-level block ({', '.join(required) or 'see schema'}); "
                       "fill required nested fields instead of deleting them.",
            },
            {
                "error": "source id(s) referenced but not defined in `sources`: S-0XX",
                "fix": "Every source_id/*_source_id must match an entry in the "
                       "top-level `sources:` block — add the missing source or "
                       "fix the reference.",
            },
            {
                "error": "unknown top-level field ignored (typo?): <key>",
                "fix": "Unknown top-level keys are dropped silently at build "
                       "time and surfaced as warnings by validate_spec — check "
                       "spelling against required_blocks/optional_blocks or "
                       "get_spec_schema.",
            },
        ],
        "workflow": [
            "1. list_templates",
            f"2. spec_guide('{model_type}') / get_spec_schema('{model_type}')",
            "3. draft the YAML spec starting from example_yaml",
            "4. validate_spec(spec_yaml=...) — repeat until valid",
            "5. build_model(spec_path) or certify(spec_yaml=...) to build",
            "6. certify / qc_workbook on the built .xlsx",
            "7. list_sources + lineage_walk on the .graph.db",
            "8. export_pptx / export_docx",
        ],
    }


@server.tool()
def get_spec_schema(model_type: str) -> dict[str, Any]:
    """Return the full JSON Schema (draft 2020-12) for a model_type's YAML spec.

    Use when spec_guide's block list is not enough and you need exact
    field-level types, enums, ranges, and nested structures while drafting or
    repairing a spec. Same schema the CLI's `modelforge schema` command emits.
    Returns {model_type, schema} or {error} for an unknown model_type.

    Conversational loop: STEP 2 (detail level) — alongside spec_guide, before
    validate_spec.
    """
    try:
        from modelforge.cli import _load_spec_class
        spec_class = _load_spec_class(model_type)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # pragma: no cover - defensive
        return {"error": f"spec loader unavailable: {e!r}"}

    schema = spec_class.model_json_schema()
    return {
        "model_type": model_type,
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"modelforge://{model_type}.schema.json",
            **schema,
        },
    }


@server.tool()
def validate_spec(spec_yaml: str, model_type: str | None = None) -> dict[str, Any]:
    """Validate a draft YAML spec WITHOUT building — the fast pre-flight check.

    Runs the same friendly validation chain as the CLI's `modelforge validate`:
    YAML parse errors, non-mapping documents, unknown model_type (with the
    known list), Pydantic field errors as plain-language one-liners with dotted
    paths (e.g. "Missing required field: pl.revenue_growth_by_year"), unknown
    top-level keys as WARNINGS (silent-typo guard), and dangling
    `*_source_id` references as ERRORS (fabricated-citation guard).

    ``spec_yaml`` is the YAML text itself (a path to an existing .yaml file
    also works); optional ``model_type`` is used only when the spec omits its
    own `model_type:` key. Returns {valid, model_type, errors[], warnings[]} —
    never raises on a bad spec.

    Conversational loop: STEP 4 — call after EVERY draft/edit and iterate until
    valid:true BEFORE spending a build via build_model or certify.
    """
    out = _validate_spec_chain(spec_yaml, model_type)
    return {k: v for k, v in out.items() if not k.startswith("_")}


@server.tool()
def certify(
    spec_yaml: str | None = None,
    workbook_path: str | None = None,
    output_dir: str | None = None,
    max_findings: int = 20,
) -> dict[str, Any]:
    """Build from a YAML spec (or take an existing workbook) and run the zero-formula-error certification audit.

    Pass EITHER ``spec_yaml`` (YAML text or a path to a .yaml file — it is
    validated, built exactly as the CLI `build` command ships it, including the
    Trust/Moat sheets and the deterministic finishing chain) OR
    ``workbook_path`` (an already-built .xlsx to audit as-is). The auditor
    recomputes every formula with the third-party `formulas` engine and flags
    any Excel error cell (#REF!/#DIV0!/#VALUE!/#NAME?/#NUM!/#N/A) plus numeric
    cells lacking font colour or number_format.

    Returns {verdict: CERTIFIED|WARN|FAIL, formula_errors[], formula_error_count,
    style_gaps[], style_gap_count, manifest_sha, xlsx, ...}. CERTIFIED = zero
    errors and zero styling gaps; WARN = zero errors, some styling gaps;
    FAIL = at least one formula error. An invalid spec returns
    {verdict: INVALID_SPEC, errors, warnings} without building.

    Conversational loop: STEP 5+6 in one call (build + audit) after
    validate_spec passes — or STEP 6 alone on a workbook built earlier. Walk
    provenance next via list_sources / lineage_walk on the returned graph_db.
    """
    if (spec_yaml is None) == (workbook_path is None):
        return {"error": "pass exactly one of spec_yaml or workbook_path"}

    graph_db: str | None = None

    if spec_yaml is not None:
        chain = _validate_spec_chain(spec_yaml)
        if not chain["valid"]:
            return {
                "verdict": "INVALID_SPEC",
                "model_type": chain["model_type"],
                "errors": chain["errors"],
                "warnings": chain["warnings"],
            }
        spec = chain["_spec"]
        spec_bytes = chain["_spec_bytes"]

        out_dir = _resolve_path(output_dir) if output_dir else Path("output").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        # Persist the spec next to the artifact when the YAML came in as text,
        # so the manifest's spec_source_path points at real bytes on disk.
        spec_file: Path | None = chain["_spec_path"]
        if spec_file is None:
            spec_file = out_dir / f"spec_{chain['model_type']}.yaml"
            spec_file.write_bytes(spec_bytes)

        out_xlsx = out_dir / f"{spec_file.stem}.xlsx"
        try:
            xlsx, graph = _build_model(
                spec, out_xlsx,
                spec_source_bytes=spec_bytes,
                spec_source_path=spec_file,
            )
        except Exception as e:
            log.exception("certify build failed")
            return {"error": f"build failed: {e!r}"}
        graph_db = str(graph)

        # Ship the same artifact the CLI `build` delivers (RedFlags + MOAT
        # sheets, re-styled, timestamp-pinned, manifest re-hashed) so the
        # badge is earned on the delivered file.
        try:
            from modelforge.cli import _inject_trust_moat_and_finish
            _inject_trust_moat_and_finish(
                xlsx, spec, spec_bytes, spec_file, quiet=True,
            )
        except Exception as e:  # pragma: no cover - injection is best-effort
            log.warning("trust/moat finishing skipped: %r", e)
    else:
        xlsx = _resolve_path(workbook_path)  # type: ignore[arg-type]
        if not xlsx.exists():
            return {"error": f"workbook not found: {xlsx}"}

    try:
        from modelforge.qc import audit_workbook
        report = audit_workbook(xlsx)
    except Exception as e:
        log.exception("certify audit failed")
        return {"error": f"audit failed: {e!r}"}

    result: dict[str, Any] = {
        "verdict": report.verdict,
        "xlsx": str(xlsx),
        "formula_errors": [
            {"cell": e.ref, "error": e.error, "found_via": e.source}
            for e in report.error_cells[:max_findings]
        ],
        "formula_error_count": report.n_errors,
        "style_gaps": [
            {"cell": g.ref, "reason": g.reason}
            for g in report.style_gaps[:max_findings]
        ],
        "style_gap_count": report.n_style_gaps,
        "manifest_sha": _manifest_sha(Path(xlsx)),
        "notes": list(report.notes),
    }
    if graph_db is not None:
        result["graph_db"] = graph_db
    return result


@server.tool()
def build_model(spec_path: str, output_dir: str | None = None) -> dict[str, Any]:
    """Generate a live-formula Excel workbook (.xlsx) plus its SQLite linkage graph (.graph.db) from a typed YAML spec.

    Use when the user has (or has just produced) a ModelForge YAML spec and wants
    the actual workbook — formulas in every cell, scenario toggles, and
    source-tagged inputs. Takes spec_path and optional output_dir; returns
    {xlsx, graph_db, spec, ok} or {error}.

    Conversational loop: STEP 5 — only after validate_spec returns valid:true.
    Prefer certify(spec_yaml=...) when you also want the audit verdict in the
    same call; build_model alone does NOT inject the Trust/Moat sheets the CLI
    `build` ships.
    """
    spec_file = _resolve_path(spec_path)
    if not spec_file.exists():
        return {"error": f"spec file not found: {spec_file}"}

    out_dir = _resolve_path(output_dir) if output_dir else Path("output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Mirror the CLI build path: read the YAML bytes, parse, resolve the typed
    # Pydantic spec class for the declared model_type, validate, then build.
    # Passing the *parsed spec* (not a Path) is required — the template factory
    # dispatches on spec.model_type. Passing spec_source_bytes makes the
    # reproducibility / manifest hashes deterministic and verifiable.
    try:
        from modelforge.cli import _load_spec_class
    except ImportError as e:
        return {"error": f"spec loader unavailable: {e!r}"}

    try:
        spec_bytes = spec_file.read_bytes()
        raw = yaml.safe_load(spec_bytes)
        model_type = raw.get("model_type", "unitranche")
        spec_class = _load_spec_class(model_type)
        spec = spec_class.model_validate(raw)
    except Exception as e:
        log.exception("spec parse failed")
        return {"error": f"spec parse failed: {e!r}"}

    out_xlsx = out_dir / f"{spec_file.stem}.xlsx"
    try:
        xlsx, graph = _build_model(
            spec, out_xlsx,
            spec_source_bytes=spec_bytes,
            spec_source_path=spec_file,
        )
    except Exception as e:
        log.exception("build_model failed")
        return {"error": f"build failed: {e!r}"}

    return {
        "xlsx": str(xlsx),
        "graph_db": str(graph),
        "spec": str(spec_file),
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

    Conversational loop: STEP 6 (structural pass) — pair with certify, which
    runs the formula-recalc audit; use both before exporting or sharing.
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

    Conversational loop: STEP 7 — after a successful build/certify, before or
    alongside lineage_walk.
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

    Conversational loop: STEP 7 (final) — the provenance walk that closes the
    loop: any number in the certified workbook traces back to a source doc page.
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

    Conversational loop: alternative to hand-drafting at STEP 3 when raw deal
    documents exist — still run validate_spec, then build/certify, on the
    extracted spec.
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

    Conversational loop: STEP 8 (deliverable) — only after certify returns
    CERTIFIED (or the user accepts a WARN).
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
def export_deck(
    workbook_path: str | None = None,
    spec_path: str | None = None,
    deck_type: str = "ic_memo",
    theme: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Render a certified, hash-stamped board deck (.pptx) from a ModelForge workbook or spec — fail-closed.

    Pass EITHER ``workbook_path`` (a built .xlsx with its
    ``<stem>.manifest.json`` sidecar next to it) OR ``spec_path`` (a YAML
    spec, built exactly as the CLI ``build`` ships it — Trust/Moat sheets,
    deterministic finishing, manifest — before the deck chain runs).

    Fail-closed chain: manifest verify → certification audit must be
    CERTIFIED → supported-template fact extraction (every numeric fact
    carries its sheet!cell ref) → compose (``ic_memo`` or ``teaser``) +
    mandatory "Certification & Red Flags" final slide → render →
    deterministic stamp. The .pptx embeds spec_sha256 + workbook_sha256 in
    its core-property keywords and is byte-identical for the same workbook.

    Returns {pptx, deck_type, theme, slides, workbook, workbook_sha256,
    spec_sha256, audit_verdict, template, red_flags, source_cells, ok} or
    {error} (uncertified/tampered workbooks and unsupported templates are
    refused with a plain-language reason).

    Conversational loop: STEP 8 (deliverable) — the certified-deck upgrade
    of export_pptx; use after certify returns CERTIFIED.
    """
    if (workbook_path is None) == (spec_path is None):
        return {"error": "pass exactly one of workbook_path or spec_path"}

    try:
        from modelforge.deck.pipeline import (
            DeckAdapterError,
            build_deck_from_workbook,
        )
    except ImportError as e:
        return {
            "error": "deck rendering requires the deck extras: "
                     "pip install 'modelforge-finance[deck]' "
                     f"(missing dependency: {getattr(e, 'name', None) or e})"
        }

    if spec_path is not None:
        built = certify(spec_yaml=str(spec_path))
        if built.get("error"):
            return {"error": f"spec build failed: {built['error']}"}
        if built.get("verdict") == "INVALID_SPEC":
            return {
                "error": "invalid spec — fix and re-validate",
                "errors": built.get("errors", []),
                "warnings": built.get("warnings", []),
            }
        xlsx = Path(built["xlsx"])
    else:
        xlsx = _resolve_path(workbook_path)  # type: ignore[arg-type]
        if not xlsx.exists():
            return {"error": f"workbook not found: {xlsx}"}

    out = _resolve_path(output_path) if output_path else None
    try:
        result = build_deck_from_workbook(
            xlsx, deck_type=deck_type, theme=theme, out_path=out,
        )
    except DeckAdapterError as e:
        return {"error": str(e)}
    except ImportError as e:  # pragma: no cover - env-dependent
        return {
            "error": "deck rendering requires the deck extras: "
                     "pip install 'modelforge-finance[deck]' "
                     f"(missing dependency: {getattr(e, 'name', None) or e})"
        }
    except Exception as e:  # pragma: no cover - defensive
        log.exception("export_deck failed")
        return {"error": f"deck export failed: {e!r}"}

    payload = result.summary()
    payload["ok"] = True
    return payload


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

    Conversational loop: outside the single-model loop — use to pick WHICH spec
    to take through validate_spec → certify when many candidates exist.
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

    Conversational loop: helper at STEP 3 — ground a spec's tax-rate assumption
    in the right jurisdiction while drafting.
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

    Conversational loop: STEP 8 (deliverable) — only after certify returns
    CERTIFIED (or the user accepts a WARN).
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

    Conversational loop: outside the core loop — check it before using the
    market-data tools to ground spec assumptions at STEP 3.
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

    Conversational loop: market-data helper at STEP 3 (drafting) — e.g. to set
    a spec's share-price or market-cap input from a live quote.
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

    Conversational loop: market-data helper at STEP 3 (drafting) — e.g. for
    volatility or historical-growth inputs to a spec.
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

    Conversational loop: market-data helper at STEP 3 (drafting) — seed
    historical_revenue/EBITDA blocks of a spec from reported figures.
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

    Conversational loop: sourcing helper at STEP 3 (drafting) — a filing makes
    a strong `sources:` entry (doc, page, publisher, date) for spec inputs.
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

    Conversational loop: drafting helper at STEP 3 — pin down the exact legal
    entity a spec's target block refers to.
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

    Conversational loop: drafting helper at STEP 3 — resolve a company name to
    a ticker before quote/fundamentals/search_filings.
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

"""Data-room ingestion pipeline — orchestrates readers → classifier → extractor → YAML.

Usage:
    from modelforge.ingest.pipeline import ingest
    result = ingest(Path("dataroom/"), template="project_finance",
                    output_yaml=Path("out.yaml"))
    # result.yaml_path, result.report_path, result.spec, result.cache_hit_rate
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml

from modelforge.ingest.classifier import ClassifierResult, classify_all
from modelforge.ingest.extractor import ExtractionResult, extract_section
from modelforge.ingest.readers.base import DocChunk, DocIndex
from modelforge.ingest.readers.discovery import discover, read_any


# Template registry — maps template name → (spec class, list of (section_name, section_cls))
def _pf_sections():
    from modelforge.spec.project_finance import (
        ConstructionPhase, DSCRCovenant, EquityIRRTarget,
        OperatingPhase, PFDebt, ProjectFinanceSpec,
    )
    from modelforge.spec.base import Target
    return ProjectFinanceSpec, [
        ("target", Target),
        ("construction", ConstructionPhase),
        ("operating", OperatingPhase),
        ("debt", PFDebt),
        ("covenant", DSCRCovenant),
        ("equity", EquityIRRTarget),
    ]


TEMPLATE_SECTIONS = {
    "project_finance": _pf_sections,
}


@dataclass
class IngestionResult:
    yaml_path: Path
    report_path: Path
    spec_dict: dict
    spec_valid: bool
    validation_errors: list[str] = field(default_factory=list)
    classifier_results: list[ClassifierResult] = field(default_factory=list)
    extraction_results: list[ExtractionResult] = field(default_factory=list)
    cache_hit_rate: float = 0.0
    elapsed_seconds: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


def _assign_source_ids(
    indexes: list[DocIndex],
    classes: list[ClassifierResult],
) -> list[dict]:
    """Attach S-NNN ids and return the Source list as plain dicts.

    S-ids assigned in discovery order. Every doc becomes a Source entry
    regardless of usage (the extractor may ignore uninformative ones).
    """
    sources: list[dict] = []
    for i, (idx, cls) in enumerate(zip(indexes, classes), start=1):
        sid = f"S-{i:03d}"
        idx.source_id = sid
        sources.append({
            "id": sid,
            "doc": idx.doc_filename,
            "page": idx.chunks[0].page if idx.chunks and idx.chunks[0].page else 1,
            "publisher": cls.publisher or "Unknown",
            "date": (cls.date or date(2026, 1, 1)).isoformat(),
            "url": None,
            "verified": cls.verified,
            "note": cls.relevance_hint or "",
        })
    return sources


def _build_context(indexes: list[DocIndex], max_chars_total: int = 40000) -> list[DocChunk]:
    """Simple context builder: all chunks tagged with their S-id + doc.

    For MVP the data room is small enough to pass all chunks to every
    section. Phase-2 can filter per-section via keyword/embeddings.
    """
    tagged: list[DocChunk] = []
    for idx in indexes:
        for c in idx.chunks:
            # Re-tag with S-id in the text so the extractor cites it
            text = f"[{idx.source_id} | {idx.doc_filename} p.{c.page or 1}]\n{c.text}"
            tagged.append(DocChunk(
                doc_filename=idx.doc_filename,
                page=c.page,
                text=text,
                kind=c.kind,
                meta=c.meta,
            ))
    return tagged


def _default_meta(template: str, dataroom_dir: Path) -> dict:
    return {
        "project_code": f"INGESTED-{dataroom_dir.name.upper()[:20]}",
        "deliverable": {"en": f"{template.replace('_',' ').title()} — ingested draft",
                        "it": f"{template.replace('_',' ').title()} — bozza ingested"},
        "analyst": "ModelForge Ingest",
        "version": "v0.1-ingest",
        "status": "draft",
        "valuation_date": date.today().isoformat(),
        "currency": "EUR",
        "unit_scale": "millions",
        "sign_convention": "costs_negative",
        "revision_log": [
            {"version": "v0.1-ingest", "date": date.today().isoformat(),
             "analyst": "ModelForge Ingest",
             "note": f"Auto-ingested from {dataroom_dir.name}."},
        ],
    }


def _default_horizon(template: str) -> dict:
    if template == "project_finance":
        return {"construction_years": 2, "operating_years": 20}
    return {}


def _assemble_spec_dict(
    template: str,
    meta: dict,
    sources: list[dict],
    section_payloads: dict[str, dict],
    horizon: dict | None = None,
) -> dict:
    spec = {"model_type": template, "meta": meta, "sources": sources}
    if horizon:
        spec["horizon"] = horizon
    spec.update(section_payloads)
    if template == "project_finance":
        spec.setdefault("historical_revenue_eur_m", [])
        spec.setdefault("historical_ebitda_eur_m", [])
        spec.setdefault("historical_net_debt_eur_m", 0.0)
        spec.setdefault("historical_net_debt_source_id",
                        sources[0]["id"] if sources else "S-001")
    return spec


def _write_yaml(path: Path, spec_dict: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(spec_dict, f, sort_keys=False, allow_unicode=True,
                       default_flow_style=None)


def ingest(
    dataroom_dir: Path,
    template: str,
    output_yaml: Path,
    max_docs: int = 50,
    model: str = "claude-opus-4-6",
    use_cache: bool = True,
    strict: bool = False,
    dry_run: bool = False,
    client: Any = None,
    log=None,
) -> IngestionResult:
    """Orchestrate a full data-room → YAML ingestion."""
    if template not in TEMPLATE_SECTIONS:
        raise ValueError(
            f"Template {template!r} not supported. Supported: "
            f"{list(TEMPLATE_SECTIONS)}"
        )

    dataroom_dir = Path(dataroom_dir)
    output_yaml = Path(output_yaml)
    log = log or (lambda msg: None)
    t0 = time.perf_counter()

    # 1. Discover
    files = discover(dataroom_dir, max_docs=max_docs)
    if not files:
        raise RuntimeError(f"No supported files found in {dataroom_dir}")
    log(f"Discovered {len(files)} files.")

    # 2. Read
    indexes = [read_any(f) for f in files]
    log(f"Read {len(indexes)} documents ({sum(i.total_text_len for i in indexes)} chars).")

    # 3. Classify
    log("Classifying documents...")
    classifier_results = classify_all(
        indexes, model=model, client=client, use_cache=use_cache,
    )
    for idx, cr in zip(indexes, classifier_results):
        log(f"  {idx.doc_filename} → {cr.doc_type} ({'✓' if cr.verified else 'unverified'})")

    # 4. Assign S-ids
    sources = _assign_source_ids(indexes, classifier_results)

    if dry_run:
        # Build minimal result and exit
        elapsed = time.perf_counter() - t0
        return IngestionResult(
            yaml_path=output_yaml, report_path=output_yaml.with_suffix(".ingestion.md"),
            spec_dict={"model_type": template, "sources": sources},
            spec_valid=False, classifier_results=classifier_results,
            cache_hit_rate=sum(1 for r in classifier_results if r.cache_hit) / max(len(classifier_results), 1),
            elapsed_seconds=elapsed,
        )

    # 5. Build extraction context
    context = _build_context(indexes)
    log(f"Context: {len(context)} chunks, {sum(len(c.text) for c in context)} chars.")

    # 6. Per-section extraction
    spec_cls, section_specs = TEMPLATE_SECTIONS[template]()
    extraction_results: list[ExtractionResult] = []
    section_payloads: dict[str, dict] = {}
    for sname, scls in section_specs:
        log(f"Extracting {sname}...")
        r = extract_section(
            template=template,
            section_name=sname,
            section_cls=scls,
            available_sources=sources,
            context_chunks=context,
            model=model,
            client=client,
            use_cache=use_cache,
        )
        extraction_results.append(r)
        section_payloads[sname] = r.payload
        ok = "✓" if r.validation_ok else "✗"
        log(f"  {sname}: {ok} ({r.input_tokens} in / {r.output_tokens} out tokens, cache={'hit' if r.cache_hit else 'miss'})")

    # 7. Assemble
    meta = _default_meta(template, dataroom_dir)
    horizon = _default_horizon(template)
    spec_dict = _assemble_spec_dict(
        template, meta, sources, section_payloads, horizon,
    )

    # 8. Validate whole spec
    validation_errors: list[str] = []
    spec_valid = True
    try:
        spec_cls.model_validate(spec_dict)
    except Exception as e:
        spec_valid = False
        validation_errors.append(str(e))
        if strict:
            raise
        log(f"Whole-spec validation failed: {str(e)[:300]}")

    # 9. Emit YAML
    _write_yaml(output_yaml, spec_dict)
    log(f"Wrote YAML: {output_yaml}")

    # 10. Report
    report_path = output_yaml.with_suffix(".ingestion.md")
    from modelforge.ingest.reporter import write_report
    write_report(
        report_path, template=template, dataroom_dir=dataroom_dir, model=model,
        classifier_results=classifier_results, extraction_results=extraction_results,
        sources=sources, spec_valid=spec_valid, validation_errors=validation_errors,
        elapsed_seconds=time.perf_counter() - t0,
    )
    log(f"Wrote report: {report_path}")

    # Stats
    elapsed = time.perf_counter() - t0
    all_calls = list(classifier_results) + list(extraction_results)
    cache_hits = sum(1 for r in all_calls if r.cache_hit)
    cache_hit_rate = cache_hits / max(len(all_calls), 1)
    total_in = sum(getattr(r, "input_tokens", 0) for r in extraction_results)
    total_out = sum(getattr(r, "output_tokens", 0) for r in extraction_results)

    return IngestionResult(
        yaml_path=output_yaml, report_path=report_path, spec_dict=spec_dict,
        spec_valid=spec_valid, validation_errors=validation_errors,
        classifier_results=classifier_results, extraction_results=extraction_results,
        cache_hit_rate=cache_hit_rate, elapsed_seconds=elapsed,
        total_input_tokens=total_in, total_output_tokens=total_out,
    )

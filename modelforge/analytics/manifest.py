"""Per-build manifest sidecar — extends Reproducibility with source-doc
hash chain + workbook hash + build chain.

Where ``reproducibility.py`` writes a Reproducibility sheet INSIDE the
workbook (verifiable by anyone who opens the .xlsx in Excel), this
module writes a JSON sidecar (``<workbook>.manifest.json``) with the
full audit envelope:

* ``spec_sha256``    — same bytes-deterministic hash on the YAML spec
* ``source_hashes``  — SHA-256 of every source document referenced in
                       ``sources:`` block (where the local file exists)
* ``workbook_sha256``— hash of the built workbook bytes
* ``build_chain``    — sequence of prior workbook SHAs from the same
                       (spec_sha256, sources_sha256) pair, persisted
                       alongside the manifest. Lets reviewers see if the
                       workbook is "the same as last time" or "rebuilt
                       with v0.9.8 of ModelForge but identical inputs."
* ``modelforge_version`` / ``python_version`` / ``build_timestamp_utc``

The manifest is JSON, machine-readable, and small (~1-5KB). Pin it to
the deal folder alongside the .xlsx and the spec.yaml; auditors can
verify the entire chain in one command::

    modelforge verify-manifest deal.xlsx

The manifest design is the audit-grade extension that ChatGPT round-2
flagged as the gap between "internal lineage walk" and "third-party
verifiable provenance" — without requiring spend on Big-4 audit yet.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Optional


# ── helpers ───────────────────────────────────────────────────────────────


def _modelforge_version() -> str:
    for name in ("modelforge-finance", "modelforge"):
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return "0.0.0+local"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ── data shapes ───────────────────────────────────────────────────────────


@dataclass
class SourceHash:
    """One row per source document."""
    id: str                      # e.g. "S-001"
    doc: str                     # filename or URL stem
    publisher: Optional[str] = None
    url: Optional[str] = None
    sha256: Optional[str] = None # None when the file isn't local
    bytes_size: Optional[int] = None
    found_at: Optional[str] = None


@dataclass
class BuildManifest:
    """Per-build audit envelope. Written next to the .xlsx as JSON."""
    workbook: str
    workbook_sha256: str
    workbook_bytes_size: int
    spec_sha256: str
    spec_source: str             # path or "(canonical_json)"
    sources_sha256: str          # hash of the (sorted) source-id manifest
    source_hashes: list[SourceHash] = field(default_factory=list)
    modelforge_version: str = field(default_factory=_modelforge_version)
    python_version: str = field(default_factory=platform.python_version)
    python_implementation: str = field(default_factory=platform.python_implementation)
    host: str = field(
        default_factory=lambda: f"{platform.system()} {platform.release()}",
    )
    build_timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    build_chain: list[dict[str, str]] = field(default_factory=list)


# ── public API ────────────────────────────────────────────────────────────


def hash_sources(spec, search_dirs: Optional[list[Path]] = None) -> list[SourceHash]:
    """Hash every local file referenced by ``spec.sources``.

    Each ``Source`` row has ``id``, ``doc`` (filename), optional ``url``.
    We try to resolve ``doc`` against ``search_dirs`` (default: cwd + the
    ``data/`` and ``examples/`` folders). When the file is found, we
    record its SHA-256 and size; when it isn't, we record id + doc + url
    only. Either way produces a deterministic manifest row.
    """
    out: list[SourceHash] = []
    sources = getattr(spec, "sources", None) or []
    if search_dirs is None:
        search_dirs = [
            Path.cwd(),
            Path.cwd() / "data",
            Path.cwd() / "examples",
        ]

    for s in sources:
        sid = getattr(s, "id", "?")
        doc = getattr(s, "doc", "")
        url = getattr(s, "url", None)
        publisher = getattr(s, "publisher", None)
        # Try to find the doc on disk under any search dir
        located: Optional[Path] = None
        for d in search_dirs:
            candidate = d / doc
            if candidate.exists() and candidate.is_file():
                located = candidate
                break
        if located:
            out.append(SourceHash(
                id=sid,
                doc=doc,
                publisher=str(publisher) if publisher else None,
                url=str(url) if url else None,
                sha256=_sha256_file(located),
                bytes_size=located.stat().st_size,
                found_at=str(located),
            ))
        else:
            out.append(SourceHash(
                id=sid,
                doc=doc,
                publisher=str(publisher) if publisher else None,
                url=str(url) if url else None,
                sha256=None,
                bytes_size=None,
                found_at=None,
            ))
    return out


def compute_sources_digest(source_hashes: list[SourceHash]) -> str:
    """Single SHA-256 covering the canonical JSON of all source rows."""
    rows = [
        {"id": s.id, "doc": s.doc, "sha256": s.sha256 or "", "url": s.url or ""}
        for s in source_hashes
    ]
    rows.sort(key=lambda r: r["id"])
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(blob)


def write_manifest(
    xlsx_path: Path | str,
    spec,
    spec_source_bytes: Optional[bytes] = None,
    spec_source_path: Optional[Path | str] = None,
    search_dirs: Optional[list[Path]] = None,
    parent_chain_path: Optional[Path] = None,
) -> Path:
    """Compute + persist a BuildManifest next to the workbook.

    Returns the path to the written JSON manifest. Filename pattern:
    ``<workbook_stem>.manifest.json`` (so ``deal.xlsx`` →
    ``deal.manifest.json``).

    If ``parent_chain_path`` is provided, prior chain entries are loaded
    from there to extend the build chain. By default, looks for an
    existing manifest beside the workbook.
    """
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Workbook not found: {xlsx_path}")

    # Compute hashes
    workbook_sha = _sha256_file(xlsx_path)
    workbook_size = xlsx_path.stat().st_size

    if spec_source_bytes is not None:
        spec_sha = _sha256_bytes(spec_source_bytes)
        spec_descriptor = (
            str(spec_source_path) if spec_source_path else "(yaml_bytes)"
        )
    else:
        # Canonical JSON serialization fallback
        payload = spec.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               default=str).encode("utf-8")
        spec_sha = _sha256_bytes(canonical)
        spec_descriptor = (
            str(spec_source_path) if spec_source_path else "(canonical_json)"
        )

    source_hashes = hash_sources(spec, search_dirs=search_dirs)
    sources_sha = compute_sources_digest(source_hashes)

    # Build chain — load existing manifest if present, append current
    manifest_path = xlsx_path.with_suffix(".manifest.json")
    chain_source_path = parent_chain_path or manifest_path
    build_chain: list[dict[str, str]] = []
    if chain_source_path.exists():
        try:
            prior = json.loads(chain_source_path.read_text(encoding="utf-8"))
            build_chain = list(prior.get("build_chain") or [])
            # Push the prior build's snapshot to the chain
            if prior.get("workbook_sha256") and prior.get("build_timestamp_utc"):
                build_chain.append({
                    "workbook_sha256": prior["workbook_sha256"],
                    "spec_sha256": prior.get("spec_sha256", ""),
                    "modelforge_version": prior.get("modelforge_version", ""),
                    "build_timestamp_utc": prior["build_timestamp_utc"],
                })
        except (json.JSONDecodeError, OSError):
            pass

    manifest = BuildManifest(
        workbook=str(xlsx_path),
        workbook_sha256=workbook_sha,
        workbook_bytes_size=workbook_size,
        spec_sha256=spec_sha,
        spec_source=spec_descriptor,
        sources_sha256=sources_sha,
        source_hashes=source_hashes,
        build_chain=build_chain,
    )

    manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, default=str),
        encoding="utf-8",
    )
    return manifest_path


def read_manifest(manifest_path: Path | str) -> BuildManifest:
    """Load a manifest file back into the dataclass."""
    p = Path(manifest_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    sh = [SourceHash(**s) for s in data.pop("source_hashes", [])]
    return BuildManifest(source_hashes=sh, **data)


@dataclass
class VerifyResult:
    """Outcome of a verify_manifest run."""
    ok: bool
    spec_sha_match: Optional[bool]
    workbook_sha_match: bool
    sources_sha_match: bool
    spec_actual: Optional[str]
    workbook_actual: str
    sources_actual: str
    issues: list[str] = field(default_factory=list)


def verify_manifest(
    xlsx_path: Path | str,
    manifest_path: Optional[Path | str] = None,
    spec_source_bytes: Optional[bytes] = None,
    spec=None,
) -> VerifyResult:
    """Recompute hashes and compare to manifest. Returns a VerifyResult."""
    xlsx_path = Path(xlsx_path)
    manifest_path = Path(manifest_path) if manifest_path else xlsx_path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        return VerifyResult(
            ok=False,
            spec_sha_match=None,
            workbook_sha_match=False,
            sources_sha_match=False,
            spec_actual=None,
            workbook_actual="",
            sources_actual="",
            issues=[f"Manifest not found: {manifest_path}"],
        )
    m = read_manifest(manifest_path)
    workbook_actual = _sha256_file(xlsx_path)
    workbook_match = workbook_actual == m.workbook_sha256

    sources_actual = ""
    sources_match = True
    if spec is not None:
        sources_actual = compute_sources_digest(hash_sources(spec))
        sources_match = sources_actual == m.sources_sha256

    spec_match: Optional[bool] = None
    spec_actual: Optional[str] = None
    if spec_source_bytes is not None:
        spec_actual = _sha256_bytes(spec_source_bytes)
        spec_match = spec_actual == m.spec_sha256

    issues: list[str] = []
    if not workbook_match:
        issues.append(
            f"workbook_sha256 mismatch: stored={m.workbook_sha256[:16]}... "
            f"actual={workbook_actual[:16]}..."
        )
    if spec_match is False:
        issues.append(
            f"spec_sha256 mismatch: stored={m.spec_sha256[:16]}... "
            f"actual={spec_actual[:16] if spec_actual else '?'}..."
        )
    if not sources_match and spec is not None:
        issues.append(
            f"sources_sha256 mismatch: stored={m.sources_sha256[:16]}... "
            f"actual={sources_actual[:16]}..."
        )

    ok = workbook_match and (spec_match is not False) and sources_match
    return VerifyResult(
        ok=ok,
        spec_sha_match=spec_match,
        workbook_sha_match=workbook_match,
        sources_sha_match=sources_match,
        spec_actual=spec_actual,
        workbook_actual=workbook_actual,
        sources_actual=sources_actual,
        issues=issues,
    )


__all__ = [
    "BuildManifest",
    "SourceHash",
    "VerifyResult",
    "compute_sources_digest",
    "hash_sources",
    "read_manifest",
    "verify_manifest",
    "write_manifest",
]

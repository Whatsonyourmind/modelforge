"""Tests for the per-build manifest sidecar (D2 lift)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from modelforge.analytics.manifest import (
    BuildManifest,
    SourceHash,
    compute_sources_digest,
    hash_sources,
    read_manifest,
    verify_manifest,
    write_manifest,
)


# ── helpers ───────────────────────────────────────────────────────────────


def _load_dcf_spec():
    """Load the canonical DCF spec used elsewhere in the suite."""
    from modelforge.spec.dcf import DCFSpec
    spec_path = Path("examples/dcf_enel.yaml")
    return DCFSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8"))), spec_path


@pytest.fixture
def built_workbook(tmp_path):
    """Build a real workbook from examples/dcf_enel.yaml and return path.

    ``with_manifest=False`` so each test controls when (and how many
    times) the manifest is written — otherwise ``build_model``'s own
    manifest call would skew the build_chain assertions.
    """
    from modelforge.templates import build_model
    spec, spec_path = _load_dcf_spec()
    out = tmp_path / "dcf_enel.xlsx"
    build_model(spec, out, with_manifest=False)
    return out, spec, spec_path.read_bytes(), spec_path


# ── source hashing ────────────────────────────────────────────────────────


def test_hash_sources_returns_one_row_per_source():
    spec, _ = _load_dcf_spec()
    rows = hash_sources(spec)
    assert len(rows) == len(spec.sources)
    for r in rows:
        assert isinstance(r, SourceHash)
        assert r.id.startswith("S-")


def test_hash_sources_marks_missing_files_with_none_sha(tmp_path):
    """Source files we can't resolve get sha256=None (not an error)."""
    spec, _ = _load_dcf_spec()
    # Search dirs that contain none of the source files
    rows = hash_sources(spec, search_dirs=[tmp_path])
    for r in rows:
        assert r.sha256 is None
        assert r.bytes_size is None


def test_compute_sources_digest_is_deterministic():
    """Same source rows → same SHA-256, regardless of input ordering."""
    s1 = SourceHash(id="S-001", doc="a.pdf", sha256="aaa", url=None)
    s2 = SourceHash(id="S-002", doc="b.pdf", sha256="bbb", url=None)
    d1 = compute_sources_digest([s1, s2])
    d2 = compute_sources_digest([s2, s1])  # reversed input
    assert d1 == d2  # sorted by id internally


def test_compute_sources_digest_differs_when_content_changes():
    s1 = SourceHash(id="S-001", doc="a.pdf", sha256="aaa", url=None)
    s2 = SourceHash(id="S-001", doc="a.pdf", sha256="bbb", url=None)
    assert compute_sources_digest([s1]) != compute_sources_digest([s2])


# ── write + read manifest ─────────────────────────────────────────────────


def test_write_manifest_creates_sidecar(built_workbook):
    xlsx, spec, spec_bytes, spec_path = built_workbook
    manifest_path = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes,
                                    spec_source_path=spec_path)
    assert manifest_path.exists()
    assert manifest_path.suffix == ".json"
    assert manifest_path.name == "dcf_enel.manifest.json"


def test_write_manifest_records_workbook_hash_and_size(built_workbook):
    xlsx, spec, spec_bytes, spec_path = built_workbook
    manifest_path = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes,
                                    spec_source_path=spec_path)
    m = read_manifest(manifest_path)
    assert len(m.workbook_sha256) == 64  # SHA-256 hex
    assert m.workbook_bytes_size > 0
    assert m.workbook_bytes_size == xlsx.stat().st_size


def test_write_manifest_records_spec_hash(built_workbook):
    xlsx, spec, spec_bytes, spec_path = built_workbook
    manifest_path = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    m = read_manifest(manifest_path)
    import hashlib
    assert m.spec_sha256 == hashlib.sha256(spec_bytes).hexdigest()


def test_write_manifest_records_modelforge_metadata(built_workbook):
    xlsx, spec, spec_bytes, _ = built_workbook
    manifest_path = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    m = read_manifest(manifest_path)
    assert m.modelforge_version != ""
    assert m.python_version != ""
    assert m.python_implementation in ("CPython", "PyPy")
    # ISO-8601 UTC timestamp
    assert "T" in m.build_timestamp_utc and m.build_timestamp_utc.endswith("+00:00")


# ── build chain ───────────────────────────────────────────────────────────


def test_second_build_appends_to_chain(built_workbook):
    """Two consecutive builds → 2nd manifest carries 1st in its build_chain."""
    xlsx, spec, spec_bytes, spec_path = built_workbook
    p1 = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    m1 = read_manifest(p1)
    # Touch the workbook so the SHA changes (simulates re-build with diff result)
    xlsx.write_bytes(xlsx.read_bytes() + b" ")
    p2 = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    m2 = read_manifest(p2)
    assert len(m2.build_chain) == 1
    assert m2.build_chain[0]["workbook_sha256"] == m1.workbook_sha256


def test_third_build_extends_chain_to_two_priors(built_workbook):
    xlsx, spec, spec_bytes, _ = built_workbook
    write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    xlsx.write_bytes(xlsx.read_bytes() + b" ")
    write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    xlsx.write_bytes(xlsx.read_bytes() + b" ")
    p3 = write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    m3 = read_manifest(p3)
    assert len(m3.build_chain) == 2
    assert all("workbook_sha256" in entry for entry in m3.build_chain)


# ── verify ────────────────────────────────────────────────────────────────


def test_verify_manifest_passes_for_unchanged_workbook(built_workbook):
    xlsx, spec, spec_bytes, _ = built_workbook
    write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    result = verify_manifest(xlsx, spec_source_bytes=spec_bytes, spec=spec)
    assert result.ok is True
    assert result.workbook_sha_match is True
    assert result.spec_sha_match is True
    assert result.sources_sha_match is True
    assert result.issues == []


def test_verify_manifest_detects_workbook_tampering(built_workbook):
    xlsx, spec, spec_bytes, _ = built_workbook
    write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    # Tamper with the workbook
    xlsx.write_bytes(xlsx.read_bytes() + b"TAMPER")
    result = verify_manifest(xlsx, spec_source_bytes=spec_bytes, spec=spec)
    assert result.ok is False
    assert result.workbook_sha_match is False
    assert any("workbook_sha256 mismatch" in i for i in result.issues)


def test_verify_manifest_detects_spec_tampering(built_workbook):
    xlsx, spec, spec_bytes, _ = built_workbook
    write_manifest(xlsx, spec, spec_source_bytes=spec_bytes)
    # Verify with different spec bytes
    tampered_bytes = spec_bytes + b"# malicious comment\n"
    result = verify_manifest(xlsx, spec_source_bytes=tampered_bytes)
    assert result.spec_sha_match is False
    assert any("spec_sha256 mismatch" in i for i in result.issues)


def test_verify_manifest_returns_failure_when_manifest_missing(tmp_path):
    fake = tmp_path / "no_manifest.xlsx"
    fake.write_bytes(b"x")
    result = verify_manifest(fake)
    assert result.ok is False
    assert "Manifest not found" in result.issues[0]


# ── reproducibility (key D2 acceptance) ──────────────────────────────────


def test_reproducibility_two_builds_from_same_spec_match_invariants(tmp_path):
    """The headline reproducibility property: two builds from identical
    inputs produce identical spec_sha256 + sources_sha256.

    NOTE: openpyxl writes a creation/modified timestamp into the workbook
    XML, so back-to-back builds *can* differ in those bytes. The manifest's
    spec_sha256 + sources_sha256 are the deterministic invariants to check
    — those MUST match across rebuilds, regardless of timestamp drift in
    the workbook itself. This test asserts that contract.
    """
    from modelforge.templates import build_model
    spec, spec_path = _load_dcf_spec()
    spec_bytes = spec_path.read_bytes()

    xlsx_a = tmp_path / "a.xlsx"
    build_model(spec, xlsx_a, with_manifest=False)
    write_manifest(xlsx_a, spec, spec_source_bytes=spec_bytes)
    m_a = read_manifest(xlsx_a.with_suffix(".manifest.json"))

    xlsx_b = tmp_path / "b.xlsx"
    build_model(spec, xlsx_b, with_manifest=False)
    write_manifest(xlsx_b, spec, spec_source_bytes=spec_bytes)
    m_b = read_manifest(xlsx_b.with_suffix(".manifest.json"))

    # Spec + sources MUST be byte-deterministic across rebuilds
    assert m_a.spec_sha256 == m_b.spec_sha256, "spec_sha256 should be deterministic"
    assert m_a.sources_sha256 == m_b.sources_sha256, "sources_sha256 should be deterministic"


def test_build_model_writes_manifest_by_default(tmp_path):
    """build_model() should write the manifest sidecar automatically."""
    from modelforge.templates import build_model
    spec, spec_path = _load_dcf_spec()
    out = tmp_path / "auto.xlsx"
    build_model(spec, out, spec_source_bytes=spec_path.read_bytes())
    assert out.with_suffix(".manifest.json").exists()


def test_build_model_skips_manifest_when_disabled(tmp_path):
    from modelforge.templates import build_model
    spec, spec_path = _load_dcf_spec()
    out = tmp_path / "skip.xlsx"
    build_model(spec, out, with_manifest=False,
                spec_source_bytes=spec_path.read_bytes())
    assert not out.with_suffix(".manifest.json").exists()

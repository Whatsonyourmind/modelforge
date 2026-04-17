"""Tests for modelforge.diff (US-017 — model diff)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from modelforge.diff import (
    DiffResult,
    compute_diff,
    render_html,
    render_markdown,
)
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


# ─── Fixtures: two versions of the same Enel DCF spec ───────────────────────


@pytest.fixture(scope="module")
def two_dcf_versions(tmp_path_factory):
    from modelforge.spec.dcf import DCFSpec
    p = ROOT / "examples" / "dcf_enel.yaml"
    raw = yaml.safe_load(p.read_bytes())
    spec_v1 = DCFSpec.model_validate(raw)

    # v2: bump beta, exit multiple, add a new source
    raw_v2 = copy.deepcopy(raw)
    raw_v2["wacc"]["beta_levered"]["base"] = 1.10
    raw_v2["terminal"]["exit_ev_ebitda_x"]["base"] = 8.5
    raw_v2["sources"].append({
        "id": "S-999", "doc": "test.pdf", "publisher": "Test",
        "date": "2026-04-17", "verified": False, "note": "",
    })
    spec_v2 = DCFSpec.model_validate(raw_v2)

    out = tmp_path_factory.mktemp("diff")
    v1 = out / "v1.xlsx"
    v2 = out / "v2.xlsx"
    build_model(spec_v1, v1, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    v2_bytes = yaml.safe_dump(raw_v2, sort_keys=False).encode("utf-8")
    build_model(spec_v2, v2, spec_source_bytes=v2_bytes, spec_source_path=v2)
    return v1, v2


# ─── Basic behaviour ─────────────────────────────────────────────────────────


def test_clean_diff_on_identical_workbooks(tmp_path_factory):
    from modelforge.spec.dcf import DCFSpec
    p = ROOT / "examples" / "dcf_enel.yaml"
    spec = DCFSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out_dir = tmp_path_factory.mktemp("cleandiff")
    a = out_dir / "a.xlsx"
    b = out_dir / "b.xlsx"
    # Build same spec twice (same bytes, should produce same SHA)
    raw_bytes = p.read_bytes()
    build_model(spec, a, spec_source_bytes=raw_bytes, spec_source_path=p)
    build_model(spec, b, spec_source_bytes=raw_bytes, spec_source_path=p)
    res = compute_diff(a, b)
    # Assumption / source / formula should be identical;
    # only build timestamp may differ (acceptable noise).
    assert not res.assumption_changes
    assert not res.source_changes
    # Allow up to 1 formula change (build-timestamp cell is hardcoded)
    assert len(res.formula_changes) == 0


def test_assumption_base_change_detected(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    beta_changes = [c for c in res.assumption_changes
                    if c.assumption_id == "A-003" and c.field == "base"]
    assert len(beta_changes) == 1
    assert beta_changes[0].driver_name == "beta_levered"
    assert float(beta_changes[0].old) == pytest.approx(0.85)
    assert float(beta_changes[0].new) == pytest.approx(1.10)


def test_added_source_detected(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    added = [c for c in res.source_changes if c.kind == "added"]
    assert any(c.source_id == "S-999" for c in added)


def test_spec_hash_drift_detected(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    sha_changes = [c for c in res.repro_changes if "SHA" in c.field]
    assert len(sha_changes) == 1
    assert sha_changes[0].old != sha_changes[0].new


def test_total_changes_counts_everything(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    assert res.total_changes == (
        len(res.assumption_changes) + len(res.source_changes)
        + len(res.formula_changes) + len(res.structural_changes)
        + len(res.repro_changes)
    )


def test_diff_is_not_clean_when_changes_exist(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    assert not res.is_clean


# ─── Rendering ──────────────────────────────────────────────────────────────


def test_markdown_output_is_well_formed(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    md = render_markdown(res)
    assert "# ModelForge diff" in md
    assert "Assumption changes" in md
    assert "beta_levered" in md


def test_html_output_is_well_formed(two_dcf_versions):
    v1, v2 = two_dcf_versions
    res = compute_diff(v1, v2)
    h = render_html(res)
    assert h.startswith("<!doctype html>")
    assert "</html>" in h
    assert "Assumption changes" in h
    assert "beta_levered" in h


def test_markdown_empty_is_explicit():
    """Placeholder result with zero changes should render a clean message."""
    res = DiffResult(v1_path=Path("a"), v2_path=Path("b"))
    md = render_markdown(res)
    assert "Clean diff" in md
    # And HTML
    h = render_html(res)
    assert "Clean diff" in h


# ─── Formula canonicalisation ────────────────────────────────────────────────


def test_formula_canonicalisation_ignores_case():
    from modelforge.diff.engine import _canonicalize_formula
    a = "=sum(A1:A10)"
    b = "=SUM(A1:A10)"
    assert _canonicalize_formula(a) == _canonicalize_formula(b)


def test_formula_canonicalisation_ignores_whitespace():
    from modelforge.diff.engine import _canonicalize_formula
    a = "= A1 + B1 "
    b = "=A1+B1"
    assert _canonicalize_formula(a) == _canonicalize_formula(b)

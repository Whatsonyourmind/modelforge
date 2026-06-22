"""Tests for OraCert — the cross-server re-derivable-result predicate + verifier.

Load-bearing guarantees:

* **Cross-runtime hash parity** — the Python content-hash kernel reproduces, byte
  for byte, hashes computed by OraClaw's TypeScript kernel (committed golden
  vectors + a real solver-produced statement).
* **Re-derives correctness, not just digests** — the solve branch re-checks
  feasibility + objective + hash witness-alone (no solver); the modelforge.build
  branch re-runs the schedule audit on the bound artifact and gates on it. Both
  catch a tampered/defective result the digest alone would pass.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import openpyxl
import pytest
import yaml

from modelforge.oracert import (
    METHOD_MODELFORGE_BUILD,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    build_modelforge_statement,
    canonicalize,
    content_hash,
    validate_statement,
    verify_statement,
)

FIX = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "examples" / "sponsor_lbo_us_saas.yaml"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Cross-runtime hash parity
# ─────────────────────────────────────────────────────────────────────────────


class TestHashParity:
    def test_golden_vectors_match_ts_kernel(self):
        vecs = json.loads((FIX / "hash_parity_vectors.json").read_text())
        assert vecs
        for v in vecs:
            assert content_hash(v["payload"]) == v["hash"], v["payload"]

    def test_negative_zero_normalised(self):
        # JS (-0).toFixed(12) drops the sign; canonicalize must too.
        assert canonicalize(-0.0) == canonicalize(0.0) == "0.000000000000"

    def test_large_value_uses_js_tostring_fallback(self):
        # |x| >= 1e21 → JS toFixed delegates to ToString (exponential).
        assert canonicalize(1e30) == "1e+30"

    def test_keys_sorted_and_no_whitespace(self):
        a = content_hash({"b": 1, "a": 2})
        b = content_hash({"a": 2, "b": 1})
        assert a == b  # key order irrelevant


# ─────────────────────────────────────────────────────────────────────────────
# Envelope validation
# ─────────────────────────────────────────────────────────────────────────────


class TestSchema:
    def test_golden_statement_is_well_formed(self):
        stmt = json.loads((FIX / "oraclaw_solve_statement.json").read_text())
        assert validate_statement(stmt) == []

    def test_missing_fields_flagged(self):
        assert validate_statement({}) != []
        assert validate_statement(
            {"_type": "x", "predicateType": PREDICATE_TYPE,
             "subject": [], "predicate": {}}
        )


# ─────────────────────────────────────────────────────────────────────────────
# solve branch — witness-alone re-derivation
# ─────────────────────────────────────────────────────────────────────────────


class TestSolveBranch:
    @pytest.fixture
    def golden(self):
        return json.loads((FIX / "oraclaw_solve_statement.json").read_text())

    def test_genuine_statement_verifies(self, golden):
        r = verify_statement(golden)
        assert r.ok, r.reasons
        assert r.method == "oraclaw.solve.certificate/v1"
        assert all(r.checks.values())

    def test_tampered_solution_rejected(self, golden):
        t = copy.deepcopy(golden)
        t["predicate"]["witness"]["solution"]["x"] += 1.0
        r = verify_statement(t)
        assert not r.ok
        # caught on feasibility, objective AND the content hash binding
        assert r.checks["primal_feasible"] is False
        assert r.checks["objective_consistent"] is False
        assert r.checks["content_hash"] is False

    def test_tampered_hash_rejected(self, golden):
        t = copy.deepcopy(golden)
        t["predicate"]["witness"]["certificate"]["contentHash"] = "0" * 64
        r = verify_statement(t)
        assert not r.ok
        assert r.checks["content_hash"] is False
        assert r.checks["subject_binds_hash"] is False

    def test_subject_digest_must_bind_hash(self, golden):
        t = copy.deepcopy(golden)
        t["subject"][0]["digest"]["sha256"] = "a" * 64
        r = verify_statement(t)
        assert not r.ok
        assert r.checks["subject_binds_hash"] is False

    def test_nonoptimal_status_rejected(self, golden):
        t = copy.deepcopy(golden)
        t["predicate"]["witness"]["certificate"]["status"] = "infeasible"
        r = verify_statement(t)
        assert not r.ok
        # status flips the hash too (status is in the hashed payload)
        assert r.checks["status_optimal"] is False


# ─────────────────────────────────────────────────────────────────────────────
# modelforge.build branch — artifact-required re-derivation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def built_workbook(tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("oracert_build")
    from modelforge.cli import _inject_trust_moat_and_finish, _load_spec_class
    from modelforge.templates import build_model

    spec_bytes = SPEC_PATH.read_bytes()
    raw = yaml.safe_load(spec_bytes)
    spec = _load_spec_class(raw["model_type"]).model_validate(raw)
    xlsx_out = out_dir / "sponsor_lbo_us_saas.xlsx"
    xlsx, _ = build_model(
        spec, xlsx_out, spec_source_bytes=spec_bytes, spec_source_path=SPEC_PATH)
    _inject_trust_moat_and_finish(xlsx, spec, spec_bytes, SPEC_PATH, quiet=True)
    return Path(xlsx)


class TestModelForgeBranch:
    def test_genuine_build_emits_and_verifies(self, built_workbook):
        stmt = build_modelforge_statement(built_workbook)
        assert validate_statement(stmt) == []
        r = verify_statement(stmt, artifact_path=built_workbook)
        assert r.ok, r.reasons
        assert r.checks["subject_digest"] is True
        assert r.checks["schedule_audit"] is True

    def test_artifact_required(self, built_workbook):
        stmt = build_modelforge_statement(built_workbook)
        r = verify_statement(stmt)  # no artifact
        assert not r.ok
        assert "artifact-required" in " ".join(r.reasons)

    def test_wrong_artifact_digest_rejected(self, built_workbook, tmp_path):
        stmt = build_modelforge_statement(built_workbook)
        other = tmp_path / "other.xlsx"
        other.write_bytes(built_workbook.read_bytes() + b"\x00")  # different bytes
        r = verify_statement(stmt, artifact_path=other)
        assert not r.ok
        assert r.checks["subject_digest"] is False

    def test_schedule_defect_caught_even_when_bytes_authentic(self, tmp_path):
        """Re-derivation (not just digest) catches a wiring defect: a hardcode
        wedged into a formula series, with the statement's digest matching the
        defective file's real bytes."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "DebtSchedule"
        for cidx, val in enumerate(
            ["Debt closing", "=C1+1", "=D1+1", 12345.0, "=F1+1", "=G1+1"], start=1
        ):
            ws.cell(row=1, column=cidx, value=val)
        p = tmp_path / "defect.xlsx"
        wb.save(p)
        sha = _sha256(p)
        stmt = {
            "_type": STATEMENT_TYPE,
            "subject": [{"name": "defect.xlsx", "digest": {"sha256": sha}}],
            "predicateType": PREDICATE_TYPE,
            "predicate": {
                "method": METHOD_MODELFORGE_BUILD,
                "redrivable": True,
                "producer": {"name": "modelforge", "version": "test"},
                "witness": {"manifest": {"workbook_sha256": sha}, "audits": ["schedule"]},
            },
        }
        r = verify_statement(stmt, artifact_path=p)
        assert not r.ok
        assert r.checks["subject_digest"] is True   # bytes are authentic
        assert r.checks["schedule_audit"] is False  # but the wiring defect is caught

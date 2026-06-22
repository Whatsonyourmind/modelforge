"""Standalone, LLM-free OraCert verifier — re-establishes result CORRECTNESS.

Dispatches on ``predicate.method``:

* ``oraclaw.solve.certificate/v1`` — **witness-alone** (no solver, no file):
  re-evaluate every constraint + variable bound (primal feasibility), recompute
  the objective from the returned solution, and recompute the certificate's
  content hash byte-identically (:mod:`modelforge.oracert.canonical`). This is
  the exact logic of OraClaw's ``verifyCertificate``, ported to Python.
* ``modelforge.build/v1`` — **artifact-required**: recompute the workbook's
  SHA-256 and match the bound subject digest + manifest hash, then re-run the
  schedule (and optionally conservation) audit on the bound ``.xlsx``. This
  branch re-derives schedule-wiring integrity + byte identity, NOT economic
  correctness, and REQUIRES the artifact.

Standard in-toto/SLSA/cosign verifiers bind by digest only; OraCert's single
verifier re-derives correctness across both heterogeneous producers.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modelforge.oracert.canonical import content_hash
from modelforge.oracert.schema import (
    METHOD_MODELFORGE_BUILD,
    METHOD_SOLVE,
    validate_statement,
)

# Tolerances mirrored from OraClaw constraintOptimizer.ts.
_PRIMAL_TOL = 1e-6
_OBJ_ABS_TOL = 1e-6
_OBJ_REL_TOL = 1e-6
_INT_TOL = 1e-6
_HIGHS_INF = 1e29


@dataclass
class VerifyResult:
    ok: bool
    method: str | None
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── solve branch: ports of recheckSolve / verifyCertificate ──────────────────

def _is_finite_bound(x: float) -> bool:
    return math.isfinite(x) and abs(x) < _HIGHS_INF


def _effective_bounds(v: dict[str, Any]) -> tuple[float, float]:
    if v.get("type") == "binary":
        return 0.0, 1.0
    lo = v.get("lower")
    hi = v.get("upper")
    return (0.0 if lo is None else float(lo), 1e30 if hi is None else float(hi))


def _js_round(x: float) -> float:
    # JS Math.round = floor(x + 0.5); differs from Python's banker's rounding.
    return math.floor(x + 0.5)


def recheck_solve(problem: dict[str, Any], solution: dict[str, Any]) -> dict[str, Any]:
    def x(n: str) -> float:
        return float(solution.get(n, 0) or 0)

    max_res = 0.0
    worst: str | None = None
    for c in problem.get("constraints", []):
        lhs = 0.0
        for n, coeff in c.get("coefficients", {}).items():
            lhs += float(coeff) * x(n)
        r = 0.0
        if c.get("lower") is not None:
            r = max(r, float(c["lower"]) - lhs)
        if c.get("upper") is not None:
            r = max(r, lhs - float(c["upper"]))
        if r > max_res:
            max_res, worst = r, c.get("name")

    for v in problem.get("variables", []):
        lo, hi = _effective_bounds(v)
        xv = x(v["name"])
        r = max(
            0.0,
            (lo - xv) if _is_finite_bound(lo) else 0.0,
            (xv - hi) if _is_finite_bound(hi) else 0.0,
        )
        if r > max_res:
            max_res, worst = r, f"var:{v['name']}"

    objective = 0.0
    for n, coeff in problem.get("objective", {}).items():
        objective += float(coeff) * x(n)

    return {
        "feasible": max_res <= _PRIMAL_TOL,
        "maxResidual": max_res,
        "worstConstraint": worst,
        "objective": objective,
    }


def _integrality_violation(problem: dict[str, Any], solution: dict[str, Any]) -> float:
    m = 0.0
    for v in problem.get("variables", []):
        if v.get("type") in ("integer", "binary"):
            xv = float(solution.get(v["name"], 0) or 0)
            m = max(m, abs(xv - _js_round(xv)))
    return m


def solve_content_hash(
    problem: dict[str, Any],
    status: str,
    objective_value: float,
    schema: str,
    algo_version: str,
    solution: dict[str, Any],
) -> str:
    """Recompute OraClaw's SolveCertificate ``contentHash`` from the witness."""
    payload = {
        "schema": schema,
        "algoVersion": algo_version,
        "direction": problem["direction"],
        "objective": problem["objective"],
        "variables": problem["variables"],
        "constraints": problem["constraints"],
        "status": status,
        "objectiveValue": objective_value,
        "solution": solution,
    }
    return content_hash(payload)


def _verify_solve(stmt: dict[str, Any]) -> VerifyResult:
    w = stmt["predicate"]["witness"]
    cert = w.get("certificate")
    problem = w.get("problem")
    solution = w.get("solution")
    res = VerifyResult(ok=False, method=METHOD_SOLVE)

    if not isinstance(cert, dict) or not isinstance(problem, dict) or not isinstance(solution, dict):
        res.reasons.append("witness must carry {certificate, problem, solution}")
        return res

    r = recheck_solve(problem, solution)
    res.checks["primal_feasible"] = bool(r["feasible"])
    if not r["feasible"]:
        res.reasons.append(
            f"primal infeasible: max residual {r['maxResidual']:.2e} "
            f"at {r['worstConstraint'] or '?'}"
        )

    obj_certified = cert.get("objectiveValue")
    obj_tol = max(_OBJ_ABS_TOL, _OBJ_REL_TOL * abs(float(obj_certified)))
    obj_ok = (
        math.isfinite(float(obj_certified))
        and abs(r["objective"] - float(obj_certified)) <= obj_tol
    )
    res.checks["objective_consistent"] = obj_ok
    if not obj_ok:
        res.reasons.append(
            f"objective mismatch: recomputed {r['objective']} vs certified {obj_certified}"
        )

    if cert.get("problemClass") == "MIP":
        iv = _integrality_violation(problem, solution)
        integral = iv <= _INT_TOL
        res.checks["integral"] = integral
        if not integral:
            res.reasons.append(f"integrality violated: max fractional {iv:.2e}")

    recomputed = solve_content_hash(
        problem,
        cert.get("status"),
        float(obj_certified),
        cert.get("schema"),
        cert.get("algoVersion"),
        solution,
    )
    hash_ok = recomputed == cert.get("contentHash")
    res.checks["content_hash"] = hash_ok
    if not hash_ok:
        res.reasons.append(
            "content hash mismatch (solution/problem do not match the certified hash)"
        )

    # The subject digest must bind the same content hash.
    subj_sha = stmt["subject"][0].get("digest", {}).get("sha256")
    subj_ok = subj_sha == cert.get("contentHash")
    res.checks["subject_binds_hash"] = subj_ok
    if not subj_ok:
        res.reasons.append("subject digest does not bind the certificate content hash")

    status_ok = cert.get("status") == "optimal"
    res.checks["status_optimal"] = status_ok
    if not status_ok:
        res.reasons.append(f"certificate status is {cert.get('status')!r}, not optimal")

    res.ok = not res.reasons
    res.notes.append("witness-alone: re-derived feasibility + objective + content hash (no solver)")
    return res


# ── modelforge.build branch: artifact-required re-derivation ─────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_modelforge_build(stmt: dict[str, Any], artifact_path: Path | None) -> VerifyResult:
    res = VerifyResult(ok=False, method=METHOD_MODELFORGE_BUILD)
    w = stmt["predicate"]["witness"]
    subj_sha = stmt["subject"][0].get("digest", {}).get("sha256")
    manifest_sha = (w.get("manifest") or {}).get("workbook_sha256")

    if artifact_path is None:
        res.reasons.append(
            "modelforge.build is artifact-required: pass the bound .xlsx to re-derive"
        )
        return res
    artifact_path = Path(artifact_path)
    if not artifact_path.exists():
        res.reasons.append(f"artifact not found: {artifact_path}")
        return res

    actual = _sha256_file(artifact_path)
    subj_ok = actual == subj_sha
    res.checks["subject_digest"] = subj_ok
    if not subj_ok:
        res.reasons.append(
            f"workbook sha256 mismatch vs subject digest: {actual} != {subj_sha}"
        )
    man_ok = manifest_sha is None or actual == manifest_sha
    res.checks["manifest_digest"] = man_ok
    if not man_ok:
        res.reasons.append(
            f"workbook sha256 mismatch vs manifest: {actual} != {manifest_sha}"
        )

    audits = w.get("audits") or ["schedule"]
    if "schedule" in audits:
        from modelforge.qc import audit_schedule

        rep = audit_schedule(artifact_path)
        ok = rep.passed
        res.checks["schedule_audit"] = ok
        if not ok:
            first = "; ".join(f.ref for f in rep.findings[:5])
            res.reasons.append(f"schedule audit failed ({rep.n_findings} findings: {first})")
    if "conservation" in audits:
        from modelforge.qc import audit_conservation

        crep = audit_conservation(artifact_path)
        ok = crep.passed
        res.checks["conservation_audit"] = ok
        if not ok:
            res.reasons.append(f"conservation audit failed (status {crep.status})")

    res.ok = not res.reasons
    res.notes.append(
        "artifact-required: re-derived workbook digest + schedule wiring "
        "(NOT economic correctness)"
    )
    return res


# ── public entry point ───────────────────────────────────────────────────────

def verify_statement(stmt: Any, artifact_path: str | Path | None = None) -> VerifyResult:
    """Validate the envelope, dispatch on method, and re-derive correctness."""
    problems = validate_statement(stmt)
    if problems:
        return VerifyResult(ok=False, method=None, reasons=problems)

    method = stmt["predicate"]["method"]
    if method == METHOD_SOLVE:
        return _verify_solve(stmt)
    if method == METHOD_MODELFORGE_BUILD:
        return _verify_modelforge_build(stmt, Path(artifact_path) if artifact_path else None)
    return VerifyResult(ok=False, method=method, reasons=[f"no verifier for method {method!r}"])

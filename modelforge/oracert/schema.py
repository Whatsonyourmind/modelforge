"""OraCert in-toto Statement v1 envelope: constants + structural validation.

The envelope is a standard in-toto Statement v1 with a custom predicate type
``oracert.dev/redrivable-result/v1`` whose predicate carries a method tag and a
re-derivation witness. This module validates shape only; correctness re-derivation
is :mod:`modelforge.oracert.verify`.
"""

from __future__ import annotations

from typing import Any

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "oracert.dev/redrivable-result/v1"

# Recognised re-derivation methods.
METHOD_SOLVE = "oraclaw.solve.certificate/v1"
METHOD_MODELFORGE_BUILD = "modelforge.build/v1"
KNOWN_METHODS = frozenset({METHOD_SOLVE, METHOD_MODELFORGE_BUILD})


def validate_statement(stmt: Any) -> list[str]:
    """Return a list of structural problems (empty == a well-formed envelope)."""
    problems: list[str] = []
    if not isinstance(stmt, dict):
        return ["statement is not an object"]

    if stmt.get("_type") != STATEMENT_TYPE:
        problems.append(f"_type must be {STATEMENT_TYPE!r}")
    if stmt.get("predicateType") != PREDICATE_TYPE:
        problems.append(f"predicateType must be {PREDICATE_TYPE!r}")

    subject = stmt.get("subject")
    if not isinstance(subject, list) or not subject:
        problems.append("subject must be a non-empty array")
    else:
        for i, s in enumerate(subject):
            if not isinstance(s, dict) or "name" not in s:
                problems.append(f"subject[{i}] missing name")
                continue
            digest = s.get("digest")
            if not isinstance(digest, dict) or not digest:
                problems.append(f"subject[{i}].digest must be a non-empty object")

    predicate = stmt.get("predicate")
    if not isinstance(predicate, dict):
        problems.append("predicate must be an object")
    else:
        method = predicate.get("method")
        if not isinstance(method, str):
            problems.append("predicate.method must be a string")
        elif method not in KNOWN_METHODS:
            problems.append(
                f"predicate.method {method!r} not recognised "
                f"(known: {sorted(KNOWN_METHODS)})"
            )
        if predicate.get("redrivable") is not True:
            problems.append("predicate.redrivable must be true")
        if not isinstance(predicate.get("witness"), dict):
            problems.append("predicate.witness must be an object")

    return problems

"""OraCert — one in-toto re-derivable-result predicate + one LLM-free verifier
shared by OraClaw (SolveCertificate) and ModelForge (BuildManifest).

Standard supply-chain predicates bind their subject by digest only; OraCert
adds a method-tagged re-derivation witness so a single standalone verifier can
re-establish the CORRECTNESS of the result — not just byte identity — across
two heterogeneous producers, with no LLM and (for the solve branch) no solver.
"""

from modelforge.oracert.canonical import canonicalize, content_hash
from modelforge.oracert.emit import build_modelforge_statement
from modelforge.oracert.schema import (
    METHOD_MODELFORGE_BUILD,
    METHOD_SOLVE,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    validate_statement,
)
from modelforge.oracert.verify import VerifyResult, verify_statement

__all__ = [
    "canonicalize",
    "content_hash",
    "build_modelforge_statement",
    "validate_statement",
    "verify_statement",
    "VerifyResult",
    "STATEMENT_TYPE",
    "PREDICATE_TYPE",
    "METHOD_SOLVE",
    "METHOD_MODELFORGE_BUILD",
]

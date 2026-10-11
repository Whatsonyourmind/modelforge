"""Evidence-binding gate — does the support given for each number state *that* quantity?

Tier 1 is deterministic and fail-closed (no LLM). See `gate.py` for verdicts,
`roles.py` for the role lexicon, `docs/evidence.md` for the spec syntax.
"""

from modelforge.evidence.gate import (
    GATE_VERSION,
    GateResult,
    LeafResult,
    Verdict,
    parse_overrides,
    run_gate,
)

__all__ = ["GATE_VERSION", "GateResult", "LeafResult", "Verdict", "parse_overrides", "run_gate"]

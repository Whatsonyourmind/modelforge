"""Evidence declarations — what each numeric leaf claims about where it came from.

A `source_id` points at a *document*. An `Evidence` record points at the
*sentence*, so the binding between a field and its support can be checked
mechanically by `modelforge.evidence` (the evidence-binding gate).

Kinds
-----
fact        The value is stated verbatim in a source. Requires `quote` (the
            exact span) and a source (`source_id` here or on the assumption).
derived     The value is computed. Requires `expr`, evaluated over `terms`
            and/or other assumptions (by `name`). The gate recomputes it.
benchmark   An external market reference. Requires `quote` and `peer_set`;
            the value may sit inside a quoted range ("150-200 bps").
assumption  Analyst judgment. Requires `owner`. Never presented as sourced.
unverified  Declared as not yet supported. Blocks a strict build.

This module is schema only (no gate logic) so the spec layer can import it
without pulling in the gate.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceKind(str, Enum):
    FACT = "fact"
    DERIVED = "derived"
    BENCHMARK = "benchmark"
    ASSUMPTION = "assumption"
    UNVERIFIED = "unverified"


class EvidenceTerm(BaseModel):
    """One named input of a derived value, optionally bound to a source span."""

    model_config = ConfigDict(extra="forbid")

    value: float
    source_id: str | None = Field(default=None, pattern=r"^S-\d{3,}$")
    quote: str | None = None
    page: int | None = None
    note: str = ""


class Evidence(BaseModel):
    """Where a numeric leaf's value comes from, precisely enough to be checked."""

    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    # fact / benchmark
    source_id: str | None = Field(default=None, pattern=r"^S-\d{3,}$")
    quote: str | None = None
    page: int | None = None
    peer_set: str | None = None
    # derived
    expr: str | None = None
    terms: dict[str, EvidenceTerm] = Field(default_factory=dict)
    # assumption
    owner: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def _required_per_kind(self) -> Evidence:
        k = self.kind
        if k in (EvidenceKind.FACT, EvidenceKind.BENCHMARK) and not (self.quote or "").strip():
            raise ValueError(f"evidence kind '{k.value}' requires a non-empty `quote` (the exact span).")
        if k == EvidenceKind.BENCHMARK and not (self.peer_set or "").strip():
            raise ValueError("evidence kind 'benchmark' requires `peer_set` (what the reference is drawn from).")
        if k == EvidenceKind.DERIVED and not (self.expr or "").strip():
            raise ValueError("evidence kind 'derived' requires `expr`.")
        if k == EvidenceKind.ASSUMPTION and not (self.owner or "").strip():
            raise ValueError("evidence kind 'assumption' requires `owner` (who answers for this judgment).")
        return self


class EvidenceOverride(BaseModel):
    """A signed human decision to ship a leaf the gate blocked.

    Overriding is allowed; overriding silently is not — every override is
    reported by the gate and written into the build's evidence sidecar.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^A-\d{3,}$")
    verdict: str  # the blocking verdict being accepted: broken | contested | unverified
    reason: str
    signed_by: str
    date: date

    @model_validator(mode="after")
    def _nonempty(self) -> EvidenceOverride:
        if not self.reason.strip() or not self.signed_by.strip():
            raise ValueError("an evidence override needs a non-empty `reason` and `signed_by`.")
        if self.verdict not in ("broken", "contested", "unverified"):
            raise ValueError("override `verdict` must be one of: broken, contested, unverified.")
        return self

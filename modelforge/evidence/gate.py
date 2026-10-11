"""The evidence-binding gate (tier 1 — deterministic, no LLM, fail-closed).

For every numeric leaf (`Assumption`) in a spec it asks one question: does
the support this spec gives for the number actually state *this quantity*?

Verdicts
--------
bound       fact/benchmark: the quote is in the cited document, states the
            value at the field's unit, and names the field's role.
derived     the declared expression recomputes to the value.
assumption  analyst judgment with an owner; no sourcing is claimed.
unverified  a binding is claimed but could not be checked (no quote, no
            dataroom, cited document missing). Blocks only with --strict.
contested   another document states a conflicting figure, or the same figure
            as a different quantity. Blocks.
broken      a deterministic check failed: quote not in the document, value or
            unit not in the quote, role mismatch, wrong arithmetic. Blocks.
overridden  a blocking verdict accepted by a signed human override.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from modelforge.evidence.corpus import Corpus, Document
from modelforge.evidence.derive import ExprError, evaluate, rationale_arithmetic
from modelforge.evidence.numbers import (
    alternative_readings,
    close,
    find_mentions,
    find_ranges,
    normalize_text,
    to_field_unit,
)
from modelforge.evidence.roles import LEXICON_VERSION, conflicts, field_role, roles_near
from modelforge.spec.evidence import Evidence, EvidenceKind, EvidenceOverride

GATE_VERSION = "1.0.0"


class Verdict(str, Enum):
    BOUND = "bound"
    DERIVED = "derived"
    ASSUMPTION = "assumption"
    UNVERIFIED = "unverified"
    CONTESTED = "contested"
    BROKEN = "broken"
    OVERRIDDEN = "overridden"


@dataclass
class Check:
    name: str
    ok: bool | None  # None = not run
    detail: str = ""


@dataclass
class LeafResult:
    id: str
    name: str
    path: str
    value: float
    unit: str
    claim: str                 # fact | derived | benchmark | assumption | unverified
    declared: bool             # True when an `evidence` block was given
    source_id: str | None
    field_role: str | None
    verdict: Verdict = Verdict.UNVERIFIED
    reasons: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    suggestion: dict | None = None
    original_verdict: Verdict | None = None
    override: dict | None = None

    def fail(self, check: str, detail: str) -> None:
        self.checks.append(Check(check, False, detail))
        self.reasons.append(detail)

    def ok(self, check: str, detail: str = "") -> None:
        self.checks.append(Check(check, True, detail))

    def skip(self, check: str, detail: str) -> None:
        self.checks.append(Check(check, None, detail))


@dataclass
class GateResult:
    leaves: list[LeafResult]
    strict: bool
    dataroom: str | None
    documents: list[dict]
    unused_overrides: list[dict]

    @property
    def blocking_verdicts(self) -> set[Verdict]:
        b = {Verdict.BROKEN, Verdict.CONTESTED}
        if self.strict:
            b.add(Verdict.UNVERIFIED)
        return b

    @property
    def blocking(self) -> list[LeafResult]:
        return [lf for lf in self.leaves if lf.verdict in self.blocking_verdicts]

    @property
    def passed(self) -> bool:
        return not self.blocking

    def counts(self) -> dict[str, int]:
        out = {v.value: 0 for v in Verdict}
        for lf in self.leaves:
            out[lf.verdict.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        def leaf(lf: LeafResult) -> dict:
            d = asdict(lf)
            d["verdict"] = lf.verdict.value
            d["original_verdict"] = lf.original_verdict.value if lf.original_verdict else None
            return d
        return {
            "gate": "evidence-binding", "tier": 1, "gate_version": GATE_VERSION,
            "lexicon_version": LEXICON_VERSION, "strict": self.strict,
            "passed": self.passed, "counts": self.counts(),
            "dataroom": self.dataroom, "documents": self.documents,
            "blocking": [lf.id for lf in self.blocking],
            "overrides": [lf.override | {"original_verdict": lf.original_verdict.value}
                          for lf in self.leaves if lf.override],
            "unused_overrides": self.unused_overrides,
            "leaves": [leaf(lf) for lf in self.leaves],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Spec walking
# ─────────────────────────────────────────────────────────────────────────────

def _iter_assumptions(spec: BaseModel):
    """Yield (path, Assumption) for every Assumption in the spec, in order."""
    from modelforge.spec.base import Assumption

    seen: set[int] = set()

    def walk(o, path: str):
        if id(o) in seen:
            return
        if isinstance(o, Assumption):
            seen.add(id(o))
            yield path, o
            return
        if isinstance(o, BaseModel):
            seen.add(id(o))
            for k, v in o.__dict__.items():
                yield from walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                yield from walk(v, f"{path}[{i}]")
        elif isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, f"{path}.{k}" if path else str(k))

    yield from walk(spec, "")


def _sources(spec: BaseModel) -> dict:
    from modelforge.spec.base import Source

    out = {}

    def walk(o):
        if isinstance(o, Source):
            out[o.id] = o
        elif isinstance(o, BaseModel):
            for v in o.__dict__.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)

    walk(spec)
    return out


def _path_key(path: str) -> str:
    """The field key a leaf is filed under: 'construction.total_capex_eur_m' ->
    'total_capex_eur_m'; list items use their parent key."""
    last = path.split(".")[-1]
    return last.split("[")[0]


# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────

def _matching_mentions(text_norm: str, value: float, unit: str):
    return [m for m in find_mentions(text_norm)
            if (v := to_field_unit(m, unit)) is not None and close(v, value)]


def _in_range(text_norm: str, value: float, unit: str) -> str | None:
    from modelforge.evidence.numbers import Mention
    for lo, hi, r_unit, scale in find_ranges(text_norm):
        conv = []
        for x in (lo, hi):
            m = Mention(str(x), x, r_unit == "currency", scale, r_unit, 0, 0, 0)
            conv.append(to_field_unit(m, unit))
        if None not in conv and conv[0] <= value <= conv[1]:
            return f"{lo:g}-{hi:g}"
    return None


def _value_in_quote(leaf: LeafResult, quote_norm: str, allow_range: bool) -> bool:
    if _matching_mentions(quote_norm, leaf.value, leaf.unit):
        leaf.ok("value_in_quote", f"{leaf.value:g} {leaf.unit} is stated in the quote")
        leaf.ok("unit_consistent")
        return True
    if allow_range and (rng := _in_range(quote_norm, leaf.value, leaf.unit)):
        leaf.ok("value_in_quote", f"{leaf.value:g} {leaf.unit} lies in the quoted range {rng}")
        leaf.ok("unit_consistent")
        return True
    for m in find_mentions(quote_norm):
        for alt, why in alternative_readings(m, leaf.unit):
            if close(alt, leaf.value):
                leaf.fail("unit_consistent",
                          f"the quote has the digits but not the quantity: {why} "
                          f"(field is {leaf.value:g} {leaf.unit})")
                return False
    leaf.fail("value_in_quote", f"{leaf.value:g} {leaf.unit} does not appear in the quote")
    return False


def _role_check(leaf: LeafResult, text_norm: str, where: str, check: str) -> bool | None:
    """True = names the field's role, False = names a conflicting role,
    None = the value is not in the text or the text names no known role."""
    if not leaf.field_role:
        return None
    verdict = None
    for m in _matching_mentions(text_norm, leaf.value, leaf.unit):
        near = roles_near(text_norm, m.start, m.end)
        roles = {h.role for h, _ in near}
        if leaf.field_role in roles:
            leaf.ok(check, f"{where} names '{leaf.field_role}' next to {m.raw}")
            return True
        bad = [(h, d) for h, d in near if conflicts(h.role, leaf.field_role)]
        if bad:
            h, _ = min(bad, key=lambda t: t[1])
            leaf.fail(check, f"{where} binds {m.raw} to '{h.phrase}' ({h.role}), but the field "
                             f"is filed as {leaf.field_role}")
            verdict = False
    return verdict


def _quote_present(leaf: LeafResult, corpus: Corpus | None, doc_ref: str | None,
                   quote_norm: str, page: int | None, check: str = "quote_present"):
    """Returns the Document if the quote was found in it, else None. Records
    an unverified reason (no corpus / doc missing) or a failure."""
    if corpus is None:
        leaf.skip(check, "no --dataroom: quote not checked against the document")
        leaf.reasons.append("quote not checked against the document (no dataroom given)")
        return None
    doc = corpus.resolve(doc_ref) if doc_ref else None
    if doc is None:
        leaf.skip(check, f"cited document '{doc_ref}' is not in the dataroom")
        leaf.reasons.append(f"cited document '{doc_ref}' is not in the dataroom")
        return None
    pages = doc.find(quote_norm)
    if not pages:
        leaf.fail(check, f"quote not found in {doc.filename}")
        return None
    if page is not None and any(p is not None for p in pages) and page not in pages:
        leaf.fail(check, f"quote is on page {', '.join(str(p) for p in pages)} of "
                         f"{doc.filename}, not page {page}")
        return None
    leaf.ok(check, f"found in {doc.filename} p.{', '.join(str(p) for p in pages)}")
    return doc


def _cross_source(leaf: LeafResult, corpus: Corpus, own_doc: Document | None, quote_norm: str):
    """Other statements in the dataroom that contradict a bound fact."""
    if not leaf.field_role:
        leaf.skip("cross_source", "field role unknown to the lexicon")
        return []
    contested = []
    want_unit = {"eur_m": "currency", "eur_k": "currency", "eur": "currency",
                 "pct": "pct", "bps": "bps", "x": "x"}.get(leaf.unit)
    for doc in corpus.docs:
        for page in doc.pages:
            q_at = page.text.find(quote_norm) if (doc is own_doc and quote_norm) else -1
            for m in find_mentions(page.text):
                if q_at >= 0 and q_at <= m.start < q_at + len(quote_norm):
                    continue  # the bound quote itself
                v = to_field_unit(m, leaf.unit)
                if v is None:
                    continue
                near = roles_near(page.text, m.start, m.end)
                if not near:
                    continue
                roles = {h.role for h, _ in near}
                where = f"{doc.filename} p.{page.number}" if page.number else doc.filename
                if close(v, leaf.value):
                    if leaf.field_role in roles:
                        continue
                    bad = [(h, d) for h, d in near if conflicts(h.role, leaf.field_role)]
                    if bad:
                        h, _ = min(bad, key=lambda t: t[1])
                        contested.append(f"{where} states {m.raw} as '{h.phrase}' ({h.role})")
                elif want_unit and m.unit == want_unit:
                    h, d = min(near, key=lambda t: t[1])
                    if h.role == leaf.field_role and d <= 3:
                        contested.append(f"{where} gives {leaf.field_role} as {m.raw}, "
                                         f"not {leaf.value:g} {leaf.unit}")
    if contested:
        leaf.checks.append(Check("cross_source", False, "; ".join(contested)))
    else:
        leaf.ok("cross_source", "no conflicting statement elsewhere in the dataroom")
    return contested


def _locate(leaf: LeafResult, corpus: Corpus, doc_ref: str | None) -> bool | None:
    """Legacy leaf (source_id, no quote): look for the value in the cited doc.
    True = found with the field's role (a quote is suggested); False = found
    only under a conflicting role; None = not determinable."""
    doc = corpus.resolve(doc_ref) if doc_ref else None
    if doc is None:
        leaf.reasons.append(f"cited document '{doc_ref}' is not in the dataroom")
        return None
    seen_conflict = None
    for page in doc.pages:
        for m in _matching_mentions(page.text, leaf.value, leaf.unit):
            near = roles_near(page.text, m.start, m.end)
            roles = {h.role for h, _ in near}
            if leaf.field_role and leaf.field_role in roles:
                lo = max(0, page.text.rfind(". ", 0, m.start) + 2)
                hi = page.text.find(". ", m.end)
                leaf.suggestion = {"source_id": leaf.source_id, "page": page.number,
                                   "quote": page.text[lo: hi if hi > 0 else len(page.text)]}
                return True
            bad = [(h, d) for h, d in near if leaf.field_role and conflicts(h.role, leaf.field_role)]
            if bad and seen_conflict is None:
                h, _ = min(bad, key=lambda t: t[1])
                seen_conflict = f"{doc.filename} p.{page.number} states {m.raw} as '{h.phrase}' ({h.role})"
    if seen_conflict:
        leaf.fail("locate", f"the cited document states this figure only as a different "
                            f"quantity: {seen_conflict}; the field is filed as {leaf.field_role}")
        return False
    leaf.reasons.append(f"{leaf.value:g} {leaf.unit} does not appear in {doc.filename} under "
                        f"the field's role")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Per-leaf evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_leaf(path, a, sources, by_name, corpus, analyst) -> LeafResult:
    ev: Evidence | None = a.evidence
    src_id = (ev.source_id if ev and ev.source_id else None) or a.source_id
    leaf = LeafResult(
        id=a.id, name=a.name, path=path, value=float(a.base), unit=a.unit,
        claim=(ev.kind.value if ev else ("fact" if a.source_id else "assumption")),
        declared=ev is not None, source_id=src_id,
        field_role=field_role(a.label.en if a.label else "", a.name, _path_key(path)),
    )
    src = sources.get(src_id) if src_id else None

    # ── undeclared ───────────────────────────────────────────────────────────
    if ev is None:
        if not a.source_id:
            leaf.verdict = Verdict.ASSUMPTION
            leaf.reasons.append(f"no source cited — analyst judgment (owner: {analyst})")
            return leaf
        broken = False
        if _role_check(leaf, normalize_text(a.rationale), "the rationale", "role_rationale") is False:
            broken = True
        if src is not None and src.note and _role_check(
                leaf, normalize_text(src.note), f"the {src_id} note", "role_source_note") is False:
            broken = True
        derived_undeclared = None
        for ra in rationale_arithmetic(a.rationale):
            if not ra.consistent:
                leaf.fail("rationale_arithmetic",
                          f"the rationale's arithmetic does not hold: '{ra.text}' computes "
                          f"{ra.computed:,.6g}, not {ra.stated:,.6g}")
                broken = True
            elif (s := ra.scaled_to(leaf.value)) is not None and close(s, leaf.value):
                derived_undeclared = ra
        if derived_undeclared is not None:
            leaf.ok("rationale_arithmetic", f"'{derived_undeclared.text}' recomputes to "
                                            f"{derived_undeclared.scaled_to(leaf.value):g}")
            leaf.reasons.append(
                f"the value is derived in the rationale ('{derived_undeclared.text}'), not a figure "
                f"stated in {src_id}; declare `evidence: {{kind: derived, expr: ..., terms: ...}}`")
        if corpus is not None and not broken and src is not None:
            if _locate(leaf, corpus, src.doc) is False:
                broken = True
        if broken:
            leaf.verdict = Verdict.BROKEN
        else:
            leaf.verdict = Verdict.UNVERIFIED
            leaf.reasons.insert(0, f"cites {src_id} but gives no quote, so the binding cannot be checked")
        return leaf

    # ── declared ─────────────────────────────────────────────────────────────
    if ev.kind == EvidenceKind.ASSUMPTION:
        leaf.verdict = Verdict.ASSUMPTION
        leaf.reasons.append(f"analyst judgment (owner: {ev.owner})" + (f" — {ev.note}" if ev.note else ""))
        return leaf
    if ev.kind == EvidenceKind.UNVERIFIED:
        leaf.verdict = Verdict.UNVERIFIED
        leaf.reasons.append("declared unverified" + (f" — {ev.note}" if ev.note else ""))
        return leaf

    if ev.kind in (EvidenceKind.FACT, EvidenceKind.BENCHMARK):
        if src is None:
            leaf.fail("source", f"{ev.kind.value} evidence names no defined source")
            leaf.verdict = Verdict.BROKEN
            return leaf
        quote_norm = normalize_text(ev.quote or "")
        _value_in_quote(leaf, quote_norm, allow_range=ev.kind == EvidenceKind.BENCHMARK)
        if ev.kind == EvidenceKind.FACT:
            _role_check(leaf, quote_norm, "the quote", "role_quote")
        doc = _quote_present(leaf, corpus, src.doc, quote_norm, ev.page)
        failed = any(c.ok is False for c in leaf.checks)
        if failed:
            leaf.verdict = Verdict.BROKEN
            return leaf
        if doc is None:
            leaf.verdict = Verdict.UNVERIFIED
            return leaf
        if ev.kind == EvidenceKind.FACT and corpus is not None:
            contested = _cross_source(leaf, corpus, doc, quote_norm)
            if contested:
                leaf.verdict = Verdict.CONTESTED
                leaf.reasons.extend(contested)
                return leaf
        leaf.verdict = Verdict.BOUND
        return leaf

    # derived
    names = {n: float(x.base) for n, x in by_name.items() if x is not a}
    names.update({k: float(t.value) for k, t in ev.terms.items()})
    try:
        result = evaluate(ev.expr, names)
    except ExprError as e:
        leaf.fail("derived_recompute", str(e))
        leaf.verdict = Verdict.BROKEN
        return leaf
    if not close(result, leaf.value):
        leaf.fail("derived_recompute", f"expr '{ev.expr}' = {result:,.6g}, but the field value is "
                                       f"{leaf.value:,.6g}")
        leaf.verdict = Verdict.BROKEN
        return leaf
    leaf.ok("derived_recompute", f"expr '{ev.expr}' = {result:,.6g}")
    unchecked = []
    for tname, t in ev.terms.items():
        if not t.source_id:
            leaf.reasons.append(f"input '{tname}' = {t.value:g} is unsourced (analyst input)")
            continue
        tsrc = sources.get(t.source_id)
        if not t.quote:
            unchecked.append(f"input '{tname}' cites {t.source_id} without a quote")
            continue
        tq = normalize_text(t.quote)
        if not any(close(m.value, t.value) or close(m.value * m.scale, t.value) for m in find_mentions(tq)):
            leaf.fail(f"term_value:{tname}", f"input '{tname}' = {t.value:g} does not appear in its quote")
            continue
        doc = _quote_present(leaf, corpus, tsrc.doc if tsrc else None, tq, t.page,
                             check=f"term_quote:{tname}")
        if doc is None and leaf.checks[-1].ok is None:
            # Not checkable (no dataroom / document missing): unverified, not
            # broken. A failed lookup keeps its reason on the leaf.
            unchecked.append(f"input '{tname}': {leaf.reasons.pop()}")
    if any(c.ok is False for c in leaf.checks):
        leaf.verdict = Verdict.BROKEN
    elif unchecked:
        leaf.verdict = Verdict.UNVERIFIED
        leaf.reasons.extend(unchecked)
    else:
        leaf.verdict = Verdict.DERIVED
    return leaf


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_overrides(raw: Any) -> tuple[list[EvidenceOverride], list[str]]:
    """Validate the spec's top-level `evidence_overrides`. Invalid entries are
    returned as errors, never silently honoured."""
    out, errors = [], []
    for i, item in enumerate(raw or []):
        try:
            out.append(EvidenceOverride.model_validate(item))
        except Exception as e:  # pydantic ValidationError
            errors.append(f"evidence_overrides[{i}]: {e}")
    return out, errors


def run_gate(spec: BaseModel, *, dataroom: Path | None = None,
             overrides: list[EvidenceOverride] | None = None,
             strict: bool = False, corpus: Corpus | None = None) -> GateResult:
    if corpus is None and dataroom is not None:
        corpus = Corpus.load(Path(dataroom))
    sources = _sources(spec)
    pairs = list(_iter_assumptions(spec))
    by_name = {a.name: a for _, a in pairs}
    analyst = getattr(getattr(spec, "meta", None), "analyst", None) or "unassigned"

    leaves = [_evaluate_leaf(p, a, sources, by_name, corpus, analyst) for p, a in pairs]

    result = GateResult(
        leaves=leaves, strict=strict,
        dataroom=str(dataroom) if dataroom else None,
        documents=[{"file": d.filename, "sha256": d.sha256, "pages": len(d.pages)}
                   for d in (corpus.docs if corpus else [])],
        unused_overrides=[],
    )
    blocking = result.blocking_verdicts
    by_id = {lf.id: lf for lf in leaves}
    for o in overrides or []:
        leaf = by_id.get(o.id)
        if leaf and leaf.verdict in blocking and leaf.verdict.value == o.verdict:
            leaf.original_verdict = leaf.verdict
            leaf.verdict = Verdict.OVERRIDDEN
            leaf.override = {"id": o.id, "verdict": o.verdict, "reason": o.reason,
                             "signed_by": o.signed_by, "date": o.date.isoformat()}
        else:
            result.unused_overrides.append(
                {"id": o.id, "verdict": o.verdict,
                 "why_unused": ("no such leaf" if leaf is None else
                                f"leaf verdict is '{leaf.verdict.value}', not a blocking '{o.verdict}'")})
    return result

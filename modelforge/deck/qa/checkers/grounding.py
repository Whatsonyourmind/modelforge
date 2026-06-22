"""Deterministic numeric-grounding gate for certified decks.

Reconciles every numeric token rendered on a composed deck back to a value
the certified workbook actually produced — either a recomputed cell fact, a
field of the composer's typed facts model (itself a deterministic function of
recomputed cells), or a centrally-declared *whitelisted derivation* of them
(leverage = debt / EBITDA, an LTV ratio, a percent-of-total share). A token
that reconciles to none of these is **unreconciled**; in fail-closed mode the
gate raises :class:`~modelforge.deck.adapter.DeckAdapterError`.

This is a deterministic **recompute-from-model-cell** anchor — distinct from
retrieved-document anchors (FinGround, ACL 2026) and from the existing deck
data-integrity checker, which verifies internal consistency only (pie≈100,
chart-NaN, footer sums) and is blind to a millions-vs-thousands format bug.
The honest claim is exactly "every rendered text token reconciles to a fact
OR a whitelisted derivation", which is strictly stronger than internal
consistency — NOT a literal raw-cell-only guarantee.

Scope: rendered **text** tokens (titles, bullets, callouts, table cells).
Native chart series are numeric IR (not format-string strings) and are not
subject to the format-string scale-bug class this gate targets; they remain
covered by the data-integrity checker. Initial template scope: ``sponsor_lbo``
+ ``real_estate`` + ``development_re`` via the ``ic_memo`` / ``teaser``
composers; other (template, deck_type) pairs are reported as ``skipped`` so
the gate never false-fails an un-whitelisted surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modelforge.deck.qa.numparse import NumericToken, extract_numeric_tokens

__all__ = [
    "GroundingFinding",
    "GroundingReport",
    "NumericGroundingChecker",
]

# Relative tolerance for float recompute drift; display-ulp dominates for the
# coarse formats (.1f millions, .1%), this guards the fine ones.
_REL_TOL = 1e-3
_ULP_FUDGE = 1.5
_ABS_FLOOR = 1e-9

# (template, deck_type) pairs with a verified token→fact mapping.
_SUPPORTED: frozenset[tuple[str, str]] = frozenset(
    {
        ("sponsor_lbo", "ic_memo"), ("sponsor_lbo", "teaser"),
        ("real_estate", "ic_memo"), ("real_estate", "teaser"),
        ("development_re", "ic_memo"), ("development_re", "teaser"),
    }
)


@dataclass(frozen=True)
class _PoolValue:
    value: float
    label: str


@dataclass
class GroundingFinding:
    slide_index: int
    raw: str
    kind: str
    candidate: float
    note: str

    @property
    def ref(self) -> str:
        return f"slide {self.slide_index} · {self.raw!r}"


@dataclass
class GroundingReport:
    template: str
    deck_type: str
    skipped: bool = False
    tokens_checked: int = 0
    findings: list[GroundingFinding] = field(default_factory=list)
    pool_size: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def unreconciled_count(self) -> int:
        return len(self.findings)

    @property
    def passed(self) -> bool:
        """Skipped surfaces pass vacuously (never false-fail); supported
        surfaces pass iff every checked token reconciled."""
        return self.skipped or not self.findings


# ─────────────────────────────────────────────────────────────────────────────
# IR text walk
# ─────────────────────────────────────────────────────────────────────────────

def _iter_strings(node: Any, skip_keys: frozenset[str]) -> list[str]:
    """All string leaves under a model_dump()-ed slide, minus skip_keys subtrees."""
    out: list[str] = []
    if isinstance(node, str):
        if node:
            out.append(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in skip_keys:
                continue
            out.extend(_iter_strings(v, skip_keys))
    elif isinstance(node, (list, tuple)):
        for v in node:
            out.extend(_iter_strings(v, skip_keys))
    return out


_SKIP_KEYS = frozenset({"speaker_notes", "slide_type", "theme", "id", "element_id"})


def _slide_strings(slide: Any) -> list[str]:
    if hasattr(slide, "model_dump"):
        dumped = slide.model_dump(mode="python")
    else:  # pragma: no cover - all IR slides are pydantic
        dumped = slide
    return _iter_strings(dumped, _SKIP_KEYS)


# ─────────────────────────────────────────────────────────────────────────────
# Value pool + derivations
# ─────────────────────────────────────────────────────────────────────────────

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _collect_numbers(node: Any, label: str, out: list[_PoolValue]) -> None:
    if _is_number(node):
        out.append(_PoolValue(float(node), label))
    elif isinstance(node, dict):
        for k, v in node.items():
            _collect_numbers(v, f"{label}.{k}", out)
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            _collect_numbers(v, f"{label}[{i}]", out)


class NumericGroundingChecker:
    """Reconcile rendered deck tokens against certified-workbook facts."""

    def __init__(self, rel_tol: float = _REL_TOL) -> None:
        self.rel_tol = rel_tol

    # -- pool construction -------------------------------------------------
    def _build_pool(self, wf: Any, facts_model: Any) -> tuple[list[_PoolValue], dict[str, float]]:
        pool: list[_PoolValue] = []
        named: dict[str, float] = {}

        # 1. Raw recomputed cell facts (the strongest anchor).
        for key, cf in getattr(wf, "facts", {}).items():
            if _is_number(getattr(cf, "value", None)):
                v = float(cf.value)
                pool.append(_PoolValue(v, f"fact:{key}={cf.ref}"))
                named[key] = v

        # 2. The composer's typed facts (deterministic derivations of cells).
        dumped: dict[str, Any] = {}
        if hasattr(facts_model, "model_dump"):
            dumped = facts_model.model_dump(mode="python")
            for k, v in dumped.items():
                _collect_numbers(v, f"deal:{k}", pool)
                if _is_number(v):
                    named.setdefault(k, float(v))

        # 3. Whitelisted derivations (named, few, documented).
        for value, label in self._derivations(named, dumped):
            pool.append(_PoolValue(value, f"derived:{label}"))

        return pool, named

    @staticmethod
    def _derivations(named: dict[str, float], dumped: dict[str, Any]) -> list[tuple[float, str]]:
        """Centrally-declared reconcilable derivations of named facts.

        Each is a number the composers compute INLINE from facts at format
        time (so it is not itself a stored field): a leverage / coverage
        multiple, an LTV-style ratio, or a percent-of-total share. Kept small
        and explicit on purpose — blanket pairwise ratios would make the gate
        permissive enough to miss real bugs.
        """
        out: list[tuple[float, str]] = []

        def ratio(num: str, den: str, name: str) -> None:
            n, d = named.get(num), named.get(den)
            if n is not None and d not in (None, 0.0):
                out.append((n / d, name))

        # debt / EBITDA leverage (ic_memo thesis "= N.Nx LTM EBITDA").
        senior = named.get("senior_debt", 0.0)
        mezz = named.get("mezz_debt", 0.0)
        rcf = named.get("rcf_drawn", 0.0)
        debt_total = senior + mezz + rcf
        ebitda = named.get("ebitda_last_fy")
        if ebitda:
            out.append((debt_total / ebitda, "leverage=debt/ebitda"))
        # also debt_eur_m / ebitda when the parts aren't separately present
        if "debt_eur_m" in named and ebitda:
            out.append((named["debt_eur_m"] / ebitda, "leverage=debt_eur_m/ebitda"))

        # real_estate ratios computed inline by the composer.
        ratio("loan_amount", "acquisition_price", "ltv=loan/acq")
        ratio("going_in_noi", "acquisition_price", "yoc=noi/acq")
        # development_re loan-to-cost (peak senior debt / total development cost).
        ratio("peak_debt", "total_dev_cost", "ltc=peak_debt/tdc")

        # Capital-structure "% of Total" column (ic_memo capital table), for
        # ALL templates: each tranche / stack-sum, the stack SUM (the "Total"
        # row amount, which may differ from total cost), and the 100% row. The
        # tranche amounts themselves are already in the pool via
        # ``capital_stack_values``; this adds only the derived figures.
        stack = dumped.get("capital_stack_values") or []
        stack_nums = [float(v) for v in stack if _is_number(v)]
        stack_sum = sum(stack_nums)
        if stack_sum:
            out.append((stack_sum, "stack_sum"))    # the "Total" row amount
            out.append((1.0, "share=total/total"))  # the "100.0%" total row
            for i, v in enumerate(stack_nums):
                out.append((v / stack_sum, f"share=stack[{i}]/sum"))

        return out

    # -- token reconciliation ---------------------------------------------
    def _candidate(self, tok: NumericToken) -> tuple[float, float]:
        """(candidate value, display-ulp) in the pool's numeric space."""
        if tok.kind == "percent":
            return tok.fraction(), tok.display_ulp() / 100.0
        if tok.kind == "bps":
            return tok.value / 10_000.0, tok.display_ulp() / 10_000.0
        if tok.kind == "multiple":
            return tok.value, tok.display_ulp()
        # currency / plain → canonical millions space
        from modelforge.deck.qa.numparse import _SCALE_TO_MILLIONS  # local: private map
        mult = _SCALE_TO_MILLIONS.get(tok.scale, 1.0)
        return tok.value_in_millions(), tok.display_ulp() * mult

    def _matches(self, candidate: float, ulp: float, pool: list[_PoolValue]) -> bool:
        tol = max(self.rel_tol * abs(candidate), ulp * _ULP_FUDGE, _ABS_FLOOR)
        for pv in pool:
            if abs(candidate - pv.value) <= max(tol, self.rel_tol * abs(pv.value)):
                return True
        return False

    def check(self, presentation: Any, wf: Any, facts_model: Any,
              deck_type: str) -> GroundingReport:
        template = getattr(wf, "template", "unknown")
        report = GroundingReport(template=template, deck_type=deck_type)

        if (template, deck_type) not in _SUPPORTED:
            report.skipped = True
            report.notes.append(
                f"({template}, {deck_type}) has no verified token→fact mapping "
                f"— grounding skipped (vacuous pass)."
            )
            return report

        pool, _named = self._build_pool(wf, facts_model)
        report.pool_size = len(pool)
        if not pool:
            report.skipped = True
            report.notes.append("empty value pool — grounding skipped.")
            return report

        for idx, slide in enumerate(presentation.slides):
            for text in _slide_strings(slide):
                for tok in extract_numeric_tokens(text):
                    report.tokens_checked += 1
                    candidate, ulp = self._candidate(tok)
                    if not self._matches(candidate, ulp, pool):
                        report.findings.append(
                            GroundingFinding(
                                slide_index=idx,
                                raw=tok.raw,
                                kind=tok.kind,
                                candidate=candidate,
                                note=(
                                    f"no certified fact or whitelisted "
                                    f"derivation within tolerance of "
                                    f"{candidate:.6g}"
                                ),
                            )
                        )
        return report

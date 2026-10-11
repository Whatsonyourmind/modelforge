"""The role lexicon — what kind of quantity a phrase names.

Hand-written, versioned, no model call. It exists for one job: notice when
the words bound to a number name a *different quantity* from the field the
number is filed under — a financing package filed as capex, an equity value
filed as enterprise value, a gross figure filed as net.

Only roles inside the same `CONFUSABLE` family can conflict. A phrase the
lexicon does not know is neutral, never a failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from modelforge.evidence.numbers import normalize_text

LEXICON_VERSION = "2026-10-11.1"

# role -> phrases (lowercase; matched on word boundaries, longest first)
ROLE_PHRASES: dict[str, tuple[str, ...]] = {
    # ── funding vs cost ──────────────────────────────────────────────────
    "capex": ("capex", "capital expenditure", "capital expenditures", "project cost",
              "project costs", "construction cost", "construction costs",
              "total investment", "investment cost", "development cost",
              "epc cost", "epc price", "epc contract price", "capital cost"),
    "financing_package": ("financing package", "funding package", "total financing",
                          "financing", "funding", "debt raise", "capital raise"),
    "debt_amount": ("senior debt", "senior loan", "senior facility", "senior green loan",
                    "green loan", "term loan", "facility amount", "loan amount",
                    "non-recourse senior", "senior tranche", "debt quantum",
                    "senior debt amount", "borrowing"),
    "equity_amount": ("equity contribution", "sponsor equity", "equity commitment",
                      "equity cheque", "equity check", "shareholder funding"),
    # ── valuation ────────────────────────────────────────────────────────
    "enterprise_value": ("enterprise value", "firm value", "ev"),
    "equity_value": ("equity value", "market capitalisation", "market capitalization",
                     "market cap", "equity purchase price"),
    # ── debt measures ────────────────────────────────────────────────────
    "gross_debt": ("gross debt", "total debt", "gross borrowings"),
    "net_debt": ("net debt", "net financial position", "net borrowings"),
    "committed": ("committed", "commitment", "commitments", "facility limit", "undrawn"),
    "drawn": ("drawn", "outstanding", "utilised", "utilized", "drawn balance"),
    # ── loan books ───────────────────────────────────────────────────────
    "gbv": ("gross book value", "gbv", "gross claim", "gross claims", "claim amount"),
    "nbv": ("net book value", "nbv", "carrying value", "carrying amount"),
    "purchase_price": ("purchase price", "consideration", "acquisition price"),
    # ── top line and profit ──────────────────────────────────────────────
    "revenue": ("revenue", "revenues", "sales", "net sales", "turnover", "ricavi"),
    "gwp": ("gross written premium", "gross written premiums", "gwp"),
    "gmv": ("gross merchandise value", "gmv", "bookings", "gross transaction value"),
    "ebitda": ("ebitda", "adjusted ebitda", "mol"),
    "ebit": ("ebit", "operating profit", "operating income"),
    "net_income": ("net income", "net profit", "profit after tax", "utile netto"),
    # ── pricing ──────────────────────────────────────────────────────────
    "margin": ("margin", "spread", "credit spread"),
    "base_rate": ("swap rate", "swap", "euribor", "base rate", "reference rate", "sofr", "sonia"),
    "all_in_rate": ("all-in rate", "all-in cost", "coupon", "interest rate"),
    "arrangement_fee": ("arrangement fee", "upfront fee", "structuring fee"),
    "commitment_fee": ("commitment fee", "commitment fees", "non-utilisation fee", "ticking fee"),
    # ── ratios ───────────────────────────────────────────────────────────
    "dscr": ("dscr", "debt service coverage ratio", "debt service cover ratio"),
    "llcr": ("llcr", "loan life coverage ratio"),
    "icr": ("icr", "interest cover", "interest coverage"),
    "ltv": ("ltv", "loan to value", "loan-to-value", "gearing"),
    "leverage": ("leverage", "net leverage", "net debt / ebitda", "net debt/ebitda"),
}

# Roles that are mistaken for one another in practice. Conflict is only ever
# declared between two roles of the same family.
CONFUSABLE: tuple[frozenset[str], ...] = (
    frozenset({"capex", "financing_package", "debt_amount", "equity_amount"}),
    frozenset({"enterprise_value", "equity_value", "purchase_price"}),
    frozenset({"gross_debt", "net_debt"}),
    frozenset({"committed", "drawn"}),
    frozenset({"gbv", "nbv", "purchase_price"}),
    frozenset({"revenue", "gwp", "gmv", "ebitda", "ebit", "net_income"}),
    frozenset({"margin", "base_rate", "all_in_rate"}),
    frozenset({"arrangement_fee", "commitment_fee"}),
    frozenset({"dscr", "llcr", "icr", "ltv", "leverage"}),
)

_PHRASES_LONGEST_FIRST: list[tuple[str, str]] = sorted(
    ((p, role) for role, ps in ROLE_PHRASES.items() for p in ps),
    key=lambda t: -len(t[0]),
)


def conflicts(a: str, b: str) -> bool:
    return a != b and any(a in fam and b in fam for fam in CONFUSABLE)


@dataclass(frozen=True)
class RoleHit:
    role: str
    phrase: str
    start: int
    end: int


def find_roles(text_norm: str) -> list[RoleHit]:
    """Non-overlapping role phrases in normalised text, longest match wins."""
    taken = [False] * len(text_norm)
    hits: list[RoleHit] = []
    for phrase, role in _PHRASES_LONGEST_FIRST:
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text_norm):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            hits.append(RoleHit(role, phrase, m.start(), m.end()))
    return sorted(hits, key=lambda h: h.start)


def field_role(*descriptors: str) -> str | None:
    """The role a field is *filed as*, from its label / name / path key.

    Descriptors are tried in order (label first); within one descriptor the
    longest phrase wins. snake_case is read as words.
    """
    for d in descriptors:
        if not d:
            continue
        words = normalize_text(d.replace("_", " "))
        # Unit suffixes in keys ("eur m", "pct", "bps") are not role words.
        words = re.sub(r"\b(eur|usd|gbp|m|k|pct|bps|yr\d*|y\d+)\b", " ", words)
        hits = find_roles(words)
        if hits:
            return max(hits, key=lambda h: len(h.phrase)).role
    return None


# Clause boundaries: sentence ends (not decimal points), semicolons, brackets.
_CLAUSE_SPLIT = re.compile(r"(?<!\d)\.(?!\d)|;|\(|\)|\n|\|")
WINDOW_WORDS = 8


def roles_near(text: str, start: int, end: int) -> list[tuple[RoleHit, int]]:
    """Role phrases in the same clause as text[start:end], within WINDOW_WORDS
    words of it, with their word distance. `text` must already be normalised."""
    # clause bounds
    lo = 0
    for m in _CLAUSE_SPLIT.finditer(text, 0, start):
        lo = m.end()
    m_hi = _CLAUSE_SPLIT.search(text, end)
    hi = m_hi.start() if m_hi else len(text)
    clause = text[lo:hi]
    out = []
    for h in find_roles(clause):
        a, b = lo + h.start, lo + h.end
        if b <= start:
            gap = text[b:start]
        elif a >= end:
            gap = text[end:a]
        else:
            gap = ""
        dist = len(gap.split())
        if dist <= WINDOW_WORDS:
            out.append((RoleHit(h.role, h.phrase, a, b), dist))
    return out

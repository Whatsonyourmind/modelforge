"""Base types used across all model templates.

These are the primitives every template composes:
    Label      — EN primary + IT secondary row label
    Source     — a citable source (doc page + publisher + verified flag)
    Assumption — a non-sourced analyst judgment (rationale + confidence)
    Scenario   — enum: WORST / BASE / BEST
    Target     — the company/opportunity being modeled
    ModelMeta  — cover-sheet metadata (analyst, date, version, revision log)
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Scenario(str, Enum):
    WORST = "worst"
    BASE = "base"
    BEST = "best"


class Confidence(str, Enum):
    H = "H"
    M = "M"
    L = "L"


class Label(BaseModel):
    """Multi-language label. EN mandatory, other languages optional.

    v0.10: expanded from EN/IT to EN + 7 secondary languages (IT/DE/ES/SV/NO/DA/NL).
    Backwards-compatible: existing code reading `.it` directly continues to work.
    New callers should use `.get(lang)` for safe lookup with EN fallback.

    Coverage status (as of v0.10):
        EN          — primary, mandatory
        IT          — full coverage, native-quality
        DE, ES      — full coverage, first-cut (review encouraged)
        SV, NO, DA, NL — full coverage, FIRST-CUT design-partner review required
    """

    en: str
    it: str = ""
    de: str = ""
    es: str = ""
    sv: str = ""
    no: str = ""
    da: str = ""
    nl: str = ""

    def __str__(self) -> str:
        return self.en

    def get(self, lang: str) -> str:
        """Return label in `lang`, falling back to `en` if missing or empty.

        Valid `lang` values: en, it, de, es, sv, no, da, nl.
        Unknown languages also fall back to en (no error — labels are display-time).
        """
        val = getattr(self, lang, "") if lang else ""
        return val or self.en


class Source(BaseModel):
    """A citable source. Referenced by ID (S-001) throughout the model.

    Rendered on the Sources sheet with full attribution. Every hardcoded
    cell sourced to S-id gets a comment linking back here.
    """

    id: str = Field(pattern=r"^S-\d{3,}$")
    doc: str  # filename or reference, e.g. "Dataroom_FY25_Audited.pdf"
    page: Optional[int] = None
    publisher: str
    date: date
    url: Optional[str] = None
    verified: bool = False
    note: str = ""  # Short note on what this source provides.


class Assumption(BaseModel):
    """An analyst assumption not directly sourced.

    When a value comes from judgment (e.g. exit multiple at year 5),
    tag it A-id rather than S-id. Requires rationale + confidence.
    """

    id: str = Field(pattern=r"^A-\d{3,}$")
    name: str  # snake_case; becomes a named range on Assumptions sheet.
    label: Label
    unit: Literal[
        "eur_m", "eur_k", "eur", "pct", "x", "years", "bps", "count", "ratio"
    ] = "eur_m"

    # Scenario values. BASE mandatory; others inherit from BASE if omitted.
    base: float
    worst: Optional[float] = None
    best: Optional[float] = None

    rationale: str  # WHY this value — required.
    confidence: Confidence = Confidence.M
    source_id: Optional[str] = Field(default=None, pattern=r"^S-\d{3,}$")

    @field_validator("rationale")
    @classmethod
    def rationale_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Assumption rationale must be non-empty (bulge-tier discipline).")
        return v

    def resolved(self, scenario: Scenario) -> float:
        if scenario == Scenario.WORST:
            return self.worst if self.worst is not None else self.base
        if scenario == Scenario.BEST:
            return self.best if self.best is not None else self.base
        return self.base


class Target(BaseModel):
    """The company / opportunity being modeled."""

    name: str  # May be anonymized (e.g. "Target SpA")
    sector: Label
    country: str = "IT"
    currency: Literal["EUR", "USD", "GBP", "CHF"] = "EUR"
    revenue_last_fy_eur_m: float
    revenue_source_id: str = Field(pattern=r"^S-\d{3,}$")
    ebitda_last_fy_eur_m: float
    ebitda_source_id: str = Field(pattern=r"^S-\d{3,}$")
    last_fy_end: date

    # Optional listed-co reference for live Trust Layer market-cap deviation
    # check. When set, the Trust Layer compares DCF-implied equity to the
    # current market cap fetched via the YahooProvider (free, no auth).
    ticker: Optional[str] = None  # e.g. "ENEL.MI", "AAPL", "BNP.PA"


class RevisionEntry(BaseModel):
    version: str  # v0.1, v1.0, ...
    date: date
    analyst: str
    note: str


class ModelMeta(BaseModel):
    """Cover sheet metadata."""

    project_code: str  # Short identifier, e.g. "LEAD-17-CDMO"
    deliverable: Label  # "Senior Unitranche Financing Proposal"
    analyst: str
    version: str = "v0.1"
    status: Literal["draft", "review", "final"] = "draft"
    valuation_date: date
    currency: Literal["EUR", "USD", "GBP", "CHF"] = "EUR"
    unit_scale: Literal["actual", "thousands", "millions"] = "millions"
    sign_convention: Literal["costs_negative", "all_positive"] = "costs_negative"
    revision_log: list[RevisionEntry] = Field(default_factory=list)
    confidentiality: str = "Strictly Private & Confidential"

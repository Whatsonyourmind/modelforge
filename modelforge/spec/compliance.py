"""Compliance & tax context — optional spec block for the ComplianceCheck sheet.

Historically the ComplianceCheck sheet (`modelforge/builder/sheets/compliance.py`)
hardcoded the jurisdiction-locked regulatory constants directly in the builder:

    - AIFMD II leverage caps   1.75x (open-ended) / 3.00x (closed-ended)
    - AIFMD II single-borrower cap 0.20 (20% of NAV)
    - Italian IRES rate        0.24
    - Italian IRAP rate        0.039
    - scenario inputs (aif_type / actual_leverage / largest_single_borrower)

These numbers are correct for the default Italian / EU regime, but they were
invisible to the analyst and could not be overridden from the spec. This block
lifts them into spec-driven, auditable, OVERRIDABLE named-input cells.

Backward-compatibility: every field defaults to the value that was previously
hardcoded. A spec that carries NO `compliance` block (the universal case today)
renders byte-identical output, because the builder falls back to these same
defaults via `getattr`.

Any template spec MAY add an optional `compliance: ComplianceContext | None`
field; the builder reads it generically through `getattr(spec, "compliance", None)`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TaxRegime(BaseModel):
    """Corporate tax regime applied on the ComplianceCheck IRES/IRAP split.

    Defaults reproduce the previously-hardcoded Italian 2026 rates so behaviour
    is unchanged when the field is omitted.
    """

    # Informational label for the regime (IT = Italy). Display-only; the rates
    # below are what actually drive the sheet.
    jurisdiction: Literal["IT", "DE", "ES", "CH", "OTHER"] = "IT"

    # IRES — Italian corporate income tax. Previously hardcoded 0.24.
    ires_rate_pct: float = 0.24

    # IRAP — regional production tax (national base + regional add-on).
    # Previously hardcoded 0.039.
    irap_rate_pct: float = 0.039


class ComplianceContext(BaseModel):
    """Jurisdiction-locked regulatory parameters for the ComplianceCheck sheet.

    Every field defaults to the value that was hardcoded in
    `builder/sheets/compliance.py`, so a spec omitting this block (or omitting
    individual fields) yields byte-identical output.
    """

    # ── AIFMD II leverage caps (commitment method) ──────────────────────────
    # Open-ended AIF max 175%; closed-ended max 300% (Art. 15a). Previously
    # hardcoded as literals 1.75 / 3.00 inside the cap formula.
    aif_leverage_cap_open_pct: float = 1.75
    aif_leverage_cap_closed_pct: float = 3.00

    # ── AIFMD II concentration / single-borrower cap ────────────────────────
    # Loans to a single borrower capped at 20% of AIF NAV (Art. 15a(4)).
    # Previously hardcoded literal 0.20.
    largest_borrower_cap_pct: float = 0.20

    # ── Scenario inputs (were context.get() defaults) ───────────────────────
    # AIF type drives which leverage cap applies via the IF() formula.
    aif_type: Literal["open", "closed"] = "closed"
    # Actual portfolio leverage tested against the cap.
    actual_leverage: float = 1.50
    # Largest single-borrower exposure as % of NAV, tested against the cap.
    largest_single_borrower_pct_nav: float = 0.15

    # ── Tax regime (IRES + IRAP) ────────────────────────────────────────────
    tax: TaxRegime = Field(default_factory=TaxRegime)

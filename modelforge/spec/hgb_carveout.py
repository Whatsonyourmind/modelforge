"""HGB Carve-out spec — Template 15 (v0.10 PREVIEW).

DACH carve-out / turnaround deal modeling with German GAAP (HGB) layer
on top of the 3-statement base.

⚠️ v0.10 PREVIEW — requires DACH accounting-expert review before production
   use. The structural skeleton is correct (HGB §§ 264 ff. P&L and BS forms)
   but Handelsbilanz-vs-Steuerbilanz reconciliation rules, GewSt Hebesatz
   localization, and latente Steuern (DTA/DTL) build are placeholders.

Why this template exists:
    DACH operational-turnaround buyers (AURELIUS, Mutares, Capvis) cannot
    use IFRS-only templates because the deal docs (Steuerbilanz, HGB-
    Jahresabschluss) are in HGB form. v0.10 ships the structural pattern;
    v0.11 backfills the DTA/DTL math and § 252-256 valuation rules.

References (for v0.11 expansion):
    - HGB § 264-289 (P&L and BS forms for Kapitalgesellschaften)
    - § 5 EStG, § 274 HGB (latente Steuern)
    - IDW S 1 (Bewertungsstandard) for valuation reconciliation
    - PWC HGB-Kompendium, KPMG Handbuch HGB
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from modelforge.spec.three_statement import ThreeStatementSpec


class HGBSpecificAssumptions(BaseModel):
    """HGB-specific drivers layered on top of the IFRS/3-statement core.

    All fields optional — when omitted, the template renders the 3-statement
    base with HGB labels but skips the reconciliation block.
    """

    hgb_form: Literal["gesamtkostenverfahren", "umsatzkostenverfahren"] = "gesamtkostenverfahren"
    """HGB § 275 P&L form. 'Gesamtkostenverfahren' (total-cost method) is more
    common for German Mittelstand carve-outs."""

    gewerbesteuer_hebesatz: float = Field(default=400.0, ge=200.0, le=900.0)
    """Local GewSt Hebesatz (%). Munich ~490, Berlin ~410, Hamburg ~470,
    Frankfurt ~460, rural DE ~300-380. Default 400% (national-ish average)."""

    soli_applicable: bool = True
    """Solidaritätszuschlag — applicable to KSt only, 5.5% surcharge.
    Reduced to high-earners only from 2021 but still applies to corporates."""

    enable_hgb_steuer_recon: bool = False
    """When True, render the Handelsbilanz vs Steuerbilanz reconciliation
    block. v0.10 ships this as a placeholder sheet only — full DTA/DTL math
    is v0.11 scope."""


class HGBCarveoutSpec(ThreeStatementSpec):
    """HGB-aware corporate model spec for DACH carve-out / turnaround deals.

    Inherits the full 3-statement structure (P&L + BS + CFS) and overlays
    the HGB-specific assumption block.

    Setting `model_type = 'hgb_carveout'` routes this through the HGB
    template builder which (a) renders all labels DE-secondary, (b) appends
    the HGB-Reconciliation worksheet documenting the IFRS↔HGB delta.
    """

    model_type: Literal["hgb_carveout"] = "hgb_carveout"
    hgb_assumptions: Optional[HGBSpecificAssumptions] = None

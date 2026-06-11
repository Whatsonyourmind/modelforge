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


class CarveoutBridgeAssumptions(BaseModel):
    """Standalone-EBITDA carve-out bridge + carve-out EV drivers (v0.12).

    A carve-out's *reported* EBITDA (as it sits inside the seller's group)
    is rarely the EBITDA the buyer actually acquires. The standalone bridge
    normalizes it for (a) parent corporate-cost allocations that disappear,
    (b) dis-synergies / stranded costs the unit must now carry alone,
    (c) time-bounded TSA (Transition Service Agreement) costs, and (d)
    one-time separation costs. The carve-out Enterprise Value is then the
    *steady-state run-rate* standalone EBITDA × an entry multiple.

    Sign convention (all magnitudes entered as POSITIVE numbers; the builder
    applies the bridge signs):
        reported_ebitda
          + allocated_corporate_costs   (add-back: seller over-allocation removed)
          - dis_synergies               (stranded / lost-scale costs, recurring)
          - tsa_costs                   (transition-period only; excluded from run-rate)
          - one_time_separation_costs   (one-off; excluded from run-rate)
          = standalone_adjusted_ebitda  (during the TSA period)

    Steady-state (run-rate) EBITDA excludes the two transitory lines
    (tsa_costs + one_time_separation_costs), and is the base for the EV
    multiple.

    All fields optional individually but the block must carry at least
    reported_ebitda + entry_multiple to render an EV.
    """

    reported_ebitda: float = Field(ge=0.0)
    """Carve-out unit EBITDA as reported in the seller's consolidated books
    (carve-out perimeter, last FY), in spec unit_scale."""

    allocated_corporate_costs: float = Field(default=0.0, ge=0.0)
    """Parent corporate-overhead allocation charged to the unit that will NOT
    transfer with the carve-out — an add-back (increases standalone EBITDA)."""

    dis_synergies: float = Field(default=0.0, ge=0.0)
    """Recurring dis-synergies / stranded costs the standalone entity now
    bears alone (own ERP/HR/finance, lost group purchasing scale). Subtracts."""

    tsa_costs: float = Field(default=0.0, ge=0.0)
    """Transition Service Agreement costs paid to the seller during the TSA
    window. Time-bounded → subtracted from the during-TSA EBITDA but EXCLUDED
    from the steady-state run-rate used for the EV multiple."""

    tsa_period_years: float = Field(default=1.0, ge=0.0, le=5.0)
    """TSA duration in years (documentation of the time-boundary). The TSA
    cost is excluded from steady-state regardless; this records the window."""

    one_time_separation_costs: float = Field(default=0.0, ge=0.0)
    """One-off carve-out separation / stand-up costs (IT cloning, rebranding,
    legal entity setup). Excluded from the steady-state run-rate."""

    entry_multiple: float = Field(default=0.0, ge=0.0, le=30.0)
    """EV / standalone-EBITDA entry multiple applied to the steady-state
    run-rate standalone EBITDA to derive the carve-out Enterprise Value."""


class HGBCarveoutSpec(ThreeStatementSpec):
    """HGB-aware corporate model spec for DACH carve-out / turnaround deals.

    Inherits the full 3-statement structure (P&L + BS + CFS) and overlays
    the HGB-specific assumption block.

    Setting `model_type = 'hgb_carveout'` routes this through the HGB
    template builder which (a) renders all labels DE-secondary, (b) appends
    the HGB-Reconciliation worksheet documenting the IFRS↔HGB delta, and
    (c) — when `carveout_bridge` is supplied — appends a standalone-EBITDA
    Carve-out Bridge worksheet with the carve-out Enterprise Value.
    """

    model_type: Literal["hgb_carveout"] = "hgb_carveout"
    hgb_assumptions: Optional[HGBSpecificAssumptions] = None
    carveout_bridge: Optional[CarveoutBridgeAssumptions] = None

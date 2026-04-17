"""Competitor model reverse-engineer — v0.5 US-016.

Takes a legacy Excel financial model (Macabacus, bank-internal,
hand-crafted — anything) and produces:

    1. A structural analysis: sheet-type classification, named
       ranges, input extraction, formula-shape clusters
    2. A partial ModelForge spec skeleton in YAML format
    3. A REVERSE_REPORT.md summary pointing at what the user needs
       to complete manually

Purpose: kill switching cost. A new ModelForge user with a legacy
Excel model from a previous bank job or a Macabacus subscription
can get most of the way to a ModelForge spec automatically.
"""

from modelforge.reverse.engine import (
    ReverseReport,
    analyze_workbook,
    classify_sheet,
    detect_template_type,
    render_markdown,
    render_spec_skeleton,
)

__all__ = [
    "ReverseReport",
    "analyze_workbook",
    "classify_sheet",
    "detect_template_type",
    "render_markdown",
    "render_spec_skeleton",
]

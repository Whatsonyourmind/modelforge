"""Audit dossier generator — v0.4 US-009.

Produces a regulator-grade PDF dossier for a built ModelForge workbook.
Every number in the workbook is traceable to a source citation or an
assumption rationale; the dossier exposes that trail in a format that
auditors, rating agencies, and credit committees can sign off on.

This is a structural moat Rogo cannot copy — their cells are values
(not formulas traced to source pages), so they cannot produce a
dossier at this fidelity.
"""

from modelforge.dossier.generator import generate_dossier

__all__ = ["generate_dossier"]

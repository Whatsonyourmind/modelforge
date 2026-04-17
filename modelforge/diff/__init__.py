"""Model diff — Git-style comparison between two ModelForge workbooks.

Produces a structured, auditable diff covering:

    * Input value changes (Assumptions BASE cells, keyed by A-### / name)
    * Formula changes (per sheet, per cell)
    * Structural changes (sheet added/removed/renamed, named ranges)
    * Source citation changes (S-### entries on Sources sheet)
    * Reproducibility metadata changes (spec SHA, version, timestamp)

Output formats: markdown (CLI-friendly) + HTML (web-renderable).
"""

from modelforge.diff.engine import DiffResult, compute_diff, render_markdown, render_html

__all__ = ["DiffResult", "compute_diff", "render_markdown", "render_html"]

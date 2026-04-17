"""ROI calculator — v0.5 US-036.

Quantifies the adoption business case for a prospective buyer:
   time saved per deal × deals/year × loaded analyst cost
   + audit / rating-agency review time saved
   + reduced rework from error reduction
   − ModelForge subscription cost
   = net annual savings + payback period.

Used by the sales process; every assumption is editable via CLI flags
so prospects can validate the numbers on their own book.
"""

from modelforge.roi.calculator import (
    ROIInputs,
    ROIResult,
    compute_roi,
    render_markdown,
)

__all__ = ["ROIInputs", "ROIResult", "compute_roi", "render_markdown"]

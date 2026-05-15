"""ModelForge Moat — verifiable proof of "fully-formulated live Excel outputs".

Why this package exists
=======================

The IC review (2026-05-15) flagged that the marketing claim "every cell
live-formulated" was technically false (~25% formula ratio at the cell
level, ~75% hardcoded inputs). The cell-ratio metric was misleading
because it counted text labels and intentional input cells.

This package replaces the loose claim with **four hard, verifiable
gates** any reviewer can run independently:

1. **Formula-density gate** — for every CORE OUTPUT sheet, ≥90% of the
   numeric cells (excluding labels, headers, intentional inputs) are
   formulas (not literal numbers).

2. **Reference-graph gate** — every output formula's references are
   named ranges or other formulas, never magic-number literals embedded
   inline. Catches "drift" formulas like ``=B5*1.05`` (where 1.05 is
   an undocumented assumption).

3. **Recalculation gate** — the third-party `formulas` engine (not
   ModelForge's writer) recomputes every formula and the values match
   the cached values openpyxl reads. Proves the model is **portable**
   and would produce the same numbers on any analyst's Excel.

4. **No-orphan-input gate** — every named-range assumption defined in
   the workbook is referenced by at least one formula. Eliminates
   "ghost assumptions" that look documented but don't drive anything.

The output is a :class:`MoatReport` and a per-workbook ``MOAT`` sheet
that surfaces the metrics so a buyer can verify the claim without
running any code.

Sheet taxonomy
==============

* **CORE_OUTPUT_SHEETS** — the valuation engine. MUST satisfy all four
  gates. Examples: ``WACCBuild``, ``Valuation``, ``FCFForecast``,
  ``Returns``, ``OperatingModel``, ``DebtSchedule``, ``Covenants``.

* **SIMULATION_SHEETS** — Monte Carlo / scenario sweep outputs. The
  simulator runs externally (not via Excel formulas) for runtime
  reasons. These sheets are **exempt** from the formula-density gate
  but still subject to source-traceability rules.

* **INPUT_SHEETS** — Cover, Sources, Assumptions, RawData. By design
  hold inputs (with cell comments + Source IDs); exempt from the
  formula-density gate.

* **REFERENCE_SHEETS** — ComparableBetas, RatingShadow. Hold input
  data with formulas only on the aggregation rows (median, mean).
  Held to a relaxed ≥30% formula threshold.

Usage::

    from modelforge.moat import MoatGate, inject_moat_sheet

    gate = MoatGate()
    report = gate.evaluate(xlsx_path)
    inject_moat_sheet(xlsx_path, report)

    if not report.passes():
        sys.exit(1)
"""

from modelforge.moat.classifier import (
    SHEET_TAXONOMY,
    SheetClass,
    classify_sheet,
)
from modelforge.moat.report import (
    GateResult,
    MoatReport,
    SheetMetrics,
)
from modelforge.moat.gate import MoatGate, MoatThresholds
from modelforge.moat.sheet import inject_moat_sheet

__all__ = [
    "GateResult",
    "MoatGate",
    "MoatReport",
    "MoatThresholds",
    "SHEET_TAXONOMY",
    "SheetClass",
    "SheetMetrics",
    "classify_sheet",
    "inject_moat_sheet",
]

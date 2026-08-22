"""MoatReport + GateResult dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


GateName = Literal["formula_density", "reference_graph", "recalculation", "no_orphan_inputs"]


@dataclass
class SheetMetrics:
    name: str
    sheet_class: str
    numeric_cells: int = 0
    formula_cells: int = 0
    hardcoded_numeric_cells: int = 0
    # Hardcoded cells the workbook *declares* as inputs by painting them the
    # blue input colour. Tracked separately because they are not failed
    # outputs — see ``formula_ratio``.
    declared_input_cells: int = 0
    formulas_with_magic_numbers: list[str] = field(default_factory=list)  # cell coords

    @property
    def formula_ratio(self) -> float:
        """Share of *computed* cells that really are formulas.

        Declared inputs are excluded from the base. The property being gated is
        "the outputs on this sheet are computed, not pasted", and an input is by
        definition not an output: the house colour convention marks it blue, and
        a sheet that legitimately carries its own input block (an opening
        balance sheet, a period-index axis, a historical FY0 column) could
        otherwise never reach the threshold no matter how live its outputs were.

        This does not soften the check that matters. A pasted output keeps the
        black formula colour — that is exactly how the IPO Valuation sheet and
        the restructuring waterfall shipped as constants — so it still counts
        against the ratio.
        """
        base = self.numeric_cells - self.declared_input_cells
        if base <= 0:
            return 1.0  # vacuous pass: nothing on this sheet claims to compute
        return self.formula_cells / base


@dataclass
class GateResult:
    name: GateName
    passed: bool
    detail: str
    metric: float | None = None
    threshold: float | None = None


@dataclass
class MoatReport:
    workbook: str
    sheet_metrics: list[SheetMetrics] = field(default_factory=list)
    gate_results: list[GateResult] = field(default_factory=list)
    orphan_named_ranges: list[str] = field(default_factory=list)
    recalc_mismatches: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)

    def passes(self) -> bool:
        return all(g.passed for g in self.gate_results)

    def core_output_density(self) -> float:
        """Aggregate formula ratio over CORE OUTPUT sheets only."""
        core = [m for m in self.sheet_metrics if m.sheet_class == "core_output"]
        total = sum(m.numeric_cells for m in core)
        if total == 0:
            return 1.0
        formulas = sum(m.formula_cells for m in core)
        return formulas / total

    def get_gate(self, name: GateName) -> GateResult | None:
        for g in self.gate_results:
            if g.name == name:
                return g
        return None

    def summary(self) -> dict:
        return {
            "workbook": self.workbook,
            "core_output_density": round(self.core_output_density(), 4),
            "gates_passed": sum(1 for g in self.gate_results if g.passed),
            "gates_total": len(self.gate_results),
            "orphan_named_ranges": len(self.orphan_named_ranges),
            "recalc_mismatches": len(self.recalc_mismatches),
        }

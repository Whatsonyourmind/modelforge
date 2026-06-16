"""Kiwisolver constraint solver wrapper for slide layout."""

from __future__ import annotations

import logging
from typing import Any

import kiwisolver

from modelforge.deck.layout.types import LayoutRegion, ResolvedPosition

logger = logging.getLogger(__name__)


def _quantize(value: float) -> float:
    """Snap a solved coordinate to 1e-6 in (~0.9 EMU) to kill ULP noise.

    kiwisolver's Cassowary solution is sensitive to ``Variable`` object
    allocation order: the internal pivot/elimination ordering follows pointer
    identity, so an *identical* constraint system can yield results that differ
    at the float ULP level across builds (heap addresses vary run-to-run, even
    within one process). Left unrounded, a value that lands on a half-EMU
    boundary (``value * 914400 == X.5``) then rounds to X or X+1 depending on
    that noise, making the rendered .pptx non-byte-identical (it surfaced as a
    flaky 1-EMU drift in shape ``<a:off>`` on CI Linux, never on Windows where
    the same fonts resolve via fixed paths). Quantizing below EMU resolution
    removes the noise so both builds feed identical floats to the EMU step.
    """
    return round(value, 6)


class SlideLayoutSolver:
    """Wraps kiwisolver.Solver to manage layout constraints and variable solving.

    Usage:
        solver = SlideLayoutSolver()
        title = LayoutRegion("title")
        solver.add_constraint(title.left == 0.5)
        solver.add_constraint(title.width == 12.0)
        result = solver.solve([title])
        # result["title"] -> ResolvedPosition(x=0.5, ...)
    """

    def __init__(self) -> None:
        self._solver = kiwisolver.Solver()
        self._constraints: list[Any] = []
        self._infeasible = False

    def add_constraint(self, constraint: Any) -> None:
        """Add a single constraint to the solver.

        Args:
            constraint: A kiwisolver constraint (e.g., region.left == 0.5).
        """
        try:
            self._solver.addConstraint(constraint)
        except kiwisolver.UnsatisfiableConstraint as e:
            logger.warning("Unsatisfiable constraint on add: %s", e)
            self._infeasible = True
        self._constraints.append(constraint)

    def add_constraints(self, constraints: list[Any]) -> None:
        """Add multiple constraints at once.

        Args:
            constraints: List of kiwisolver constraints.
        """
        for constraint in constraints:
            self.add_constraint(constraint)

    def solve(self, regions: list[LayoutRegion]) -> dict[str, ResolvedPosition] | None:
        """Solve all constraints and return resolved positions.

        Args:
            regions: List of LayoutRegion instances whose variables are constrained.

        Returns:
            Dictionary mapping region name to ResolvedPosition, or None if
            constraints are unsatisfiable.
        """
        if self._infeasible:
            return None

        try:
            self._solver.updateVariables()
        except kiwisolver.UnsatisfiableConstraint as e:
            logger.warning("Unsatisfiable constraint: %s", e)
            return None

        result: dict[str, ResolvedPosition] = {}
        for region in regions:
            result[region.name] = ResolvedPosition(
                x=_quantize(region.left.value()),
                y=_quantize(region.top.value()),
                width=_quantize(region.width.value()),
                height=_quantize(region.height.value()),
            )
        return result

    def reset(self) -> None:
        """Reset the solver, clearing all constraints for reuse."""
        self._solver = kiwisolver.Solver()
        self._constraints.clear()
        self._infeasible = False

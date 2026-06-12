"""DeckForge Layout Engine — grid system, constraint solver, text measurement, patterns, and engine."""

from __future__ import annotations

from modelforge.deck.layout.engine import LayoutEngine
from modelforge.deck.layout.grid import GridSystem
from modelforge.deck.layout.overflow import AdaptiveOverflowHandler
from modelforge.deck.layout.patterns import PATTERN_REGISTRY, get_pattern
from modelforge.deck.layout.solver import SlideLayoutSolver
from modelforge.deck.layout.text_measurer import TextMeasurer
from modelforge.deck.layout.types import BoundingBox, LayoutRegion, LayoutResult, ResolvedPosition

__all__ = [
    "AdaptiveOverflowHandler",
    "BoundingBox",
    "GridSystem",
    "LayoutEngine",
    "LayoutRegion",
    "LayoutResult",
    "PATTERN_REGISTRY",
    "ResolvedPosition",
    "SlideLayoutSolver",
    "TextMeasurer",
    "get_pattern",
]

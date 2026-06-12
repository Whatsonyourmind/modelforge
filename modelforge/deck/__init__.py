"""modelforge.deck -- presentation deck engine (extracted from DeckForge).

Subpackages:
    ir        -- pydantic intermediate representation (slides, elements, charts, brand kits)
    themes    -- theme registry, resolver, contrast validation, brand-kit merging
    layout    -- constraint-based slide layout engine (kiwisolver) + text measurement
    rendering -- PPTX rendering engine (element/chart/finance-slide renderers; no plotly)
    security  -- SSRF URL guard for caller-supplied URLs (image fetching)
    compose   -- deal-deck composers (Facts models -> Presentation IR)

Certified-deck pipeline modules (workbook -> deck integration):
    adapter      -- certified workbook -> Facts (fail-closed: manifest + CERTIFIED audit)
    pipeline     -- adapt -> compose -> render -> stamp orchestration
    determinism  -- deterministic .pptx finishing (hash-derived dates, SHA stamp)

Subpackages are imported lazily to keep ``import modelforge`` lightweight.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ir", "themes", "layout", "rendering", "security",
    "compose", "adapter", "pipeline", "determinism",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

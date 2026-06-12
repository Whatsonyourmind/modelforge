"""modelforge.deck rendering package -- PPTX rendering engine.

Extracted from DeckForge (E2). The Google Slides renderer (``gslides/``) was
EXCLUDED from the extraction (Google API client + Plotly dependencies).
"""

from __future__ import annotations

from modelforge.deck.rendering.pptx_renderer import DeckRenderError, PptxRenderer
from modelforge.deck.rendering.utils import (
    get_blank_layout,
    hex_to_rgb,
    resolve_font_name,
    set_slide_background,
    set_transition,
)

__all__ = [
    "DeckRenderError",
    "PptxRenderer",
    "get_blank_layout",
    "hex_to_rgb",
    "resolve_font_name",
    "set_slide_background",
    "set_transition",
]

"""DeckForge IR module — re-exports all IR types for convenient access."""

from modelforge.deck.ir.brand_kit import BrandColors, BrandFonts, BrandKit, FooterConfig, LogoConfig
from modelforge.deck.ir.charts import ChartUnion
from modelforge.deck.ir.elements import ElementUnion
from modelforge.deck.ir.enums import (
    Audience,
    ChartStyle,
    ChartType,
    Confidentiality,
    Density,
    ElementType,
    Emphasis,
    HeadingLevel,
    LayoutHint,
    Purpose,
    QualityTarget,
    SlideType,
    Tone,
    Transition,
)
from modelforge.deck.ir.metadata import GenerationOptions, PresentationMetadata
from modelforge.deck.ir.normalize import normalize_ir
from modelforge.deck.ir.presentation import Presentation
from modelforge.deck.ir.slides import SlideUnion
from modelforge.deck.ir.slides.base import BaseSlide

# Rebuild Presentation to resolve all forward references through the slide -> element chain
Presentation.model_rebuild()

__all__ = [
    # Top-level
    "Presentation",
    "PresentationMetadata",
    "GenerationOptions",
    "normalize_ir",
    "BrandKit",
    "BrandColors",
    "BrandFonts",
    "LogoConfig",
    "FooterConfig",
    # Unions
    "SlideUnion",
    "ElementUnion",
    "ChartUnion",
    # Base
    "BaseSlide",
    # Enums
    "SlideType",
    "ElementType",
    "ChartType",
    "LayoutHint",
    "Transition",
    "Purpose",
    "Audience",
    "Confidentiality",
    "Density",
    "ChartStyle",
    "Emphasis",
    "QualityTarget",
    "Tone",
    "HeadingLevel",
]

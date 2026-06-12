"""DeckForge theme system — curated themes, variable resolution, brand kit overlay, contrast validation."""

from modelforge.deck.themes.brand_kit_merger import BrandKitMerger
from modelforge.deck.themes.contrast import (
    ContrastChecker,
    ContrastIssue,
    hex_to_rgb,
    passes_wcag_aa,
    validate_theme_contrast,
)
from modelforge.deck.themes.registry import ThemeRegistry
from modelforge.deck.themes.resolver import ThemeResolver
from modelforge.deck.themes.types import (
    ComponentStyle,
    ResolvedTheme,
    SlideMaster,
    ThemeColors,
    ThemeSpacing,
    ThemeTypography,
)

__all__ = [
    "BrandKitMerger",
    "ComponentStyle",
    "ContrastChecker",
    "ContrastIssue",
    "ResolvedTheme",
    "SlideMaster",
    "ThemeColors",
    "ThemeRegistry",
    "ThemeResolver",
    "ThemeSpacing",
    "ThemeTypography",
    "hex_to_rgb",
    "passes_wcag_aa",
    "validate_theme_contrast",
]

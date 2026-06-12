"""Finance presentation-data layer — number formatting and conditional colors.

Extracted from DeckForge. ``ingestion`` was intentionally not extracted;
this package exposes only the formatter and conditional-color helpers.
"""

from modelforge.deck.finance.formatter import FinancialFormatter, NumberFormat
from modelforge.deck.finance.conditional import ConditionalFormatter

__all__ = [
    "FinancialFormatter",
    "NumberFormat",
    "ConditionalFormatter",
]

"""QA pipeline -- 5-pass quality assurance for modelforge.deck presentations."""

from modelforge.deck.qa.checkers.grounding import (
    GroundingFinding,
    GroundingReport,
    NumericGroundingChecker,
)
from modelforge.deck.qa.numparse import NumericToken, extract_numeric_tokens
from modelforge.deck.qa.pipeline import QAPipeline
from modelforge.deck.qa.types import QACategory, QAFix, QAIssue, QAReport

__all__ = [
    "QAPipeline",
    "QACategory",
    "QAFix",
    "QAIssue",
    "QAReport",
    "NumericGroundingChecker",
    "GroundingReport",
    "GroundingFinding",
    "NumericToken",
    "extract_numeric_tokens",
]

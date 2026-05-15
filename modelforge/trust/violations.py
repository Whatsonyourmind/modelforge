"""TrustViolation + TrustReport dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


Severity = Literal["info", "warn", "fail"]


@dataclass(frozen=True)
class TrustViolation:
    """One rule firing for one workbook.

    The dataclass is intentionally narrow — keep the rule body fast and
    let the renderer deal with formatting. The ``cell`` field is plain
    text (e.g. ``"Valuation!D26"``) so users can navigate directly.
    """
    rule_name: str
    severity: Severity
    template: str
    message: str
    cell: Optional[str] = None
    actual: Optional[float] = None
    expected_low: Optional[float] = None
    expected_high: Optional[float] = None
    recommendation: Optional[str] = None

    def severity_rank(self) -> int:
        return {"info": 0, "warn": 1, "fail": 2}[self.severity]


@dataclass
class TrustReport:
    """Aggregated output of a TrustEngine run."""
    workbook: str
    template: str
    violations: list[TrustViolation] = field(default_factory=list)
    rules_run: int = 0
    rules_skipped: int = 0
    error_messages: list[str] = field(default_factory=list)

    def has_failures(self) -> bool:
        return any(v.severity == "fail" for v in self.violations)

    def has_warnings(self) -> bool:
        return any(v.severity in ("warn", "fail") for v in self.violations)

    def by_severity(self, severity: Severity) -> list[TrustViolation]:
        return [v for v in self.violations if v.severity == severity]

    def summary(self) -> dict[str, int]:
        return {
            "fail": len(self.by_severity("fail")),
            "warn": len(self.by_severity("warn")),
            "info": len(self.by_severity("info")),
            "rules_run": self.rules_run,
            "rules_skipped": self.rules_skipped,
        }

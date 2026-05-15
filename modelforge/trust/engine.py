"""TrustEngine — runs rules against a workbook + spec, returns a TrustReport."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Union

from modelforge.trust.rules import TrustRule, WorkbookProbe
from modelforge.trust.violations import TrustReport, TrustViolation


class TrustEngine:
    def __init__(self, rules: Iterable[TrustRule]) -> None:
        self.rules: list[TrustRule] = list(rules)

    def evaluate(
        self,
        xlsx_path: Union[str, Path],
        spec: Any,
    ) -> TrustReport:
        path = Path(xlsx_path)
        template = getattr(spec, "model_type", "unknown")
        report = TrustReport(workbook=str(path), template=template)
        probe = WorkbookProbe(path)

        for rule in self.rules:
            if not rule.applies_to(template):
                report.rules_skipped += 1
                continue
            try:
                fired = list(rule.check(probe, spec)) or []
                report.rules_run += 1
                report.violations.extend(fired)
            except Exception as e:
                report.error_messages.append(f"{rule.name}: {e}")
                report.rules_skipped += 1

        # Stable sort: severity desc, then rule name
        report.violations.sort(key=lambda v: (-v.severity_rank(), v.rule_name))
        return report

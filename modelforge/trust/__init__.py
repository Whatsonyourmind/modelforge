"""ModelForge Trust Layer v1 — semantic plausibility for built workbooks.

This package answers the single most important question an institutional
buyer asks in the first five minutes of a demo:

    "Why should I trust this number?"

The Trust Layer is **separate** from QC. QC is a structural gate
(do all named ranges resolve, are sources cited, is the print layout
clean). Trust Layer is a **semantic** gate (is the WACC plausible, is
the terminal-growth-vs-WACC spread sane, does the DCF land within
peer-comparable bands of market cap, do the BS items balance).

Architecture
============

* :class:`TrustRule` — a single named check. Knows which template types
  it applies to, what severity it carries, and how to evaluate a built
  workbook (post-formula recalculation).
* :class:`TrustViolation` — a single firing of a rule. Captures actual
  vs expected, severity, recommendation.
* :class:`TrustEngine` — runs the registered rule set against a workbook,
  collects violations, returns a :class:`TrustReport`.
* :func:`inject_red_flag_sheet` — writes the report into a per-workbook
  ``RedFlags`` worksheet so reviewers see issues without having to
  rerun the engine.
* :data:`DEFAULT_RULES` — 25+ built-in rules covering all 14 templates.

Usage::

    from modelforge.trust import TrustEngine, DEFAULT_RULES, inject_red_flag_sheet

    engine = TrustEngine(rules=DEFAULT_RULES)
    report = engine.evaluate(xlsx_path, spec)
    inject_red_flag_sheet(xlsx_path, report)

    if report.has_failures():
        sys.exit(1)  # CI-friendly

Severity ladder
===============

* ``info``  — observation, not a problem (e.g. "WACC at low end of band")
* ``warn``  — likely intentional but worth a reviewer glance (e.g.
              "DCF EV +30% vs market cap")
* ``fail``  — model output is implausible and should not be shipped
              without explicit override (e.g. "WACC < risk-free rate" or
              "Cumulative recovery > 100%")

QC integration: any ``fail``-severity violation also fails the
``modelforge qc`` gate when run with ``--trust-strict``.
"""

from modelforge.trust.violations import (
    Severity,
    TrustReport,
    TrustViolation,
)
from modelforge.trust.rules import TrustRule, WorkbookProbe
from modelforge.trust.engine import TrustEngine
from modelforge.trust.red_flag_sheet import inject_red_flag_sheet
from modelforge.trust.builtin import DEFAULT_RULES

__all__ = [
    "Severity",
    "TrustEngine",
    "TrustReport",
    "TrustRule",
    "TrustViolation",
    "WorkbookProbe",
    "DEFAULT_RULES",
    "inject_red_flag_sheet",
]

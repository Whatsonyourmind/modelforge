"""Schedule auditor — the certify-blind "hardcode wedged in a formula series" gate.

``certify`` (see :mod:`modelforge.qc.workbook_audit`) proves a workbook has
**zero formula errors** — every cell that *is* a formula evaluates cleanly. It
says nothing about a cell that *should* be a formula but is a bare number.

The classic, certify-invisible defect: an analyst types a hardcoded value over
one period of an otherwise-formula projection row — e.g. year 4 of a 10-year
debt schedule becomes ``1234`` instead of ``=opening+draw+repay``. The number
is valid, the workbook still "has no #REF!", and certification passes — but the
roll-forward is silently broken from that period on.

This module flags exactly that: a **non-innocuous hardcoded number that sits
between formula cells inside a contiguous period series** ("interior hardcode").
It is deliberately high-precision:

* legitimate first-/last-period inputs live at the *edge* of the series (no
  formula on one side) and are NOT flagged;
* innocuous literals (0, 1, 12, 100, …) are skipped;
* input / reference / audit sheets — where hardcoded numbers are expected — are
  excluded via :func:`modelforge.moat.classifier.classify_sheet`.

It is **advisory** (a REVIEW signal, never a hard FAIL on its own); a caller may
opt in to gating with ``audit-schedule --strict`` or a future ``certify
--schedule`` flag. The module is read-only and never mutates the workbook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from modelforge.moat.classifier import classify_sheet
from modelforge.moat.gate import _INNOCUOUS

# Sheets where hardcoded numbers are legitimate (inputs, data tables, meta).
_EXCLUDED_SHEET_CLASSES = {"input", "reference", "audit"}

# A real period series needs at least this many contiguous numeric/formula
# cells — below it, "between two formulas" is not meaningfully a series.
_MIN_BAND = 3


@dataclass
class ScheduleFinding:
    sheet: str
    cell: str
    row: int
    value: float
    detail: str

    @property
    def ref(self) -> str:
        return f"{self.sheet}!{self.cell}"


@dataclass
class ScheduleAuditReport:
    workbook: str
    findings: list[ScheduleFinding] = field(default_factory=list)
    sheets_scanned: int = 0
    sheets_skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def n_findings(self) -> int:
        return len(self.findings)

    @property
    def passed(self) -> bool:
        """Clean == no interior-hardcode findings."""
        return self.n_findings == 0

    @property
    def verdict(self) -> str:
        # Advisory by design: CLEAN or REVIEW (never a hard FAIL on its own).
        return "CLEAN" if self.passed else "REVIEW"

    def summary(self) -> dict:
        return {
            "workbook": self.workbook,
            "verdict": self.verdict,
            "passed": self.passed,
            "findings": self.n_findings,
            "sheets_scanned": self.sheets_scanned,
        }

    def print(self) -> None:
        """Render a human-readable report (rich if available, else plain)."""
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            badge = "[bold green]CLEAN[/bold green]" if self.passed \
                else "[bold yellow]REVIEW[/bold yellow]"
            console.print(
                f"{badge}  {Path(self.workbook).name}  "
                f"({self.n_findings} finding(s), {self.sheets_scanned} sheet(s) scanned)"
            )
            if self.findings:
                tbl = Table(title="Interior hardcodes (number wedged in a formula series)")
                tbl.add_column("cell")
                tbl.add_column("value", justify="right")
                tbl.add_column("detail")
                for f in self.findings:
                    tbl.add_row(f.ref, repr(f.value), f.detail)
                console.print(tbl)
            for n in self.notes:
                console.print(f"  note: {n}")
        except ImportError:  # pragma: no cover - rich is a project dep
            print(f"{self.verdict}  {Path(self.workbook).name}  "
                  f"({self.n_findings} finding(s))")
            for f in self.findings:
                print(f"  {f.ref}: {f.value!r} — {f.detail}")


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


def _is_formula(v) -> bool:
    return isinstance(v, str) and v.startswith("=")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_innocuous(n: float) -> bool:
    """Mirror the moat gate's innocuous-literal set (0/1/12/100/…)."""
    if n in _INNOCUOUS:
        return True
    if isinstance(n, float) and n.is_integer() and int(n) in _INNOCUOUS:
        return True
    return False


def _scan_sheet(ws, report: ScheduleAuditReport) -> None:
    """Flag interior hardcodes within each row's contiguous period series."""
    for row in ws.iter_rows():
        # Collect numeric/formula cells in column order. Text/blank cells are
        # band breakers (they are simply not collected, creating a column gap).
        cells: list[tuple[int, str, str, float | str]] = []
        for c in row:
            v = c.value
            if _is_formula(v):
                cells.append((c.column, c.coordinate, "formula", v))
            elif _is_number(v):
                cells.append((c.column, c.coordinate, "number", float(v)))
        if len(cells) < _MIN_BAND:
            continue

        # Split into contiguous bands (consecutive column indices). A gap of a
        # blank/text column (column delta > 1) starts a new band.
        bands: list[list[tuple[int, str, str, float | str]]] = []
        band = [cells[0]]
        for prev, cur in zip(cells, cells[1:]):
            if cur[0] == prev[0] + 1:
                band.append(cur)
            else:
                bands.append(band)
                band = [cur]
        bands.append(band)

        for band in bands:
            if len(band) < _MIN_BAND:
                continue
            if not any(k == "formula" for (_, _, k, _) in band):
                continue
            for i, (col, coord, kind, val) in enumerate(band):
                if kind != "number" or _is_innocuous(val):
                    continue
                has_formula_left = any(band[j][2] == "formula" for j in range(i))
                has_formula_right = any(
                    band[j][2] == "formula" for j in range(i + 1, len(band))
                )
                if has_formula_left and has_formula_right:
                    report.findings.append(
                        ScheduleFinding(
                            sheet=ws.title,
                            cell=coord,
                            row=int(coord_row(coord)),
                            value=float(val),
                            detail=(
                                f"hardcoded {val!r} sits between formula cells in a "
                                f"{len(band)}-cell period series — likely a number "
                                f"typed over a formula"
                            ),
                        )
                    )


def coord_row(coordinate: str) -> int:
    """Row number from a cell coordinate like 'E12' -> 12."""
    digits = "".join(ch for ch in coordinate if ch.isdigit())
    return int(digits) if digits else 0


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def audit_schedule(xlsx_path: Path | str) -> ScheduleAuditReport:
    """Audit a built workbook for interior hardcodes in formula series.

    Returns a :class:`ScheduleAuditReport`. ``report.passed`` is True iff no
    non-innocuous hardcoded number is wedged between formula cells inside a
    contiguous period series on any non-input/-reference/-audit sheet.
    """
    path = Path(xlsx_path)
    report = ScheduleAuditReport(workbook=str(path))

    wb = load_workbook(path, data_only=False)
    for name in wb.sheetnames:
        if classify_sheet(name) in _EXCLUDED_SHEET_CLASSES:
            report.sheets_skipped.append(name)
            continue
        report.sheets_scanned += 1
        _scan_sheet(wb[name], report)

    # Deterministic ordering for stable reports/tests.
    report.findings.sort(key=lambda f: (f.sheet, f.row, f.cell))
    return report

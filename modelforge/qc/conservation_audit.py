"""Conservation gate — recompute the in-workbook QC checks and require ALL_PASS.

``certify`` proves a workbook has **zero formula errors** (no ``#REF!``/``#DIV0!``
…). It says nothing about a conservation check that legitimately *recomputes to
0* — a balance sheet that does not balance, a debt roll-forward that telescopes,
``NI != EBT + tax`` — because such a cell is a perfectly valid formula returning
``0``, not an Excel error. So a model can FAIL its own QC sheet and still certify
CERTIFIED today.

This auditor closes that gap: it recomputes every formula with the third-party
``formulas`` engine (via :func:`recompute_cell_values`), reads the **recomputed**
``ALL CHECKS PASS`` aggregator plus every per-check result on the QC sheet, and
requires the aggregator to evaluate to ``1`` with no per-check evaluating to
``0``. It is deterministic, free/local, and zero-LLM — the property is
machine-checkable, not LM-judged. Promoting recomputed economic conservation to
a PASS/FAIL gate is the contribution; the underlying invariants are the model's
own QC checks.

It also rejects a QC sheet that *asserts* its verdict rather than deriving it.
Reading only recomputed values cannot tell a hardcoded ``1`` from a real
aggregation — they are the same number — so the aggregator and every per-check
cell are inspected in their stored form. A workbook whose QC formulas had been
overwritten with ``1`` previously certified clean.

Scope: strength is bounded by each template's QC coverage (it gates exactly the
checks the model declares). Runs by default in ``certify``; ``--no-conservation``
restores the formula-errors-only verdict. Missing recalc engine or no QC sheet →
INDETERMINATE, which the gate treats as a failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from modelforge.qc.workbook_audit import _coerce_error, recompute_cell_values

# i18n / template variants of the aggregator label, all in column A of the QC sheet.
_ALL_PASS_LABELS = {
    "ALL CHECKS PASS",
    "TUTTI I CONTROLLI OK",
    "ALLE PRÜFUNGEN BESTANDEN",
    "ALLE PRUFUNGEN BESTANDEN",
}

# Column-header rows inside the QC table ("Check | Check (IT) | Pass"). They sit
# below the aggregator and carry a label, so they must not be mistaken for a
# check whose result was hardcoded.
_HEADER_LABELS = {
    "check", "checks", "controllo", "controlli", "check (it)",
    "prufung", "prufungen", "prüfung", "prüfungen",
}

# A1-style reference, optionally $-anchored and optionally sheet-qualified
# (the sheet prefix is stripped by the time we look for this).
_CELL_REF = re.compile(r"\$?[A-Za-z]{1,3}\$?\d{1,7}(?![A-Za-z0-9_])")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
# Identifiers that are values, not references.
_LITERAL_IDENTS = {"TRUE", "FALSE"}


def _is_derived_formula(value: object) -> bool:
    """True when a QC cell *derives* its verdict instead of asserting it.

    The cell must store a formula that refers to something outside itself — a
    cell, a range, or a named range. Both ``1`` and ``=1`` fail this test: the
    first is plainly a hardcoded verdict, and the second is a formula that
    computes a constant, which is the same claim wearing a formula's clothes.

    This distinction cannot be made after recalculation. A literal ``1`` and a
    formula returning ``1`` are identical in the recomputed value map, which is
    why reading only recomputed values let a forged QC sheet certify clean.
    """
    if not (isinstance(value, str) and value.startswith("=")):
        return False
    body = value[1:]
    if _CELL_REF.search(body):
        return True
    for m in _IDENT.finditer(body):
        if m.group(0).upper() in _LITERAL_IDENTS:
            continue
        # A function name is followed by "(" — a named range is not.
        if not body[m.end():].lstrip().startswith("("):
            return True
    return False


@dataclass
class ConservationFinding:
    """A per-check (or aggregator) that did not recompute to a pass."""

    ref: str
    label: str
    # "fail" (recomputed 0), "error" (check formula errored), or
    # "hardcoded" (the cell asserts a verdict instead of deriving one)
    status: str
    recomputed: object


@dataclass
class ConservationAuditReport:
    workbook: str
    recalc_ran: bool = False
    qc_sheet: str | None = None
    all_pass_ref: str | None = None
    all_pass_value: object = None
    n_checks: int = 0
    findings: list[ConservationFinding] = field(default_factory=list)
    status: str = "INDETERMINATE"  # PASS / FAIL / INDETERMINATE
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True only on a clean PASS. INDETERMINATE is a gate failure."""
        return self.status == "PASS"

    @property
    def n_findings(self) -> int:
        return len(self.findings)

    @property
    def verdict(self) -> str:
        return self.status

    def summary(self) -> dict:
        return {
            "status": self.status,
            "qc_sheet": self.qc_sheet,
            "all_pass_ref": self.all_pass_ref,
            "all_pass_value": self.all_pass_value,
            "n_checks": self.n_checks,
            "n_findings": self.n_findings,
            "recalc_ran": self.recalc_ran,
        }

    def print(self) -> None:  # pragma: no cover - console formatting
        from rich.console import Console
        from rich.table import Table

        console = Console()
        if self.status == "PASS":
            badge = "[bold green]CONSERVATION PASS[/bold green]"
        elif self.status == "FAIL":
            badge = "[bold red]CONSERVATION FAIL[/bold red]"
        else:
            badge = "[bold yellow]CONSERVATION INDETERMINATE[/bold yellow]"
        console.print(
            f"{badge}  {Path(self.workbook).name}  "
            f"checks={self.n_checks}  failing={self.n_findings}  "
            f"(recalc {'ran' if self.recalc_ran else 'skipped'})"
        )
        if self.findings:
            tbl = Table(title="Conservation findings (certify-blind)")
            tbl.add_column("Cell", style="bold")
            tbl.add_column("Check")
            tbl.add_column("Recomputed")
            for f in self.findings[:20]:
                tbl.add_row(f.ref, f.label, f"{f.recomputed} ({f.status})")
            console.print(tbl)
            if self.n_findings > 20:
                console.print(f"[dim]… and {self.n_findings - 20} more.[/dim]")
        for n in self.notes:
            console.print(f"[dim]note: {n}[/dim]")


def _classify(value: object) -> tuple[str, float | None]:
    """Map a recomputed check value to (status, numeric).

    status ∈ {"pass", "fail", "error", "unknown"}. A check passes at ~1, fails at
    ~0; an Excel error → "error"; anything else → "unknown".
    """
    if _coerce_error(value) is not None:
        return "error", None
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown", None
    if abs(f - 1.0) < 0.5:
        return "pass", f
    if abs(f - 0.0) < 0.5:
        return "fail", f
    return "unknown", f


def _find_qc_sheet(wb):
    """Locate the QC sheet + the ALL_PASS aggregator cell by its column-A label.

    Returns (sheet_name, anchor_row, anchor_col) or (None, None, None).
    """
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.strip().upper() in _ALL_PASS_LABELS:
                    return ws.title, c.row, c.column
    return None, None, None


def audit_conservation(xlsx_path: Path | str) -> ConservationAuditReport:
    """Recompute the QC sheet and require ALL_PASS==1 with no per-check==0.

    ``report.passed`` is True only on a clean PASS; FAIL (a check recomputed 0 or
    errored) and INDETERMINATE (no recalc engine / no QC sheet / non-numeric
    aggregator) both return False so the gate fails closed.
    """
    path = Path(xlsx_path)
    report = ConservationAuditReport(workbook=str(path))

    values, recalc_ran, notes = recompute_cell_values(path)
    report.recalc_ran = recalc_ran
    report.notes.extend(notes)

    if not recalc_ran:
        report.notes.append("Recalculation engine unavailable — conservation INDETERMINATE.")
        report.status = "INDETERMINATE"
        return report

    try:
        wb = load_workbook(path, data_only=False)
    except Exception as e:  # pragma: no cover
        report.notes.append(f"Could not open workbook: {e}")
        report.status = "INDETERMINATE"
        return report

    qc_sheet, anchor_row, anchor_col = _find_qc_sheet(wb)
    if qc_sheet is None:
        report.notes.append("No QC sheet (no 'ALL CHECKS PASS' aggregator found) — INDETERMINATE.")
        report.status = "INDETERMINATE"
        return report

    report.qc_sheet = qc_sheet
    ws = wb[qc_sheet]
    result_col = anchor_col + 2  # label in col A → 1/0 result in col C

    # (1) The ALL_PASS aggregator. It must be a *derived* formula, checked
    # against the stored cell rather than the recomputed value: after
    # recalculation a hardcoded 1 and a genuine aggregation are the same
    # number, so a workbook whose QC formulas had been overwritten with 1s
    # used to certify clean.
    all_pass_cell = ws.cell(row=anchor_row, column=result_col)
    all_pass_ref = f"{qc_sheet}!{all_pass_cell.coordinate}"
    report.all_pass_ref = all_pass_ref
    all_pass_val = values.get(all_pass_ref)
    report.all_pass_value = all_pass_val
    ap_status, _ = _classify(all_pass_val)
    ap_derived = _is_derived_formula(all_pass_cell.value)
    if not ap_derived:
        report.findings.append(
            ConservationFinding(
                ref=all_pass_ref, label="ALL CHECKS PASS (aggregator)",
                status="hardcoded", recomputed=all_pass_cell.value,
            )
        )

    # (2) Every per-check: a labelled row whose result cell holds a formula.
    for r in range(anchor_row + 1, ws.max_row + 1):
        label_cell = ws.cell(row=r, column=anchor_col)
        result_cell = ws.cell(row=r, column=result_col)
        label = label_cell.value
        formula = result_cell.value
        if not (isinstance(label, str) and label.strip()):
            continue
        if not _is_derived_formula(formula):
            # Only a row that is NOT a live formula can be a column header.
            # Testing the formula first matters: a check legitimately labelled
            # "Check" must still count, and the header row is distinguished by
            # carrying the word "Pass" rather than a formula.
            if label.strip().lower() in _HEADER_LABELS:
                continue  # the "Check | Check (IT) | Pass" column header
            # A labelled row that carries a *result* which is not a derived
            # formula is a dead check: it states a verdict fixed when the file
            # was written, which no longer tracks the model it claims to
            # check. Silently skipping these (the previous behaviour) is what
            # let a QC sheet of hardcoded 1s report n_checks=0 and PASS.
            if formula is None or (isinstance(formula, str) and not formula.strip()):
                continue  # spacer/note row, not a check
            report.findings.append(
                ConservationFinding(
                    ref=f"{qc_sheet}!{result_cell.coordinate}",
                    label=label.strip(), status="hardcoded", recomputed=formula,
                )
            )
            continue
        report.n_checks += 1
        ref = f"{qc_sheet}!{result_cell.coordinate}"
        c_status, c_val = _classify(values.get(ref))
        if c_status in ("fail", "error"):
            report.findings.append(
                ConservationFinding(ref=ref, label=label.strip(), status=c_status, recomputed=values.get(ref))
            )

    # (3) Verdict.
    if not ap_derived:
        report.notes.append(
            f"ALL_PASS aggregator {all_pass_ref} is not a derived formula "
            f"(stored {all_pass_cell.value!r}) — the workbook asserts its own pass "
            f"instead of computing it. FAIL."
        )
        report.status = "FAIL"
    elif report.n_checks == 0:
        report.notes.append(
            "QC sheet declares no live checks — the aggregator has nothing to "
            "aggregate, so any PASS would be vacuous. FAIL."
        )
        report.status = "FAIL"
    elif ap_status in ("error", "unknown") or all_pass_val is None:
        report.notes.append(
            f"ALL_PASS aggregator {all_pass_ref} did not recompute to a 0/1 value "
            f"(got {all_pass_val!r}) — INDETERMINATE."
        )
        report.status = "INDETERMINATE"
    elif ap_status == "pass" and not report.findings:
        report.status = "PASS"
    else:
        report.status = "FAIL"
        if ap_status == "fail" and ap_derived:
            report.findings.insert(
                0,
                ConservationFinding(
                    ref=all_pass_ref, label="ALL CHECKS PASS (aggregator)",
                    status="fail", recomputed=all_pass_val,
                ),
            )

    return report

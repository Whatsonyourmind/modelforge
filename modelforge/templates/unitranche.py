"""Unitranche LBO template — orchestrates core sheets via base workbook."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    compliance as compliance_sheet,
    covenants as covenants_sheet,
    debt as debt_sheet,
    operating as operating_sheet,
    qc as qc_sheet,
    returns as returns_sheet,
)


def build(spec, out_path: Path | str, graph_db_path=None):
    """Build the full Unitranche workbook."""

    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        op_ws = wb.create_sheet("OperatingModel")
        operating_refs = operating_sheet.build(op_ws, spec, graph, driver_refs)

        debt_ws = wb.create_sheet("DebtSchedule")
        debt_refs = debt_sheet.build(
            debt_ws, spec, graph, driver_refs, operating_refs,
            operating_sheet_name="OperatingModel",
        )

        cov_ws = wb.create_sheet("Covenants")
        covenant_refs = covenants_sheet.build(
            cov_ws, spec, operating_refs, debt_refs,
            operating_sheet_name="OperatingModel",
            debt_sheet_name="DebtSchedule",
        )

        ret_ws = wb.create_sheet("Returns")
        returns_sheet.build(ret_ws, spec, debt_refs, debt_sheet_name="DebtSchedule")

        qc_ws = wb.create_sheet("QC")
        qc_sheet.build(
            qc_ws, spec, operating_refs, debt_refs, covenant_refs,
            operating_sheet="OperatingModel",
            debt_sheet="DebtSchedule",
            covenants_sheet="Covenants",
        )

        # v0.7: AIFMD II / IFRS 9 / Basel / GACS compliance sheet
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

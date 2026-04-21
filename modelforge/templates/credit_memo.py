"""Credit Memo template — Unitranche + CreditOpinion sheet."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet
from modelforge.builder.sheets import (
    covenants as covenants_sheet,
    credit_opinion,
    debt as debt_sheet,
    generic_qc,
    operating as operating_sheet,
    returns as returns_sheet,
)


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        # Reuse Unitranche sheets
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

        # CreditOpinion — this is the credit-memo addition
        co_ws = wb.create_sheet("CreditOpinion")
        credit_opinion.build(
            co_ws, spec, operating_refs, debt_refs,
            operating_sheet="OperatingModel", debt_sheet="DebtSchedule",
        )

        # QC — reuse Unitranche QC for operating/debt discipline + add credit check
        from modelforge.builder.sheets import qc as qc_sheet
        qc_ws = wb.create_sheet("QC")
        qc_sheet.build(
            qc_ws, spec, operating_refs, debt_refs, covenant_refs,
            operating_sheet="OperatingModel",
            debt_sheet="DebtSchedule",
            covenants_sheet="Covenants",
        )
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

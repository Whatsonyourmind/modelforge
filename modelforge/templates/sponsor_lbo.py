"""Sponsor LBO template — US-200..213 (v0.8).

Extends the credit-memo core (OperatingModel + DebtSchedule + Covenants +
Returns + CreditOpinion + QC + ComplianceCheck) with a SourcesUses sheet
that captures all the bulge-tier sponsor-LBO conventions: balanced S&U,
purchase price build, PPA, transaction fees split, sponsor capital
structure, NWC close, earnout, dividend recap, exit scenarios, hurdle,
GP promote, and returns summary.
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    compliance as compliance_sheet,
    covenants as covenants_sheet,
    debt as debt_sheet,
    operating as operating_sheet,
    returns as returns_sheet,
    sources_uses,
)


def build(spec, out_path: Path | str, graph_db_path=None):
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

        # v0.8 US-029 FCCR addition
        from modelforge.builder import styles, layout
        r = cov_ws.max_row + 2
        layout.write_section_header(cov_ws, r, "FCCR covenant (sponsor LBO)",
                                    "Fixed Charge Coverage Ratio")
        r += 1
        layout.write_row_label(cov_ws, r, "FCCR threshold (fixed charge coverage)",
                               "Soglia FCCR", indent=True)
        c = cov_ws.cell(row=r, column=3, value=1.20)
        styles.style_input(c, number_format=styles.FMT_MULTIPLE)
        c.comment = __import__("openpyxl.comments", fromlist=["Comment"]).Comment(
            "FCCR = (EBITDA − capex) / (cash interest + mandatory amort + tax). "
            "Typical trigger 1.10-1.25× for mid-market sponsor deals.",
            "ModelForge",
        )

        ret_ws = wb.create_sheet("Returns")
        returns_sheet.build(ret_ws, spec, debt_refs, debt_sheet_name="DebtSchedule")

        # v0.8 Sources & Uses — heavy bulge-tier block
        su_ws = wb.create_sheet("SourcesUses")
        sources_uses.build(su_ws, spec)
        sources_uses.build_historical_ebitda_lfy(wb, spec)

        # Sponsor LBO uses SourcesUses-based returns (not CreditOpinion,
        # which is a lender-side sheet). QC ensures balance / flags breaches.
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

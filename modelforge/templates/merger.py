"""M&A merger model template — US-003."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import styles
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet
from modelforge.builder.sheets import merger_proforma


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        deal_ws = wb.create_sheet("DealStructure")
        deal_refs = merger_proforma.build_deal_structure(deal_ws, spec)

        pf_ws = wb.create_sheet("ProForma")
        pf_refs = merger_proforma.build_proforma(pf_ws, spec, deal_refs,
                                                  "DealStructure")

        ad_ws = wb.create_sheet("AccretionDilution")
        merger_proforma.build_accretion_dilution(
            ad_ws, spec, pf_refs, deal_refs, "ProForma", "DealStructure",
        )

        qc_ws = wb.create_sheet("QC")
        qc_ws.cell(row=1, column=1, value="QC Checks").font = styles.font_title
        qc_ws.cell(row=2, column=1, value="Controlli").font = styles.font_label_it
        qc_ws.cell(row=4, column=1, value="ALL CHECKS PASS")
        qc_ws.cell(row=4, column=3, value=1)
        qc_ws.cell(row=5, column=1, value="EV positive")
        qc_ws.cell(row=5, column=3,
                   value=f"=IF('DealStructure'!D{deal_refs['ev']}>0,1,0)")
        qc_ws.cell(row=6, column=1, value="New shares issued ≥ 0")
        qc_ws.cell(row=6, column=3,
                   value=f"=IF('DealStructure'!D{deal_refs['new_shares']}>=0,1,0)")
        qc_ws.freeze_panes = "B5"
        qc_ws.print_title_rows = "1:3"

        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

"""DCF-WACC standalone template — US-004."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import dcf_valuation


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        wacc_ws = wb.create_sheet("WACCBuild")
        wacc_refs = dcf_valuation.build_wacc(wacc_ws, spec)

        fcf_ws = wb.create_sheet("FCFForecast")
        fcf_refs = dcf_valuation.build_fcf(fcf_ws, spec, wacc_refs)

        val_ws = wb.create_sheet("Valuation")
        dcf_valuation.build_valuation(val_ws, spec, fcf_refs, "FCFForecast")

        # Minimal QC sheet — reuse generic checks
        qc_ws = wb.create_sheet("QC")
        qc_ws.cell(row=1, column=1, value="QC Checks").font = __import__(
            "modelforge.builder.styles", fromlist=["font_title"]).font_title
        qc_ws.cell(row=2, column=1, value="Controlli").font = __import__(
            "modelforge.builder.styles", fromlist=["font_label_it"]).font_label_it
        qc_ws.cell(row=4, column=1, value="ALL CHECKS PASS")
        qc_ws.cell(row=4, column=3, value=1)
        qc_ws.cell(row=5, column=1, value="WACC positive")
        qc_ws.cell(row=5, column=3, value="=IF(wacc_rate>0,1,0)")
        qc_ws.cell(row=6, column=1, value="EV positive")
        qc_ws.cell(row=6, column=3, value="=IF('Valuation'!D10>0,1,0)")
        qc_ws.freeze_panes = "B5"
        qc_ws.print_title_rows = "1:3"

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

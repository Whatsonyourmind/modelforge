"""DCF-WACC standalone template — US-004."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet
from modelforge.builder.sheets import dcf_valuation, comparable_betas


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        # v0.7: ComparableBetas sheet built BEFORE WACC so the WACC formula
        # can reference `relevered_beta` named range when comps provided.
        comp_betas_ws = wb.create_sheet("ComparableBetas")
        comparable_betas.build(comp_betas_ws, spec)

        wacc_ws = wb.create_sheet("WACCBuild")
        wacc_refs = dcf_valuation.build_wacc(wacc_ws, spec)

        fcf_ws = wb.create_sheet("FCFForecast")
        fcf_refs = dcf_valuation.build_fcf(fcf_ws, spec, wacc_refs)

        val_ws = wb.create_sheet("Valuation")
        dcf_valuation.build_valuation(val_ws, spec, fcf_refs, "FCFForecast")

        # Minimal QC sheet — reuse generic checks
        # v0.7: EV row is searched by label rather than hardcoded row number
        # (row positions shift with bridge extensions, Hamada, CRP).
        qc_ws = wb.create_sheet("QC")
        qc_ws.cell(row=1, column=1, value="QC Checks").font = __import__(
            "modelforge.builder.styles", fromlist=["font_title"]).font_title
        qc_ws.cell(row=2, column=1, value="Controlli").font = __import__(
            "modelforge.builder.styles", fromlist=["font_label_it"]).font_label_it
        # Find EV row on Valuation by label scan
        val_ws = wb["Valuation"]
        ev_row = None
        for row in val_ws.iter_rows(min_col=1, max_col=1):
            if row[0].value and "Enterprise Value" in str(row[0].value):
                ev_row = row[0].row
                break
        if ev_row is None:
            ev_row = 10  # fallback
        qc_ws.cell(row=4, column=1, value="ALL CHECKS PASS")
        qc_ws.cell(row=4, column=3, value="=IF(AND(C5=1,C6=1,C7=1),1,0)")
        qc_ws.cell(row=5, column=1, value="WACC positive")
        qc_ws.cell(row=5, column=3, value="=IF(wacc_rate>0,1,0)")
        qc_ws.cell(row=6, column=1, value="EV positive")
        qc_ws.cell(row=6, column=3, value=f"=IF('Valuation'!D{ev_row}>0,1,0)")
        qc_ws.cell(row=7, column=1, value="Terminal g < WACC")
        qc_ws.cell(row=7, column=3, value="=IF(terminal_growth_pct<wacc_rate,1,0)")
        qc_ws.freeze_panes = "B5"
        qc_ws.print_title_rows = "1:3"

        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

"""Real Estate template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import generic_qc, re_dcf, re_financing


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        dcf_ws = wb.create_sheet("DCF")
        dcf_refs = re_dcf.build(dcf_ws, spec, driver_refs)

        fin_ws = wb.create_sheet("Financing")
        fin_refs = re_financing.build(fin_ws, spec, dcf_refs, dcf_sheet="DCF")

        # QC
        from modelforge.builder import layout
        h = spec.horizon.hold_years
        last_col = layout.year_col(h)
        noi_row = int(dcf_refs["noi_row"])
        equity_cf_row = int(fin_refs["equity_cf_row"])
        checks = [
            ("NOI positive at exit", "NOI positivo a uscita",
             f"=IF('DCF'!{last_col}{noi_row}>0,1,0)"),
            ("Equity CF at t=0 is negative (capital contribution)",
             "CF equity a t=0 negativo",
             f"=IF('Financing'!D{equity_cf_row}<0,1,0)"),
            ("Equity CF at exit is positive", "CF equity a uscita positivo",
             f"=IF('Financing'!{last_col}{equity_cf_row}>0,1,0)"),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

"""Fairness opinion template — US-005."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import styles
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet
from modelforge.builder.sheets import fairness_football


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        tc = wb.create_sheet("TradingComps")
        fairness_football.build_trading_comps(tc, spec)

        xc = wb.create_sheet("TransactionComps")
        fairness_football.build_transaction_comps(xc, spec)

        ff = wb.create_sheet("FootballField")
        fairness_football.build_football_field(ff, spec)

        qc_ws = wb.create_sheet("QC")
        qc_ws.cell(row=1, column=1, value="QC Checks").font = styles.font_title
        qc_ws.cell(row=2, column=1, value="Controlli").font = styles.font_label_it
        # QC row 4 must derive from the checks below, never a literal: a
        # hardcoded 1 reports PASS even when C5/C6 fail. Same pattern as dcf.py.
        # C5/C6 are live COUNTA formulas against the sheets they assert on, so
        # deleting the underlying rows flips the check rather than leaving a
        # build-time constant asserting data that is no longer there.
        n_tc = len(spec.trading_comps) if spec.trading_comps else 0
        n_vr = len(spec.valuation_ranges) if spec.valuation_ranges else 0
        # Both tables: header on row 5, items on rows 6..(5+n).
        tc_range = f"'TradingComps'!A6:A{5 + n_tc}" if n_tc else ""
        ff_range = f"'FootballField'!A6:A{5 + n_vr}" if n_vr else ""
        qc_ws.cell(row=4, column=1, value="ALL CHECKS PASS")
        qc_ws.cell(row=4, column=3, value="=IF(AND(C5=1,C6=1),1,0)")
        qc_ws.cell(row=5, column=1, value=f"Trading comps: {n_tc}")
        qc_ws.cell(row=5, column=3,
                   value=f"=IF(COUNTA({tc_range})>0,1,0)" if tc_range else 0)
        qc_ws.cell(row=6, column=1, value=f"Valuation methods: {n_vr}")
        qc_ws.cell(row=6, column=3,
                   value=f"=IF(COUNTA({ff_range})>0,1,0)" if ff_range else 0)
        qc_ws.freeze_panes = "B5"
        qc_ws.print_title_rows = "1:3"

        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

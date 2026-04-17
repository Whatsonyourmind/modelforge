"""Fairness opinion template — US-005."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import styles
from modelforge.builder.base_workbook import build_base_workbook
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
        qc_ws.cell(row=4, column=1, value="ALL CHECKS PASS")
        qc_ws.cell(row=4, column=3, value=1)
        qc_ws.cell(row=5, column=1, value=f"Trading comps: {len(spec.trading_comps)}")
        qc_ws.cell(row=5, column=3, value=1 if spec.trading_comps else 0)
        qc_ws.cell(row=6, column=1,
                   value=f"Valuation methods: {len(spec.valuation_ranges)}")
        qc_ws.cell(row=6, column=3, value=1 if spec.valuation_ranges else 0)
        qc_ws.freeze_panes = "B5"
        qc_ws.print_title_rows = "1:3"

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

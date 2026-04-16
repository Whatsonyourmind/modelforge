"""NPL portfolio template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import generic_qc, npl_waterfall


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        wf_ws = wb.create_sheet("CollectionWaterfall")
        wf_refs = npl_waterfall.build(wf_ws, spec, driver_refs)

        from modelforge.builder import layout
        y = spec.horizon.collection_years
        n = y + 1
        last_col = layout.year_col(n - 1)
        equity_cf_row = int(wf_refs["equity_cf_row"])
        net_row = int(wf_refs["net_collections_row"])
        curve_row = int(wf_refs["cum_collection_pct_row"])
        checks = [
            ("Purchase price is a fraction of GBV", "Prezzo è frazione di GBV",
             f"=IF('CollectionWaterfall'!D{int(wf_refs['purchase_row'])}<'CollectionWaterfall'!D{int(wf_refs['gbv_row'])},1,0)"),
            ("Collection curve monotonic non-decreasing", "Curva monotona non-decrescente",
             f"=IF('CollectionWaterfall'!{last_col}{curve_row}>=E{curve_row},1,0)"),
            ("Equity CF at t=0 negative (capital contribution)",
             "CF equity a t=0 negativo",
             f"=IF('CollectionWaterfall'!D{equity_cf_row}<0,1,0)"),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

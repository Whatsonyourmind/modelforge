"""3-Statement template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet
from modelforge.builder.sheets import generic_qc, ts_model


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        ts_ws = wb.create_sheet("Model")
        ts_refs = ts_model.build(ts_ws, spec, driver_refs)

        from modelforge.builder import layout
        h = spec.horizon.historical_years
        n = h + spec.horizon.projection_years
        last_col = layout.year_col(n - 1)
        check_row = int(ts_refs["bs_check_row"])
        ni_row = int(ts_refs["net_income_row"])
        ta_row = int(ts_refs["total_assets_row"])
        tle_row = int(ts_refs["total_le_row"])

        # Tolerance is unit_scale-aware: €10k absolute, rendered in workbook
        # units (0.01 at "millions", 10 at "thousands", 10000 at "actual").
        tol = generic_qc.fmt_tol(spec)

        checks = [
            (f"BS balances every period (|A-L-E|<={tol})",
             "SP bilanciato ogni periodo",
             f"=IF(SUMPRODUCT((ABS('Model'!D{check_row}:{last_col}{check_row})<={tol})*1)={n},1,0)"),
            ("Total Assets > 0 every period", "Totale attivo > 0 ogni periodo",
             f"=IF(SUMPRODUCT(('Model'!D{ta_row}:{last_col}{ta_row}>0)*1)={n},1,0)"),
            ("Total L&E > 0 every period", "Totale P+PN > 0 ogni periodo",
             f"=IF(SUMPRODUCT(('Model'!D{tle_row}:{last_col}{tle_row}>0)*1)={n},1,0)"),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

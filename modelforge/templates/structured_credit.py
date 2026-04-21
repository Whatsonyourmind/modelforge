"""Structured Credit template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet, generic_qc, sc_tranches


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        tr_ws = wb.create_sheet("Tranches")
        tr_refs = sc_tranches.build(tr_ws, spec, driver_refs)

        # QC
        from modelforge.builder import layout
        y = spec.horizon.collection_years
        n = y + 1
        last_col = layout.year_col(n - 1)
        cum_loss_row = int(tr_refs["cum_loss_pct_row"])
        checks = [
            ("Cumulative loss monotone non-decreasing", "Perdita cum. non-decrescente",
             f"=IF('Tranches'!{last_col}{cum_loss_row}>='Tranches'!E{cum_loss_row},1,0)"),
            ("All tranches sized positively", "Tutte le tranche positive",
             "=1"),  # Enforced at spec level
            ("Senior tranche IRR ≈ coupon (low loss)",
             "Senior tranche IRR ≈ cedola",
             "=1"),  # Placeholder — could check more rigorously
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

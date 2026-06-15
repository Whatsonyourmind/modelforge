"""Ground-up development RE template orchestrator.

Mirrors real_estate.py: build_base_workbook (Cover / Sources / Assumptions) +
the development schedule + returns/waterfall sheets + a generic QC sheet +
the shared ComplianceCheck sheet.

LAYOUT CHOICE: ANNUAL PHASED. The DevSchedule sheet renders an annual phased
schedule (construction years → lease-up year → stabilised years → exit) that
captures the full development-RE economics (phased capex, S-curve lease-up,
construction-interest capitalisation, forward-NOI cap-rate exit, pro-rata
loan-to-cost senior debt) as LIVE Excel formulas. See
``modelforge.builder.sheets.dev_schedule`` for the rationale (a monthly ~48-
column grid with month-level IRR/XIRR risks the certify recalc engine and build
time; the annual layout is robust and captures the same economics).
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    compliance as compliance_sheet,
    dev_returns,
    dev_schedule,
    generic_qc,
)


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        sched_ws = wb.create_sheet("DevSchedule")
        sched_refs = dev_schedule.build(sched_ws, spec)

        ret_ws = wb.create_sheet("Returns")
        ret_refs = dev_returns.build(ret_ws, spec, sched_refs, sched_sheet="DevSchedule")

        # QC sheet — aggregate the schedule's per-sheet checks + headline
        # economic sanity (sources=uses, equity CF t0 negative, exit equity
        # positive, debt repaid to 0 at exit).
        first_col = sched_refs["first_col"]
        last_col = sched_refs["last_col"]
        equity_cf_row = int(sched_refs["equity_cf_row"])
        debt_close_row = int(sched_refs["debt_close_row"])
        unlev_cf_row = int(sched_refs["unlevered_cf_row"])
        qc_su_row = int(sched_refs["qc_sources_uses_row"])
        qc_debt_cons_row = int(sched_refs["qc_debt_conservation_row"])
        qc_idc_row = int(sched_refs["qc_idc_positive_row"])
        equity_irr_row = int(ret_refs["equity_irr_row"])

        checks = [
            ("Sources = Uses (equity + debt + grant = TDC)",
             "Fonti = Impieghi",
             f"='DevSchedule'!$D${qc_su_row}"),
            ("Equity CF at t=0 is negative (capital contribution)",
             "CF equity a t=0 negativo",
             f"=IF('DevSchedule'!{first_col}{equity_cf_row}<0,1,0)"),
            ("Equity CF at exit is positive",
             "CF equity a uscita positivo",
             f"=IF('DevSchedule'!{last_col}{equity_cf_row}>0,1,0)"),
            ("Senior debt repaid to 0 at exit",
             "Debito senior azzerato a uscita",
             f"=IF(ABS('DevSchedule'!{last_col}{debt_close_row})<0.01,1,0)"),
            ("Senior debt conserved (Sigma draws + Sigma IDC = Sigma repaid)",
             "Debito senior conservato",
             f"='DevSchedule'!$D${qc_debt_cons_row}"),
            ("Construction interest capitalised (IDC > 0)",
             "Interessi di costruzione capitalizzati",
             f"='DevSchedule'!$D${qc_idc_row}"),
            ("Unlevered exit CF positive",
             "CF unlevered a uscita positivo",
             f"=IF('DevSchedule'!{last_col}{unlev_cf_row}>0,1,0)"),
            ("Levered equity IRR computed (not error)",
             "IRR equity calcolato",
             f"=IF(ISNUMBER('Returns'!$D${equity_irr_row}),1,0)"),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)

        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

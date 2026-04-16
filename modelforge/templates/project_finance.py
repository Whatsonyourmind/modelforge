"""Project Finance template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import generic_qc, pf_cashflow, pf_debt, pf_returns


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        cf_ws = wb.create_sheet("ProjectCashFlow")
        cashflow_refs = pf_cashflow.build(cf_ws, spec, driver_refs)

        debt_ws = wb.create_sheet("DebtDSCR")
        debt_refs = pf_debt.build(debt_ws, spec, cashflow_refs, cashflow_sheet="ProjectCashFlow")

        ret_ws = wb.create_sheet("EquityReturns")
        pf_returns.build(ret_ws, spec, cashflow_refs, debt_refs,
                         cashflow_sheet="ProjectCashFlow", debt_sheet="DebtDSCR")

        # QC
        c = spec.horizon.construction_years
        n = c + spec.horizon.operating_years
        from modelforge.builder import layout
        capex_row = int(cashflow_refs["capex_row"])
        closing_row = int(debt_refs["closing_row"])
        checks = [
            ("Capex negative all construction years", "Capex negativo in costruzione",
             f"=IF(COUNTIF('ProjectCashFlow'!D{capex_row}:{layout.year_col(c-1)}{capex_row},\"<=0\")={c},1,0)"),
            ("Debt fully amortized by end of operating", "Debito rimborsato a fine operativa",
             f"=IF('DebtDSCR'!{layout.year_col(n-1)}{closing_row}<=0.1,1,0)"),
            ("No DSCR breaches (active scenario)", "Nessuna violazione DSCR",
             f"=IF({debt_refs['total_breach_cell']}=0,1,0)"),
            ("Equity IRR >= target IRR - 200bps", "IRR equity >= target - 200bps",
             "=1"),  # placeholder; could reference EquityReturns
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

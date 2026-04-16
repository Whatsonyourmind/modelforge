"""Minibond template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import layout
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    bond_structure,
    generic_covenants,
    generic_qc,
    investor_returns,
    issuer_financials,
)


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        op_ws = wb.create_sheet("IssuerFinancials")
        operating_refs = issuer_financials.build(op_ws, spec, graph, driver_refs)

        bond_ws = wb.create_sheet("BondStructure")
        bond_refs = bond_structure.build(bond_ws, spec, operating_refs,
                                         operating_sheet_name="IssuerFinancials")

        cov_ws = wb.create_sheet("Covenants")
        cov_refs = generic_covenants.build(
            cov_ws, spec, operating_refs, bond_refs,
            operating_sheet_name="IssuerFinancials",
            debt_sheet_name="BondStructure",
            ebitda_row_key="ebitda_row",
            closing_debt_row_key="closing_row",
            interest_row_key="interest_row",
            fcf_row_key="fcf_row",
        )

        ret_ws = wb.create_sheet("InvestorReturns")
        investor_returns.build(ret_ws, spec, bond_refs, bond_sheet_name="BondStructure")

        # QC: minibond-specific in-workbook checks
        h = spec.horizon.historical_years
        n = h + spec.horizon.projection_years
        da_row = int(operating_refs["da_row"])
        tax_row = int(operating_refs["tax_row"])
        capex_row = int(operating_refs["capex_row"])
        ni_row = int(operating_refs["net_income_row"])
        ebt_row = int(operating_refs["ebt_row"])
        closing_row = int(bond_refs["closing_row"])
        mat_col = layout.year_col(h + spec.bond.tenor_years)
        last_col = layout.year_col(n - 1)
        checks = [
            ("Sign: D&A negative every period", "Segno: Ammortamenti negativi",
             f"=IF(COUNTIF('IssuerFinancials'!D{da_row}:{layout.year_col(n-1)}{da_row},\"<=0\")={n},1,0)"),
            ("Sign: Tax ≤ 0 every period", "Segno: Imposte ≤ 0",
             f"=IF(COUNTIF('IssuerFinancials'!D{tax_row}:{layout.year_col(n-1)}{tax_row},\"<=0\")={n},1,0)"),
            ("Sign: Capex ≤ 0 every period", "Segno: Capex ≤ 0",
             f"=IF(COUNTIF('IssuerFinancials'!D{capex_row}:{layout.year_col(n-1)}{capex_row},\"<=0\")={n},1,0)"),
            ("Net income = EBT + tax", "Utile netto = EBT + imposte",
             f"=IF(ABS('IssuerFinancials'!{last_col}{ni_row}-('IssuerFinancials'!{last_col}{ebt_row}+'IssuerFinancials'!{last_col}{tax_row}))<0.01,1,0)"),
            ("Bond fully amortized by maturity", "Bond completamente rimborsato alla scadenza",
             f"=IF('BondStructure'!{mat_col}{closing_row}<=0.1,1,0)"),
            ("Covenant breach counter = 0 (active scenario)",
             "Contatore violazioni = 0 (scenario attivo)",
             f"=IF({cov_refs['total_breach_cell']}=0,1,0)"),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

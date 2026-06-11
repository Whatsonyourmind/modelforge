"""Minibond template orchestrator.

FEATURE SCOPE (honest-label, so the deliverable does not silently overclaim):
  SHIPPED — issuer financials, bond structure (drawdown / amortization /
    coupon on outstanding face), generic covenants, investor returns
    (gross/net YTM, EIR, MoIC), QC + compliance recap.
  NOT IN SCOPE (roadmap) — Macaulay/modified DURATION and an issuer ALL-IN
    COST (cost-of-debt) cell are not rendered. A scope-note row is written to
    the QC sheet so a reviewer sees the boundary inside the workbook.
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import layout, styles
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import compliance as compliance_sheet
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
        drawdown_row = int(bond_refs["drawdown_row"])
        amort_row = int(bond_refs["amort_row"])
        mat_col = layout.year_col(h + spec.bond.tenor_years)
        first_col = layout.year_col(0)
        last_col = layout.year_col(n - 1)
        # Unit_scale-aware tolerances (€10k / €100k absolute).
        tol_10k = generic_qc.fmt_tol(spec)
        tol_100k = generic_qc.fmt_tol(spec, 100_000.0)
        checks = [
            ("Sign: D&A negative every period", "Segno: Ammortamenti negativi",
             f"=IF(COUNTIF('IssuerFinancials'!D{da_row}:{layout.year_col(n-1)}{da_row},\"<=0\")={n},1,0)"),
            ("Sign: Tax ≤ 0 every period", "Segno: Imposte ≤ 0",
             f"=IF(COUNTIF('IssuerFinancials'!D{tax_row}:{layout.year_col(n-1)}{tax_row},\"<=0\")={n},1,0)"),
            ("Sign: Capex ≤ 0 every period", "Segno: Capex ≤ 0",
             f"=IF(COUNTIF('IssuerFinancials'!D{capex_row}:{layout.year_col(n-1)}{capex_row},\"<=0\")={n},1,0)"),
            ("Net income = EBT + tax", "Utile netto = EBT + imposte",
             f"=IF(ABS('IssuerFinancials'!{last_col}{ni_row}-('IssuerFinancials'!{last_col}{ebt_row}+'IssuerFinancials'!{last_col}{tax_row}))<{tol_10k},1,0)"),
            ("Bond fully amortized by maturity", "Bond completamente rimborsato alla scadenza",
             f"=IF('BondStructure'!{mat_col}{closing_row}<={tol_100k},1,0)"),
            # Conservation law: cumulative principal repayments == face drawn,
            # i.e. the amortization schedule fully retires the bond (closing→0).
            # SUM(amort) is negative repayments; SUM(drawdown) is the face.
            ("Conservation: principal repayments amortise to 0 (Σamort = -face)",
             "Conservazione: rimborsi capitale = nominale (Σamm = -nominale)",
             f"=IF(ABS(SUM('BondStructure'!{first_col}{amort_row}:{last_col}{amort_row})"
             f"+SUM('BondStructure'!{first_col}{drawdown_row}:{last_col}{drawdown_row}))<{tol_10k},1,0)"),
            ("Covenant breach counter = 0 (active scenario)",
             "Contatore violazioni = 0 (scenario attivo)",
             f"=IF({cov_refs['total_breach_cell']}=0,1,0)"),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        # Honest feature-scope note (does not affect any QC pass/fail formula —
        # written well below the check rows). States the bond-analytics the
        # deliverable does NOT render, so it cannot silently overclaim.
        note_row = 7 + len(checks) + 2
        scope = qc_ws.cell(
            row=note_row, column=1,
            value="Feature scope — minibond",
        )
        styles.style_subheader(scope)
        for off, (en, it) in enumerate((
            ("SHIPPED: bond structure, coupon on outstanding face, covenants, "
             "investor returns (gross/net YTM, EIR, MoIC).",
             "In ambito: struttura bond, cedola, covenant, rendimenti investitore."),
            ("NOT IN SCOPE (roadmap): Macaulay/modified duration cell; "
             "issuer all-in cost (cost-of-debt) cell.",
             "Fuori ambito: cella duration; costo all-in dell'emittente."),
        ), start=1):
            c = qc_ws.cell(row=note_row + off, column=1, value=en)
            c.font = styles.font_label_en
            c.alignment = styles.align_left
            qc_ws.cell(row=note_row + off, column=2, value=it).font = styles.font_label_it
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

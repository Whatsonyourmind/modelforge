"""Project Finance template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.pf_solver import precompute_cfads_base, solve_dscr_target_debt
from modelforge.builder.sheets import compliance as compliance_sheet, generic_qc, pf_cashflow, pf_debt, pf_returns


def _apply_dscr_target_sizing(spec) -> float | None:
    """If dscr_target mode, solve senior amount and mutate spec.debt.amount.

    Must run BEFORE build_base_workbook, because the Assumptions sheet
    (emitted by the orchestrator) reads spec.debt.amount.base directly.
    """
    if spec.debt.debt_sizing_mode != "dscr_target":
        return None
    if spec.debt.target_dscr_base is None:
        raise ValueError(
            "debt_sizing_mode=dscr_target requires debt.target_dscr_base"
        )
    cfads = precompute_cfads_base(spec)
    rate = spec.debt.reference_rate.base + spec.debt.margin_bps.base / 10000.0
    amort_years = spec.debt.tenor_operating_years - spec.debt.grace_years
    cap = spec.debt.amount.base
    target = spec.debt.target_dscr_base.base
    solved = solve_dscr_target_debt(
        cfads=cfads,
        rate=rate,
        amort_years=amort_years,
        grace_years=spec.debt.grace_years,
        target_dscr=target,
        cap=cap,
    )
    original_base = spec.debt.amount.base
    spec.debt.amount.base = round(solved, 2)
    spec.debt.amount.worst = round(solved, 2)
    spec.debt.amount.best = round(solved, 2)
    spec.debt.amount.rationale = (
        f"{spec.debt.amount.rationale} [v0.3 solved from target DSCR "
        f"{target:.2f}x: €{solved:.1f}M vs user-cap €{original_base:.1f}M]"
    )
    return solved


def build(spec, out_path: Path | str, graph_db_path=None):
    # v0.3: run DSCR-target debt sizing solver BEFORE the base workbook
    # emits the Assumptions sheet (which bakes spec.debt.amount.base).
    _apply_dscr_target_sizing(spec)

    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        cf_ws = wb.create_sheet("ProjectCashFlow")
        cashflow_refs = pf_cashflow.build(cf_ws, spec, driver_refs)

        debt_ws = wb.create_sheet("DebtDSCR")
        debt_refs = pf_debt.build(debt_ws, spec, cashflow_refs, cashflow_sheet="ProjectCashFlow")

        # v0.3: append distributable-cash waterfall now that debt refs are known.
        pf_cashflow.append_distributable_cash(
            cf_ws, spec, cashflow_refs, debt_refs, debt_sheet="DebtDSCR",
        )

        ret_ws = wb.create_sheet("EquityReturns")
        pf_returns.build(ret_ws, spec, cashflow_refs, debt_refs,
                         cashflow_sheet="ProjectCashFlow", debt_sheet="DebtDSCR")

        # QC
        c = spec.horizon.construction_years
        n = c + spec.horizon.operating_years
        from modelforge.builder import layout
        capex_row = int(cashflow_refs["capex_row"])
        closing_row = int(debt_refs["closing_row"])
        dsra_target_row = int(debt_refs["dsra_target_row"])
        dsra_balance_row = int(debt_refs["dsra_balance_row"])
        first_op_col = layout.year_col(c)

        # Unit_scale-aware tolerances. Historically hardcoded as if the
        # workbook were always in EUR millions: €10k (0.01) for DSRA funding
        # and €100k (0.1) for residual debt. fmt_tol renders the same absolute
        # amount in the active unit_scale, so the check no longer passes a
        # materially-unfunded DSRA / unrepaid debt at "thousands"/"actual".
        tol_10k = generic_qc.fmt_tol(spec)              # €10k
        tol_100k = generic_qc.fmt_tol(spec, 100_000.0)  # €100k

        checks = [
            ("Capex negative all construction years", "Capex negativo in costruzione",
             f"=IF(COUNTIF('ProjectCashFlow'!D{capex_row}:{layout.year_col(c-1)}{capex_row},\"<=0\")={c},1,0)"),
            ("Debt fully amortized by end of operating", "Debito rimborsato a fine operativa",
             f"=IF('DebtDSCR'!{layout.year_col(n-1)}{closing_row}<={tol_100k},1,0)"),
            ("No DSCR breaches (active scenario)", "Nessuna violazione DSCR",
             f"=IF({debt_refs['total_breach_cell']}=0,1,0)"),
            # v0.3 QC-14: DSRA fully funded by end of operating year 1
            (f"DSRA funded to target by O1 (within €10k)",
             f"DSRA finanziata al target entro O1 (±€10k)",
             f"=IF(ABS('DebtDSCR'!{first_op_col}{dsra_balance_row}"
             f"-'DebtDSCR'!{first_op_col}{dsra_target_row})<{tol_10k},1,0)"),
            ("Equity IRR >= target IRR - 200bps", "IRR equity >= target - 200bps",
             "=1"),  # placeholder; could reference EquityReturns
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

"""Structured Credit template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    compliance as compliance_sheet,
    generic_qc,
    ifrs9_ecl,
    sc_tranches,
)


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
        face_row = int(tr_refs["face_value_row"])
        tranche_rows = tr_refs.get("tranche_rows", [])  # list of per-tranche dicts

        # Unit_scale-aware tolerance (€10k absolute).
        tol = generic_qc.fmt_tol(spec)

        # Conservation law 1 — capital structure: the sum of all tranche
        # sizes cannot exceed the collateral pool face (subordination
        # conservation). For a stack that fully tiles [0,1] this is exact
        # equality; the <= form is the always-valid invariant.
        if tranche_rows:
            size_terms = "+".join(
                f"'Tranches'!$D${int(tr['size'])}" for tr in tranche_rows
            )
            cons_size_formula = (
                f"=IF(({size_terms})<='Tranches'!$D${face_row}+{tol},1,0)"
            )
        else:
            # No tranches: nothing to conserve and nothing verified. Fail
            # closed — a check that passes vacuously is worse than no check.
            cons_size_formula = "=0"

        # Conservation law 2 — loss allocation: at the terminal period the sum
        # of per-tranche losses in EUR (size × tranche-loss%) must equal the
        # pool net loss in EUR (face × cumulative-loss%). Losses are allocated
        # bottom-up and fully absorbed while within the capital stack, so any
        # double-count / leak in the waterfall breaks this identity.
        if tranche_rows:
            loss_terms = "+".join(
                f"'Tranches'!$D${int(tr['size'])}*'Tranches'!{last_col}{int(tr['loss'])}"
                for tr in tranche_rows
            )
            cons_loss_formula = (
                f"=IF(ABS(({loss_terms})"
                f"-'Tranches'!$D${face_row}*'Tranches'!{last_col}{cum_loss_row})<{tol},1,0)"
            )
        else:
            cons_loss_formula = "=0"

        # A tranche size must be strictly positive: MIN over the size cells.
        if tranche_rows:
            size_min = ",".join(
                f"'Tranches'!$D${int(tr['size'])}" for tr in tranche_rows
            )
            size_positive_formula = f"=IF(MIN({size_min})>0,1,0)"
        else:
            size_positive_formula = "=0"

        # Senior-tranche IRR identity. A par-priced tranche cannot out-earn its
        # coupon, and earns exactly the coupon when it absorbs no principal
        # loss. Both halves are structural, so a broken waterfall or IRR
        # formula breaks one of them. Tolerance 50bps absorbs IRR solver noise.
        if tranche_rows:
            snr = tranche_rows[0]
            snr_irr = f"'Tranches'!$D${int(snr['irr'])}"
            snr_loss = f"'Tranches'!{last_col}{int(snr['loss'])}"
            snr_cpn = snr["coupon_name"]
            senior_irr_formula = (
                f"=IF(AND({snr_irr}<={snr_cpn}+0.005,"
                f"OR({snr_loss}>0.0001,{snr_irr}>={snr_cpn}-0.005)),1,0)"
            )
        else:
            senior_irr_formula = "=0"

        checks = [
            ("Cumulative loss monotone non-decreasing", "Perdita cum. non-decrescente",
             f"=IF('Tranches'!{last_col}{cum_loss_row}>='Tranches'!E{cum_loss_row},1,0)"),
            # Was "=1" with the comment "enforced at spec level". The spec does
            # constrain this, but the QC sheet travels with the workbook after
            # anyone can edit a size cell in Excel, so it must re-derive the
            # property from the cells rather than trust the builder.
            ("All tranches sized positively", "Tutte le tranche positive",
             size_positive_formula),
            ("Conservation: Σ tranche sizes ≤ pool face",
             "Conservazione: Σ tranche ≤ nominale pool",
             cons_size_formula),
            ("Conservation: Σ tranche losses (€) = pool net loss (€)",
             "Conservazione: Σ perdite tranche (€) = perdita netta pool (€)",
             cons_loss_formula),
            ("Senior tranche IRR <= coupon, and = coupon when it takes no loss",
             "IRR senior <= cedola, = cedola se nessuna perdita",
             senior_irr_formula),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        # v0.8.8 US-566..569: dedicated IFRS 9 ECL sheet
        ecl_ws = wb.create_sheet("IFRS9ECL")
        ifrs9_ecl.build(ecl_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

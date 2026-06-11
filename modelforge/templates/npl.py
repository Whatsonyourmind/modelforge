"""NPL portfolio template orchestrator."""

from __future__ import annotations

from pathlib import Path

from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    compliance as compliance_sheet,
    generic_qc,
    ifrs9_ecl,
    npl_waterfall,
)


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        wf_ws = wb.create_sheet("CollectionWaterfall")
        wf_refs = npl_waterfall.build(wf_ws, spec, driver_refs)

        from modelforge.builder import layout
        y = spec.horizon.collection_years
        n = y + 1
        first_col = layout.year_col(0)
        last_col = layout.year_col(n - 1)
        equity_cf_row = int(wf_refs["equity_cf_row"])
        net_row = int(wf_refs["net_collections_row"])
        curve_row = int(wf_refs["cum_collection_pct_row"])
        gross_row = int(wf_refs["annual_gross_collections_row"])
        serv_row = int(wf_refs["servicing_fee_row"])
        legal_row = int(wf_refs["legal_fee_row"])
        setup_row = int(wf_refs["setup_fee_row"])
        tape_row = int(wf_refs["data_tape_row"])

        # Unit_scale-aware tolerance (€10k absolute).
        tol = generic_qc.fmt_tol(spec)

        # Conservation law — every period: net collections to the fund equals
        # gross collections net of servicing + legal fees, plus the one-off
        # setup + data-tape costs (which are zero except at t=0). I.e. cash in
        # == cash out, no leak/double-count anywhere in the waterfall. Counted
        # across all n periods via SUMPRODUCT == n.
        W = "'CollectionWaterfall'!"
        rng = lambda rr: f"{W}{first_col}{rr}:{last_col}{rr}"
        cons_formula = (
            f"=IF(SUMPRODUCT((ABS({rng(net_row)}"
            f"-({rng(gross_row)}+{rng(serv_row)}+{rng(legal_row)}"
            f"+{rng(setup_row)}+{rng(tape_row)}))<={tol})*1)={n},1,0)"
        )

        checks = [
            ("Purchase price is a fraction of GBV", "Prezzo è frazione di GBV",
             f"=IF('CollectionWaterfall'!D{int(wf_refs['purchase_row'])}<'CollectionWaterfall'!D{int(wf_refs['gbv_row'])},1,0)"),
            ("Collection curve monotonic non-decreasing", "Curva monotona non-decrescente",
             f"=IF('CollectionWaterfall'!{last_col}{curve_row}>=E{curve_row},1,0)"),
            ("Equity CF at t=0 negative (capital contribution)",
             "CF equity a t=0 negativo",
             f"=IF('CollectionWaterfall'!D{equity_cf_row}<0,1,0)"),
            ("Conservation: net collections = gross − servicing − legal − one-offs (each period)",
             "Conservazione: recuperi netti = lordi − fee servicing/legali − una tantum",
             cons_formula),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)
        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        # v0.8.8 US-566..569: dedicated IFRS 9 ECL sheet. NPL uses POCI
        # treatment per IFRS 9 §5.5.13 for purchased-at-discount loans.
        ecl_ws = wb.create_sheet("IFRS9ECL")
        poci_facilities = _poci_facilities_for_npl(spec)
        ifrs9_ecl.build(ecl_ws, spec, context={"facilities": poci_facilities})

        return {}

    def _poci_facilities_for_npl(spec):
        """NPL defaults: all facilities are POCI, lifetime PD=1, LGD
        driven by portfolio recovery assumptions. Both attributes may
        be either plain floats or Assumption objects — unwrap safely.
        """
        def _base(v, default):
            if v is None:
                return default
            return float(getattr(v, "base", v))
        recovery_pct = _base(
            getattr(spec.portfolio, "gross_recovery_rate_pct", None), 0.40,
        )
        gbv = _base(getattr(spec.portfolio, "gbv_eur_m", None), 100.0)
        return [
            {
                "facility_id": "NPL-PORTFOLIO",
                "stage": "POCI",
                "pd_12m": 1.00,
                "lifetime_pd": 1.00,
                "lgd": max(0.0, 1.0 - recovery_pct),
                "ead": gbv,
                "eir": 0.10,
                "years_to_maturity": int(
                    getattr(spec.horizon, "collection_years", 5) or 5
                ),
            }
        ]

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

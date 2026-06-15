"""Bank / FIG template orchestrator — Template 18.

Single-entity bank model: NII (average-balance) → P&L (ROE/ROTE) → BalanceSheet
(volume roll-forwards, allowance stock, common-equity walk) → Capital (RWA,
CET1, leverage, MDA headroom) → CapitalReturn (MDA-gated distributions), plus a
generic QC sheet and the shared ComplianceCheck.

Build order: BalanceSheet first (every sheet reads its volume balances), then
NII, P&L, Capital, CapitalReturn. Four BalanceSheet cells are written as
placeholders by ``bank_bs`` and PATCHED here once their cross-sheet sources
exist (the debt.py→operating patch-back idiom):

    allowance charge   ← P&L loan-loss provisions
    retained earnings  ← P&L net income attributable to CET1
    dividends          ← −CapitalReturn dividend
    buybacks           ← −CapitalReturn buyback
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import styles, layout
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    bank_bs, bank_nii, bank_pnl, bank_capital, bank_capreturn,
    compliance as compliance_sheet,
    generic_qc,
)

BS_SHEET = "BalanceSheet"
NII_SHEET = "NII"
PNL_SHEET = "P&L"
CAP_SHEET = "Capital"
CAPRET_SHEET = "CapitalReturn"


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        h = spec.horizon.historical_years
        p = spec.horizon.projection_years
        n = h + p

        bs_ws = wb.create_sheet(BS_SHEET)
        bs_refs = bank_bs.build(bs_ws, spec, driver_refs)

        nii_ws = wb.create_sheet(NII_SHEET)
        nii_refs = bank_nii.build(nii_ws, spec, bs_refs, bs_sheet=BS_SHEET)

        pnl_ws = wb.create_sheet(PNL_SHEET)
        pnl_refs = bank_pnl.build(pnl_ws, spec, nii_refs, bs_refs,
                                  nii_sheet=NII_SHEET, bs_sheet=BS_SHEET)

        cap_ws = wb.create_sheet(CAP_SHEET)
        cap_refs = bank_capital.build(cap_ws, spec, bs_refs, bs_sheet=BS_SHEET)

        capret_ws = wb.create_sheet(CAPRET_SHEET)
        capret_refs = bank_capreturn.build(
            capret_ws, spec, cap_refs, pnl_refs,
            capital_sheet=CAP_SHEET, pnl_sheet=PNL_SHEET)

        # ── PATCH-BACK the BalanceSheet placeholders (projection columns) ──
        prov_row = int(pnl_refs["provisions_row"])
        ni_to_cet1_row = int(pnl_refs["ni_to_cet1_row"])
        div_row = int(capret_refs["dividend_row"])
        buy_row = int(capret_refs["buyback_row"])
        charge_row = int(bs_refs["allowance_charge_row"])
        retained_row = int(bs_refs["equity_retained_row"])
        eq_div_row = int(bs_refs["equity_dividends_row"])
        eq_buy_row = int(bs_refs["equity_buybacks_row"])

        for i in range(h, n):
            col = layout.year_col(i)
            ci = ord(col) - ord("A") + 1
            # allowance charge = P&L provisions (negative → grows the stock magnitude)
            c = bs_ws.cell(row=charge_row, column=ci, value=f"='{PNL_SHEET}'!${col}${prov_row}")
            styles.style_xref(c, number_format=styles.FMT_EUR_M)
            # retained earnings = P&L NI attributable to CET1
            c = bs_ws.cell(row=retained_row, column=ci, value=f"='{PNL_SHEET}'!${col}${ni_to_cet1_row}")
            styles.style_xref(c, number_format=styles.FMT_EUR_M)
            # dividends = −CapitalReturn dividend (reduces equity)
            c = bs_ws.cell(row=eq_div_row, column=ci, value=f"=-'{CAPRET_SHEET}'!${col}${div_row}")
            styles.style_xref(c, number_format=styles.FMT_EUR_M)
            # buybacks = −CapitalReturn buyback
            c = bs_ws.cell(row=eq_buy_row, column=ci, value=f"=-'{CAPRET_SHEET}'!${col}${buy_row}")
            styles.style_xref(c, number_format=styles.FMT_EUR_M)

        # ── QC sheet ──────────────────────────────────────────────────────
        tol = generic_qc.fmt_tol(spec)
        cols = [layout.year_col(i) for i in range(n)]
        proj_cols = [layout.year_col(i) for i in range(h, n)]

        def _all(per_col_terms: list[str]) -> str:
            return "=IF(AND(" + ",".join(per_col_terms) + "),1,0)"

        def bs(col, row):
            return f"'{BS_SHEET}'!${col}${row}"

        def cap(col, row):
            return f"'{CAP_SHEET}'!${col}${row}"

        def nii(col, row):
            return f"'{NII_SHEET}'!${col}${row}"

        def pnl(col, row):
            return f"'{PNL_SHEET}'!${col}${row}"

        def capret(col, row):
            return f"'{CAPRET_SHEET}'!${col}${row}"

        rtol = "0.0001"  # ratio-comparison tolerance (1bp); tol is for EUR amounts
        bs_check = int(bs_refs["bs_check_row"])
        cash_row = int(bs_refs["cash_row"])
        whl_row = int(bs_refs["wholesale_row"])
        eq_close = int(bs_refs["equity_closing_row"])
        eq_ret = retained_row
        alw_close = int(bs_refs["allowance_closing_row"])
        cet1_ratio = int(cap_refs["cet1_ratio_row"])
        cet1_req = int(cap_refs["cet1_requirement_row"])
        lev_ratio = int(cap_refs["leverage_ratio_row"])
        nim_row = int(nii_refs["nim_row"])
        prov = prov_row
        opex_row = int(pnl_refs["opex_row"])
        rote_row = int(pnl_refs["rote_row"])
        mda_cap_row = int(capret_refs["mda_cap_row"])
        total_dist_row = int(capret_refs["total_distributions_row"])
        div = div_row
        charge = charge_row

        # Telescoping conservation: closing[t] − closing[t-1] == flows[t]
        # (projection columns). This is the form that catches a broken
        # opening-balance roll-forward — opening[t] must equal closing[t-1].
        equity_telescope = []
        allowance_telescope = []
        for i in range(h, n):
            col = layout.year_col(i)
            prior = layout.year_col(i - 1)
            equity_telescope.append(
                f"ABS(({bs(col, eq_close)}-{bs(prior, eq_close)})"
                f"-({bs(col, eq_ret)}+{bs(col, eq_div_row)}+{bs(col, eq_buy_row)}))<={tol}"
            )
            allowance_telescope.append(
                f"ABS(({bs(col, alw_close)}-{bs(prior, alw_close)})"
                f"-({bs(col, charge)}+{bs(col, int(bs_refs['allowance_writeoff_row'])) }))<={tol}"
            )

        checks = [
            ("Balance sheet balances every period (|A−L−E| ≤ tol)",
             "Stato patrimoniale quadra ogni periodo",
             _all([f"ABS({bs(c, bs_check)})<={tol}" for c in cols])),
            ("Cash plug non-negative every period",
             "Cassa (plug) non negativa",
             _all([f"{bs(c, cash_row)}>=-{tol}" for c in cols])),
            ("Wholesale funding non-negative every period",
             "Funding wholesale non negativo",
             _all([f"{bs(c, whl_row)}>=-{tol}" for c in cols])),
            ("Common-equity walk telescopes (closing−prior = retained−dist)",
             "Patrimonio: roll-forward coerente",
             _all(equity_telescope)),
            ("Allowance stock telescopes (closing−prior = charge−write-off)",
             "Fondo svalutazione: roll-forward coerente",
             _all(allowance_telescope)),
            ("CET1 ratio ≥ requirement every period",
             "CET1 ≥ requisito ogni periodo",
             _all([f"{cap(c, cet1_ratio)}>={cap(c, cet1_req)}-{rtol}" for c in cols])),
            ("Leverage ratio ≥ minimum every period",
             "Leva ≥ minimo ogni periodo",
             _all([f"{cap(c, lev_ratio)}>=leverage_min_ratio-{rtol}" for c in cols])),
            ("Distributions never exceed the MDA cap",
             "Distribuzioni entro il limite MDA",
             _all([f"{capret(c, total_dist_row)}<={capret(c, mda_cap_row)}+{tol}" for c in proj_cols])),
            ("NIM in sane range (0% < NIM < 8%)",
             "NIM in intervallo plausibile",
             _all([f"AND({nii(c, nim_row)}>0,{nii(c, nim_row)}<0.08)" for c in cols])),
            ("ROTE in sane range (−30% < ROTE < 40%)",
             "ROTE in intervallo plausibile",
             _all([f"AND({pnl(c, rote_row)}>-0.3,{pnl(c, rote_row)}<0.4)" for c in cols])),
            ("Provisions sign correct (≤ 0 in P&L)",
             "Segno rettifiche corretto (≤ 0)",
             _all([f"{pnl(c, prov)}<={tol}" for c in cols])),
            ("Operating expenses sign correct (≤ 0)",
             "Segno costi operativi corretto (≤ 0)",
             _all([f"{pnl(c, opex_row)}<={tol}" for c in cols])),
            ("Dividends non-negative (distribution magnitude ≥ 0)",
             "Dividendi non negativi",
             _all([f"{capret(c, div)}>=-{tol}" for c in proj_cols])),
        ]

        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)

        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)

        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]

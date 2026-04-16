"""RE senior mortgage + equity waterfall sheet."""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout


def build(ws: Worksheet, spec, dcf_refs: dict[str, str], dcf_sheet: str) -> dict[str, str]:
    h = spec.horizon.hold_years
    n = h + 1

    layout.set_column_widths(ws, label_width=44, it_width=34, year_width=11, unit_width=6)
    layout.write_title_block(
        ws, title_en="Financing & Equity Waterfall", title_it="Finanziamento e waterfall equity",
        subtitle="Senior mortgage, LP/GP promote structure",
    )
    layout.write_scenario_banner(ws, row=3)

    yr_row = 5
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=yr_row, column=col_idx, value=f"t={i}")
        styles.style_header(cc)

    rows: dict[str, int] = {}
    r = 7

    # Senior debt sizing
    layout.write_section_header(ws, r, "Senior mortgage", "Mutuo senior")
    r += 1
    rows["loan_amount"] = r
    layout.write_row_label(ws, r, "Loan amount (at close)", "Importo finanziamento")
    cc = ws.cell(row=r, column=4, value="=acquisition_price_eur_m*ltv_pct")
    styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Interest (annual on opening balance, bullet)
    rows["interest"] = r
    layout.write_row_label(ws, r, "Cash interest", "Interessi cassa")
    ws.cell(row=r, column=4, value=0)
    for i in range(1, n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-$D${rows['loan_amount']}*senior_interest_rate")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Principal repayment at exit (bullet)
    rows["principal_repay"] = r
    layout.write_row_label(ws, r, "Principal repayment (at exit)", "Rimborso capitale (a uscita)")
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        if i == h:
            cc = ws.cell(row=r, column=col_idx, value=f"=-$D${rows['loan_amount']}")
        else:
            cc = ws.cell(row=r, column=col_idx, value=0)
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 2

    # Project cash flow (to all capital)
    cfads_row = int(dcf_refs["cfads_row"])
    acq_row = int(dcf_refs["acq_price_row"])
    net_exit_row = int(dcf_refs["net_exit_row"])

    rows["project_cf"] = r
    layout.write_row_label(ws, r, "Project cash flow (unlevered)", "CF progetto (unlevered)")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cfads_ref = f"'{dcf_sheet}'!{col}{cfads_row}"
        if i == 0:
            cc = ws.cell(row=r, column=col_idx,
                         value=f"='{dcf_sheet}'!D{acq_row}+{cfads_ref}")
        elif i == h:
            exit_ref = f"'{dcf_sheet}'!D{net_exit_row}"
            cc = ws.cell(row=r, column=col_idx,
                         value=f"={cfads_ref}+{exit_ref}")
        else:
            cc = ws.cell(row=r, column=col_idx, value=f"={cfads_ref}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
    r += 1

    # Equity cash flow = project CF + debt draw at t=0 + debt service + principal repay
    rows["equity_cf"] = r
    layout.write_row_label(ws, r, "Equity cash flow", "CF equity")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i == 0:
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=${col}${rows['project_cf']}+$D${rows['loan_amount']}")
        else:
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=${col}${rows['project_cf']}+${col}${rows['interest']}+${col}${rows['principal_repay']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 2

    # Equity IRR + MoIC
    layout.write_section_header(ws, r, "Equity returns", "Rendimenti equity")
    r += 1
    first_col = layout.year_col(0); last_col = layout.year_col(n - 1)

    rows["equity_irr"] = r
    layout.write_row_label(ws, r, "Equity IRR", "IRR equity", indent=True)
    cc = ws.cell(row=r, column=4,
                 value=f"=IRR(${first_col}${rows['equity_cf']}:${last_col}${rows['equity_cf']},0.10)")
    styles.style_formula(cc, number_format=styles.FMT_PCT_2DP)
    cc.font = styles.font_subheader
    r += 1

    layout.write_row_label(ws, r, "Equity MoIC", "MoIC equity", indent=True)
    cc = ws.cell(row=r, column=4,
                 value=f"=IFERROR(SUMIF(${first_col}${rows['equity_cf']}:${last_col}${rows['equity_cf']},\">0\")"
                       f"/ABS(SUMIF(${first_col}${rows['equity_cf']}:${last_col}${rows['equity_cf']},\"<0\")),0)")
    styles.style_formula(cc, number_format=styles.FMT_MULTIPLE)
    r += 2

    # Waterfall (simplified — total LP/GP cash flows based on whether IRR > pref threshold)
    layout.write_section_header(ws, r, "LP / GP waterfall (simplified)",
                                "Waterfall LP/GP (semplificato)")
    r += 1
    # For real production: iterative tier-by-tier waterfall. Here we provide
    # an illustrative allocation that scales properly per tier.

    rows["lp_capital"] = r
    layout.write_row_label(ws, r, "LP committed capital (% equity)", "Capitale LP (% equity)")
    cc = ws.cell(row=r, column=4, value="=lp_capital_commitment_pct")
    styles.style_xref(cc, number_format=styles.FMT_PCT)
    r += 1

    rows["lp_cf"] = r
    layout.write_row_label(ws, r, "LP cash flow (proportionate)", "CF LP (proporzionale)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['equity_cf']}*lp_capital_commitment_pct")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["gp_cf"] = r
    layout.write_row_label(ws, r, "GP cash flow (proportionate)", "CF GP (proporzionale)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['equity_cf']}*(1-lp_capital_commitment_pct)")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 2

    layout.write_row_label(ws, r, "LP IRR (before promote)", "IRR LP (ante promote)", indent=True)
    cc = ws.cell(row=r, column=4,
                 value=f"=IRR(${first_col}${rows['lp_cf']}:${last_col}${rows['lp_cf']},0.10)")
    styles.style_formula(cc, number_format=styles.FMT_PCT_2DP)
    r += 1

    layout.write_row_label(ws, r, "GP IRR (before promote)", "IRR GP (ante promote)", indent=True)
    cc = ws.cell(row=r, column=4,
                 value=f"=IRR(${first_col}${rows['gp_cf']}:${last_col}${rows['gp_cf']},0.10)")
    styles.style_formula(cc, number_format=styles.FMT_PCT_2DP)
    r += 1

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    ws.print_title_cols = "A:C"

    out = {f"{k}_row": str(v) for k, v in rows.items()}
    return out

"""Investor Returns sheet (Minibond Template 2).

Gross-to-net view from the bondholder's perspective:
    Gross cash flow (coupon + principal at maturity/amort)
    – withholding tax
    – transaction costs at entry
    = Net cash flow
    → Gross YTM, Net YTM (after-tax), MoIC
"""

from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout
from modelforge.builder.i18n import L


def build(ws: Worksheet, spec, bond_refs: dict[str, str], bond_sheet_name: str) -> None:
    h = spec.horizon.historical_years
    p = spec.horizon.projection_years

    layout.set_column_widths(ws, label_width=44, it_width=34, year_width=12, unit_width=6)
    layout.write_title_block(
        ws, title_en="Investor Returns", title_it="Rendimento investitore",
        subtitle="Gross YTM · Net YTM (after Italian withholding) · IFRS 9 EIR",
    )
    layout.write_scenario_banner(ws, row=3)

    # Periods 0..p (annual)
    yr_row = 5
    ws.cell(row=yr_row, column=3, value="Period").font = styles.font_subheader
    for i in range(p + 1):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=yr_row, column=col_idx, value=f"t={i}")
        styles.style_header(c)

    r = 7
    rows: dict[str, int] = {}
    interest_row = int(bond_refs["interest_row"])
    amort_row = int(bond_refs["amort_row"])

    layout.write_section_header(ws, r, "Gross bondholder cash flow", "CF lordo al bondholder")
    r += 1
    rows["gross_cf"] = r
    layout.write_row_label(ws, r, "Gross cash flow", "CF lordo")

    # t=0: -notional + transaction cost (negative, cost to investor)
    notional = spec.bond.notional.name
    tx_cost = spec.bond.arrangement_fee_pct.name  # investor-side we use transaction_cost_bps
    tx_cost_inv = spec.investor_adjustments.transaction_cost_bps.name
    c0 = ws.cell(row=r, column=4,
                 value=f"=-{notional}-({notional}*{tx_cost_inv}/10000)")
    styles.style_formula(c0, number_format=styles.FMT_EUR_M)

    for i in range(1, p + 1):
        debt_col = layout.year_col(h + (i - 1))
        interest_ref = f"'{bond_sheet_name}'!{debt_col}{interest_row}"
        amort_ref = f"'{bond_sheet_name}'!{debt_col}{amort_row}"
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-{interest_ref}-{amort_ref}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 2

    # Withholding tax (on interest only, principal is return of capital)
    layout.write_section_header(ws, r, "Net bondholder cash flow (after WHT)",
                                "CF netto al bondholder (al netto WHT)")
    r += 1
    rows["wht"] = r
    layout.write_row_label(ws, r, "Withholding tax on coupon", "Ritenuta d'acconto su cedola", indent=True)
    c0 = ws.cell(row=r, column=4, value=0)
    styles.style_formula(c0, number_format=styles.FMT_EUR_M)
    for i in range(1, p + 1):
        debt_col = layout.year_col(h + (i - 1))
        interest_ref = f"'{bond_sheet_name}'!{debt_col}{interest_row}"
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        # withholding = positive_coupon * wht_rate, which reduces investor CF
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-(-{interest_ref})*withholding_tax_pct")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    rows["net_cf"] = r
    layout.write_row_label(ws, r, "Net cash flow", "CF netto")
    for i in range(p + 1):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=${col}${rows['gross_cf']}+${col}${rows['wht']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
        c.font = styles.font_subheader
        c.border = styles.BORDER_TOP_THIN
    r += 2

    # Summary metrics
    layout.write_section_header(ws, r, "Return metrics", "Metriche di rendimento")
    r += 1
    first_col = layout.year_col(0); last_col = layout.year_col(p)

    layout.write_row_label(ws, r, "Gross YTM", "YTM lordo", indent=True)
    c = ws.cell(row=r, column=4,
                value=f"=IRR(${first_col}${rows['gross_cf']}:${last_col}${rows['gross_cf']},0.05)")
    styles.style_formula(c, number_format=styles.FMT_PCT_2DP)
    c.font = styles.font_subheader
    r += 1

    layout.write_row_label(ws, r, "Net YTM (after WHT)", "YTM netto (post WHT)", indent=True)
    c = ws.cell(row=r, column=4,
                value=f"=IRR(${first_col}${rows['net_cf']}:${last_col}${rows['net_cf']},0.04)")
    styles.style_formula(c, number_format=styles.FMT_PCT_2DP)
    c.font = styles.font_subheader
    r += 1

    layout.write_row_label(ws, r, "EIR (IFRS 9, incl. fees)",
                           "EIR (IFRS 9, incl. commissioni)", indent=True)
    c = ws.cell(row=r, column=4,
                value=f"=IRR(${first_col}${rows['gross_cf']}:${last_col}${rows['gross_cf']},0.05)")
    styles.style_formula(c, number_format=styles.FMT_PCT_2DP)
    c.font = styles.font_subheader
    c.comment = Comment(
        "IFRS 9 §B5.4.1 — EIR includes all fees that are an integral part "
        "of the instrument. Principal and coupon cash flows on the gross CF "
        "line already include the upfront transaction cost.",
        "ModelForge",
    )
    r += 1

    layout.write_row_label(ws, r, "MoIC (gross)", "MoIC (lordo)", indent=True)
    c = ws.cell(row=r, column=4,
                value=f"=IFERROR(SUMIF(${first_col}${rows['gross_cf']}:${last_col}${rows['gross_cf']},\">0\")"
                      f"/ABS(SUMIF(${first_col}${rows['gross_cf']}:${last_col}${rows['gross_cf']},\"<0\")),0)")
    styles.style_formula(c, number_format=styles.FMT_MULTIPLE)
    c.font = styles.font_subheader
    r += 1

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    ws.print_title_cols = "A:C"

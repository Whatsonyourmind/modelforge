"""Project Finance debt schedule + DSCR covenant.

Drawdown during construction phase, amortization during operating phase.
DSCR = CADS / Debt Service monitored period-by-period.
"""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout


def build(ws: Worksheet, spec, cashflow_refs: dict[str, str],
          cashflow_sheet: str) -> dict[str, str]:
    c = spec.horizon.construction_years
    o = spec.horizon.operating_years
    n = c + o

    layout.set_column_widths(ws, label_width=44, it_width=34, year_width=11, unit_width=6)
    layout.write_title_block(
        ws, title_en="Project Debt & DSCR", title_it="Debito di progetto & DSCR",
        subtitle=f"Commitment {spec.meta.currency} · {c + spec.debt.tenor_operating_years - spec.debt.grace_years}y senior · DSCR-driven",
    )
    layout.write_scenario_banner(ws, row=3)

    yr_row = 5
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        phase = "C" if i < c else "O"
        yr = i + 1 if i < c else (i - c + 1)
        cc = ws.cell(row=yr_row, column=col_idx, value=f"{phase}{yr}")
        styles.style_header(cc)

    rows: dict[str, int] = {}
    r = 7

    layout.write_section_header(ws, r, "Debt roll-forward", "Piano del debito")
    r += 1

    # Opening
    rows["opening"] = r
    layout.write_row_label(ws, r, "Opening debt", "Debito iniziale")
    ws.cell(row=r, column=3, value=spec.meta.currency).font = styles.font_label_it
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i == 0:
            cc = ws.cell(row=r, column=col_idx, value=0)
        else:
            prior = layout.year_col(i - 1)
            cc = ws.cell(row=r, column=col_idx, value=f"=${prior}${r + 3}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Drawdown — during construction, proportional to capex phasing
    rows["drawdown"] = r
    layout.write_row_label(ws, r, "Drawdown", "Tiraggio", indent=True)
    debt_amount = spec.debt.amount.name
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        phasing = spec.construction.capex_phasing_pct[i].name
        cc = ws.cell(row=r, column=col_idx, value=f"={debt_amount}*{phasing}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    for i in range(c, n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=0)
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Scheduled amortization — linear during operating after grace
    rows["amort"] = r
    layout.write_row_label(ws, r, "Scheduled amortization", "Ammortamento", indent=True)
    grace_end_col_idx = c + spec.debt.grace_years  # first year of amort (0-based)
    amort_years = spec.debt.tenor_operating_years - spec.debt.grace_years
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        if i < grace_end_col_idx or i >= c + spec.debt.tenor_operating_years:
            cc = ws.cell(row=r, column=col_idx, value=0)
        else:
            cc = ws.cell(row=r, column=col_idx, value=f"=-{debt_amount}/{amort_years}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Closing
    rows["closing"] = r
    layout.write_row_label(ws, r, "Closing debt", "Debito finale")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['opening']}+${col}${rows['drawdown']}+${col}${rows['amort']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 2

    # Interest
    rows["avg_balance"] = r
    layout.write_row_label(ws, r, "Average balance", "Debito medio", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=(${col}${rows['opening']}+${col}${rows['closing']})/2")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    ref = spec.debt.reference_rate.name
    margin = spec.debt.margin_bps.name
    rows["rate"] = r
    layout.write_row_label(ws, r, "All-in rate", "Tasso all-in", indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"={ref}+({margin}/10000)")
        styles.style_formula(cc, number_format=styles.FMT_PCT_2DP)
    r += 1

    rows["interest"] = r
    layout.write_row_label(ws, r, "Cash interest", "Interessi cassa")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-${col}${rows['avg_balance']}*${col}${rows['rate']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
    r += 1

    # Total debt service (negative) = interest + amort
    rows["debt_service"] = r
    layout.write_row_label(ws, r, "Total debt service", "Servizio totale del debito")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['interest']}+${col}${rows['amort']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 2

    # DSCR covenant
    layout.write_section_header(ws, r, "DSCR covenant", "Covenant DSCR")
    r += 1

    cads_row = int(cashflow_refs["cads_row"])

    rows["dscr"] = r
    layout.write_row_label(ws, r, "DSCR (CADS / |debt service|)", "DSCR")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i < c:
            cc = ws.cell(row=r, column=col_idx, value="")
        else:
            cads_ref = f"'{cashflow_sheet}'!{col}{cads_row}"
            ds_ref = f"${col}${rows['debt_service']}"
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=IFERROR({cads_ref}/ABS({ds_ref}),0)")
            styles.style_formula(cc, number_format=styles.FMT_MULTIPLE)
    r += 1

    rows["dscr_threshold"] = r
    layout.write_row_label(ws, r, "DSCR threshold", "Soglia DSCR", indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        if i < c:
            ws.cell(row=r, column=col_idx, value="")
        else:
            op_idx = i - c
            if op_idx < len(spec.covenant.threshold_by_year):
                a = spec.covenant.threshold_by_year[op_idx]
                cc = ws.cell(row=r, column=col_idx, value=f"={a.name}")
                styles.style_xref(cc, number_format=styles.FMT_MULTIPLE)
    r += 1

    rows["dscr_breach"] = r
    layout.write_row_label(ws, r, "DSCR breach flag", "Violazione DSCR", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i < c:
            ws.cell(row=r, column=col_idx, value="")
        else:
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=IF(${col}${rows['dscr']}<${col}${rows['dscr_threshold']},1,0)")
            styles.style_formula(cc, number_format=styles.FMT_INTEGER)
            cc.alignment = styles.align_center
    r += 1

    # Total breach counter
    rows["total_breach"] = r
    layout.write_row_label(ws, r, "Total DSCR breaches", "Violazioni totali DSCR")
    first_op_col = layout.year_col(c); last_col = layout.year_col(n - 1)
    cc = ws.cell(row=r, column=3,
                 value=f"=SUM(${first_op_col}${rows['dscr_breach']}:${last_col}${rows['dscr_breach']})")
    styles.style_formula(cc, number_format=styles.FMT_INTEGER)
    cc.font = styles.font_subheader

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    ws.print_title_cols = "A:C"

    out = {f"{k}_row": str(v) for k, v in rows.items()}
    out["total_breach_cell"] = f"'{ws.title}'!$C${rows['total_breach']}"
    return out

"""3-Statement model sheet — P&L + BS + CFS integrated."""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout
from modelforge.builder.i18n import L


def build(ws: Worksheet, spec, driver_refs: dict[str, str]) -> dict[str, str]:
    h = spec.horizon.historical_years
    p = spec.horizon.projection_years
    n = h + p

    layout.set_column_widths(ws, label_width=44, it_width=34, year_width=11, unit_width=6)
    layout.write_title_block(
        ws, title_en="3-Statement Model", title_it="Modello a tre prospetti",
        subtitle=f"P&L · BS · CFS integrated · {spec.meta.currency} {spec.meta.unit_scale}",
    )
    layout.write_scenario_banner(ws, row=3)

    # Year headers
    yr_row = 5
    base_fy_year = spec.target.last_fy_end.year
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        yr = base_fy_year - (h - 1) + i
        is_hist = i < h
        cc = ws.cell(row=yr_row, column=col_idx, value=f"{'A' if is_hist else 'E'} {yr}")
        styles.style_header(cc)

    rows: dict[str, int] = {}
    r = 7

    # ── P&L ──────────────────────────────────────────────────────────────
    layout.write_section_header(ws, r, "Profit & Loss", "Conto economico")
    r += 1

    rows["revenue_growth"] = r
    layout.write_row_label(ws, r, L("revenue_growth").en, L("revenue_growth").it)
    ws.cell(row=r, column=3, value="%").font = styles.font_label_it
    for i in range(p):
        a = spec.pl.revenue_growth_by_year[i]
        col_idx = ord(layout.year_col(h + i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"={a.name}")
        styles.style_xref(cc, number_format=styles.FMT_PCT)
    r += 1

    rows["revenue"] = r
    layout.write_row_label(ws, r, L("revenue").en, L("revenue").it)
    ws.cell(row=r, column=3, value=spec.meta.currency).font = styles.font_label_it
    for i in range(h):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=spec.historical_revenue_eur_m[i])
        styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(p):
        col = layout.year_col(h + i); col_idx = ord(col) - ord("A") + 1
        prior_col = layout.year_col(h + i - 1)
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${prior_col}${r}*(1+${col}${rows['revenue_growth']})")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    # Historical growth formulas
    for i in range(1, h):
        col = layout.year_col(i); prior_col = layout.year_col(i - 1)
        col_idx = ord(col) - ord("A") + 1
        gc = ws.cell(row=rows["revenue_growth"], column=col_idx,
                     value=f"=IFERROR(${col}${rows['revenue']}/${prior_col}${rows['revenue']}-1,0)")
        styles.style_formula(gc, number_format=styles.FMT_PCT)
    r += 1

    rows["ebitda_margin"] = r
    layout.write_row_label(ws, r, L("ebitda_margin").en, L("ebitda_margin").it)
    ws.cell(row=r, column=3, value="%").font = styles.font_label_it
    for i in range(h):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        hrev = spec.historical_revenue_eur_m[i]
        val = spec.historical_ebitda_eur_m[i] / hrev if hrev else 0
        cc = ws.cell(row=r, column=col_idx, value=val)
        styles.style_input(cc, number_format=styles.FMT_PCT)
    for i in range(p):
        a = spec.pl.ebitda_margin_by_year[i]
        col_idx = ord(layout.year_col(h + i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"={a.name}")
        styles.style_xref(cc, number_format=styles.FMT_PCT)
    r += 1

    rows["ebitda"] = r
    layout.write_row_label(ws, r, L("ebitda").en, L("ebitda").it)
    for i in range(h):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=spec.historical_ebitda_eur_m[i])
        styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(p):
        col = layout.year_col(h + i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}*${col}${rows['ebitda_margin']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["da"] = r
    layout.write_row_label(ws, r, L("da").en, L("da").it, indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=-${col}${rows['revenue']}*da_pct_revenue")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["ebit"] = r
    layout.write_row_label(ws, r, L("ebit").en, L("ebit").it)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebitda']}+${col}${rows['da']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Interest (cross-ref to BS debt row — which we build below)
    rows["interest"] = r
    layout.write_row_label(ws, r, L("interest_expense").en, L("interest_expense").it, indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    r += 1

    rows["ebt"] = r
    layout.write_row_label(ws, r, L("ebt").en, L("ebt").it)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebit']}+${col}${rows['interest']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["tax"] = r
    layout.write_row_label(ws, r, L("tax").en, L("tax").it, indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-MAX(${col}${rows['ebt']},0)*effective_tax_rate")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["net_income"] = r
    layout.write_row_label(ws, r, L("net_income").en, L("net_income").it)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebt']}+${col}${rows['tax']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 2

    # ── Balance Sheet ────────────────────────────────────────────────────
    layout.write_section_header(ws, r, "Balance Sheet", "Stato patrimoniale")
    r += 1

    # Assets
    rows["cash"] = r
    layout.write_row_label(ws, r, "Cash", "Cassa", indent=True)
    # Cash is the plug — formula later in CFS section; here hardcode opening
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.cash_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["receivables"] = r
    layout.write_row_label(ws, r, "Accounts receivable", "Crediti", indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.receivables_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}/365*receivables_days")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["inventory"] = r
    layout.write_row_label(ws, r, "Inventory", "Magazzino", indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.inventory_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}/365*inventory_days")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["net_ppe"] = r
    layout.write_row_label(ws, r, "Net PP&E", "Immobilizzazioni nette", indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.net_ppe_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${prior}${r}+${col}${rows['revenue']}*capex_pct_revenue+${col}${rows['da']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["total_assets"] = r
    layout.write_row_label(ws, r, "TOTAL ASSETS", "TOTALE ATTIVO")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['cash']}+${col}${rows['receivables']}+${col}${rows['inventory']}+${col}${rows['net_ppe']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 2

    # Liabilities & Equity
    rows["payables"] = r
    layout.write_row_label(ws, r, "Accounts payable", "Debiti v/fornitori", indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.payables_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}/365*payables_days")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # v0.7: Debt roll-forward (US-075 from v0.6 PRD)
    # BOP debt + draws − scheduled repayments = EOP. Opening balance
    # from spec; draws/repayments default to zero unless spec provides
    # debt_annual_repayment_eur_m which applies linearly from year 1.
    rows["debt"] = r
    layout.write_row_label(ws, r, "Debt", "Debito finanziario", indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.debt_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    annual_repay = getattr(spec.opening_bs, 'debt_annual_repayment_eur_m', 0.0) or 0.0
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        # Roll-forward: prior balance minus scheduled repayment (not below 0)
        cc = ws.cell(
            row=r, column=col_idx,
            value=f"=MAX(${prior}${r}-{annual_repay},0)",
        )
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["equity"] = r
    layout.write_row_label(ws, r, "Equity (retained earnings)", "Patrimonio netto", indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.equity_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        # Equity = prior equity + net income - dividends
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${prior}${r}+${col}${rows['net_income']}"
                           f"-MAX(${col}${rows['net_income']},0)*dividend_payout_ratio")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["total_le"] = r
    layout.write_row_label(ws, r, "TOTAL L & E", "TOTALE PASSIVO + PN")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['payables']}+${col}${rows['debt']}+${col}${rows['equity']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 1

    rows["bs_check"] = r
    layout.write_row_label(ws, r, "BS check (A - L - E)", "Check BS (A - P - PN)")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['total_assets']}-${col}${rows['total_le']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 2

    # Now patch Interest row (=-debt * rate, on opening debt)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1) if i > 0 else col
        opening_debt_ref = f"${prior}${rows['debt']}"
        int_cell = ws.cell(row=rows["interest"], column=col_idx)
        int_cell.value = f"=-{opening_debt_ref}*interest_on_debt_pct"
        styles.style_formula(int_cell, number_format=styles.FMT_EUR_M)

    # ── Cash Flow Statement ──────────────────────────────────────────────
    layout.write_section_header(ws, r, "Cash Flow Statement", "Rendiconto finanziario")
    r += 1

    rows["cf_ni"] = r
    layout.write_row_label(ws, r, "Net income (from P&L)", "Utile netto (da CE)")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['net_income']}")
        styles.style_xref(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_da_addback"] = r
    layout.write_row_label(ws, r, "+ D&A (non-cash)", "+ Ammortamenti", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-${col}${rows['da']}")  # flip sign since da is negative
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_nwc"] = r
    layout.write_row_label(ws, r, "- ΔNWC", "- ΔCCN", indent=True)
    ws.cell(row=r, column=4, value=0)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        cc = ws.cell(
            row=r, column=col_idx,
            value=(
                f"=-(${col}${rows['receivables']}-${prior}${rows['receivables']}"
                f"+${col}${rows['inventory']}-${prior}${rows['inventory']}"
                f"-${col}${rows['payables']}+${prior}${rows['payables']})"
            ),
        )
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_cfo"] = r
    layout.write_row_label(ws, r, "CFO (operating)", "CFO")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['cf_ni']}+${col}${rows['cf_da_addback']}+${col}${rows['cf_nwc']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
    r += 1

    rows["cf_capex"] = r
    layout.write_row_label(ws, r, "Capex", "Capex", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-${col}${rows['revenue']}*capex_pct_revenue")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_cfi"] = r
    layout.write_row_label(ws, r, "CFI (investing)", "CFI")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=${col}${rows['cf_capex']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_div"] = r
    layout.write_row_label(ws, r, "- Dividends paid", "- Dividendi", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-MAX(${col}${rows['net_income']},0)*dividend_payout_ratio")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_cff"] = r
    layout.write_row_label(ws, r, "CFF (financing)", "CFF")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=${col}${rows['cf_div']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_net_change"] = r
    layout.write_row_label(ws, r, "Net change in cash", "Variazione di cassa")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['cf_cfo']}+${col}${rows['cf_cfi']}+${col}${rows['cf_cff']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 1

    # Patch Cash row with t>0 values from CFS
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        cash_cell = ws.cell(row=rows["cash"], column=col_idx)
        cash_cell.value = f"=${prior}${rows['cash']}+${col}${rows['cf_net_change']}"
        styles.style_formula(cash_cell, number_format=styles.FMT_EUR_M)

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    ws.print_title_cols = "A:C"

    out = {f"{k}_row": str(v) for k, v in rows.items()}
    return out

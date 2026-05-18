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
    layout.write_section_header(ws, r, L("ts_pnl_header").en, L("ts_pnl_header").secondary)
    r += 1

    rows["revenue_growth"] = r
    layout.write_row_label(ws, r, L("revenue_growth").en, L("revenue_growth").secondary)
    ws.cell(row=r, column=3, value="%").font = styles.font_label_it
    for i in range(p):
        a = spec.pl.revenue_growth_by_year[i]
        col_idx = ord(layout.year_col(h + i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"={a.name}")
        styles.style_xref(cc, number_format=styles.FMT_PCT)
    r += 1

    rows["revenue"] = r
    layout.write_row_label(ws, r, L("revenue").en, L("revenue").secondary)
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
    layout.write_row_label(ws, r, L("ebitda_margin").en, L("ebitda_margin").secondary)
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
    layout.write_row_label(ws, r, L("ebitda").en, L("ebitda").secondary)
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
    layout.write_row_label(ws, r, L("da").en, L("da").secondary, indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=-${col}${rows['revenue']}*da_pct_revenue")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["ebit"] = r
    layout.write_row_label(ws, r, L("ebit").en, L("ebit").secondary)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebitda']}+${col}${rows['da']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Interest (cross-ref to BS debt row — which we build below)
    rows["interest"] = r
    layout.write_row_label(ws, r, L("interest_expense").en, L("interest_expense").secondary, indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    r += 1

    rows["ebt"] = r
    layout.write_row_label(ws, r, L("ebt").en, L("ebt").secondary)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebit']}+${col}${rows['interest']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["tax"] = r
    layout.write_row_label(ws, r, L("tax").en, L("tax").secondary, indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-MAX(${col}${rows['ebt']},0)*effective_tax_rate")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["net_income"] = r
    layout.write_row_label(ws, r, L("net_income").en, L("net_income").secondary)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebt']}+${col}${rows['tax']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 2

    # ── Balance Sheet ────────────────────────────────────────────────────
    layout.write_section_header(ws, r, L("ts_bs_header").en, L("ts_bs_header").secondary)
    r += 1

    # Assets
    rows["cash"] = r
    layout.write_row_label(ws, r, L("ts_cash").en, L("ts_cash").secondary, indent=True)
    # Cash is the plug — formula later in CFS section; here hardcode opening
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.cash_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["receivables"] = r
    layout.write_row_label(ws, r, L("ts_ar").en, L("ts_ar").secondary, indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.receivables_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}/365*receivables_days")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["inventory"] = r
    layout.write_row_label(ws, r, L("ts_inventory").en, L("ts_inventory").secondary, indent=True)
    cc = ws.cell(row=r, column=4, value=spec.opening_bs.inventory_eur_m)
    styles.style_input(cc, number_format=styles.FMT_EUR_M)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}/365*inventory_days")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["net_ppe"] = r
    layout.write_row_label(ws, r, L("ts_net_ppe").en, L("ts_net_ppe").secondary, indent=True)
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
    layout.write_row_label(ws, r, L("ts_total_assets").en, L("ts_total_assets").secondary)
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
    layout.write_row_label(ws, r, L("ts_ap").en, L("ts_ap").secondary, indent=True)
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
    layout.write_row_label(ws, r, L("ts_debt").en, L("ts_debt").secondary, indent=True)
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
    layout.write_row_label(ws, r, L("ts_equity").en, L("ts_equity").secondary, indent=True)
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
    layout.write_row_label(ws, r, L("ts_total_le").en, L("ts_total_le").secondary)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['payables']}+${col}${rows['debt']}+${col}${rows['equity']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 1

    rows["bs_check"] = r
    layout.write_row_label(ws, r, L("ts_bs_check").en, L("ts_bs_check").secondary)
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
    layout.write_section_header(ws, r, L("ts_cfs_header").en, L("ts_cfs_header").secondary)
    r += 1

    rows["cf_ni"] = r
    layout.write_row_label(ws, r, L("ts_ni_from_pl").en, L("ts_ni_from_pl").secondary)
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
    layout.write_row_label(ws, r, L("ts_cfo").en, L("ts_cfo").secondary)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['cf_ni']}+${col}${rows['cf_da_addback']}+${col}${rows['cf_nwc']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
    r += 1

    rows["cf_capex"] = r
    layout.write_row_label(ws, r, L("ts_capex").en, L("ts_capex").secondary, indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-${col}${rows['revenue']}*capex_pct_revenue")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_cfi"] = r
    layout.write_row_label(ws, r, L("ts_cfi").en, L("ts_cfi").secondary)
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
    layout.write_row_label(ws, r, L("ts_cff").en, L("ts_cff").secondary)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=${col}${rows['cf_div']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cf_net_change"] = r
    layout.write_row_label(ws, r, L("ts_net_change_cash").en, L("ts_net_change_cash").secondary)
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

    r += 1
    # ── v0.8 Supplementary: NOL, DTA/DTL, SBC, Minority, Revolver ────────
    layout.write_section_header(
        ws, r, "Supplementary schedules (NOL, DTA/DTL, SBC, MI, Revolver)",
        "Schedules supplementari",
    )
    r += 1

    # v0.8 US-220: NOL schedule — Italian 5-year limit + 80% current-year
    # offset (post Legge Bilancio 2024). Opening → Generated → Used (cap
    # 80% of positive EBT) → Expired (>5y) → Closing.
    rows["nol_opening"] = r
    layout.write_row_label(ws, r, "NOL balance (opening)",
                           "Perdite fiscali (apertura)", indent=True)
    ws.cell(row=r, column=4, value=0)  # opens at zero (or spec override)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${prior}${r + 4}")  # forward ref to closing below
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["nol_generated"] = r
    layout.write_row_label(ws, r, "NOL generated (NI < 0)",
                           "Perdita generata", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=MAX(-${col}${rows['ebt']},0)")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["nol_used"] = r
    layout.write_row_label(ws, r, "NOL used (80% cap on positive EBT)",
                           "Perdite utilizzate (80% cap)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(
            row=r, column=col_idx,
            value=(f"=MIN(${col}${rows['nol_opening']},"
                   f"MAX(${col}${rows['ebt']},0)*0.8)"),
        )
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["nol_expired"] = r
    layout.write_row_label(ws, r, "NOL expired (>5 years)",
                           "Perdite scadute (>5 anni)", indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    r += 1

    rows["nol_closing"] = r
    layout.write_row_label(ws, r, "NOL balance (closing)",
                           "Perdite fiscali (chiusura)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(
            row=r, column=col_idx,
            value=(f"=${col}${rows['nol_opening']}"
                   f"+${col}${rows['nol_generated']}"
                   f"-${col}${rows['nol_used']}"
                   f"-${col}${rows['nol_expired']}"),
        )
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # v0.8 US-221: DTA from NOL + DTL on D&A book-tax difference
    rows["dta"] = r
    layout.write_row_label(ws, r, "DTA (NOL × tax rate)",
                           "Imposte differite attive", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['nol_closing']}*effective_tax_rate")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["dtl"] = r
    layout.write_row_label(ws, r, "DTL (accumulated on D&A timing diffs)",
                           "Imposte differite passive", indent=True)
    # Simplified: DTL accumulates at 5% of |D&A| × tax rate per year as
    # a proxy for book-vs-tax D&A timing differences.
    ws.cell(row=r, column=4, value=0)
    for i in range(1, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        prior = layout.year_col(i - 1)
        cc = ws.cell(
            row=r, column=col_idx,
            value=(f"=${prior}${r}+ABS(${col}${rows['da']})*0.05"
                   f"*effective_tax_rate"),
        )
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # v0.8 US-222: SBC — expense as % revenue (non-cash, CFS addback).
    rows["sbc_expense"] = r
    layout.write_row_label(ws, r, "Stock-based compensation (SBC) expense",
                           "Compensi in azioni (costo)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-${col}${rows['revenue']}*0.01")  # 1% default
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    ws.cell(row=r, column=4).comment = __import__(
        "openpyxl.comments", fromlist=["Comment"]).Comment(
        "SBC expense default 1% of revenue. Non-cash → added back on CFS. "
        "For full wire into EBIT + FD dilution, pass "
        "sbc_pct_revenue + options_outstanding via spec (future US).",
        "ModelForge",
    )
    r += 1

    # v0.8 US-223: Minority interest — NI attributable to NCI (default 0)
    rows["minority_ni"] = r
    layout.write_row_label(ws, r, "(−) Minority interest in NI",
                           "(−) Interessenze di minoranza su utile",
                           indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)  # default 0 for wholly-owned
    r += 1

    rows["ni_to_parent"] = r
    layout.write_row_label(ws, r, "Net income to parent",
                           "Utile netto di gruppo (parent)")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=(f"=${col}${rows['net_income']}"
                            f"-${col}${rows['minority_ni']}"))
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["minority_bs"] = r
    layout.write_row_label(ws, r, "Minority interest (BS equity)",
                           "PN di terzi (SP)", indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    r += 1

    # v0.8 US-224: Revolver plug — auto-draw when ending cash < 0.
    # Simple proxy: revolver draw = MAX(0, −cash). Does not iterate; meant
    # as a structural placeholder until the revolver facility is sized.
    rows["revolver_plug"] = r
    layout.write_row_label(ws, r, "Revolver draw (plug when cash < 0)",
                           "Utilizzo revolver (se cassa < 0)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=MAX(-${col}${rows['cash']},0)")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["revolver_commit_fee"] = r
    layout.write_row_label(ws, r, "Revolver commitment fee (0.5% × undrawn)",
                           "Commissione impegno revolver", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        # Flat 100m capacity × 0.5% × (1 − utilization). Simplified.
        cc = ws.cell(row=r, column=col_idx,
                     value=(f"=-MAX(100-${col}${r-1},0)*0.005"))
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    ws.print_title_cols = "A:C"

    out = {f"{k}_row": str(v) for k, v in rows.items()}
    return out

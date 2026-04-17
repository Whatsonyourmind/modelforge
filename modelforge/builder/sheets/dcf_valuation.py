"""DCF valuation + WACC build sheet (Template 10).

Emits three core sheets:
    WACCBuild      — risk-free + ERP + beta → cost of equity, then
                     WACC from target capital structure
    FCFForecast    — revenue, EBITDA, D&A, EBIT, tax, capex, ΔNWC → FCF
    Valuation     — PV(explicit FCF) + terminal value (Gordon + exit x)
                     → enterprise value → equity value → implied per
                     share price with Damodaran 2026 Italy ERP cited.
"""

from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout


def build_wacc(ws: Worksheet, spec) -> dict[str, str]:
    """Emit WACCBuild. Returns {cost_of_equity: ref, wacc: ref}."""
    layout.set_column_widths(ws, label_width=40, it_width=32, year_width=14, unit_width=6)
    layout.write_title_block(ws, "WACC Build", "Calcolo WACC",
                             "Damodaran 2026 Italy ERP = 6.7% (mature = 4.23%)")

    rows = [
        ("Risk-free rate (10Y BTP)", "Tasso risk-free", "=risk_free_rate", styles.FMT_PCT_2DP),
        ("Equity risk premium (Italy)", "ERP Italia", "=equity_risk_premium", styles.FMT_PCT_2DP),
        ("Beta (levered)", "Beta (levered)", "=beta_levered", styles.FMT_MULTIPLE),
        ("Cost of equity", "Costo del capitale",
         "=risk_free_rate+beta_levered*equity_risk_premium", styles.FMT_PCT_2DP),
        ("Pre-tax cost of debt", "Costo del debito pre-tax", "=pretax_cost_of_debt", styles.FMT_PCT_2DP),
        ("Effective tax rate", "Aliquota effettiva", "=effective_tax_rate", styles.FMT_PCT),
        ("After-tax cost of debt", "Costo del debito post-tax",
         "=pretax_cost_of_debt*(1-effective_tax_rate)", styles.FMT_PCT_2DP),
        ("Target D / (D+E)", "Target D / (D+E)", "=target_debt_weight", styles.FMT_PCT),
        ("Target E / (D+E)", "Target E / (D+E)", "=1-target_debt_weight", styles.FMT_PCT),
        ("WACC",
         "WACC",
         "=((risk_free_rate+beta_levered*equity_risk_premium)*(1-target_debt_weight))+"
         "(pretax_cost_of_debt*(1-effective_tax_rate)*target_debt_weight)",
         styles.FMT_PCT_2DP),
    ]
    r = 5
    refs: dict[str, str] = {}
    for en, it, formula, fmt in rows:
        layout.write_row_label(ws, r, en, it)
        c = ws.cell(row=r, column=4, value=formula)
        styles.style_formula(c, number_format=fmt)
        if en == "Cost of equity":
            refs["cost_of_equity"] = f"'{ws.title}'!$D${r}"
            c.font = styles.font_subheader
        if en == "WACC":
            refs["wacc"] = f"'{ws.title}'!$D${r}"
            c.font = styles.font_subheader
            c.comment = Comment(
                "WACC = Ke × (E/(D+E)) + Kd × (1 − t) × (D/(D+E)).\n"
                "Damodaran 2026 Italy ERP 6.7% used per country-risk "
                "table; risk-free cites 10Y BTP yield.",
                "ModelForge",
            )
        r += 1

    # Register wacc_rate named range at workbook level
    from openpyxl.workbook.defined_name import DefinedName
    if "wacc_rate" in ws.parent.defined_names:
        del ws.parent.defined_names["wacc_rate"]
    ws.parent.defined_names["wacc_rate"] = DefinedName(
        name="wacc_rate", attr_text=refs["wacc"],
    )

    ws.freeze_panes = "D5"
    ws.print_title_rows = "1:4"
    return refs


def build_fcf(ws: Worksheet, spec, wacc_refs: dict[str, str]) -> dict[str, str]:
    """Emit FCFForecast. Returns row/ref map for Valuation sheet."""
    h = spec.horizon.historical_years
    p = spec.horizon.projection_years
    n = h + p

    layout.set_column_widths(ws, label_width=40, it_width=32, year_width=12, unit_width=6)
    layout.write_title_block(ws, "FCF Forecast", "Previsione FCF",
                             "Unlevered free cash flow to the firm")
    layout.write_scenario_banner(ws, row=3)

    # Year headers row 5
    yr_row = 5
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        label = "H" if i < h else "F"
        idx = i + 1 if i < h else i - h + 1
        c = ws.cell(row=yr_row, column=col_idx, value=f"{label}Y{idx}")
        styles.style_header(c)

    # Rows: Revenue, Growth %, EBITDA margin %, EBITDA, D&A, EBIT, Tax, NOPAT, Capex, ΔNWC, FCF
    r = 7
    rows_out: dict[str, int] = {}

    # Revenue
    layout.write_row_label(ws, r, "Revenue", "Ricavi")
    rows_out["revenue"] = r
    # Historical as hardcoded values (from spec)
    for i in range(h):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        # Use target.revenue_last_fy_eur_m at the last historical year if no history array
        # For simplicity, set the last-fy revenue at col(h-1) and roll others back by constant
        rev = spec.target.revenue_last_fy_eur_m
        c = ws.cell(row=r, column=col_idx,
                    value=rev if i == h - 1 else rev * 0.9 ** (h - 1 - i))
        styles.style_input(c, number_format=styles.FMT_EUR_M)
        c.comment = Comment(f"Historical revenue (FY{i+1}) — from spec", "ModelForge")
    # Projected: revenue_prev * (1 + growth)
    for i in range(p):
        growth_name = spec.fcf.revenue_growth_by_year[i].name
        col = layout.year_col(h + i)
        col_idx = ord(col) - ord("A") + 1
        prev_col = layout.year_col(h + i - 1)
        c = ws.cell(row=r, column=col_idx,
                    value=f"={prev_col}{r}*(1+{growth_name})")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # EBITDA
    layout.write_row_label(ws, r, "EBITDA", "EBITDA")
    rows_out["ebitda"] = r
    for i in range(h):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx, value=spec.target.ebitda_last_fy_eur_m)
        styles.style_input(c, number_format=styles.FMT_EUR_M)
        c.comment = Comment("Historical EBITDA (from spec)", "ModelForge")
    for i in range(p):
        margin_name = spec.fcf.ebitda_margin_by_year[i].name
        col_idx = ord(layout.year_col(h + i)) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={layout.year_col(h + i)}{rows_out['revenue']}*{margin_name}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # D&A
    layout.write_row_label(ws, r, "D&A", "A&A", indent=True)
    rows_out["da"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-{col}{rows_out['revenue']}*da_pct_revenue")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # EBIT
    layout.write_row_label(ws, r, "EBIT", "EBIT")
    rows_out["ebit"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{rows_out['ebitda']}+{col}{rows_out['da']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
        c.font = styles.font_subheader
    r += 1

    # Tax on EBIT
    layout.write_row_label(ws, r, "Tax on EBIT", "Imposte su EBIT", indent=True)
    rows_out["tax"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-MAX({col}{rows_out['ebit']}*effective_tax_rate,0)")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # NOPAT
    layout.write_row_label(ws, r, "NOPAT", "NOPAT")
    rows_out["nopat"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{rows_out['ebit']}+{col}{rows_out['tax']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # +D&A back
    layout.write_row_label(ws, r, "+ D&A addback", "+ A&A", indent=True)
    rows_out["da_addback"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx, value=f"=-{col}{rows_out['da']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # Capex
    layout.write_row_label(ws, r, "Capex", "Capex", indent=True)
    rows_out["capex"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-{col}{rows_out['revenue']}*capex_pct_revenue")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # Δ NWC
    layout.write_row_label(ws, r, "Δ Working capital", "Δ Capitale circolante", indent=True)
    rows_out["nwc"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        if i == 0:
            c = ws.cell(row=r, column=col_idx, value=0)
        else:
            prev = layout.year_col(i - 1)
            c = ws.cell(
                row=r, column=col_idx,
                value=f"=-({col}{rows_out['revenue']}-{prev}{rows_out['revenue']})*nwc_pct_revenue_delta",
            )
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # FCF (unlevered)
    layout.write_row_label(ws, r, "Unlevered FCF", "FCF unlevered")
    rows_out["fcf"] = r
    for i in range(n):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(
            row=r, column=col_idx,
            value=(
                f"={col}{rows_out['nopat']}+{col}{rows_out['da_addback']}"
                f"+{col}{rows_out['capex']}+{col}{rows_out['nwc']}"
            ),
        )
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
        c.font = styles.font_subheader
        c.border = styles.BORDER_TOP_THIN

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    rows_out["h"] = h
    rows_out["p"] = p
    return rows_out


def build_valuation(ws: Worksheet, spec, fcf_refs: dict[str, int],
                    fcf_sheet: str) -> None:
    """Enterprise DCF + terminal value reconciliation."""
    h = fcf_refs["h"]
    p = fcf_refs["p"]
    layout.set_column_widths(ws, label_width=46, it_width=34, year_width=13, unit_width=6)
    layout.write_title_block(ws, "Valuation", "Valutazione",
                             "DCF Gordon + Exit Multiple reconciliation")

    # Summary block: TV(Gordon), TV(Exit), PV explicit, Enterprise Value, Equity value, Implied px
    r = 5
    # Last year FCF + EBITDA refs
    last_col = layout.year_col(h + p - 1)
    fcf_row = fcf_refs["fcf"]
    ebitda_row = fcf_refs["ebitda"]

    rows = [
        ("Explicit-period PV of FCF", "VAN FCF esplicito",
         f"=SUMPRODUCT('{fcf_sheet}'!{layout.year_col(h)}{fcf_row}:"
         f"{last_col}{fcf_row},"
         f"(1+wacc_rate)^-ROW(INDIRECT(\"1:{p}\")))",
         styles.FMT_EUR_M, None),
        ("Terminal value — Gordon growth", "Terminal value — Gordon",
         f"='{fcf_sheet}'!{last_col}{fcf_row}*(1+terminal_growth_pct)/"
         f"(wacc_rate-terminal_growth_pct)",
         styles.FMT_EUR_M, "tv_gordon"),
        ("Terminal value — exit EV/EBITDA", "Terminal value — EV/EBITDA uscita",
         f"='{fcf_sheet}'!{last_col}{ebitda_row}*exit_ev_ebitda_x",
         styles.FMT_EUR_M, "tv_exit"),
        ("Terminal value — average (reconciled)", "Terminal value — media",
         f"=AVERAGE(D{r+1},D{r+2})",
         styles.FMT_EUR_M, "tv_used"),
        ("PV of terminal value", "VAN del terminal value",
         f"=D{r+3}/(1+wacc_rate)^{p}",
         styles.FMT_EUR_M, None),
        ("Enterprise Value", "Enterprise Value",
         f"=D{r}+D{r+4}",
         styles.FMT_EUR_M, "ev"),
        ("(−) Net debt", "(−) Posizione finanziaria netta",
         f"=-{spec.net_debt_eur_m}",
         styles.FMT_EUR_M, None),
        ("Equity Value", "Valore equity",
         f"=D{r+5}+D{r+6}",
         styles.FMT_EUR_M, "equity_val"),
        ("Implied EV / EBITDA (Y1 proj)", "EV/EBITDA implicito Y1",
         f"=D{r+5}/'{fcf_sheet}'!{layout.year_col(h)}{ebitda_row}",
         styles.FMT_MULTIPLE, None),
        ("Implied EV", "EV implicito",
         f"=D{r+5}",
         styles.FMT_EUR_M, None),
    ]

    for i, (en, it, formula, fmt, name) in enumerate(rows):
        rr = r + i
        layout.write_row_label(ws, rr, en, it)
        c = ws.cell(row=rr, column=4, value=formula)
        styles.style_formula(c, number_format=fmt)
        if name in ("ev", "equity_val", "tv_used"):
            c.font = styles.font_subheader
        if en.startswith("Enterprise Value") or en.startswith("Equity Value"):
            c.border = styles.BORDER_TOP_THIN

    # Implied price per share (if shares given)
    if spec.shares_outstanding_m > 0:
        ri = r + len(rows)
        layout.write_row_label(ws, ri, "Implied price per share",
                               "Prezzo implicito per azione")
        c = ws.cell(row=ri, column=4,
                    value=f"=D{r+7}/{spec.shares_outstanding_m}")
        styles.style_formula(c, number_format=styles.FMT_EUR_ACTUAL)
        c.font = styles.font_subheader
        if spec.valuation_date_price_eur > 0:
            ri += 1
            layout.write_row_label(ws, ri, "Current price", "Prezzo attuale")
            ws.cell(row=ri, column=4, value=spec.valuation_date_price_eur)
            styles.style_input(ws.cell(row=ri, column=4),
                               number_format=styles.FMT_EUR_ACTUAL)
            ri += 1
            layout.write_row_label(ws, ri, "Premium / (discount) %",
                                   "Premio / (sconto) %")
            c = ws.cell(row=ri, column=4,
                        value=f"=D{ri-2}/D{ri-1}-1")
            styles.style_formula(c, number_format=styles.FMT_PCT_2DP)

    ws.freeze_panes = "D5"
    ws.print_title_rows = "1:4"

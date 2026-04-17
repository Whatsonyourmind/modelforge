"""M&A merger pro-forma + accretion/dilution sheet (Template 9).

One sheet per view:
    DealStructure  — offer price, deal value, financing split (cash/stock)
    ProForma       — standalone target + acquirer → pro-forma
                     incremental interest + synergies → pro-forma NI
    AccretionDilution — standalone EPS vs pro-forma EPS, year-by-year
"""

from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout


def build_deal_structure(ws: Worksheet, spec) -> dict[str, int]:
    layout.set_column_widths(ws, label_width=44, it_width=34, year_width=14, unit_width=6)
    layout.write_title_block(ws, "Deal Structure", "Struttura dell'operazione",
                             "Consideration split + financing impact")

    r = 5
    rows: list[tuple[str, str, str, str, str | None]] = [
        ("Target current share price", "Prezzo corrente target",
         f"={spec.target_financials.share_price_eur}", styles.FMT_EUR_ACTUAL, None),
        ("Offer premium %", "Premio offerto",
         "=offer_premium_pct", styles.FMT_PCT, None),
        ("Offer price per share", "Prezzo offerto",
         f"=D{r}*(1+offer_premium_pct)", styles.FMT_EUR_ACTUAL, "offer_px"),
        ("Target shares outstanding (m)", "Azioni target (m)",
         f"={spec.target_financials.shares_outstanding_m}", styles.FMT_MULTIPLE, None),
        ("Equity purchase price (€m)", "Prezzo equity (€m)",
         f"=D{r+2}*D{r+3}", styles.FMT_EUR_M, "equity_price"),
        ("(+) Target net debt", "(+) PFN target",
         f"={spec.target_financials.net_debt_eur_m}", styles.FMT_EUR_M, None),
        ("Enterprise Value", "Enterprise Value",
         f"=D{r+4}+D{r+5}", styles.FMT_EUR_M, "ev"),
        ("Cash consideration % (of equity)", "Cash consideration %",
         "=cash_mix_pct", styles.FMT_PCT, None),
        ("Cash consideration (€m)", "Consideration cash (€m)",
         f"=D{r+4}*cash_mix_pct", styles.FMT_EUR_M, "cash_cons"),
        ("Stock consideration (€m)", "Consideration in azioni (€m)",
         f"=D{r+4}*(1-cash_mix_pct)", styles.FMT_EUR_M, "stock_cons"),
        ("Shares issued by acquirer (m)", "Azioni emesse acquirer (m)",
         f"=D{r+9}/{spec.acquirer.share_price_eur}", styles.FMT_MULTIPLE, "new_shares"),
        ("Incremental interest expense (€m)", "Interessi incrementali (€m)",
         f"=-D{r+8}*financing_rate_pct", styles.FMT_EUR_M, "incr_int"),
    ]
    refs: dict[str, int] = {}
    for i, (en, it, formula, fmt, name) in enumerate(rows):
        rr = r + i
        layout.write_row_label(ws, rr, en, it)
        c = ws.cell(row=rr, column=4, value=formula)
        styles.style_formula(c, number_format=fmt)
        if name:
            refs[name] = rr
            if name in ("ev", "equity_price", "incr_int"):
                c.font = styles.font_subheader

    ws.freeze_panes = "D5"
    ws.print_title_rows = "1:4"
    return refs


def build_proforma(ws: Worksheet, spec, deal_refs: dict[str, int],
                   deal_sheet: str) -> dict[str, int]:
    p = spec.horizon.projection_years
    layout.set_column_widths(ws, label_width=40, it_width=32, year_width=12, unit_width=6)
    layout.write_title_block(ws, "Pro Forma", "Pro forma",
                             "Standalone acquirer + target + synergies")
    layout.write_scenario_banner(ws, row=3)

    # Year headers row 5
    yr_row = 5
    for i in range(p):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=yr_row, column=col_idx, value=f"Y{i+1}")
        styles.style_header(c)

    r = 7
    out: dict[str, int] = {}

    # Revenue rows
    layout.write_section_header(ws, r, "Revenue", "Ricavi")
    r += 1
    layout.write_row_label(ws, r, "Acquirer revenue", "Ricavi acquirer")
    out["acq_rev"] = r
    for i in range(p):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=spec.acquirer.revenue_eur_m * (1.03 ** i))
        styles.style_input(c, number_format=styles.FMT_EUR_M)
        c.comment = Comment("Acquirer revenue assumed to grow 3% p.a. (illustrative)",
                            "ModelForge")
    r += 1
    layout.write_row_label(ws, r, "Target revenue", "Ricavi target")
    out["tgt_rev"] = r
    for i in range(p):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=spec.target_financials.revenue_eur_m * (1.04 ** i))
        styles.style_input(c, number_format=styles.FMT_EUR_M)
        c.comment = Comment("Target revenue assumed to grow 4% p.a. (illustrative)",
                            "ModelForge")
    r += 1
    layout.write_row_label(ws, r, "Revenue synergies", "Sinergie di ricavo", indent=True)
    out["syn_rev"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        ramp = f"MIN(1,synergy_realization_y1_pct+{i}*(1-synergy_realization_y1_pct)/{max(p-1,1)})"
        c = ws.cell(row=r, column=col_idx,
                    value=f"=revenue_synergies_eur_m*{ramp}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1
    layout.write_row_label(ws, r, "Pro-forma revenue", "Ricavi pro-forma")
    out["pf_rev"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['acq_rev']}+{col}{out['tgt_rev']}+{col}{out['syn_rev']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
        c.font = styles.font_subheader
    r += 2

    # EBITDA
    layout.write_section_header(ws, r, "EBITDA", "EBITDA")
    r += 1
    acq_margin = spec.acquirer.ebitda_eur_m / spec.acquirer.revenue_eur_m
    tgt_margin = spec.target_financials.ebitda_eur_m / spec.target_financials.revenue_eur_m
    layout.write_row_label(ws, r, "Acquirer EBITDA", "EBITDA acquirer")
    out["acq_ebitda"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['acq_rev']}*{acq_margin}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1
    layout.write_row_label(ws, r, "Target EBITDA", "EBITDA target")
    out["tgt_ebitda"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['tgt_rev']}*{tgt_margin}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1
    layout.write_row_label(ws, r, "Cost synergies", "Sinergie di costo", indent=True)
    out["syn_cost"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        ramp = f"MIN(1,synergy_realization_y1_pct+{i}*(1-synergy_realization_y1_pct)/{max(p-1,1)})"
        c = ws.cell(row=r, column=col_idx,
                    value=f"=cost_synergies_eur_m*{ramp}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1
    layout.write_row_label(ws, r, "Integration cost (one-time)",
                           "Costi d'integrazione (una tantum)", indent=True)
    out["integ"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-integration_cost_eur_m" if i == 0 else 0)
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1
    layout.write_row_label(ws, r, "Pro-forma EBITDA", "EBITDA pro-forma")
    out["pf_ebitda"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['acq_ebitda']}+{col}{out['tgt_ebitda']}"
                          f"+{col}{out['syn_cost']}+{col}{out['integ']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
        c.font = styles.font_subheader
    r += 2

    # Pro-forma EBITDA → EBIT walk using REAL standalone D&A
    # (no more EBITDA × 0.9 heuristic — that inflated accretion on
    # high-D&A industries like telecom, utilities, industrials).
    layout.write_section_header(ws, r, "Pro-forma Net Income",
                                "Utile netto pro-forma")
    r += 1

    # Combined D&A (acquirer + target) grown at 3% p.a. as a proxy
    # for aggregate depreciation schedule; positive number here, then
    # subtracted when walking to EBIT.
    combined_da = spec.acquirer.da_eur_m + spec.target_financials.da_eur_m
    layout.write_row_label(ws, r, "(−) Combined D&A",
                           "(−) A&A combinato", indent=True)
    out["pf_da"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        # Negative (cost) — D&A grown 3% p.a.
        c = ws.cell(row=r, column=col_idx, value=-combined_da * (1.03 ** i))
        styles.style_input(c, number_format=styles.FMT_EUR_M)
        c.comment = Comment(
            f"Combined acquirer + target D&A = €{combined_da:,.0f}m FY0, "
            f"grown 3% p.a. as aggregate depreciation proxy. Populate "
            f"spec.acquirer.da_eur_m + spec.target_financials.da_eur_m "
            f"from audited financials.",
            "ModelForge",
        )
    r += 1

    layout.write_row_label(ws, r, "Pro-forma EBIT",
                           "EBIT pro-forma", indent=True)
    out["pf_ebit"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['pf_ebitda']}+{col}{out['pf_da']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    # Standalone combined interest (acquirer + target) grown 3% p.a.
    combined_int = (spec.acquirer.interest_expense_eur_m
                    + spec.target_financials.interest_expense_eur_m)
    layout.write_row_label(ws, r, "(−) Standalone interest (combined)",
                           "(−) Interessi standalone combinati", indent=True)
    out["pf_standalone_int"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx, value=-combined_int * (1.03 ** i))
        styles.style_input(c, number_format=styles.FMT_EUR_M)
        c.comment = Comment(
            f"Standalone interest combined = €{combined_int:,.0f}m. "
            f"Populated from spec.acquirer.interest_expense_eur_m + "
            f"spec.target_financials.interest_expense_eur_m.",
            "ModelForge",
        )
    r += 1

    layout.write_row_label(ws, r, "(−) Incremental interest (new debt)",
                           "(−) Interessi incrementali (nuovo debito)",
                           indent=True)
    out["pf_int"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"='{deal_sheet}'!$D${deal_refs['incr_int']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    layout.write_row_label(ws, r, "Pre-tax income",
                           "Utile ante imposte", indent=True)
    out["pf_pretax"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['pf_ebit']}+{col}{out['pf_standalone_int']}"
                          f"+{col}{out['pf_int']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1

    layout.write_row_label(ws, r, "(−) Pro-forma tax",
                           "(−) Tasse pro-forma", indent=True)
    out["pf_tax"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=-MAX({col}{out['pf_pretax']}*effective_tax_rate,0)")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    r += 1
    layout.write_row_label(ws, r, "Pro-forma Net Income",
                           "Utile netto pro-forma")
    out["pf_ni"] = r
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{out['pf_pretax']}+{col}{out['pf_tax']}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
        c.font = styles.font_subheader
        c.border = styles.BORDER_TOP_THIN

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    return out


def build_accretion_dilution(
    ws: Worksheet, spec, pf_refs: dict[str, int], deal_refs: dict[str, int],
    pf_sheet: str, deal_sheet: str,
) -> None:
    p = spec.horizon.projection_years
    layout.set_column_widths(ws, label_width=46, it_width=34, year_width=12, unit_width=6)
    layout.write_title_block(ws, "Accretion / Dilution",
                             "Accretion / Diluizione",
                             "Standalone EPS vs pro-forma EPS")
    layout.write_scenario_banner(ws, row=3)

    yr_row = 5
    for i in range(p):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        c = ws.cell(row=yr_row, column=col_idx, value=f"Y{i+1}")
        styles.style_header(c)

    r = 7
    # Standalone EPS (acquirer)
    acq_std_ni = spec.acquirer.net_income_eur_m
    acq_shares = spec.acquirer.shares_outstanding_m
    layout.write_row_label(ws, r, "Acquirer standalone EPS",
                           "EPS acquirer standalone")
    for i in range(p):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        val = acq_std_ni * (1.03 ** i) / acq_shares
        c = ws.cell(row=r, column=col_idx, value=val)
        styles.style_input(c, number_format=styles.FMT_EUR_ACTUAL)
        c.comment = Comment("Standalone EPS = NI × 3% growth / shares",
                            "ModelForge")
    std_eps_row = r
    r += 1

    # Pro-forma EPS
    layout.write_row_label(ws, r, "Pro-forma EPS", "EPS pro-forma")
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        formula = (
            f"='{pf_sheet}'!{col}{pf_refs['pf_ni']}/"
            f"({acq_shares}+'{deal_sheet}'!$D${deal_refs['new_shares']})"
        )
        c = ws.cell(row=r, column=col_idx, value=formula)
        styles.style_formula(c, number_format=styles.FMT_EUR_ACTUAL)
    pf_eps_row = r
    r += 1

    # Accretion / dilution
    layout.write_row_label(ws, r, "Accretion / (dilution) %",
                           "Accretion / (diluizione) %")
    for i in range(p):
        col = layout.year_col(i)
        col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{pf_eps_row}/{col}{std_eps_row}-1")
        styles.style_formula(c, number_format=styles.FMT_PCT_2DP)
        c.font = styles.font_subheader
        c.border = styles.BORDER_TOP_THIN

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"

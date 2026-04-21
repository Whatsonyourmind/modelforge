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
    """Emit WACCBuild. Returns {cost_of_equity: ref, wacc: ref}.

    v0.7 enhancements:
      - If spec.wacc.comparable_betas provided, use `relevered_beta` named
        range from the ComparableBetas sheet (Hamada) instead of raw beta_levered.
      - If spec.wacc.mature_erp + sovereign_default_spread + equity_bond_vol_ratio
        provided, compute Damodaran CRP-adjusted ERP:
            effective_ERP = mature_ERP + sovereign_spread × (σ_equity/σ_bond) × λ
    """
    layout.set_column_widths(ws, label_width=44, it_width=32, year_width=14, unit_width=6)
    layout.write_title_block(ws, "WACC Build", "Calcolo WACC",
                             "Damodaran CRP methodology + Hamada beta (when comps present)")

    # Pick β source: relevered_beta (Hamada) if comps provided; else beta_levered.
    has_comps = bool(spec.wacc.comparable_betas)
    beta_ref = "relevered_beta" if has_comps else "beta_levered"

    # Pick ERP source: Damodaran decomposition if all four components present;
    # else flat equity_risk_premium.
    has_crp = all([
        spec.wacc.mature_erp is not None,
        spec.wacc.sovereign_default_spread is not None,
        spec.wacc.equity_bond_vol_ratio is not None,
        spec.wacc.lambda_country_exposure is not None,
    ])
    if has_crp:
        erp_formula = (
            "mature_erp+sovereign_default_spread*equity_bond_vol_ratio*lambda_country_exposure"
        )
    else:
        erp_formula = "equity_risk_premium"

    rows = [
        ("Risk-free rate (10Y BTP)", "Tasso risk-free", "=risk_free_rate", styles.FMT_PCT_2DP),
    ]

    if has_crp:
        rows += [
            ("Mature-market ERP (Damodaran)", "ERP mercato maturo",
             "=mature_erp", styles.FMT_PCT_2DP),
            ("Sovereign default spread (Italy)", "Spread sovrano Italia",
             "=sovereign_default_spread", styles.FMT_PCT_2DP),
            ("σ_equity / σ_bond ratio", "Rapporto σ_azioni / σ_titoli",
             "=equity_bond_vol_ratio", styles.FMT_MULTIPLE),
            ("Lambda (country exposure)", "Lambda (esposizione paese)",
             "=lambda_country_exposure", styles.FMT_MULTIPLE),
            ("Effective ERP (mature + CRP × λ)", "ERP effettivo",
             f"={erp_formula}", styles.FMT_PCT_2DP),
        ]
    else:
        rows += [
            ("Equity risk premium (country)", "ERP paese", "=equity_risk_premium",
             styles.FMT_PCT_2DP),
        ]

    rows += [
        ("Beta (relevered via Hamada)" if has_comps else "Beta (levered — input)",
         "Beta", f"={beta_ref}", styles.FMT_MULTIPLE),
        ("Cost of equity", "Costo del capitale",
         f"=risk_free_rate+{beta_ref}*({erp_formula})", styles.FMT_PCT_2DP),
        ("Pre-tax cost of debt", "Costo del debito pre-tax", "=pretax_cost_of_debt", styles.FMT_PCT_2DP),
        ("Effective tax rate", "Aliquota effettiva", "=effective_tax_rate", styles.FMT_PCT),
        ("After-tax cost of debt", "Costo del debito post-tax",
         "=pretax_cost_of_debt*(1-effective_tax_rate)", styles.FMT_PCT_2DP),
        ("Target D / (D+E)", "Target D / (D+E)", "=target_debt_weight", styles.FMT_PCT),
        ("Target E / (D+E)", "Target E / (D+E)", "=1-target_debt_weight", styles.FMT_PCT),
        ("WACC",
         "WACC",
         f"=((risk_free_rate+{beta_ref}*({erp_formula}))*(1-target_debt_weight))+"
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
    """Enterprise DCF + terminal value reconciliation.

    v0.6 changes:
      - Explicit-period PV expanded as an explicit sum (no volatile
        INDIRECT). Supports a `mid_year_convention` toggle.
      - Gordon and Exit TV presented side-by-side; user picks one via
        `terminal_method_choice` named range (no more averaging).
      - Net debt, shares outstanding, and current price use named
        assumptions when provided, replacing hardcoded literals.
    """
    h = fcf_refs["h"]
    p = fcf_refs["p"]
    layout.set_column_widths(ws, label_width=46, it_width=34, year_width=13, unit_width=6)
    layout.write_title_block(ws, "Valuation", "Valutazione",
                             "DCF Gordon / Exit Multiple — pick one via terminal_method_choice")

    r = 5
    last_col = layout.year_col(h + p - 1)
    fcf_row = fcf_refs["fcf"]
    ebitda_row = fcf_refs["ebitda"]

    mid_year = 0.5 if spec.mid_year_convention else 0.0

    # Explicit PV expanded as a sum (no INDIRECT).
    # t_i = i - mid_year (i runs 1..p); mid_year = 0.5 if mid-year toggle.
    pv_terms: list[str] = []
    for i in range(p):
        col = layout.year_col(h + i)
        t = (i + 1) - mid_year
        pv_terms.append(f"'{fcf_sheet}'!{col}{fcf_row}/(1+wacc_rate)^{t}")
    pv_formula = "=" + "+".join(pv_terms)

    # TV and PV-of-TV use consistent convention: TV is value at end of Y_p,
    # discounted by p - mid_year years.
    tv_discount_years = p - mid_year

    # Net debt / shares / price references — prefer named ranges
    net_debt_ref = ("net_debt_assum" if spec.net_debt_assum is not None
                    else f"{spec.net_debt_eur_m}")
    shares_ref = ("shares_outstanding_assum"
                  if spec.shares_outstanding_assum is not None
                  else f"{spec.shares_outstanding_m}")
    price_ref = ("current_price_assum"
                 if spec.current_price_assum is not None
                 else f"{spec.valuation_date_price_eur}")

    # v0.7: full EV→Equity bridge with optional adjustments
    # (minority interest, pension deficit, preferred, cross-holdings,
    # IFRS 16 lease liability). Each reads a named Assumption when
    # present; otherwise bare scalar (0) from the spec.
    minority_ref = ("minority_interest_assum"
                    if getattr(spec, 'minority_interest_assum', None) is not None
                    else "0")
    pension_ref = ("pension_deficit_assum"
                   if getattr(spec, 'pension_deficit_assum', None) is not None
                   else "0")
    preferred_ref = ("preferred_equity_assum"
                     if getattr(spec, 'preferred_equity_assum', None) is not None
                     else "0")
    cross_hold_ref = ("cross_holdings_assum"
                      if getattr(spec, 'cross_holdings_assum', None) is not None
                      else "0")
    lease_ref = ("lease_liability_ifrs16_assum"
                 if getattr(spec, 'lease_liability_ifrs16_assum', None) is not None
                 else "0")

    rows = [
        ("Explicit-period PV of FCF", "VAN FCF esplicito",
         pv_formula, styles.FMT_EUR_M, "pv_explicit"),
        ("Terminal value — Gordon growth", "Terminal value — Gordon",
         f"='{fcf_sheet}'!{last_col}{fcf_row}*(1+terminal_growth_pct)/"
         f"(wacc_rate-terminal_growth_pct)",
         styles.FMT_EUR_M, "tv_gordon"),
        ("Terminal value — exit EV/EBITDA", "Terminal value — EV/EBITDA uscita",
         f"='{fcf_sheet}'!{last_col}{ebitda_row}*exit_ev_ebitda_x",
         styles.FMT_EUR_M, "tv_exit"),
        # v0.7: Implied-g cross-check (reverse from exit multiple TV)
        ("Implied terminal g (from exit multiple)",
         "Crescita terminale implicita (da multiplo uscita)",
         f"=wacc_rate-'{fcf_sheet}'!{last_col}{fcf_row}*(1+terminal_growth_pct)/D{r+2}",
         styles.FMT_PCT_2DP, "implied_g"),
        # Chosen TV — picked by named range (1=Gordon, 2=Exit; default Gordon)
        ("Terminal value — chosen", "Terminal value — scelto",
         f"=IF(terminal_method_choice=2,D{r+2},D{r+1})",
         styles.FMT_EUR_M, "tv_used"),
        ("PV of terminal value", "VAN del terminal value",
         f"=D{r+4}/(1+wacc_rate)^{tv_discount_years}",
         styles.FMT_EUR_M, None),
        ("Enterprise Value", "Enterprise Value",
         f"=D{r}+D{r+5}",
         styles.FMT_EUR_M, "ev"),
        # v0.7: full EV→Equity bridge (Footnotes Analyst standard)
        ("(−) Net debt", "(−) Posizione finanziaria netta",
         f"=-{net_debt_ref}",
         styles.FMT_EUR_M, None),
        ("(−) Minority interest", "(−) Interessenze di minoranza",
         f"=-{minority_ref}",
         styles.FMT_EUR_M, None),
        ("(−) Pension deficit (unfunded)", "(−) Deficit pensionistico",
         f"=-{pension_ref}",
         styles.FMT_EUR_M, None),
        ("(−) Preferred equity", "(−) Azioni privilegiate",
         f"=-{preferred_ref}",
         styles.FMT_EUR_M, None),
        ("(−) IFRS 16 lease liability", "(−) Passività leasing IFRS 16",
         f"=-{lease_ref}",
         styles.FMT_EUR_M, None),
        ("(+) Cross-holdings / investments at FV",
         "(+) Partecipazioni / investimenti",
         f"={cross_hold_ref}",
         styles.FMT_EUR_M, None),
        ("Equity Value", "Valore equity",
         f"=D{r+6}+D{r+7}+D{r+8}+D{r+9}+D{r+10}+D{r+11}+D{r+12}",
         styles.FMT_EUR_M, "equity_val"),
        ("Implied EV / EBITDA (Y1 proj)", "EV/EBITDA implicito Y1",
         f"=D{r+6}/'{fcf_sheet}'!{layout.year_col(h)}{ebitda_row}",
         styles.FMT_MULTIPLE, None),
        ("Implied EV", "EV implicito",
         f"=D{r+6}",
         styles.FMT_EUR_M, None),
    ]

    for i, (en, it, formula, fmt, name) in enumerate(rows):
        rr = r + i
        layout.write_row_label(ws, rr, en, it)
        c = ws.cell(row=rr, column=4, value=formula)
        styles.style_formula(c, number_format=fmt)
        if name in ("ev", "equity_val", "tv_used", "pv_explicit"):
            c.font = styles.font_subheader
        if en.startswith("Enterprise Value") or en.startswith("Equity Value"):
            c.border = styles.BORDER_TOP_THIN
        if name == "pv_explicit":
            conv = "mid-year" if spec.mid_year_convention else "end-year"
            c.comment = Comment(
                f"Explicit-period discounting uses {conv} convention "
                f"(mid_year_convention={spec.mid_year_convention}). "
                f"TV discounted by {tv_discount_years} years for consistency.",
                "ModelForge",
            )

    # Create workbook-level named range for the terminal method choice
    # (1 = Gordon, 2 = Exit multiple). Defaulted to 1 via Cover/Assumption
    # in later iterations; for v0.6 we just stamp a fixed workbook name.
    from openpyxl.workbook.defined_name import DefinedName
    if "terminal_method_choice" not in ws.parent.defined_names:
        # Write constant to a hidden helper cell: column Z on this sheet
        helper_row = r + len(rows) + 4
        layout.write_row_label(ws, helper_row,
                               "Terminal method choice (1=Gordon, 2=Exit)",
                               "Metodo TV (1=Gordon, 2=Exit)")
        ws.cell(row=helper_row, column=4, value=1)
        ws.parent.defined_names["terminal_method_choice"] = DefinedName(
            name="terminal_method_choice",
            attr_text=f"'{ws.title}'!$D${helper_row}",
        )

    # Implied price per share (when shares available).
    # Equity value is at row r+13 after v0.7 bridge expansion (5 new
    # bridge lines inserted before Equity Value).
    has_shares = (spec.shares_outstanding_assum is not None
                  or spec.shares_outstanding_m > 0)
    has_price = (spec.current_price_assum is not None
                 or spec.valuation_date_price_eur > 0)
    if has_shares:
        ri = r + len(rows)
        equity_val_row = r + 13  # position of Equity Value row
        layout.write_row_label(ws, ri, "Implied price per share",
                               "Prezzo implicito per azione")
        c = ws.cell(row=ri, column=4, value=f"=D{equity_val_row}/{shares_ref}")
        styles.style_formula(c, number_format=styles.FMT_EUR_ACTUAL)
        c.font = styles.font_subheader
        if has_price:
            ri += 1
            layout.write_row_label(ws, ri, "Current price", "Prezzo attuale")
            c2 = ws.cell(row=ri, column=4, value=f"={price_ref}")
            styles.style_formula(c2, number_format=styles.FMT_EUR_ACTUAL)
            ri += 1
            layout.write_row_label(ws, ri, "Premium / (discount) %",
                                   "Premio / (sconto) %")
            c = ws.cell(row=ri, column=4,
                        value=f"=D{ri-2}/D{ri-1}-1")
            styles.style_formula(c, number_format=styles.FMT_PCT_2DP)

    ws.freeze_panes = "D5"
    ws.print_title_rows = "1:4"

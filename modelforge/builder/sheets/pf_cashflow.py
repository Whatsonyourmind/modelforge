"""Project Finance cashflow sheet.

Construction phase: capex per year, IDC capitalized, no revenue.
Operating phase: revenue → opex → EBITDA → tax → CADS → debt service → dividends.

Layout: columns D..D+N where N = construction_years + operating_years.

v0.3: CFADS (DSCR numerator) unchanged; after pf_debt has emitted, the
template orchestrator calls `append_distributable_cash(ws, cashflow_refs,
debt_refs)` which adds:
    - Senior debt service (from DebtDSCR)
    - DSRA funding (from DebtDSCR)
    - Distributable cash to equity

DSRA funding is DOWNSTREAM of the DSCR check per market convention.
"""

from __future__ import annotations

import openpyxl.comments
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout
from modelforge.builder.i18n import L


def build(ws: Worksheet, spec, driver_refs: dict[str, str]) -> dict[str, str]:
    c = spec.horizon.construction_years
    o = spec.horizon.operating_years
    n = c + o

    layout.set_column_widths(ws, label_width=44, it_width=34, year_width=11, unit_width=6)
    layout.write_title_block(
        ws, title_en="Project Cash Flow", title_it="Flusso di cassa del progetto",
        subtitle=f"{c}y construction · {o}y operating · {spec.meta.currency} {spec.meta.unit_scale}",
    )
    layout.write_scenario_banner(ws, row=3)

    yr_row = 5
    ws.cell(row=yr_row, column=3, value="Phase").font = styles.font_subheader
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        phase = "C" if i < c else "O"
        yr = i + 1 if i < c else (i - c + 1)
        c_cell = ws.cell(row=yr_row, column=col_idx, value=f"{phase}{yr}")
        styles.style_header(c_cell)

    rows: dict[str, int] = {}
    r = 7

    # CONSTRUCTION
    layout.write_section_header(ws, r, "Construction phase", "Fase di costruzione")
    r += 1

    rows["capex"] = r
    layout.write_row_label(ws, r, "Capex (outflow)", "Capex (uscita)", indent=True)
    ws.cell(row=r, column=3, value=spec.meta.currency).font = styles.font_label_it
    capex_total = spec.construction.total_capex_eur_m.name
    for i in range(c):
        phasing = spec.construction.capex_phasing_pct[i].name
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=-{capex_total}*{phasing}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    for i in range(c, n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=0)
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 2

    # OPERATING
    layout.write_section_header(ws, r, "Operating phase", "Fase operativa")
    r += 1

    rows["revenue"] = r
    layout.write_row_label(ws, r, L("revenue").en, L("revenue").it)
    ws.cell(row=r, column=3, value=spec.meta.currency).font = styles.font_label_it
    yr1 = spec.operating.availability_payment_eur_m_yr1.name
    idx = spec.operating.revenue_indexation_pct.name
    # v0.8 US-240: panel degradation compounds into revenue when present.
    # Revenue_t = Revenue_{t-1} × (1 + indexation) × (1 − degradation).
    deg_assum = getattr(spec.operating, "panel_degradation_pct_annual", None)
    deg_factor = f"*(1-{deg_assum.name})" if deg_assum is not None else ""
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    for i in range(c, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i == c:
            cc = ws.cell(row=r, column=col_idx, value=f"={yr1}")
        else:
            prior_col = layout.year_col(i - 1)
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=${prior_col}${r}*(1+{idx}){deg_factor}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    if deg_assum is not None:
        ws.cell(row=r, column=4).comment = openpyxl.comments.Comment(
            f"Revenue compounds at (1+indexation)×(1−{deg_assum.name}) per "
            "year (panel degradation, solar PV convention 0.5% p.a. "
            "per manufacturer warranty).",
            "ModelForge",
        )
    r += 1

    # v0.8 US-241: P90 alternative revenue row (downside scenario used
    # by the debt sizer when debt_sizing_mode='dscr_target_p90').
    # P90 = P50 × (1 − p90_haircut). Held as a parallel row so both
    # P50 and P90 CFADS are available to the audit trail.
    p90_assum = getattr(spec.operating, "p90_revenue_haircut_pct", None)
    if p90_assum is not None:
        rows["revenue_p90"] = r
        layout.write_row_label(ws, r, "Revenue — P90 (downside, haircut)",
                               "Ricavi — P90 (scenario downside)", indent=True)
        for i in range(c):
            col_idx = ord(layout.year_col(i)) - ord("A") + 1
            ws.cell(row=r, column=col_idx, value=0)
        for i in range(c, n):
            col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=${col}${rows['revenue']}*(1-{p90_assum.name})")
            styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        ws.cell(row=r, column=4).comment = openpyxl.comments.Comment(
            "P90 revenue = P50 × (1 − p90_haircut). Used by debt sizer "
            "under dscr_target_p90 mode per Solargis/NREL bankability "
            "convention. Both P50 and P90 CFADS kept live for audit trail.",
            "ModelForge",
        )
        r += 1

    rows["opex"] = r
    layout.write_row_label(ws, r, "Opex (cost)", "Opex (costo)", indent=True)
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    for i in range(c, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-${col}${rows['revenue']}*opex_pct_revenue")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["ebitda"] = r
    layout.write_row_label(ws, r, L("ebitda").en, L("ebitda").it)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['revenue']}+${col}${rows['opex']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
    r += 1

    # v0.6: Full tax walk with D&A and interest shields.
    # D&A straight-line over the operating period, starting at COD.
    rows["da"] = r
    layout.write_row_label(ws, r, "D&A (straight-line)", "A&A (lineare)", indent=True)
    capex_total = spec.construction.total_capex_eur_m.name
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    for i in range(c, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=-{capex_total}/{o}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["ebit"] = r
    layout.write_row_label(ws, r, "EBIT", "EBIT", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebitda']}+${col}${rows['da']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Interest expense — placeholder; pf_debt will patch to cross-sheet ref.
    rows["interest"] = r
    layout.write_row_label(ws, r, "Interest expense (ref)",
                           "Oneri finanziari (rif.)", indent=True)
    for i in range(n):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=0)
        styles.style_xref(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Taxable income = EBIT + Interest (Interest is negative)
    rows["taxable"] = r
    layout.write_row_label(ws, r, "Taxable income", "Imponibile", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebit']}+${col}${rows['interest']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Tax — only positive taxable income is taxed (no NOL carry-forward yet)
    rows["tax"] = r
    layout.write_row_label(ws, r, "Taxes (on EBIT − Interest)",
                           "Imposte (su EBIT − Oneri)", indent=True)
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    for i in range(c, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-MAX(${col}${rows['taxable']},0)*effective_tax_rate")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # CFADS = EBITDA − cash taxes (simplified: no ΔWC, no maint capex for
    # a merchant solar SPV where both are negligible — documented at
    # the row label). Per Breaking Into Wall Street / Edward Bodmer
    # convention, the full formula is
    #   CFADS = EBITDA − cash taxes − ΔWC − maintenance capex
    rows["cads"] = r  # Cash Available for Debt Service
    layout.write_row_label(ws, r, "CFADS (= EBITDA − cash taxes)",
                           "CFADS (= EBITDA − imposte in cassa)")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=${col}${rows['ebitda']}+${col}${rows['tax']}")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    r += 1

    ws.freeze_panes = "D7"
    ws.print_title_rows = "5:5"
    ws.print_title_cols = "A:C"

    out = {f"{k}_row": str(v) for k, v in rows.items()}
    # Track where the distributable-cash section should begin (append later)
    out["_next_row"] = str(r + 1)
    return out


def append_distributable_cash(
    ws: Worksheet,
    spec,
    cashflow_refs: dict[str, str],
    debt_refs: dict[str, str],
    debt_sheet: str,
) -> dict[str, str]:
    """Append debt-service + DSRA + distributable-cash rows.

    Called by the template orchestrator AFTER pf_debt.build has emitted, so
    debt_refs are known. DSCR numerator stays CFADS (above); DSRA only
    affects distributable cash per market convention.
    """
    c = spec.horizon.construction_years
    o = spec.horizon.operating_years
    n = c + o

    r = int(cashflow_refs["_next_row"])

    layout.write_section_header(
        ws, r, "Waterfall — equity distributions", "Waterfall — distribuzioni equity",
    )
    r += 1

    debt_service_row = int(debt_refs["debt_service_row"])
    dsra_funding_row = int(debt_refs["dsra_funding_row"])
    cads_row = int(cashflow_refs["cads_row"])

    rows: dict[str, int] = {}

    # CADS passthrough for clarity
    rows["cads_ref"] = r
    layout.write_row_label(ws, r, "CADS (from above)", "CADS (dal sopra)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx, value=f"=${col}${cads_row}")
        styles.style_xref(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Debt service (cross-sheet pull, negative)
    rows["ds_pull"] = r
    layout.write_row_label(ws, r, "Senior debt service", "Servizio debito senior", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"='{debt_sheet}'!{col}{debt_service_row}")
        styles.style_xref(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # DSRA funding (cross-sheet pull, negative when funding, positive on release)
    rows["dsra_pull"] = r
    layout.write_row_label(ws, r, "DSRA funding / release", "DSRA finanziamento", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"='{debt_sheet}'!{col}{dsra_funding_row}")
        styles.style_xref(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # Distributable cash (gross, pre lock-up) = CADS + debt service + DSRA
    # (debt service is negative; DSRA funding is negative when funding)
    rows["distributable_gross"] = r
    layout.write_row_label(ws, r, "Distributable cash — pre lock-up",
                           "Cassa distribuibile — pre lock-up", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=(f"=${col}${rows['cads_ref']}"
                            f"+${col}${rows['ds_pull']}"
                            f"+${col}${rows['dsra_pull']}"))
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    # v0.8 US-244: Lock-up test pass flag — DSCR ≥ lock_up_threshold.
    # Reads DSCR from DebtDSCR sheet, threshold from named range.
    dscr_row = int(debt_refs.get("dscr_row", 0))
    rows["lockup_pass"] = r
    layout.write_row_label(ws, r, "Lock-up test pass (DSCR ≥ threshold)",
                           "Lock-up test — superato", indent=True)
    lockup_name = spec.covenant.lock_up_threshold.name
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i < c or dscr_row == 0:
            ws.cell(row=r, column=col_idx, value=0)
        else:
            cc = ws.cell(
                row=r, column=col_idx,
                value=(f"=IF('{debt_sheet}'!{col}{dscr_row}>="
                       f"{lockup_name},1,0)"),
            )
            styles.style_formula(cc, number_format=styles.FMT_INTEGER)
    r += 1

    # Distributable cash (net, post lock-up) = IF lock-up pass, gross; else 0
    rows["distributable"] = r
    layout.write_row_label(ws, r, "Distributable cash to equity (post lock-up)",
                           "Cassa distribuibile agli equity holder")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i < c or dscr_row == 0:
            cc = ws.cell(row=r, column=col_idx,
                         value=f"=${col}${rows['distributable_gross']}")
        else:
            cc = ws.cell(
                row=r, column=col_idx,
                value=(f"=IF(${col}${rows['lockup_pass']}=1,"
                       f"${col}${rows['distributable_gross']},0)"),
            )
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
        cc.font = styles.font_subheader
        cc.border = styles.BORDER_TOP_THIN
    ws.cell(row=r, column=4).comment = openpyxl.comments.Comment(
        "Distributable cash is blocked (=0) when DSCR < lock_up_threshold "
        "per bulge-bracket covenant standard. Gross pre-lock-up figure "
        "retained above for auditor inspection.",
        "ModelForge",
    )
    r += 1

    return {f"{k}_row": str(v) for k, v in rows.items()}

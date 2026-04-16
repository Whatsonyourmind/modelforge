"""Project Finance cashflow sheet.

Construction phase: capex per year, IDC capitalized, no revenue.
Operating phase: revenue → opex → EBITDA → tax → CADS → debt service → dividends.

Layout: columns D..D+N where N = construction_years + operating_years.
"""

from __future__ import annotations

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
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    for i in range(c, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if i == c:
            cc = ws.cell(row=r, column=col_idx, value=f"={yr1}")
        else:
            prior_col = layout.year_col(i - 1)
            cc = ws.cell(row=r, column=col_idx, value=f"=${prior_col}${r}*(1+{idx})")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
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

    # Tax (simplified on EBITDA; full PF models add D&A shield — omitted for brevity)
    rows["tax"] = r
    layout.write_row_label(ws, r, "Taxes (on EBITDA proxy)", "Imposte (proxy su EBITDA)", indent=True)
    for i in range(c):
        col_idx = ord(layout.year_col(i)) - ord("A") + 1
        ws.cell(row=r, column=col_idx, value=0)
    for i in range(c, n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        cc = ws.cell(row=r, column=col_idx,
                     value=f"=-MAX(${col}${rows['ebitda']},0)*effective_tax_rate")
        styles.style_formula(cc, number_format=styles.FMT_EUR_M)
    r += 1

    rows["cads"] = r  # Cash Available for Debt Service
    layout.write_row_label(ws, r, "CADS (Cash Available for Debt Service)", "CADS")
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
    return out

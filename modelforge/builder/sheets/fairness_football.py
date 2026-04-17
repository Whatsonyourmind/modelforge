"""Fairness football-field sheet (Template 11).

Emits three sheets:
    TradingComps       — comparable companies trading table with median / mean
    TransactionComps   — precedent transactions (if provided)
    FootballField      — methodology × (low, high) valuation ranges +
                         native Excel bar chart, premium/discount vs
                         current price.
"""

from __future__ import annotations

from openpyxl.chart import BarChart, Reference
from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout


def _write_comp_table(ws: Worksheet, title_en: str, title_it: str,
                      subtitle: str, comps, include_date: bool) -> None:
    layout.set_column_widths(ws, label_width=36, it_width=24, year_width=14, unit_width=8)
    layout.write_title_block(ws, title_en, title_it, subtitle)

    hr = 5
    headers = ["Company", "EV / EBITDA (x)", "EV / Revenue (x)"]
    if include_date:
        headers.append("Announced")
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=hr, column=i, value=h)
        styles.style_header(c)

    if not comps:
        ws.cell(row=hr + 1, column=1, value="(no items in spec)").font = styles.font_label_it
        ws.freeze_panes = f"A{hr + 1}"
        ws.print_title_rows = f"{hr}:{hr}"
        return

    r0 = hr + 1
    for i, it in enumerate(comps):
        r = r0 + i
        ws.cell(row=r, column=1, value=it.name).font = styles.font_label_en
        c1 = ws.cell(row=r, column=2, value=it.ev_ebitda_x)
        styles.style_input(c1, number_format=styles.FMT_MULTIPLE)
        c1.comment = Comment(f"{it.name} EV/EBITDA (from spec).", "ModelForge")
        c2 = ws.cell(row=r, column=3, value=it.ev_revenue_x)
        styles.style_input(c2, number_format=styles.FMT_MULTIPLE)
        c2.comment = Comment(f"{it.name} EV/Revenue (from spec).", "ModelForge")
        if include_date:
            ws.cell(row=r, column=4, value=it.date or "").font = styles.font_label_it
    r_last = r0 + len(comps) - 1

    # Summary row: median + mean
    r_sum = r_last + 2
    ws.cell(row=r_sum, column=1, value="Median").font = styles.font_subheader
    ws.cell(row=r_sum, column=2,
            value=f"=MEDIAN(B{r0}:B{r_last})").number_format = styles.FMT_MULTIPLE
    ws.cell(row=r_sum, column=3,
            value=f"=MEDIAN(C{r0}:C{r_last})").number_format = styles.FMT_MULTIPLE
    r_sum += 1
    ws.cell(row=r_sum, column=1, value="Mean").font = styles.font_subheader
    ws.cell(row=r_sum, column=2,
            value=f"=AVERAGE(B{r0}:B{r_last})").number_format = styles.FMT_MULTIPLE
    ws.cell(row=r_sum, column=3,
            value=f"=AVERAGE(C{r0}:C{r_last})").number_format = styles.FMT_MULTIPLE

    ws.freeze_panes = f"A{r0}"
    ws.print_title_rows = f"{hr}:{hr}"


def build_trading_comps(ws: Worksheet, spec) -> None:
    _write_comp_table(ws, "Trading Comps", "Comparabili quotati",
                      "Public comparable companies",
                      spec.trading_comps, include_date=False)


def build_transaction_comps(ws: Worksheet, spec) -> None:
    _write_comp_table(ws, "Transaction Comps", "Transazioni comparabili",
                      "Precedent M&A transactions",
                      spec.transaction_comps, include_date=True)


def build_football_field(ws: Worksheet, spec) -> None:
    layout.set_column_widths(ws, label_width=44, it_width=28, year_width=14, unit_width=6)
    layout.write_title_block(ws, "Football Field", "Football Field",
                             "Valuation range by methodology")

    hr = 5
    headers = ["Methodology", "EV low (€m)", "EV high (€m)",
               "Mid (€m)", "Equity low (€m)", "Equity high (€m)"]
    if spec.shares_outstanding_m > 0 and spec.current_price_eur > 0:
        headers += ["Implied price low (€)", "Implied price high (€)",
                    "Premium low", "Premium high"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=hr, column=i, value=h)
        styles.style_header(c)

    r0 = hr + 1
    for i, vr in enumerate(spec.valuation_ranges):
        r = r0 + i
        ws.cell(row=r, column=1, value=vr.method).font = styles.font_label_en
        c_low = ws.cell(row=r, column=2, value=vr.ev_low_eur_m)
        styles.style_input(c_low, number_format=styles.FMT_EUR_M)
        c_low.comment = Comment(
            f"{vr.method} low bound — {vr.note or 'no note'}",
            "ModelForge",
        )
        c_high = ws.cell(row=r, column=3, value=vr.ev_high_eur_m)
        styles.style_input(c_high, number_format=styles.FMT_EUR_M)
        c_high.comment = Comment(
            f"{vr.method} high bound — {vr.note or 'no note'}",
            "ModelForge",
        )
        # Mid
        cm = ws.cell(row=r, column=4, value=f"=AVERAGE(B{r},C{r})")
        styles.style_formula(cm, number_format=styles.FMT_EUR_M)
        # Equity bounds (EV − net debt)
        el = ws.cell(row=r, column=5, value=f"=B{r}-{spec.net_debt_eur_m}")
        styles.style_formula(el, number_format=styles.FMT_EUR_M)
        eh = ws.cell(row=r, column=6, value=f"=C{r}-{spec.net_debt_eur_m}")
        styles.style_formula(eh, number_format=styles.FMT_EUR_M)
        if spec.shares_outstanding_m > 0 and spec.current_price_eur > 0:
            pl = ws.cell(row=r, column=7,
                         value=f"=E{r}/{spec.shares_outstanding_m}")
            styles.style_formula(pl, number_format=styles.FMT_EUR_ACTUAL)
            ph = ws.cell(row=r, column=8,
                         value=f"=F{r}/{spec.shares_outstanding_m}")
            styles.style_formula(ph, number_format=styles.FMT_EUR_ACTUAL)
            ws.cell(row=r, column=9,
                    value=f"=G{r}/{spec.current_price_eur}-1").number_format = styles.FMT_PCT_2DP
            ws.cell(row=r, column=10,
                    value=f"=H{r}/{spec.current_price_eur}-1").number_format = styles.FMT_PCT_2DP

    r_last = r0 + len(spec.valuation_ranges) - 1

    # ── Football field bar chart (EV low/high per methodology)
    chart = BarChart()
    chart.type = "bar"
    chart.style = 11
    chart.title = "Football field — EV range by methodology"
    chart.y_axis.title = "Method"
    chart.x_axis.title = "EV (€m)"
    chart.overlap = 100

    low_ref = Reference(ws, min_col=2, min_row=hr, max_col=2, max_row=r_last)
    high_ref = Reference(ws, min_col=3, min_row=hr, max_col=3, max_row=r_last)
    chart.add_data(low_ref, titles_from_data=True)
    chart.add_data(high_ref, titles_from_data=True)
    cats = Reference(ws, min_col=1, min_row=r0, max_col=1, max_row=r_last)
    chart.set_categories(cats)
    chart.height = max(8, 0.7 * (r_last - r0 + 1))
    chart.width = 18
    ws.add_chart(chart, f"L{hr}")

    ws.freeze_panes = f"A{r0}"
    ws.print_title_rows = f"{hr}:{hr}"

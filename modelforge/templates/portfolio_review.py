"""Portfolio Review template — Template 16 (v0.10 PREVIEW).

Aggregator template: N portfolio companies × monitoring metrics in one
workbook. Different shape from single-deal templates — does not use
build_base_workbook framework.

v0.10: minimal renderer (Cover + Portfolio matrix + Aggregate summary + QC).
v0.11: sparklines, heatmaps, exception flagging.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from modelforge.builder import layout, styles
from modelforge.builder.i18n import L


def build(spec, out_path: Path | str, graph_db_path=None):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    wb.remove(wb.active)

    _build_cover_sheet(wb, spec)
    _build_portfolio_matrix_sheet(wb, spec)
    _build_aggregate_summary_sheet(wb, spec)
    _build_qc_sheet(wb, spec)

    wb.save(out_path)

    # Portfolio review template doesn't use the linkage graph (no formulas
    # cross-reference per-portco rows). Return a null graph path so the
    # registry signature stays consistent.
    return out_path, out_path.with_suffix(".graph.db")


def _build_cover_sheet(wb, spec) -> None:
    ws = wb.create_sheet("Cover")
    layout.set_column_widths(ws, label_width=28, it_width=28, year_width=18)
    layout.write_title_block(
        ws,
        title_en=f"{spec.fund_name} — Portfolio Review {spec.review_quarter}",
        title_it=f"{spec.fund_name} — Riepilogo portafoglio {spec.review_quarter}",
        subtitle=f"{spec.meta.confidentiality} · {spec.meta.status.upper()} · {spec.meta.version}",
    )

    rows = [
        ("Fund", "Fondo", spec.fund_name),
        ("Vintage", "Annata", str(spec.fund_vintage) if spec.fund_vintage else ""),
        ("AUM (in unit_scale)", "AUM", str(spec.fund_aum) if spec.fund_aum else ""),
        ("Review quarter", "Trimestre", spec.review_quarter),
        ("Portfolio companies", "Società in portafoglio", str(len(spec.portfolio))),
        ("Analyst", "Analista", spec.meta.analyst),
        ("Valuation date", "Data valutazione", spec.meta.valuation_date.isoformat()),
        ("Version", "Versione", spec.meta.version),
    ]
    r = 4
    for en, it, val in rows:
        layout.write_row_label(ws, r, en, it)
        ws.cell(row=r, column=3, value=val)
        r += 1


def _build_portfolio_matrix_sheet(wb, spec) -> None:
    """N rows (one per portco) × M columns (metrics)."""
    ws = wb.create_sheet("Portfolio")
    layout.set_column_widths(ws, label_width=22, it_width=22, year_width=14)

    layout.write_title_block(
        ws,
        title_en="Portfolio Matrix",
        title_it="Matrice del portafoglio",
        subtitle="One row per portfolio company. Sort/filter as needed.",
    )

    # Header row at row 4
    headers = [
        "ID", "Name", "Sector", "Country",
        "Entry Lev", "Curr Lev",
        "Plan EBITDA (Q)", "Actual EBITDA (Q)", "Δ % vs Plan",
        "Cov Cushion %", "Cash Trap", "Rating",
        "Next Cov Test", "Narrative",
    ]
    r = 4
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=r, column=c, value=h)
        styles.style_label_en(cell)

    # Data rows
    for i, portco in enumerate(spec.portfolio):
        r = 5 + i
        cells_data = [
            portco.portco_id, portco.name, portco.sector, portco.country,
            portco.entry_leverage, portco.current_leverage,
            portco.plan_ebitda_q, portco.actual_ebitda_q,
            # Δ% vs Plan as formula
            None,
            portco.covenant_cushion_pct,
            "YES" if portco.cash_trap_active else "no",
            portco.rating_internal or "",
            portco.next_covenant_test_date.isoformat() if portco.next_covenant_test_date else "",
            portco.narrative,
        ]
        for c, v in enumerate(cells_data, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            # Δ% vs Plan: formula at column 9
            if c == 9 and portco.plan_ebitda_q and portco.actual_ebitda_q:
                # Excel cells use 1-indexed column letters
                from openpyxl.utils import get_column_letter
                plan_col = get_column_letter(7)
                actual_col = get_column_letter(8)
                cell.value = f"={actual_col}{r}/{plan_col}{r}-1"
                cell.number_format = "0.00%"


def _build_aggregate_summary_sheet(wb, spec) -> None:
    """Roll-up summary across the portfolio."""
    ws = wb.create_sheet("Summary")
    layout.set_column_widths(ws, label_width=34, it_width=30, year_width=18)
    layout.write_title_block(
        ws,
        title_en="Aggregate Summary",
        title_it="Riepilogo aggregato",
        subtitle="Roll-up metrics across the portfolio.",
    )

    n = len(spec.portfolio)
    lev_values = [p.current_leverage for p in spec.portfolio if p.current_leverage is not None]
    cushion_values = [p.covenant_cushion_pct for p in spec.portfolio if p.covenant_cushion_pct is not None]
    cash_traps = sum(1 for p in spec.portfolio if p.cash_trap_active)
    rating_dist: dict[str, int] = {}
    for p in spec.portfolio:
        if p.rating_internal:
            rating_dist[p.rating_internal] = rating_dist.get(p.rating_internal, 0) + 1

    rows = [
        ("Total portfolio companies", "Totale società", n),
        ("Avg current leverage (×)", "Leva media corrente (×)",
         round(sum(lev_values) / len(lev_values), 2) if lev_values else "n/a"),
        ("Max current leverage (×)", "Leva max corrente (×)",
         round(max(lev_values), 2) if lev_values else "n/a"),
        ("Min covenant cushion %", "Min cushion covenant %",
         round(min(cushion_values), 1) if cushion_values else "n/a"),
        ("Cash-trap-active portcos", "Portco con cash-trap attivo", cash_traps),
        ("Rating 1 (outperform)", "Rating 1", rating_dist.get("1", 0)),
        ("Rating 2", "Rating 2", rating_dist.get("2", 0)),
        ("Rating 3 (on-plan)", "Rating 3 (on-plan)", rating_dist.get("3", 0)),
        ("Rating 4 (watch)", "Rating 4 (watch)", rating_dist.get("4", 0)),
        ("Rating 5 (workout)", "Rating 5 (workout)", rating_dist.get("5", 0)),
    ]
    r = 4
    for en, it, val in rows:
        layout.write_row_label(ws, r, en, it)
        c = ws.cell(row=r, column=3, value=val)
        if isinstance(val, float):
            c.number_format = "#,##0.00"
        r += 1


def _build_qc_sheet(wb, spec) -> None:
    """Minimal QC — every portco has portco_id + name; covenant cushion in plausible range."""
    ws = wb.create_sheet("QC")
    layout.write_title_block(
        ws,
        title_en="QC checks",
        title_it="Controlli QC",
        subtitle="Portfolio review v0.10 PREVIEW — minimal check set.",
    )
    layout.set_column_widths(ws, label_width=50, it_width=40, year_width=12)

    checks = [
        (
            f"All {len(spec.portfolio)} portcos have portco_id + name",
            f"Tutte le {len(spec.portfolio)} portco hanno ID + nome",
            all(p.portco_id and p.name for p in spec.portfolio),
        ),
        (
            "No duplicate portco_ids",
            "Nessun ID duplicato",
            len({p.portco_id for p in spec.portfolio}) == len(spec.portfolio),
        ),
        (
            "Covenant cushion %, when present, is in [-100, 500] range",
            "Cushion in range plausibile",
            all(
                (p.covenant_cushion_pct is None or -100.0 <= p.covenant_cushion_pct <= 500.0)
                for p in spec.portfolio
            ),
        ),
        (
            "Current leverage, when present, is positive",
            "Leva corrente positiva",
            all(
                (p.current_leverage is None or p.current_leverage > 0)
                for p in spec.portfolio
            ),
        ),
    ]
    r = 4
    for en, it, ok in checks:
        layout.write_row_label(ws, r, en, it)
        c = ws.cell(row=r, column=3, value="PASS" if ok else "FAIL")
        styles.style_label_en(c)
        r += 1

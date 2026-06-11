"""HGB Carve-out template — Template 15 (v0.11 BETA).

⚠️ v0.11 BETA — first-cut Hinzurechnungen + GewSt math shipped.
   DTA/DTL recon refinement, § 252-256 Anlagevermögen valuation rules,
   BilMoG pension provisions remain v0.12 scope.
   DACH accounting-expert review recommended before production use.

FEATURE SCOPE (honest-label): this is a 3-statement model + a German
   tax-overlay (HGB ↔ IFRS reconciliation with § 8 GewStG + GewSt build). It
   does NOT ship a carve-out EV bridge (standalone-EBITDA bridge → EV via
   multiple/DCF) or a TSA time-boundary. That boundary is stated in the
   HGB-Recon "Out-of-scope" section so the deliverable cannot silently
   overclaim a full carve-out valuation.

Pattern: this template wraps the existing 3-statement builder, forcing the
secondary language to DE, and appends an HGB-Reconciliation worksheet that
implements § 8 GewStG Hinzurechnungen and a per-period Gewerbesteuer build
that flows back to the effective-tax-rate reconciliation.
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import layout, styles
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.i18n import apply_runtime_secondary_lang, reset_runtime_secondary_lang
from modelforge.builder.sheets import compliance as compliance_sheet, generic_qc, ts_model


def _build_hgb_recon_sheet(wb, spec, ts_refs: dict) -> None:
    """Append HGB-Reconciliation worksheet with real § 8 GewStG math.

    Sections:
      1. § 8 GewStG Hinzurechnungen (interest add-back)
      2. Gewerbesteuer build (per-period)
      3. Effective tax rate reconciliation (KSt + SolZ + GewSt vs spec)
      4. Notes — v0.12 scope (DTA/DTL refinement, § 252-256, BilMoG)
    """
    ws = wb.create_sheet("HGB-Recon")
    layout.set_column_widths(ws, label_width=48, it_width=42, year_width=14)
    layout.write_title_block(
        ws,
        title_en="HGB ↔ IFRS Reconciliation (v0.11 BETA)",
        title_it="Überleitung HGB ↔ IFRS (Beta v0.11)",
        subtitle="§ 8 GewStG Hinzurechnungen + Gewerbesteuer build + effective-tax-rate reconciliation.",
    )

    hebesatz = (
        spec.hgb_assumptions.gewerbesteuer_hebesatz
        if spec.hgb_assumptions is not None else 400.0
    )
    soli = (
        spec.hgb_assumptions.soli_applicable
        if spec.hgb_assumptions is not None else True
    )

    h = spec.horizon.historical_years
    n = h + spec.horizon.projection_years

    interest_row = int(ts_refs["interest_row"])
    ebit_row = int(ts_refs["ebit_row"])
    ebt_row = int(ts_refs["ebt_row"])
    tax_row = int(ts_refs["tax_row"])
    ni_row = int(ts_refs["net_income_row"])

    # Year columns — Hinzurechnungen written into the same column layout.
    # Year header at row 4
    r = 4
    ws.cell(row=r, column=1, value="Year / Periode").font = styles.font_header
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        is_hist = i < h
        year_label = f"FY{i - h + 1:+d}" if not is_hist else f"H{i + 1}"
        ws.cell(row=r, column=col_idx, value=year_label).font = styles.font_header
    r += 1

    # ── Section 1: § 8 GewStG Hinzurechnungen ────────────────────────────
    r += 1
    layout.write_section_header(
        ws, r,
        "§ 8 GewStG Hinzurechnungen (interest add-back)",
        "Hinzurechnungen § 8 GewStG (Zinsen)",
    )
    r += 1

    # Row: Cash interest expense (pulled from Model)
    layout.write_row_label(
        ws, r,
        "Cash interest expense (from Model)",
        "Cash-Zinsaufwand (aus Modell)",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        # Interest expense is negative in the Model (cost convention) — abs() it
        c = ws.cell(row=r, column=col_idx,
                    value=f"=ABS('Model'!{col}{interest_row})")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    interest_abs_row = r
    r += 1

    # Row: Threshold (€100k = €0.1m at unit_scale=millions)
    layout.write_row_label(
        ws, r,
        "Freibetrag § 8 Nr. 1 GewStG (€100k)",
        "Freibetrag § 8 Nr. 1 GewStG",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx, value=0.1)  # €100k at unit_scale=millions
        styles.style_input(c, number_format=styles.FMT_EUR_M)
    threshold_row = r
    r += 1

    # Row: Excess interest (above threshold)
    layout.write_row_label(
        ws, r,
        "Excess interest above threshold",
        "Übersteigender Betrag",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(
            row=r, column=col_idx,
            value=f"=MAX(0,{col}{interest_abs_row}-{col}{threshold_row})",
        )
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    excess_row = r
    r += 1

    # Row: Hinzurechnung (25% of excess)
    layout.write_row_label(
        ws, r,
        "Hinzurechnung (25% of excess) → Gewerbeertrag",
        "Hinzurechnung 25% → Gewerbeertrag",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=0.25*{col}{excess_row}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    hinzu_row = r
    r += 2

    # ── Section 2: Gewerbesteuer build ─────────────────────────────────
    layout.write_section_header(
        ws, r,
        f"Gewerbesteuer build (Hebesatz {hebesatz:.0f}%)",
        f"Gewerbesteuer-Berechnung (Hebesatz {hebesatz:.0f}%)",
    )
    r += 1

    # Row: Gewerbeertrag = EBIT + Hinzurechnungen
    layout.write_row_label(
        ws, r,
        "Gewerbeertrag (EBIT + Hinzurechnungen)",
        "Gewerbeertrag",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(
            row=r, column=col_idx,
            value=f"=MAX(0,'Model'!{col}{ebit_row}+{col}{hinzu_row})",
        )
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    gew_ertrag_row = r
    r += 1

    # Row: Steuermesszahl 3.5%
    layout.write_row_label(
        ws, r,
        "Steuermesszahl 3.5%",
        "Steuermesszahl 3,5%",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=0.035*{col}{gew_ertrag_row}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    messzahl_row = r
    r += 1

    # Row: Gewerbesteuer = Messzahl × Hebesatz (Hebesatz stored as %, e.g. 400% = 4.00)
    layout.write_row_label(
        ws, r,
        f"Gewerbesteuer (× Hebesatz {hebesatz:.0f}%)",
        f"Gewerbesteuer (Hebesatz {hebesatz:.0f}%)",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"={col}{messzahl_row}*{hebesatz/100:.4f}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    gewst_row = r
    r += 2

    # ── Section 3: Effective tax rate reconciliation ─────────────────────
    layout.write_section_header(
        ws, r,
        "Effective tax rate reconciliation (KSt + SolZ + GewSt vs spec)",
        "Effektiver Steuersatz — Überleitung",
    )
    r += 1

    # KSt 15%
    layout.write_row_label(ws, r, "KSt 15% × EBT", "KSt 15% × EBT", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx,
                    value=f"=0.15*MAX(0,'Model'!{col}{ebt_row})")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    kst_row = r
    r += 1

    # SolZ 5.5% × KSt (if applicable)
    layout.write_row_label(
        ws, r,
        f"SolZ {'5.5%' if soli else 'n/a'} × KSt",
        f"SolZ {'5,5%' if soli else 'n. a.'} × KSt",
        indent=True,
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        coef = 0.055 if soli else 0.0
        c = ws.cell(row=r, column=col_idx,
                    value=f"={coef}*{col}{kst_row}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    solz_row = r
    r += 1

    # GewSt (reference)
    layout.write_row_label(ws, r, "GewSt (from above)", "GewSt (siehe oben)", indent=True)
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(row=r, column=col_idx, value=f"={col}{gewst_row}")
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    gewst_ref_row = r
    r += 1

    # Total tax = KSt + SolZ + GewSt
    layout.write_row_label(ws, r, "Total HGB-computed tax", "Steueraufwand HGB-berechnet")
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(
            row=r, column=col_idx,
            value=f"={col}{kst_row}+{col}{solz_row}+{col}{gewst_ref_row}",
        )
        styles.style_formula(c, number_format=styles.FMT_EUR_M)
    total_tax_row = r
    r += 1

    # Effective rate = total_tax / EBT
    layout.write_row_label(
        ws, r,
        "Effective tax rate (HGB-computed)",
        "Effektivsteuersatz HGB-berechnet",
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        c = ws.cell(
            row=r, column=col_idx,
            value=f"=IFERROR({col}{total_tax_row}/'Model'!{col}{ebt_row},0)",
        )
        styles.style_formula(c, number_format="0.0%")
    eff_rate_row = r
    r += 1

    # Spec-supplied rate
    layout.write_row_label(
        ws, r,
        "Effective tax rate (spec assumption)",
        "Effektivsteuersatz Spec",
    )
    spec_eff_rate = None
    if hasattr(spec, "pl") and hasattr(spec.pl, "effective_tax_rate"):
        try:
            spec_eff_rate = spec.pl.effective_tax_rate.base
        except AttributeError:
            spec_eff_rate = None
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        v = spec_eff_rate if spec_eff_rate is not None else "n/a"
        c = ws.cell(row=r, column=col_idx, value=v)
        if isinstance(v, (int, float)):
            styles.style_input(c, number_format="0.0%")
    r += 1

    # Delta
    layout.write_row_label(
        ws, r,
        "Δ (HGB-computed − spec)",
        "Δ (HGB − Spec)",
    )
    for i in range(n):
        col = layout.year_col(i); col_idx = ord(col) - ord("A") + 1
        if spec_eff_rate is not None:
            c = ws.cell(
                row=r, column=col_idx,
                value=f"={col}{eff_rate_row}-{spec_eff_rate}",
            )
            styles.style_formula(c, number_format="0.0%;[Red]-0.0%")
    r += 2

    # ── Section 4: Notes — v0.12 scope ────────────────────────────────
    layout.write_section_header(
        ws, r,
        "Out-of-scope for v0.11 (v0.12 roadmap)",
        "Außerhalb v0.11 — Roadmap v0.12",
    )
    r += 1
    notes = [
        ("Carve-out EV bridge & standalone EBITDA bridge (NOT shipped)",
         "Carve-out-EV-Brücke / Standalone-EBITDA-Brücke (nicht enthalten)"),
        ("Anlagevermögen valuation",
         "Bewertung HGB §§ 252-256 vs IFRS 16 / IAS 36 (impairment)"),
        ("Inventory — strenges Niederstwertprinzip",
         "Vorräte: HGB strenges Niederstwertprinzip vs IAS 2 (NRV)"),
        ("Pension provisions — BilMoG vs IAS 19",
         "Pensionsrückstellungen: BilMoG vs IAS 19 (Diskontsatz, Biometrie)"),
        ("Latente Steuern — § 274 Aktivierungswahlrecht",
         "DTA-Aktivierungswahlrecht (§ 274 HGB) vs IAS 12 (Pflicht)"),
        ("Ausschüttungssperre § 268 (8)",
         "Ausschüttungssperre § 268 Abs. 8 HGB"),
        ("Real-estate & license-fee Hinzurechnungen",
         "Hinzurechnungen Mieten/Pachten/Lizenzen (§ 8 Nr. 1 d/e/f GewStG)"),
    ]
    for en, de in notes:
        ws.cell(row=r, column=1, value=en).font = styles.font_label_en
        ws.cell(row=r, column=2, value=de).font = styles.font_label_it
        r += 1

    # Freeze panes at first year column
    ws.freeze_panes = "D5"


def build(spec, out_path: Path | str, graph_db_path=None):
    """Build an HGB carve-out workbook.

    Forces secondary_lang="de" so all rendered labels are German.
    Renders 3-statement base + HGB-Recon sheet (§ 8 GewStG + ETR recon).
    """
    apply_runtime_secondary_lang("de")
    try:
        # Use a mutable holder so the inner core_sheets closure can pass
        # ts_refs out to the outer scope for the HGB-Recon sheet.
        _captured: dict = {}

        def core_sheets(wb, spec, graph, driver_refs, source_rows):
            ts_ws = wb.create_sheet("Model")
            ts_refs = ts_model.build(ts_ws, spec, driver_refs)
            _captured["ts_refs"] = ts_refs

            h = spec.horizon.historical_years
            n = h + spec.horizon.projection_years
            last_col = layout.year_col(n - 1)
            check_row = int(ts_refs["bs_check_row"])
            ta_row = int(ts_refs["total_assets_row"])
            tle_row = int(ts_refs["total_le_row"])

            checks = [
                ("BS balances every period (|A-L-E|<0.01)",
                 "Bilanzgleichgewicht je Periode",
                 f"=IF(SUMPRODUCT((ABS('Model'!D{check_row}:{last_col}{check_row})<=0.01)*1)={n},1,0)"),
                ("Total Assets > 0 every period", "Aktivsumme > 0 je Periode",
                 f"=IF(SUMPRODUCT(('Model'!D{ta_row}:{last_col}{ta_row}>0)*1)={n},1,0)"),
                ("Total L&E > 0 every period", "Passivsumme > 0 je Periode",
                 f"=IF(SUMPRODUCT(('Model'!D{tle_row}:{last_col}{tle_row}>0)*1)={n},1,0)"),
            ]
            qc_ws = wb.create_sheet("QC")
            generic_qc.build(qc_ws, checks)

            _build_hgb_recon_sheet(wb, spec, ts_refs)

            compliance_ws = wb.create_sheet("ComplianceCheck")
            compliance_sheet.build(compliance_ws, spec)

            return {}

        result = build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]
    finally:
        reset_runtime_secondary_lang()

    return result

"""HGB Carve-out template — Template 15 (v0.10 PREVIEW).

⚠️ v0.10 PREVIEW — STRUCTURAL SKELETON ONLY.
   Requires DACH accounting-expert review before production use.
   See modelforge/spec/hgb_carveout.py for the reference list.

Pattern: this template wraps the existing 3-statement builder, forcing the
secondary language to DE, and appends an HGB-Reconciliation worksheet that
documents the IFRS-to-HGB delta block (currently placeholders).

When v0.11 ships the full DTA/DTL math, this template gets a real
recon-build path; the SaaS shell auto-picks-up the upgrade with no spec
change required.
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import layout, styles
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.i18n import apply_runtime_secondary_lang, reset_runtime_secondary_lang
from modelforge.builder.sheets import compliance as compliance_sheet, generic_qc, ts_model


def _build_hgb_recon_sheet(wb, spec) -> None:
    """Append HGB-Reconciliation worksheet — v0.10 PREVIEW placeholder.

    Documents the IFRS-to-HGB reconciliation areas an analyst would have to
    fill in by hand today. v0.11 will replace this with formulas + driver
    rows for each line.
    """
    ws = wb.create_sheet("HGB-Recon")
    layout.write_title_block(
        ws,
        title_en="HGB ↔ IFRS Reconciliation (v0.10 PREVIEW)",
        title_it="Überleitung HGB ↔ IFRS (Vorschau v0.10)",
        subtitle="Structural skeleton — requires DACH accounting-expert completion.",
    )

    rows = [
        ("Section", "Beschreibung / Description", "v0.10 status"),
        ("Anlagevermögen / Long-term assets",
         "Bewertung HGB §§ 252-256 vs IFRS 16 / IAS 36 (impairment)", "placeholder"),
        ("Vorräte / Inventory",
         "HGB Strenges Niederstwertprinzip vs IAS 2 (NRV)", "placeholder"),
        ("Pensionsrückstellungen / Pension provisions",
         "BilMoG-Bewertung vs IAS 19 (discount rate, biometrics)", "placeholder"),
        ("Latente Steuern / Deferred taxes",
         "DTA aktivierungswahlrecht (§ 274) vs IAS 12 (mandatory)", "placeholder"),
        ("Rückstellungen / Provisions",
         "HGB voraussichtliche Verpflichtung vs IAS 37 (probable + measurable)", "placeholder"),
        ("Eigenkapital / Equity",
         "Gewinnrücklage vs Retained earnings — Ausschüttungssperre § 268 (8)", "placeholder"),
        ("Gewerbesteuer / Trade tax",
         "Hinzurechnungen § 8 GewStG (Zinsen, Mieten) — Hebesatz-abhängig", f"hebesatz: {spec.hgb_assumptions.gewerbesteuer_hebesatz if spec.hgb_assumptions else 400}%"),
    ]
    r = 4
    for en, de, status in rows:
        ws.cell(row=r, column=1, value=en).font = styles.font_label_en
        ws.cell(row=r, column=2, value=de).font = styles.font_label_it
        ws.cell(row=r, column=3, value=status).font = styles.font_label_en
        r += 1

    r += 2
    note = ws.cell(
        row=r, column=1,
        value="v0.10 PREVIEW — this sheet documents the IFRS-to-HGB recon "
              "scope. v0.11 ships DTA/DTL math + § 252-256 valuation rules + "
              "Hebesatz-localized GewSt build. Until then, treat the IFRS "
              "numbers from the 'Model' sheet as the canonical figures and "
              "use this sheet as an analyst checklist."
    )
    note.font = styles.font_label_en
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)


def build(spec, out_path: Path | str, graph_db_path=None):
    """Build an HGB carve-out workbook.

    Forces secondary_lang="de" so all rendered labels are German.
    Renders 3-statement base + HGB-Recon stub sheet.
    """
    # Apply DE secondary language for the duration of this build.
    apply_runtime_secondary_lang("de")
    try:
        def core_sheets(wb, spec, graph, driver_refs, source_rows):
            ts_ws = wb.create_sheet("Model")
            ts_refs = ts_model.build(ts_ws, spec, driver_refs)

            h = spec.horizon.historical_years
            n = h + spec.horizon.projection_years
            last_col = layout.year_col(n - 1)
            check_row = int(ts_refs["bs_check_row"])
            ni_row = int(ts_refs["net_income_row"])
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

            _build_hgb_recon_sheet(wb, spec)

            compliance_ws = wb.create_sheet("ComplianceCheck")
            compliance_sheet.build(compliance_ws, spec)

            return {}

        result = build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]
    finally:
        # Restore default Italian secondary so subsequent non-HGB builds
        # render correctly.
        reset_runtime_secondary_lang()

    return result

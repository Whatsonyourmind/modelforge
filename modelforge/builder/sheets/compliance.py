"""Italian / EU regulatory compliance checks.

Adds a dedicated `ComplianceCheck` sheet to any credit / PF / NPL / SC
workbook. Encodes the quantitative tests a BaFin / ECB / Banca d'Italia
supervisor would run on AIFM activity or a Basel NPL / securitization
capital computation.

Sections:
  1. AIFMD II leverage & concentration tests (Art. 15a + Art. 17)
  2. Loan-originating AIF classification (>50% NAV test)
  3. IFRS 9 three-stage ECL recap (summary)
  4. Basel III/IV NPL calendar provisioning (Reg. EU 2019/630)
  5. GACS eligibility (NPL only)
  6. IRES + IRAP split (tax transparency)

References cited inline:
  - BCLP "AIFMD II Leverage Limits" (April 2024 transposition)
  - Linklaters "Loan Origination under AIFMD II"
  - Clifford Chance / Dechert guidance
  - BIS IFRS 9 FSI summary
  - Regulation (EU) 2019/630 (calendar provisioning)
  - KPMG / Jones Day GACS
  - PwC Italy IRES/IRAP tax summaries
"""

from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles, layout


def build(ws: Worksheet, spec, context: dict | None = None) -> None:
    """Emit ComplianceCheck sheet.

    `context` may carry fund-level parameters (NAV, total_commitments) when
    applicable; absent fields render as informational placeholders.
    """
    context = context or {}

    layout.set_column_widths(ws, label_width=54, it_width=32, year_width=14, unit_width=8)
    layout.write_title_block(
        ws, "Compliance Check", "Controllo di conformità",
        "AIFMD II / IFRS 9 / Basel III-IV / GACS — Italian & EU regulatory plumbing",
    )

    r = 5

    # ─── Section 1: AIFMD II leverage & concentration ──────────────────────
    layout.write_section_header(ws, r, "AIFMD II leverage & concentration",
                                 "AIFMD II leva & concentrazione")
    r += 1

    # AIFMD II leverage cap (commitment method)
    # Open-ended AIF: 175%; closed-ended: 300%
    ws.cell(row=r, column=1, value="AIF type (open/closed)").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Tipo AIF").font = styles.font_label_it
    aif_type_cell = ws.cell(row=r, column=4, value=context.get("aif_type", "closed"))
    styles.style_input(aif_type_cell)
    aif_type_row = r
    r += 1

    ws.cell(row=r, column=1, value="AIFMD II leverage cap (commitment)").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Limite AIFMD II").font = styles.font_label_it
    cap_cell = ws.cell(
        row=r, column=4,
        value=f'=IF($D${aif_type_row}="open",1.75,3.00)',
    )
    styles.style_formula(cap_cell, number_format=styles.FMT_PCT_2DP)
    cap_cell.comment = Comment(
        "AIFMD II Article 15a: open-ended AIF max 175% leverage "
        "(commitment method), closed-ended max 300%. "
        "Source: BCLP April 2024 transposition note.",
        "ModelForge",
    )
    cap_row = r
    r += 1

    ws.cell(row=r, column=1, value="Actual portfolio leverage").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Leva effettiva").font = styles.font_label_it
    actual_lev = ws.cell(row=r, column=4,
                         value=context.get("actual_leverage", 1.50))
    styles.style_input(actual_lev, number_format=styles.FMT_PCT_2DP)
    actual_row = r
    r += 1

    ws.cell(row=r, column=1, value="AIFMD II leverage compliance").font = styles.font_subheader
    comp_cell = ws.cell(
        row=r, column=4,
        value=f'=IF($D${actual_row}<=$D${cap_row},"PASS","FAIL")',
    )
    styles.style_formula(comp_cell, number_format="General")
    comp_cell.font = styles.font_subheader
    r += 2

    # AIFMD II single-borrower cap (20% NAV)
    ws.cell(row=r, column=1, value="Largest single borrower % NAV").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Maggior debitore % NAV").font = styles.font_label_it
    sb_cell = ws.cell(row=r, column=4,
                      value=context.get("largest_single_borrower_pct_nav", 0.15))
    styles.style_input(sb_cell, number_format=styles.FMT_PCT_2DP)
    sb_row = r
    r += 1

    ws.cell(row=r, column=1, value="AIFMD II single-borrower cap").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Limite singolo debitore").font = styles.font_label_it
    cap2 = ws.cell(row=r, column=4, value=0.20)
    styles.style_input(cap2, number_format=styles.FMT_PCT_2DP)
    cap2_row = r
    r += 1

    ws.cell(row=r, column=1, value="Single-borrower compliance").font = styles.font_subheader
    comp2 = ws.cell(
        row=r, column=4,
        value=f'=IF($D${sb_row}<=$D${cap2_row},"PASS","FAIL")',
    )
    styles.style_formula(comp2)
    comp2.font = styles.font_subheader
    comp2.comment = Comment(
        "AIFMD II Article 15a(4): loans to single borrower capped at 20% "
        "of AIF NAV. Source: Clifford Chance guidance.",
        "ModelForge",
    )
    r += 2

    # ─── Section 2: Loan-originating AIF status ────────────────────────────
    layout.write_section_header(ws, r, "Loan-originating AIF status",
                                 "Classificazione AIF con origination")
    r += 1

    ws.cell(row=r, column=1, value="Originated loans % NAV").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Prestiti originati % NAV").font = styles.font_label_it
    lorig = ws.cell(row=r, column=4,
                    value=context.get("originated_loans_pct_nav", 0.55))
    styles.style_input(lorig, number_format=styles.FMT_PCT_2DP)
    lorig_row = r
    r += 1

    ws.cell(row=r, column=1, value="Loan-originating AIF flag").font = styles.font_subheader
    flag = ws.cell(
        row=r, column=4,
        value=f'=IF($D${lorig_row}>=0.50,"YES — closed-ended required if >60%","NO")',
    )
    styles.style_formula(flag)
    flag.font = styles.font_subheader
    flag.comment = Comment(
        "AIFMD II: AIF deemed loan-originating if >50% NAV in "
        "originated loans. Must be closed-ended if origination >60% NAV. "
        "Source: Linklaters / Ropes & Gray.",
        "ModelForge",
    )
    r += 2

    # ─── Section 3: IFRS 9 three-stage ECL recap ───────────────────────────
    layout.write_section_header(ws, r, "IFRS 9 three-stage ECL",
                                 "IFRS 9 modello a tre stadi")
    r += 1

    # v0.8 US-260: Canonical ECL formula for auditor reference
    ws.cell(row=r, column=1,
            value="ECL formula (canonical): ECL = PD × LGD × EAD × DF").font = styles.font_subheader
    ws.cell(row=r, column=2,
            value="Formula ECL: PD × LGD × EAD × Fattore sconto").font = styles.font_label_it
    r += 1
    ws.cell(row=r, column=1,
            value="  where PD = probability of default, LGD = loss given "
                  "default, EAD = exposure at default, DF = discount factor"
            ).font = styles.font_label_it
    r += 2

    stages = [
        ("Stage 1 (12-month ECL — no SICR)",
         "Stadio 1 (ECL 12m — no SICR)",
         "12m PD × LGD × EAD × DF"),
        ("Stage 2 (Lifetime ECL — SICR triggered)",
         "Stadio 2 (ECL lifetime — SICR)",
         "Lifetime PD × LGD × EAD × DF | 30+DPD backstop"),
        ("Stage 3 (Lifetime ECL — credit-impaired)",
         "Stadio 3 (ECL lifetime — impaired)",
         "PD 100% × LGD × EAD × DF | interest on NET"),
    ]
    for en, it, f in stages:
        ws.cell(row=r, column=1, value=en).font = styles.font_label_en
        ws.cell(row=r, column=2, value=it).font = styles.font_label_it
        ws.cell(row=r, column=4, value=f).font = styles.font_label_it
        r += 1

    # SICR triggers
    r += 1
    ws.cell(row=r, column=1, value="SICR triggers (document bank policy)").font = styles.font_subheader
    r += 1
    triggers = [
        "Absolute PD threshold breach",
        "Relative PD doubling vs origination",
        "Rating downgrade by ≥2 notches",
        "Watchlist flag",
        "Forbearance granted",
        "30+ days past due (DPD) presumption",
    ]
    for t in triggers:
        ws.cell(row=r, column=1, value=f"  • {t}").font = styles.font_label_it
        r += 1
    r += 1

    # ─── Section 4: Basel NPL calendar provisioning ────────────────────────
    layout.write_section_header(ws, r, "Basel NPL calendar provisioning",
                                 "Calendar provisioning NPL")
    r += 1

    ws.cell(row=r, column=1, value="Regulation (EU) 2019/630 — NPL minimum coverage").font = styles.font_label_en
    r += 1

    bands = [
        ("Unsecured NPEs", "NPE non garantite", "0% / 35% / 100% (Y1-2 / Y3 / Y3+)"),
        ("NPEs secured by real estate", "NPE garantite da immobili", "0% / 25% / 70% / 100% (Y1-4 / Y5 / Y7 / Y9+)"),
        ("NPEs secured by other collateral", "NPE garantite altro", "0% / 35% / 70% / 100% (Y1-2 / Y3 / Y4 / Y7+)"),
    ]
    for en, it, f in bands:
        ws.cell(row=r, column=1, value=f"  • {en}").font = styles.font_label_en
        ws.cell(row=r, column=2, value=it).font = styles.font_label_it
        ws.cell(row=r, column=4, value=f).font = styles.font_label_it
        r += 1
    ws.cell(row=r, column=1, value="").comment = Comment(
        "Minimum prudential backstop per Regulation (EU) 2019/630 "
        "applied to credit facilities originated from 26-Apr-2019.",
        "ModelForge",
    )
    r += 2

    # ─── Section 5: GACS eligibility (NPL) ─────────────────────────────────
    layout.write_section_header(ws, r, "GACS (Garanzia Cartolarizzazione Sofferenze)",
                                 "GACS — Garanzia stato su senior NPL")
    r += 1

    gacs_items = [
        ("Senior tranche rating ≥ BBB-", "Rating senior ≥ investment grade",
         context.get("senior_rating", "BBB")),
        ("Legge 130/1999 SPV (bankruptcy-remote)", "SPV legge 130/1999",
         "YES (required)"),
        ("Guarantee fee priced on IT financial CDS", "Fee garanzia su CDS finanziari italiani",
         "IT Italian financial-sector CDS basket (5Y)"),
        ("Servicer fit-and-proper (Banca d'Italia)", "Servicer requisiti",
         "Required"),
    ]
    for en, it, val in gacs_items:
        ws.cell(row=r, column=1, value=f"  • {en}").font = styles.font_label_en
        ws.cell(row=r, column=2, value=it).font = styles.font_label_it
        ws.cell(row=r, column=4, value=val).font = styles.font_label_it
        r += 1
    r += 1

    # ─── Section 6: IRES + IRAP split (Italian tax transparency) ───────────
    layout.write_section_header(ws, r, "Italian tax — IRES + IRAP split",
                                 "Tassazione italiana — IRES + IRAP")
    r += 1

    ws.cell(row=r, column=1, value="IRES rate").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Aliquota IRES").font = styles.font_label_it
    c = ws.cell(row=r, column=4, value=0.24)
    styles.style_input(c, number_format=styles.FMT_PCT_2DP)
    r += 1

    ws.cell(row=r, column=1, value="IRAP rate (national base + regional)").font = styles.font_label_en
    ws.cell(row=r, column=2, value="Aliquota IRAP").font = styles.font_label_it
    c = ws.cell(row=r, column=4, value=0.039)
    styles.style_input(c, number_format=styles.FMT_PCT_2DP)
    r += 1

    ws.cell(row=r, column=1, value="IRES+IRAP combined (approximate)").font = styles.font_subheader
    ws.cell(row=r, column=2, value="IRES+IRAP combinate (stima)").font = styles.font_label_it
    c = ws.cell(row=r, column=4, value=f"=D{r-2}+D{r-1}")
    styles.style_formula(c, number_format=styles.FMT_PCT_2DP)
    c.font = styles.font_subheader
    c.comment = Comment(
        "Caveat: IRES and IRAP have DIFFERENT tax bases. IRES includes "
        "financial items; IRAP excludes them. The 'combined' rate is "
        "an APPROXIMATION for non-financial corporates. Banks / insurers "
        "pay IRAP at 4.65% + 2pp (Italian 2026 Budget Law). "
        "Source: PwC Italy Corporate Tax Summaries.",
        "ModelForge",
    )
    r += 2

    r += 1

    # ─── Section 7: Basel securitization capital framework (v0.8.7 US-510/512)
    layout.write_section_header(
        ws, r, "Basel III/IV securitization capital (SEC-SA / SEC-IRBA / SEC-ERBA)",
        "Capitale Basel su cartolarizzazioni",
    )
    r += 1

    ws.cell(row=r, column=1, value="Framework hierarchy (BCBS d374 / CRR Art. 254)").font = styles.font_subheader
    ws.cell(row=r, column=2, value="Gerarchia framework").font = styles.font_label_it
    r += 1

    bsec_items = [
        ("SEC-IRBA (internal ratings-based)",
         "Banca IRB con rating interni",
         "Priority 1 — required if bank has IRB approval for underlying"),
        ("SEC-ERBA (external ratings-based)",
         "Basato su rating esterni",
         "Priority 2 — used when ECAI rating available on tranche"),
        ("SEC-SA (standardised approach)",
         "Approccio standard",
         "Priority 3 — fallback; Kirb-based look-through formula"),
        ("Risk-weight floor (all approaches)",
         "Floor ponderazione",
         "15% minimum on senior; 100% on mezz; 1,250% on equity/residual"),
        ("Output floor (Basel IV)",
         "Output floor Basel IV",
         "72.5% of SA by 2028 (phased from 50% in 2022)"),
        ("STS qualifying (Reg. EU 2017/2402)",
         "STS conforme",
         "Simple / Transparent / Standardised — reduced RW"),
    ]
    for en, it, val in bsec_items:
        ws.cell(row=r, column=1, value=f"  • {en}").font = styles.font_label_en
        ws.cell(row=r, column=2, value=it).font = styles.font_label_it
        ws.cell(row=r, column=4, value=val).font = styles.font_label_it
        r += 1

    ws.cell(row=r, column=1, value="").comment = Comment(
        "Basel III/IV securitization framework per BCBS d374 (December 2014) "
        "implemented in EU via CRR Art. 254 / Reg. EU 2017/2401 + 2402 (STS). "
        "Hierarchy: SEC-IRBA > SEC-ERBA > SEC-SA. Output floor 72.5% of SA "
        "applicable from 2028. Sources: BIS BCBS d374; EBA technical "
        "standards; Banca d'Italia Circolare 285 Title III.",
        "ModelForge",
    )
    r += 2

    ws.freeze_panes = "D5"
    ws.print_title_rows = "1:4"

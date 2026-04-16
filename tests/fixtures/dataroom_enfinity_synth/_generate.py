"""Generate a synthetic Enfinity-like data room.

Creates PDFs + XLSXs that simulate what a real EUR 214M Italian solar PF
data room would contain. All content is derived from *public* press
releases and benchmarks — nothing confidential.

Run once:
    python tests/fixtures/dataroom_enfinity_synth/_generate.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from openpyxl import Workbook


HERE = Path(__file__).parent


def _pdf(filename: str, title: str, paragraphs: list[str]) -> None:
    doc = SimpleDocTemplate(str(HERE / filename), pagesize=A4,
                            leftMargin=50, rightMargin=50,
                            topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "T", parent=styles["Heading1"], fontSize=14, spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "B", parent=styles["Normal"], fontSize=11, leading=14, spaceAfter=10,
    )
    story = [Paragraph(title, title_style), Spacer(1, 6)]
    for para in paragraphs:
        story.append(Paragraph(para, body_style))
    doc.build(story)


def generate() -> None:
    # 1. Press release (verified, press_release)
    _pdf(
        "01_enfinity_press_release.pdf",
        "Enfinity Global secures EUR 316M to finance 276 MW of solar projects in Italy",
        [
            "PR Newswire, 15 August 2025. Enfinity Global today announced the closing of a EUR 316 million financing package for 276 MW of utility-scale solar photovoltaic projects across Italy. The non-recourse senior green loan of EUR 214 million was arranged as a club deal with ING, Rabobank, and BNP Paribas, alongside EUR 101 million of VAT, PPA and decommissioning facilities.",
            "The portfolio comprises 8 utility-scale solar plants located across southern and central Italy and is expected to reach commercial operation by late 2026. Enfinity Global serves as sponsor, with the senior green loan qualifying as Art. 9 sustainable investment under the EU Taxonomy.",
            "Revenue will be derived from a blend of FER X regulated tariff awards and merchant Power Purchase Agreements, providing a stabilised cash flow profile over a 20-year operating period.",
            "The senior facility has an 18-year operating-years tenor with a 1-year grace period, and is priced at 175 bps over 10-year EUR swap. A 1.25 percent arrangement fee applies.",
        ],
    )

    # 2. Information Memorandum excerpt (unverified, IM)
    _pdf(
        "02_enfinity_IM_extract.pdf",
        "Enfinity Solar Italy Portfolio - Information Memorandum (Extract)",
        [
            "Section 4 - Portfolio Overview. The subject portfolio comprises eight (8) greenfield solar photovoltaic plants aggregating to 276 MWdc of installed capacity across five Italian regions (Puglia, Sicilia, Lazio, Basilicata, Sardegna).",
            "Section 7 - Revenue Assumptions. Blended weighted-average PPA + FER X tariff is projected at EUR 75/MWh for 2026 vintage awards, in line with the GSE FER X auction results published 15 February 2026. Annual revenue indexation is modeled at 1.5 percent, reflecting partial CPI linkage of FER X tariffs.",
            "Section 9 - Operating Costs. Steady-state O&amp;M, land lease, insurance and grid fees aggregate to approximately 22 percent of revenue. Fixed cost inflation is set at 2.0 percent per annum. A Maintenance &amp; Major Repairs Account (MMRA) is funded at 2.0 percent of annual revenues.",
            "Section 11 - Capex Phasing. Total project capex of EUR 316 million is phased 35 percent in Year 1 (site preparation, module procurement, long-lead equipment) and 65 percent in Year 2 (installation, grid connection, commissioning, commercial operation date).",
            "Section 15 - Corporate Tax. Effective tax rate applied to operating profit is 27.9 percent (IRES 24.0 percent + IRAP 3.9 percent) per PwC Italy tax summary.",
        ],
    )

    # 3. Terna irradiation benchmark (verified, market_benchmark)
    _pdf(
        "03_terna_irradiation_report_2025.pdf",
        "Terna - Italian Solar Irradiation Benchmark 2025",
        [
            "Terna S.p.A., 30 January 2026. This report publishes average solar irradiation values across the Italian peninsula for grid-connected utility-scale photovoltaic systems operating during 2025, expressed in kWh/kWp/year.",
            "Zone A (Sicilia, Puglia, Basilicata, Sardegna southern): 1,600 to 1,650 kWh/kWp/year. Zone B (Lazio, Campania, Abruzzo): 1,450 to 1,550 kWh/kWp/year. Zone C (central and northern regions): 1,250 to 1,400 kWh/kWp/year.",
            "Blended national average for utility-scale assets across southern and central Italy is 1,550 kWh/kWp/year. Assuming a 276 MW utility-scale portfolio spread across these zones, expected gross energy yield is approximately 428 GWh per annum.",
        ],
    )

    # 4. GSE FER X auction results (verified, regulatory_filing)
    _pdf(
        "04_gse_fer_x_results.pdf",
        "GSE - FER X Auction Results, 15 February 2026",
        [
            "Gestore dei Servizi Energetici (GSE), 15 February 2026. The second 2025-2026 FER X auction for utility-scale solar photovoltaic awarded a volume-weighted average tariff of EUR 72/MWh for projects reaching commercial operation between 2026 and 2027.",
            "Combined with merchant PPA pricing of approximately EUR 78/MWh for the same vintage (per AFRY January 2026 reference curves), the blended effective revenue per MWh for solar portfolios structured with a 60/40 FER X / merchant mix is approximately EUR 75/MWh.",
        ],
    )

    # 5. ECB 10Y EUR swap (verified, market_benchmark)
    _pdf(
        "05_ecb_euro_swap_10y.pdf",
        "ECB Statistical Data Warehouse - 10Y EUR Swap Rate, April 2026",
        [
            "European Central Bank Statistical Data Warehouse, extracted 10 April 2026. The 10-year Euro Interest Rate Swap (EURIBOR 6M basis) traded at an average of 2.85 percent during the first week of April 2026.",
            "This rate is used as the reference swap rate for fixed-rate infrastructure project finance debt pricing.",
        ],
    )

    # 6. PwC tax reference (verified, market_benchmark)
    _pdf(
        "06_pwc_italy_tax.pdf",
        "PwC Italy - Corporate Tax Quick Reference, Q1 2026",
        [
            "PwC Italy, 15 January 2026. The effective Italian corporate income tax rate applicable to SPV-level taxable profits is the sum of IRES (24.0 percent) and IRAP (3.9 percent), totaling 27.9 percent.",
            "Project finance SPVs generally qualify for the standard regime absent special incentives.",
        ],
    )

    # 7. Loan term sheet (verified, contract_loan)
    _pdf(
        "07_senior_green_loan_term_sheet.pdf",
        "Senior Green Loan - Summary Term Sheet",
        [
            "Borrower: SolarCo Italia S.p.A. (SPV). Lenders: ING Bank, Rabobank, BNP Paribas (club deal; joint arrangement).",
            "Facility: Senior Green Loan. Facility amount: EUR 214,000,000. Tenor: 18 operating years from COD, plus 2-year construction availability period. Grace period: 1 operating year post-COD.",
            "Pricing: EUR Swap 10Y + 175 bps margin. Arrangement fee: 1.25% of facility amount, payable upfront. Commitment fee: 75 bps p.a. on undrawn commitments.",
            "Covenants: Debt Service Coverage Ratio (DSCR) minimum 1.20x year 1, stepping to 1.30x from year 4 onward. Dividend lock-up trigger at DSCR 1.15x. Debt Service Reserve Account (DSRA) at 6 months of forward debt service.",
            "Amortization: sculpted level debt service profile over the 17-year amortization period (operating years 2 through 18).",
        ],
    )

    # 8. XLSX projections summary (sponsor-prepared, unverified)
    wb = Workbook()
    ws = wb.active
    ws.title = "Projections"
    ws.append(["Enfinity Solar Portfolio - Five-year projections (sponsor estimate)"])
    ws.append([])
    ws.append(["Year", "Revenue EURm", "Opex EURm", "EBITDA EURm", "DSCR"])
    ws.append(["2027 O1", 32.1, -7.1, 25.0, 2.19])
    ws.append(["2028 O2", 32.6, -7.2, 25.4, 1.30])
    ws.append(["2029 O3", 33.1, -7.3, 25.8, 1.31])
    ws.append(["2030 O4", 33.6, -7.4, 26.2, 1.32])
    ws.append(["2031 O5", 34.1, -7.5, 26.6, 1.33])
    ws.append([])
    ws.append(["Notes: sponsor projections assume FER X / merchant blend EUR 75/MWh, Terna irradiation 1,550 kWh/kWp/yr, 1.5% revenue indexation, 22% opex ratio."])
    wb.save(HERE / "08_sponsor_projections.xlsx")

    # 9. CSV irradiation time-series (verified, operational_report)
    import csv
    with (HERE / "09_plant_irradiation_2025.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "plant_id", "irradiation_kWh_per_kWp", "production_MWh"])
        for m in range(1, 13):
            w.writerow([f"2025-{m:02d}", "Puglia_01", 120 + m * 5, 3200 + m * 50])
            w.writerow([f"2025-{m:02d}", "Sicilia_02", 135 + m * 4, 3600 + m * 60])


if __name__ == "__main__":
    generate()
    print("Generated synthetic Enfinity data room at:", HERE)

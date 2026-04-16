"""EN / IT label pairs.

Every canonical row label in a ModelForge workbook has an EN primary form
and an IT secondary form, used for:
    - Italian mid-market buyers who want Italian labels
    - Non-Italian LPs / lenders who read English
    - Both audiences seeing the same workbook without a retranslate

Extend here when adding new labels. Keep keys snake_case.
"""

from __future__ import annotations

from modelforge.spec.base import Label


LABELS: dict[str, Label] = {
    # Cover
    "project_code": Label(en="Project code", it="Codice progetto"),
    "deliverable": Label(en="Deliverable", it="Consegna"),
    "analyst": Label(en="Analyst", it="Analista"),
    "valuation_date": Label(en="Valuation date", it="Data valutazione"),
    "version": Label(en="Version", it="Versione"),
    "status": Label(en="Status", it="Stato"),
    "currency": Label(en="Currency", it="Valuta"),
    "unit_scale": Label(en="Units", it="Unità"),
    "sign_convention": Label(en="Sign convention", it="Convenzione di segno"),
    "target": Label(en="Target", it="Target"),
    "sector": Label(en="Sector", it="Settore"),
    "country": Label(en="Country", it="Paese"),
    "confidentiality": Label(en="Confidentiality", it="Riservatezza"),
    "revision_log": Label(en="Revision log", it="Registro revisioni"),

    # Scenario
    "scenario": Label(en="Scenario", it="Scenario"),
    "scenario_worst": Label(en="Worst", it="Peggiore"),
    "scenario_base": Label(en="Base", it="Base"),
    "scenario_best": Label(en="Best", it="Migliore"),
    "scenario_active": Label(en="Active scenario", it="Scenario attivo"),

    # Sources sheet
    "source_id": Label(en="Source ID", it="ID fonte"),
    "source_doc": Label(en="Document", it="Documento"),
    "source_page": Label(en="Page", it="Pagina"),
    "source_publisher": Label(en="Publisher", it="Editore"),
    "source_date": Label(en="Date", it="Data"),
    "source_url": Label(en="URL", it="URL"),
    "source_verified": Label(en="Verified", it="Verificato"),
    "source_note": Label(en="Note", it="Note"),

    # Assumptions sheet
    "assumption_id": Label(en="ID", it="ID"),
    "assumption_name": Label(en="Driver", it="Driver"),
    "assumption_label": Label(en="Description", it="Descrizione"),
    "assumption_unit": Label(en="Unit", it="Unità"),
    "assumption_worst": Label(en="Worst", it="Peggiore"),
    "assumption_base": Label(en="Base", it="Base"),
    "assumption_best": Label(en="Best", it="Migliore"),
    "assumption_active": Label(en="Active", it="Attivo"),
    "assumption_rationale": Label(en="Rationale", it="Motivazione"),
    "assumption_confidence": Label(en="Conf.", it="Conf."),
    "assumption_source": Label(en="Source", it="Fonte"),

    # Operating model
    "revenue": Label(en="Revenue", it="Ricavi"),
    "revenue_growth": Label(en="Revenue growth %", it="Crescita ricavi %"),
    "cogs": Label(en="Cost of sales", it="Costo del venduto"),
    "gross_profit": Label(en="Gross profit", it="Margine lordo"),
    "opex": Label(en="Operating expenses", it="Costi operativi"),
    "ebitda": Label(en="EBITDA", it="EBITDA"),
    "ebitda_margin": Label(en="EBITDA margin %", it="Margine EBITDA %"),
    "da": Label(en="D&A", it="Ammortamenti"),
    "ebit": Label(en="EBIT", it="EBIT"),
    "interest_expense": Label(en="Interest expense", it="Oneri finanziari"),
    "ebt": Label(en="Profit before tax", it="Utile ante imposte"),
    "tax": Label(en="Taxes", it="Imposte"),
    "net_income": Label(en="Net income", it="Utile netto"),

    # Cash flow
    "capex_maint": Label(en="Maintenance capex", it="Capex manutenzione"),
    "capex_growth": Label(en="Growth capex", it="Capex crescita"),
    "capex_total": Label(en="Total capex", it="Capex totale"),
    "nwc_change": Label(en="Δ Net working capital", it="Δ Capitale circolante"),
    "fcf_to_debt": Label(en="Free cash flow to debt", it="FCF al debito"),

    # Debt schedule
    "debt_opening": Label(en="Opening debt", it="Debito iniziale"),
    "debt_drawdown": Label(en="Drawdown", it="Erogazione"),
    "debt_repayment": Label(en="Scheduled amortization", it="Ammortamento"),
    "debt_voluntary_prepay": Label(en="Voluntary prepayment", it="Rimborso volontario"),
    "debt_closing": Label(en="Closing debt", it="Debito finale"),
    "debt_average": Label(en="Average debt", it="Debito medio"),
    "reference_rate": Label(en="Reference rate", it="Tasso di riferimento"),
    "margin_bps": Label(en="Margin (bps)", it="Margine (bps)"),
    "all_in_rate": Label(en="All-in rate", it="Tasso all-in"),
    "cash_interest": Label(en="Cash interest", it="Interessi cassa"),
    "arrangement_fee": Label(en="Arrangement fee", it="Commissione di strutturazione"),

    # Covenants
    "leverage_ratio": Label(en="Leverage (Net debt / EBITDA)", it="Leva (PFN / EBITDA)"),
    "leverage_threshold": Label(en="Leverage covenant", it="Covenant leva"),
    "leverage_headroom": Label(en="Leverage headroom %", it="Headroom leva %"),
    "icr": Label(en="Interest coverage (EBITDA / Interest)", it="ICR (EBITDA / Oneri)"),
    "icr_threshold": Label(en="ICR covenant", it="Covenant ICR"),
    "icr_headroom": Label(en="ICR headroom %", it="Headroom ICR %"),

    # Returns
    "lender_cashflow": Label(en="Lender cash flow", it="Flusso al finanziatore"),
    "lender_irr": Label(en="Lender IRR", it="IRR finanziatore"),
    "lender_moic": Label(en="Lender MoIC", it="MoIC finanziatore"),
    "lender_apr": Label(en="Lender APR", it="APR finanziatore"),

    # QC
    "qc_check": Label(en="QC check", it="Controllo QC"),
    "qc_pass": Label(en="Pass", it="Superato"),
    "qc_fail": Label(en="Fail", it="Fallito"),
    "qc_all_pass": Label(en="ALL CHECKS PASS", it="TUTTI I CONTROLLI OK"),
}


def L(key: str) -> Label:
    """Lookup a label by key. Raises if missing (intentional — forces explicit i18n)."""
    if key not in LABELS:
        raise KeyError(
            f"Label '{key}' not found in i18n dictionary. Add it to modelforge/builder/i18n.py."
        )
    return LABELS[key]

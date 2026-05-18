"""Multi-language label pairs.

v0.10: expanded from EN/IT to EN + 7 secondary languages.

Every canonical row label in a ModelForge workbook has an EN primary form
and up to 7 secondary forms (IT/DE/ES/SV/NO/DA/NL), used for:
    - Workbook rendering in the analyst's working language
    - Cross-border deal modeling where source-doc language ≠ IC language
    - Multi-LP reporting where LPs read different languages

Coverage status (v0.10):
    EN          — primary, mandatory
    IT          — full coverage, native-quality (shipped since v0.1)
    DE, ES      — full coverage, first-cut (review encouraged)
    SV, NO, DA, NL — full coverage, FIRST-CUT — design-partner native-speaker
                     review required before production use. The translations
                     below are based on standard finance/accounting vocabulary
                     and should be ~95% correct, but idiomatic refinement is
                     expected from native-speaker reviewers in v0.11.

Extend here when adding new labels. Keep keys snake_case.
"""

from __future__ import annotations

from modelforge.spec.base import Label


LABELS: dict[str, Label] = {
    # ---------- Cover sheet ----------
    "project_code": Label(
        en="Project code", it="Codice progetto", de="Projektcode",
        es="Código del proyecto", sv="Projektkod", no="Prosjektkode",
        da="Projektkode", nl="Projectcode",
    ),
    "deliverable": Label(
        en="Deliverable", it="Consegna", de="Liefergegenstand",
        es="Entregable", sv="Leverans", no="Leveranse",
        da="Leverance", nl="Op te leveren product",
    ),
    "analyst": Label(
        en="Analyst", it="Analista", de="Analyst",
        es="Analista", sv="Analytiker", no="Analytiker",
        da="Analytiker", nl="Analist",
    ),
    "valuation_date": Label(
        en="Valuation date", it="Data valutazione", de="Bewertungsstichtag",
        es="Fecha de valoración", sv="Värderingsdatum", no="Verdsettingsdato",
        da="Værdiansættelsesdato", nl="Waarderingsdatum",
    ),
    "version": Label(
        en="Version", it="Versione", de="Version",
        es="Versión", sv="Version", no="Versjon",
        da="Version", nl="Versie",
    ),
    "status": Label(
        en="Status", it="Stato", de="Status",
        es="Estado", sv="Status", no="Status",
        da="Status", nl="Status",
    ),
    "currency": Label(
        en="Currency", it="Valuta", de="Währung",
        es="Moneda", sv="Valuta", no="Valuta",
        da="Valuta", nl="Valuta",
    ),
    "unit_scale": Label(
        en="Units", it="Unità", de="Einheiten",
        es="Unidades", sv="Enheter", no="Enheter",
        da="Enheder", nl="Eenheden",
    ),
    "sign_convention": Label(
        en="Sign convention", it="Convenzione di segno", de="Vorzeichenkonvention",
        es="Convención de signos", sv="Teckenkonvention", no="Fortegnskonvensjon",
        da="Fortegnskonvention", nl="Tekenconventie",
    ),
    "target": Label(
        en="Target", it="Target", de="Zielobjekt",
        es="Objetivo", sv="Mål", no="Mål",
        da="Mål", nl="Doelvennootschap",
    ),
    "sector": Label(
        en="Sector", it="Settore", de="Sektor",
        es="Sector", sv="Sektor", no="Sektor",
        da="Sektor", nl="Sector",
    ),
    "country": Label(
        en="Country", it="Paese", de="Land",
        es="País", sv="Land", no="Land",
        da="Land", nl="Land",
    ),
    "confidentiality": Label(
        en="Confidentiality", it="Riservatezza", de="Vertraulichkeit",
        es="Confidencialidad", sv="Sekretess", no="Konfidensialitet",
        da="Fortrolighed", nl="Vertrouwelijkheid",
    ),
    "revision_log": Label(
        en="Revision log", it="Registro revisioni", de="Revisionsprotokoll",
        es="Registro de revisiones", sv="Revisionslogg", no="Revisjonslogg",
        da="Revisionslog", nl="Revisielogboek",
    ),

    # ---------- Scenario ----------
    "scenario": Label(
        en="Scenario", it="Scenario", de="Szenario",
        es="Escenario", sv="Scenario", no="Scenario",
        da="Scenarie", nl="Scenario",
    ),
    "scenario_worst": Label(
        en="Worst", it="Peggiore", de="Worst-Case",
        es="Pesimista", sv="Värsta", no="Verste",
        da="Værste", nl="Slechtste",
    ),
    "scenario_base": Label(
        en="Base", it="Base", de="Basis",
        es="Base", sv="Bas", no="Basis",
        da="Basis", nl="Basis",
    ),
    "scenario_best": Label(
        en="Best", it="Migliore", de="Best-Case",
        es="Optimista", sv="Bästa", no="Beste",
        da="Bedste", nl="Beste",
    ),
    "scenario_active": Label(
        en="Active scenario", it="Scenario attivo", de="Aktives Szenario",
        es="Escenario activo", sv="Aktivt scenario", no="Aktivt scenario",
        da="Aktivt scenarie", nl="Actief scenario",
    ),

    # ---------- Sources sheet ----------
    "source_id": Label(
        en="Source ID", it="ID fonte", de="Quellen-ID",
        es="ID de fuente", sv="Käll-ID", no="Kilde-ID",
        da="Kilde-ID", nl="Bron-ID",
    ),
    "source_doc": Label(
        en="Document", it="Documento", de="Dokument",
        es="Documento", sv="Dokument", no="Dokument",
        da="Dokument", nl="Document",
    ),
    "source_page": Label(
        en="Page", it="Pagina", de="Seite",
        es="Página", sv="Sida", no="Side",
        da="Side", nl="Pagina",
    ),
    "source_publisher": Label(
        en="Publisher", it="Editore", de="Herausgeber",
        es="Editor", sv="Utgivare", no="Utgiver",
        da="Udgiver", nl="Uitgever",
    ),
    "source_date": Label(
        en="Date", it="Data", de="Datum",
        es="Fecha", sv="Datum", no="Dato",
        da="Dato", nl="Datum",
    ),
    "source_url": Label(en="URL", it="URL", de="URL", es="URL", sv="URL", no="URL", da="URL", nl="URL"),
    "source_verified": Label(
        en="Verified", it="Verificato", de="Verifiziert",
        es="Verificado", sv="Verifierad", no="Verifisert",
        da="Verificeret", nl="Geverifieerd",
    ),
    "source_note": Label(
        en="Note", it="Note", de="Notiz",
        es="Nota", sv="Anteckning", no="Notat",
        da="Note", nl="Notitie",
    ),

    # ---------- Assumptions sheet ----------
    "assumption_id": Label(en="ID", it="ID", de="ID", es="ID", sv="ID", no="ID", da="ID", nl="ID"),
    "assumption_name": Label(
        en="Driver", it="Driver", de="Treiber",
        es="Driver", sv="Drivare", no="Driver",
        da="Driver", nl="Drijfveer",
    ),
    "assumption_label": Label(
        en="Description", it="Descrizione", de="Beschreibung",
        es="Descripción", sv="Beskrivning", no="Beskrivelse",
        da="Beskrivelse", nl="Beschrijving",
    ),
    "assumption_unit": Label(
        en="Unit", it="Unità", de="Einheit",
        es="Unidad", sv="Enhet", no="Enhet",
        da="Enhed", nl="Eenheid",
    ),
    "assumption_worst": Label(
        en="Worst", it="Peggiore", de="Worst-Case",
        es="Pesimista", sv="Värsta", no="Verste",
        da="Værste", nl="Slechtste",
    ),
    "assumption_base": Label(
        en="Base", it="Base", de="Basis",
        es="Base", sv="Bas", no="Basis",
        da="Basis", nl="Basis",
    ),
    "assumption_best": Label(
        en="Best", it="Migliore", de="Best-Case",
        es="Optimista", sv="Bästa", no="Beste",
        da="Bedste", nl="Beste",
    ),
    "assumption_active": Label(
        en="Active", it="Attivo", de="Aktiv",
        es="Activo", sv="Aktiv", no="Aktiv",
        da="Aktiv", nl="Actief",
    ),
    "assumption_rationale": Label(
        en="Rationale", it="Motivazione", de="Begründung",
        es="Justificación", sv="Motivering", no="Begrunnelse",
        da="Begrundelse", nl="Onderbouwing",
    ),
    "assumption_confidence": Label(
        en="Conf.", it="Conf.", de="Konf.",
        es="Conf.", sv="Konf.", no="Konf.",
        da="Konf.", nl="Conf.",
    ),
    "assumption_source": Label(
        en="Source", it="Fonte", de="Quelle",
        es="Fuente", sv="Källa", no="Kilde",
        da="Kilde", nl="Bron",
    ),

    # ---------- Operating model ----------
    "revenue": Label(
        en="Revenue", it="Ricavi", de="Umsatzerlöse",
        es="Ingresos", sv="Intäkter", no="Inntekter",
        da="Indtægter", nl="Omzet",
    ),
    "revenue_growth": Label(
        en="Revenue growth %", it="Crescita ricavi %", de="Umsatzwachstum %",
        es="Crecimiento de ingresos %", sv="Intäktstillväxt %", no="Inntektsvekst %",
        da="Indtægtsvækst %", nl="Omzetgroei %",
    ),
    "cogs": Label(
        en="Cost of sales", it="Costo del venduto", de="Umsatzkosten",
        es="Coste de ventas", sv="Försäljningskostnader", no="Salgskostnader",
        da="Vareforbrug", nl="Kostprijs van de omzet",
    ),
    "gross_profit": Label(
        en="Gross profit", it="Margine lordo", de="Bruttoergebnis",
        es="Beneficio bruto", sv="Bruttoresultat", no="Bruttoresultat",
        da="Bruttoresultat", nl="Brutowinst",
    ),
    "opex": Label(
        en="Operating expenses", it="Costi operativi", de="Betriebsaufwendungen",
        es="Gastos operativos", sv="Rörelsekostnader", no="Driftskostnader",
        da="Driftsomkostninger", nl="Bedrijfskosten",
    ),
    "ebitda": Label(en="EBITDA", it="EBITDA", de="EBITDA", es="EBITDA", sv="EBITDA", no="EBITDA", da="EBITDA", nl="EBITDA"),
    "ebitda_margin": Label(
        en="EBITDA margin %", it="Margine EBITDA %", de="EBITDA-Marge %",
        es="Margen EBITDA %", sv="EBITDA-marginal %", no="EBITDA-margin %",
        da="EBITDA-margin %", nl="EBITDA-marge %",
    ),
    "da": Label(
        en="D&A", it="Ammortamenti", de="Abschreibungen",
        es="Amortización y depreciación", sv="Av- och nedskrivningar", no="Av- og nedskrivninger",
        da="Af- og nedskrivninger", nl="Afschrijvingen",
    ),
    "ebit": Label(en="EBIT", it="EBIT", de="EBIT", es="EBIT", sv="EBIT", no="EBIT", da="EBIT", nl="EBIT"),
    "interest_expense": Label(
        en="Interest expense", it="Oneri finanziari", de="Zinsaufwand",
        es="Gastos financieros", sv="Räntekostnader", no="Rentekostnader",
        da="Renteomkostninger", nl="Rentelasten",
    ),
    "ebt": Label(
        en="Profit before tax", it="Utile ante imposte", de="Ergebnis vor Steuern",
        es="Beneficio antes de impuestos", sv="Resultat före skatt", no="Resultat før skatt",
        da="Resultat før skat", nl="Winst vóór belasting",
    ),
    "tax": Label(
        en="Taxes", it="Imposte", de="Steuern",
        es="Impuestos", sv="Skatter", no="Skatter",
        da="Skatter", nl="Belastingen",
    ),
    "net_income": Label(
        en="Net income", it="Utile netto", de="Jahresüberschuss",
        es="Beneficio neto", sv="Nettoresultat", no="Nettoresultat",
        da="Nettoresultat", nl="Nettowinst",
    ),

    # ---------- Cash flow ----------
    "capex_maint": Label(
        en="Maintenance capex", it="Capex manutenzione", de="Erhaltungsinvestitionen",
        es="Capex de mantenimiento", sv="Underhållsinvesteringar", no="Vedlikeholdsinvesteringer",
        da="Vedligeholdelsesinvesteringer", nl="Onderhoudsinvesteringen",
    ),
    "capex_growth": Label(
        en="Growth capex", it="Capex crescita", de="Wachstumsinvestitionen",
        es="Capex de crecimiento", sv="Tillväxtinvesteringar", no="Vekstinvesteringer",
        da="Vækstinvesteringer", nl="Groei-investeringen",
    ),
    "capex_total": Label(
        en="Total capex", it="Capex totale", de="Gesamtinvestitionen",
        es="Capex total", sv="Totala investeringar", no="Totale investeringer",
        da="Samlede investeringer", nl="Totale investeringen",
    ),
    "nwc_change": Label(
        en="Δ Net working capital", it="Δ Capitale circolante", de="Δ Working Capital",
        es="Δ Fondo de maniobra", sv="Δ Rörelsekapital", no="Δ Arbeidskapital",
        da="Δ Arbejdskapital", nl="Δ Werkkapitaal",
    ),
    "fcf_to_debt": Label(
        en="Free cash flow to debt", it="FCF al debito", de="Free Cash Flow zum Schuldendienst",
        es="FCF para deuda", sv="Fritt kassaflöde till skuldservice", no="Fri kontantstrøm til gjeldsbetjening",
        da="Frit pengestrøm til gældsservice", nl="Vrije kasstroom voor schuldaflossing",
    ),

    # ---------- Debt schedule ----------
    "debt_opening": Label(
        en="Opening debt", it="Debito iniziale", de="Schulden Anfangsbestand",
        es="Deuda inicial", sv="Skuld ingående", no="Gjeld inngående",
        da="Gæld primo", nl="Beginstand schuld",
    ),
    "debt_drawdown": Label(
        en="Drawdown", it="Erogazione", de="Inanspruchnahme",
        es="Disposición", sv="Utbetalning", no="Uttak",
        da="Træk", nl="Opname",
    ),
    "debt_repayment": Label(
        en="Scheduled amortization", it="Ammortamento", de="Planmäßige Tilgung",
        es="Amortización programada", sv="Planenlig amortering", no="Planmessig nedbetaling",
        da="Planlagt afdrag", nl="Geplande aflossing",
    ),
    "debt_voluntary_prepay": Label(
        en="Voluntary prepayment", it="Rimborso volontario", de="Sondertilgung",
        es="Amortización anticipada", sv="Frivillig förtidsbetalning", no="Frivillig førtidig nedbetaling",
        da="Frivillig forudbetaling", nl="Vrijwillige vervroegde aflossing",
    ),
    "debt_closing": Label(
        en="Closing debt", it="Debito finale", de="Schulden Endbestand",
        es="Deuda final", sv="Skuld utgående", no="Gjeld utgående",
        da="Gæld ultimo", nl="Eindstand schuld",
    ),
    "debt_average": Label(
        en="Average debt", it="Debito medio", de="Durchschnittliche Schulden",
        es="Deuda media", sv="Genomsnittlig skuld", no="Gjennomsnittlig gjeld",
        da="Gennemsnitlig gæld", nl="Gemiddelde schuld",
    ),
    "reference_rate": Label(
        en="Reference rate", it="Tasso di riferimento", de="Referenzzinssatz",
        es="Tipo de referencia", sv="Referensränta", no="Referanserente",
        da="Referencerente", nl="Referentierente",
    ),
    "margin_bps": Label(
        en="Margin (bps)", it="Margine (bps)", de="Marge (bps)",
        es="Margen (bps)", sv="Marginal (bps)", no="Margin (bps)",
        da="Margin (bps)", nl="Marge (bps)",
    ),
    "all_in_rate": Label(
        en="All-in rate", it="Tasso all-in", de="All-in-Zinssatz",
        es="Tipo todo incluido", sv="Total ränta", no="Total rente",
        da="Total rente", nl="Total rente",
    ),
    "cash_interest": Label(
        en="Cash interest", it="Interessi cassa", de="Zinsen (Cash)",
        es="Intereses en efectivo", sv="Kontantränta", no="Kontantrenter",
        da="Kontantrenter", nl="Cashrente",
    ),
    "arrangement_fee": Label(
        en="Arrangement fee", it="Commissione di strutturazione", de="Bearbeitungsgebühr",
        es="Comisión de estructuración", sv="Arrangemangsavgift", no="Arrangementsgebyr",
        da="Arrangementsgebyr", nl="Arrangement fee",
    ),

    # ---------- Covenants ----------
    "leverage_ratio": Label(
        en="Leverage (Net debt / EBITDA)", it="Leva (PFN / EBITDA)", de="Verschuldungsgrad (Nettoverschuldung / EBITDA)",
        es="Apalancamiento (Deuda neta / EBITDA)", sv="Skuldsättning (Nettoskuld / EBITDA)", no="Gjeldsgrad (Nettogjeld / EBITDA)",
        da="Gearing (Nettogæld / EBITDA)", nl="Hefboomratio (Nettoschuld / EBITDA)",
    ),
    "leverage_threshold": Label(
        en="Leverage covenant", it="Covenant leva", de="Verschuldungs-Covenant",
        es="Covenant de apalancamiento", sv="Skuldsättningskovenant", no="Gjeldskovenant",
        da="Gearings-covenant", nl="Hefboom-convenant",
    ),
    "leverage_headroom": Label(
        en="Leverage headroom %", it="Headroom leva %", de="Verschuldungs-Spielraum %",
        es="Margen apalancamiento %", sv="Skuldsättningsmarginal %", no="Gjeldsmargin %",
        da="Gearings-margin %", nl="Hefboom-marge %",
    ),
    "icr": Label(
        en="Interest coverage (EBITDA / Interest)", it="ICR (EBITDA / Oneri)", de="Zinsdeckungsgrad (EBITDA / Zinsen)",
        es="Cobertura de intereses (EBITDA / Intereses)", sv="Räntetäckning (EBITDA / Räntor)", no="Rentedekning (EBITDA / Renter)",
        da="Rentedækning (EBITDA / Renter)", nl="Rentedekking (EBITDA / Rente)",
    ),
    "icr_threshold": Label(
        en="ICR covenant", it="Covenant ICR", de="ICR-Covenant",
        es="Covenant de ICR", sv="ICR-kovenant", no="ICR-kovenant",
        da="ICR-covenant", nl="ICR-convenant",
    ),
    "icr_headroom": Label(
        en="ICR headroom %", it="Headroom ICR %", de="ICR-Spielraum %",
        es="Margen ICR %", sv="ICR-marginal %", no="ICR-margin %",
        da="ICR-margin %", nl="ICR-marge %",
    ),

    # ---------- Returns ----------
    "lender_cashflow": Label(
        en="Lender cash flow", it="Flusso al finanziatore", de="Kreditgeber-Cashflow",
        es="Flujo al prestamista", sv="Långivares kassaflöde", no="Långivers kontantstrøm",
        da="Långivers pengestrøm", nl="Kasstroom kredietverlener",
    ),
    "lender_irr": Label(
        en="Lender IRR", it="IRR finanziatore", de="Kreditgeber-IRR",
        es="TIR del prestamista", sv="Långivar-IRR", no="Långiver-IRR",
        da="Långiver-IRR", nl="IRR kredietverlener",
    ),
    "lender_moic": Label(
        en="Lender MoIC", it="MoIC finanziatore", de="Kreditgeber-MoIC",
        es="MoIC del prestamista", sv="Långivar-MoIC", no="Långiver-MoIC",
        da="Långiver-MoIC", nl="MoIC kredietverlener",
    ),
    "lender_apr": Label(
        en="Lender APR", it="APR finanziatore", de="Kreditgeber-APR",
        es="TAE del prestamista", sv="Långivar-APR", no="Långiver-APR",
        da="Långiver-APR", nl="APR kredietverlener",
    ),

    # ---------- QC ----------
    "qc_check": Label(
        en="QC check", it="Controllo QC", de="QC-Prüfung",
        es="Comprobación QC", sv="QC-kontroll", no="QC-kontroll",
        da="QC-kontrol", nl="QC-controle",
    ),
    "qc_pass": Label(
        en="Pass", it="Superato", de="Bestanden",
        es="Aprobado", sv="Godkänd", no="Godkjent",
        da="Godkendt", nl="Geslaagd",
    ),
    "qc_fail": Label(
        en="Fail", it="Fallito", de="Fehlgeschlagen",
        es="Fallido", sv="Underkänd", no="Underkjent",
        da="Ikke godkendt", nl="Mislukt",
    ),
    "qc_all_pass": Label(
        en="ALL CHECKS PASS", it="TUTTI I CONTROLLI OK", de="ALLE PRÜFUNGEN BESTANDEN",
        es="TODAS LAS COMPROBACIONES APROBADAS", sv="ALLA KONTROLLER GODKÄNDA", no="ALLE KONTROLLER GODKJENT",
        da="ALLE KONTROLLER GODKENDT", nl="ALLE CONTROLES GESLAAGD",
    ),
}


# Languages supported as secondary (in addition to EN primary).
SECONDARY_LANGS: tuple[str, ...] = ("it", "de", "es", "sv", "no", "da", "nl")

# Languages flagged as first-cut — design-partner native-speaker review required
# before claiming production-grade quality. Builders may print a warning when
# building with one of these as the secondary.
FIRST_CUT_LANGS: frozenset[str] = frozenset({"sv", "no", "da", "nl"})


def L(key: str) -> Label:
    """Lookup a label by key. Raises if missing (intentional — forces explicit i18n)."""
    if key not in LABELS:
        raise KeyError(
            f"Label '{key}' not found in i18n dictionary. Add it to modelforge/builder/i18n.py."
        )
    return LABELS[key]


def label_in(key: str, lang: str) -> str:
    """Lookup a label and return it in the given language, falling back to EN.

    Convenience wrapper for callers that want one-shot lookup + render.
    """
    return L(key).get(lang)


# ---- v0.10 runtime-secondary-language swap ----
#
# Most sheet renderers in modelforge/builder/sheets/*.py read `label.it` directly
# (~30 call sites). Refactoring all of them to a runtime lang parameter is a v0.11
# scope item. As a v0.10 shim, callers can apply_runtime_secondary_lang("de")
# at the top of build_workbook(); this mutates every Label's `.it` slot to point
# at the requested secondary language. Existing code reading `.it` then renders
# in the requested language without modification.
#
# Limitations:
#   - Process-global state (sequential builds in different langs overwrite each
#     other). Build_workbook resets to "it" on exit (see workbook.py).
#   - Hardcoded Italian strings outside the Label-class system (e.g. monte_carlo
#     sheet titles) are NOT affected. These ship as v0.11 cleanup.

_ORIGINAL_IT_VALUES: dict[str, str] = {k: lbl.it for k, lbl in LABELS.items()}


def apply_runtime_secondary_lang(lang: str) -> None:
    """Mutate every Label's `.it` field to the requested secondary language.

    Pass `lang="it"` to restore the default Italian secondary.
    Pass `lang="en"` to make secondary identical to primary (effectively monolingual).
    """
    if lang not in SECONDARY_LANGS and lang != "it" and lang != "en":
        raise ValueError(
            f"Unknown secondary language '{lang}'. "
            f"Supported: {SECONDARY_LANGS} (or 'en' / 'it')."
        )
    for key, lbl in LABELS.items():
        if lang == "it":
            new_secondary = _ORIGINAL_IT_VALUES[key]
        elif lang == "en":
            new_secondary = lbl.en
        else:
            new_secondary = getattr(lbl, lang, "") or lbl.en
        object.__setattr__(lbl, "it", new_secondary)


def reset_runtime_secondary_lang() -> None:
    """Restore the original Italian secondary on every Label."""
    apply_runtime_secondary_lang("it")

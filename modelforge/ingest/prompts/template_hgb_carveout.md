# HGB Carve-out template — extractor guidance (v0.10 PREVIEW)

Target spec class: `modelforge.spec.hgb_carveout.HGBCarveoutSpec` (extends
`ThreeStatementSpec`).

⚠️ v0.10 PREVIEW — extraction reuses the 3-statement pipeline. The HGB-
specific block (`hgb_assumptions`) is hand-completed post-ingest until
v0.11 adds dedicated extraction rules for HGB Jahresabschluss / Steuerbilanz.

## A-id allocation

Same as 3-statement (see `template_three_statement.md`):
- `A-001 – A-019` — P&L drivers
- `A-020 – A-039` — BS drivers
- `A-040 – A-059` — HGB-specific (reserved for v0.11 expansion)

## Field → source

Inherits 3-statement field mapping. Additional HGB-specific fields:

| Field | Source |
|---|---|
| `hgb_assumptions.gewerbesteuer_hebesatz` | Local municipality (Hebesatz table — Munich ~490, Berlin ~410, Hamburg ~470, Frankfurt ~460, rural DE ~300-380) |
| `hgb_assumptions.hgb_form` | Existing P&L form in Jahresabschluss — usually `gesamtkostenverfahren` for German Mittelstand |
| `hgb_assumptions.soli_applicable` | Default true (Solidaritätszuschlag applies to corporates) |
| `hgb_assumptions.enable_hgb_steuer_recon` | Set true if Steuerbilanz available in dataroom; false if only Handelsbilanz |

## Sources to look for in DACH datarooms

- Handelsbilanz (HGB-form annual accounts)
- Steuerbilanz (tax-form for DTA/DTL reconciliation — often separate file)
- IFRS reconciliation if multinational parent group
- VCI sector benchmarks (Verband der Chemischen Industrie) for industry margins
- PwC / KPMG / EY Germany sector reports for capex norms

## v0.11 roadmap (out of scope for v0.10)

- Latente Steuern (DTA/DTL) extraction from § 274 disclosures
- § 252-256 valuation principle flags (Niederstwertprinzip etc.)
- GewSt Hinzurechnungen (§ 8 GewStG) line-item extraction
- BilMoG pension provision parameters

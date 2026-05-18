# Changelog

All notable changes to ModelForge.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [0.10.0] — 2026-05-18 — Foreign-Market Expansion

Retires Italian-only positioning. Ships the foreign-market substrate for a
US + UK + DACH + Nordic + Benelux GTM motion. Six persona interviews across
30 target firms drove the scope. See `PRD_v010_foreign_markets.md` for the
full design + rationale.

### Added
- **Multi-language label expansion** — `Label` class now supports EN + 7
  secondary languages (IT/DE/ES/SV/NO/DA/NL). All ~80 existing labels in
  `modelforge/builder/i18n.py` populated across all secondaries. SV/NO/DA/NL
  are flagged first-cut and emit `UserWarning` when used as secondary —
  design-partner native-speaker review encouraged.
- **`Label.get(lang)` accessor** — safe lookup with EN fallback. Backwards
  compatible with v0.9.x callers reading `.it` directly.
- **`build_workbook(..., secondary_lang="de")` parameter** — runtime swap
  of the secondary-language column. Implemented via a global label-dict
  mutation that auto-resets after build.
- **HGB Carve-out template (PREVIEW)** — `model_type: hgb_carveout`. DACH
  operational-turnaround / carve-out modeling with HGB-form P&L + BS, DE
  secondary labels, and a Handelsbilanz vs Steuerbilanz reconciliation
  stub sheet. Includes example `hgb_carveout_dach_chemicals.yaml`.
  ⚠️ Requires DACH accounting-expert review for production use.
- **Portfolio Review template (PREVIEW)** — `model_type: portfolio_review`.
  Quarterly portfolio-aggregation across N portcos with covenant cushion,
  leverage trend, EBITDA actual-vs-plan, internal rating distribution.
  Example `portfolio_review_us_lower_mm.yaml`.
- **20 new tests** at `tests/test_v010_foreign_markets.py` covering Label
  class, i18n coverage, runtime lang swap, template registration, and
  example round-trip builds.
- **PRD** at `PRD_v010_foreign_markets.md` documenting the v0.10 scope
  + persona research + risk register.

### Changed
- **README** scrubbed of "Italian private capital" positioning. Hero line
  now reads "Built for private capital teams who model deals at scale —
  US MM direct lending, UK/EU credit, DACH/Nordic special situations,
  distressed and turnaround." Tax-jurisdiction list reordered to put US
  and UK first. Template descriptions de-localized.
- **`templates/__init__.py` REGISTRY** grows from 14 → 16 entries. New
  `PREVIEW_TEMPLATES` constant exposes preview-flag templates to the CLI
  and MCP server.
- **`ingest/pipeline.py` TEMPLATE_SECTIONS** updated to cover the 2 new
  templates. HGB reuses `_three_statement_sections` (same spec shape).
  Portfolio review has its own minimal section builder.
- **Sensitivity factor registry** (`analytics/factors.py`) extended with
  `hgb_carveout` → `_THREE_STATEMENT` factor list, `portfolio_review` →
  placeholder. Aggregator-template sensitivity engine is v0.11 scope.

### Deferred to v0.11 / v0.12
- Native-speaker validation of SV/NO/DA/NL translations.
- Renderer-layer multi-language refactor — `modelforge/builder/sheets/*.py`
  currently hardcode `label.it` direct access. v0.10 ships a runtime
  monkey-patch as a shim; v0.11 refactors the ~30 call sites to read via
  `label.get(secondary_lang)`.
- Full HGB DTA/DTL math + § 252-256 valuation rule library.
- Portfolio aggregation auto-import from Allvue/eFront/Investran.
- LMA-specific covenant package templates.
- Italian-language hardcoded strings outside the Label class (Monte Carlo
  sheet titles, etc.) — small set, v0.11 cleanup.

### Strategic context
v0.10 closes the non-compete liability of the v0.9.x README (which marketed
the product as "Built for Italian private capital") and unblocks the
30-firm W1 outreach motion to foreign actors: US MM direct lenders,
UK/EU credit funds, DACH/Nordic special-situations shops, Benelux family
MM PE. See `PRD_v010_foreign_markets.md` §2 for the six-persona interview
that drove the prioritization.

## [0.9.7] — 2026-05-15 — Trust Layer v1

Trust Layer semantic gates (separate from structural QC) — 25+ built-in
plausibility rules across all 14 templates. Catches issues like DCF EV
8× real market cap before QA.

(Older versions: see git log.)

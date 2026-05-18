# Changelog

All notable changes to ModelForge.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [0.11.0] — 2026-05-18 — Quality Lift (Trust + HGB + Foreign Examples)

Closes the v0.10 PREVIEW/BETA gaps and pushes product quality toward the
SCORECARD round-3 target. Ships in the same session as v0.10. 667/667 tests
passing. PyPI publish still user-action.

### Added
- **6 new Trust Layer rules** — 2 for `hgb_carveout` (Hebesatz in legal DE
  range [200%, 900%]; effective tax above KSt + SolZ 15.83% floor) and 4
  for `portfolio_review` (avg leverage 1-12x; no impossible cushion <-100%;
  cash-trap concentration ≤25%; rating 4/5 portcos ≤30%). Total Trust rules
  now 30+.
- **HGB-Recon real math** — promoted from v0.10 documentation stub to v0.11
  BETA with three live-formula sections: § 8 GewStG Hinzurechnungen
  (interest add-back with €100k Freibetrag), Gewerbesteuer build (3.5%
  Steuermesszahl × user-supplied Hebesatz), and effective-tax-rate
  reconciliation (KSt 15% + SolZ 5.5% × KSt + GewSt vs spec assumption).
  Out-of-scope for v0.11 documented inline (Anlagevermögen § 252-256,
  BilMoG pensions, Real-estate / license-fee Hinzurechnungen).
- **5 new sheet-title labels** in `i18n.py` — Monte Carlo / Sensitivity /
  Reproducibility / Risk Analysis / Assumptions titles now go through the
  Label class with full EN + 7 secondary coverage. The Italian secondary
  is preserved; new languages render correctly when `secondary_lang` is
  swapped.
- **Foreign-market example** — `sponsor_lbo_us_saas.yaml`. US enterprise
  SaaS sponsor LBO ($85M revenue target). Country=US, currency=USD, SOFR
  reference rate, LSTA covenant pack references, IRS tax sources. Builds
  end-to-end (51KB workbook).
- **10 new tests** at `tests/test_v011_quality_lift.py` — Trust Layer
  coverage, HGB recon math verification, Hebesatz formula flow-through,
  hardcoded-Italian → Label class refactor, US sponsor LBO build,
  i18n validation on import.
- **i18n import-time coverage check** — `_validate_coverage()` runs once
  at module load; missing translations fail loudly during dev rather than
  at render time.

### Changed
- **Hardcoded Italian strings → Label class** in the 4 analytics sheet
  titles (`monte_carlo.py`, `reproducibility.py`, `risk_sheet.py`,
  `sensitivity.py`) and the Assumptions sheet title. These previously
  bypassed the multi-language system and rendered Italian regardless of
  `secondary_lang`. Now they participate correctly.
- **HGB template label** updated from "v0.10 PREVIEW" to "v0.11 BETA" —
  template now produces real numbers, not just documentation, but still
  requires DACH accounting-expert review for production use.
- **Total label count** in `i18n.py`: 80 → 85 labels.

### Renderer refactor — deferred decision
The "thread `secondary_lang` through every sheet builder" plan from v0.10
was reviewed and deferred to v0.12+. The current runtime-swap shim in
`apply_runtime_secondary_lang()` is functionally equivalent for sequential
build invocations (the actual usage pattern in CLI / MCP / SaaS shell).
The 83 hardcoded `.it` access sites in `modelforge/builder/sheets/*.py`
work correctly under the swap — they read whatever the runtime secondary
language is currently set to. A proper refactor remains valuable for
multi-tenant concurrent builds (true SaaS) but is not gating any v0.11
buyer persona.

### Deferred to v0.12
- Multi-tenant-safe renderer (thread `secondary_lang` through sheet
  builders to remove the global-state shim).
- Anlagevermögen valuation per HGB §§ 252-256 (impairment recon).
- BilMoG pension provision math (vs IAS 19).
- Real-estate + license-fee Hinzurechnungen (§ 8 Nr. 1 d/e/f GewStG).
- Latente Steuern § 274 DTA Aktivierungswahlrecht recon.
- UK/Nordic/Benelux foreign YAML examples (v0.11 ships 1 US example;
  v0.12 adds the rest using the same string-substitution pattern).
- Hardcoded Italian strings in specialized regulatory sheets
  (`compliance.py`, `ifrs9_ecl.py`) — content is inherently EU-regulatory,
  multi-language treatment is lower-leverage than v0.11 wedge.

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
  now reads "Built for [redacted] who model deals at scale —
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
v0.10 closes the [redacted] of the v0.9.x README (which marketed
the product as "[redacted]") and unblocks the
[redacted] W1 outreach motion to foreign actors: US MM direct lenders,
[redacted], [redacted] shops, Benelux family
MM PE. See `PRD_v010_foreign_markets.md` §2 for the six-persona interview
that drove the prioritization.

## [0.9.7] — 2026-05-15 — Trust Layer v1

Trust Layer semantic gates (separate from structural QC) — 25+ built-in
plausibility rules across all 14 templates. Catches issues like DCF EV
8× real market cap before QA.

(Older versions: see git log.)

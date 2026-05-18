# PRD v0.10 — Foreign-Market Expansion

**Version**: 0.10.0
**Status**: Approved for implementation (this session)
**Author**: Luka Stanisljevic
**Date**: 2026-05-18
**Tracking**: `PRD_v010_foreign_markets.md`

---

## 1. Summary

v0.10 retires ModelForge's Italian-only positioning and ships the foreign-market substrate needed for a US + UK + DACH + Nordic + Benelux GTM motion. Three buckets of work:

1. **Multi-language label expansion** — EN/IT today → EN + 7 secondaries (IT, DE, ES, SV, NO, DA, NL).
2. **HGB (German GAAP) template** — DACH carve-out / turnaround buyers cannot use IFRS-only templates.
3. **Foreign-market example library** — Italian-only examples (TIM, Iliad, Enel, Amplifon, CDMO) signal Italian specialization. v0.10 ships a balanced library.
4. **Portfolio aggregation template** — quarterly portfolio review across N companies (gap surfaced by every persona interview).

Strategic context: Luka is currently employed in Italian financial services with an active non-compete. Italian-market positioning in public-facing surface (README, examples, marketing) is a legal liability. v0.10 closes the gap.

---

## 2. Motivation — six persona interviews

Six persona interviews across the W1 [redacted] outreach list converged on one universal pain and four geographic differentiators:

**Universal pain (all 6 personas):**
- *"N analysts ship N versions of the same template to IC. Audit nightmare. Pre-IC rebuild eats hours."*

**Geographic differentiators driving v0.10:**

| Persona | Firm archetype | Key blocker for ModelForge adoption |
|---|---|---|
| Sarah Chen | US upper-MM direct lending (Antares, Golub, Sixth Street) | None new — sponsor_lbo + unitranche cover this. **Buyable today.** |
| Marcus Lee | US distressed (Centerbridge, Marathon, King Street) | None new — restructuring + structured_credit cover this. **Buyable today.** |
| Emma Bennett | UK/EU credit (AlbaCore, Bridgepoint) | Multi-language labels (DE/ES already advertised, must back the claim). |
| Klaus Hoffmann | DACH turnaround (AURELIUS, Mutares, Capvis) | HGB accounting reconciliation. EN/DE labels. |
| Anders Lindqvist | DACH/Nordic MM credit (Triton, EQT MM, Nordic Capital) | SV/NO/DA labels. |
| Sven Vandeberg | Benelux family MM PE (NPM, Waterland) | NL labels. |

**Conclusion**: v0.9.7 is buyable as-is for personas #1 + #2 (US-only buyers, ~10 firms in the W1 list). Personas #3–#6 (~20 firms) require v0.10 unlocks.

---

## 3. Goals & non-goals

**Goals**
- Eliminate Italian-only positioning from all public surface (README, example filenames, marketing copy).
- Make every label-driven sheet renderable in any of 8 languages (EN primary + 7 secondaries).
- Ship one preview HGB template good enough for a first-cut DACH turnaround model.
- Add ≥3 foreign-market examples spanning US, UK, DACH, Nordic.
- Ship one portfolio-aggregation template skeleton.

**Non-goals (explicitly deferred to v0.11+)**
- Native-speaker validation of SV/NO/DA/NL translations — first-cut today, design-partner refinement after.
- Full HGB §§ 252–256 valuation rule library — preview template only.
- Multi-currency consolidation depth (FX hedge accounting nuance) — flagged in personas but separate scope.
- Portfolio-aggregation auto-import from Allvue / eFront / Investran — manual YAML ingestion only in v0.10.

---

## 4. User stories

### US-1 — DACH turnaround analyst (Klaus persona)
*As an analyst at AURELIUS, I want to generate an HGB-aware carve-out model from a teaser YAML in under an hour, with DE/EN labels, so that I can return a first-cut underwriting view before the deal is gone.*

### US-2 — UK/EU credit underwriter (Emma persona)
*As an underwriter at AlbaCore, I want to render the same workbook in EN-primary with my choice of DE/ES/IT secondary labels depending on the source-doc language, so that my IC and the borrower's CFO both read the model in their own language.*

### US-3 — Nordic credit director (Anders persona)
*As Head of Credit at Triton, I want SV/NO/DA labels available so my Stockholm/Oslo/Copenhagen analysts can render labels in their native language without retranslating.*

### US-4 — Benelux MM investment director (Sven persona)
*As an Investment Director at NPM Capital, I want NL labels and a portfolio-aggregation template so my 12-pro team can run the quarterly review across 25 portcos in one workbook.*

### US-5 — Non-compete-safe positioning (Luka persona)
*As the author, I need the public README and example library to read as "private capital — multi-jurisdiction" not "Italian private capital," so that targeted outreach to non-Italian firms does not create a non-compete dispute with my current employer.*

---

## 5. Functional requirements

### FR-1 — Label class supports 8 languages

`modelforge.spec.base.Label` currently:
```python
class Label(BaseModel):
    en: str
    it: str = ""
```

v0.10:
```python
class Label(BaseModel):
    en: str          # primary, mandatory
    it: str = ""     # backwards-compatible Italian secondary
    de: str = ""     # German
    es: str = ""     # Spanish
    sv: str = ""     # Swedish
    no: str = ""     # Norwegian Bokmål
    da: str = ""     # Danish
    nl: str = ""     # Dutch
```

All fields beyond `en` are optional. When a renderer asks for a missing language, fall back to `en`. No existing code breaks.

### FR-2 — i18n.py ships full coverage for IT + DE + ES; first-cut for SV + NO + DA + NL

For every label currently in `i18n.py` (~80 keys), v0.10 populates all 7 secondaries. SV/NO/DA/NL marked `# DESIGN PARTNER REVIEW` in inline comments — these need native-speaker validation in v0.11.

### FR-3 — Builder accepts `lang` parameter

The builder API:
```python
build_model(spec, output_path, secondary_lang="de")
```

Default remains `it` for backwards compatibility. New `secondary_lang` values: `it | de | es | sv | no | da | nl | none`. Validated at boundary, raises on unknown.

### FR-4 — HGB template preview

New module: `modelforge/templates/hgb_carveout.py`.

Coverage (preview, not exhaustive):
- HGB § 264 ff. balance sheet structure (Aktiva / Passiva)
- HGB § 275 income statement (Gesamtkostenverfahren or Umsatzkostenverfahren — preview supports Gesamtkostenverfahren only)
- Handelsbilanz vs Steuerbilanz reconciliation row (latente Steuern — placeholder, not full DTA/DTL build)
- KSt + SolZ + GewSt (already in tax engine — reuse, with HGB-row mapping)
- DE secondary labels throughout

Stamped at top of file: `# v0.10 preview — requires DACH accounting-expert review before production use.`

### FR-5 — Portfolio aggregation template skeleton

New module: `modelforge/templates/portfolio_review.py`.

Per-portco rows × columns (entry leverage, current leverage, EBITDA actual vs plan, covenant headroom, cash trap status, next event). Aggregation summary block at top. Optional language secondary.

YAML spec sketch:
```yaml
template: portfolio_review
quarter: 2026-Q2
portfolio:
  - portco_id: PC-001
    name: TechCo
    sector: Software
    entry_leverage: 6.2
    current_leverage: 5.8
    ebitda_plan: 14.5
    ebitda_actual: 13.2
    next_covenant_test: 2026-09-30
    ...
```

### FR-6 — Foreign-market YAML examples (new)

Add to `examples/`:
- `sponsor_lbo_us_techco.yaml` — US sponsor-backed LBO ($800M EV)
- `unitranche_uk_servicesco.yaml` — UK direct lending unitranche (£250M)
- `real_estate_dach_logistics.yaml` — German logistics RE (€180M)
- `restructuring_nordic_industrials.yaml` — Swedish industrials restructuring
- `hgb_carveout_dach_chemicals.yaml` — DACH chemicals carve-out (HGB template)
- `portfolio_review_us_lower_mm.yaml` — US lower-MM credit fund portfolio review

Existing Italian examples (TIM, Iliad, Enel, Amplifon, CDMO, Stevanato) retained — they're real anonymized references for the IT secondary language. They're balanced by 6 new foreign examples, so the directory now reads as "global with IT support" not "Italian product."

### FR-7 — Tests

Per new module:
- Unit test: builder renders successfully in each new language
- Integration test: round-trip YAML → XLSX → QC pass for each new example
- Lint: ruff clean

### FR-8 — Version bump

`pyproject.toml`: `0.9.7` → `0.10.0`. `CHANGELOG.md` entry.

---

## 6. Technical design

### 6.1 — Label class refactor

Pydantic BaseModel addition of optional fields is backwards-compatible. The `__str__` method (returns `self.en`) is unchanged. Existing call sites that read `.it` directly continue to work; new call sites use `.get(lang)` accessor (added in v0.10) for safe lookup.

```python
class Label(BaseModel):
    en: str
    it: str = ""
    de: str = ""
    es: str = ""
    sv: str = ""
    no: str = ""
    da: str = ""
    nl: str = ""

    def __str__(self) -> str:
        return self.en

    def get(self, lang: str) -> str:
        """Return label in `lang`, falling back to `en` if missing."""
        val = getattr(self, lang, "") or self.en
        return val
```

### 6.2 — i18n.py rewrite scope

~80 labels × 6 new languages = ~480 translations. Domain vocabulary is limited and consistent (finance/accounting terms). Translation strategy:

- **DE**: Use Standard German finance vocabulary; some terms are international (EBITDA, ICR) and stay English.
- **ES**: Same.
- **SV/NO/DA**: First-cut from Swedish baseline, then localized for NO/DA dialect differences. Mark for review.
- **NL**: First-cut; mark for review.

### 6.3 — HGB template design pattern

Follows existing `sponsor_lbo.py` / `unitranche.py` pattern:
- Pydantic spec class
- Sheet modules (cover, sources, assumptions, hgb_aktiva, hgb_passiva, hgb_guv, recon_st_hb, qc)
- Tax module reuse (DE jurisdiction already shipped)

### 6.4 — Portfolio review template design

Different shape from existing per-deal templates: it's an N-portco aggregator, not a single-deal model. Subclasses a new `AggregatorTemplate` base instead of the existing `DealTemplate`.

---

## 7. Implementation plan — this session

Sequential because of dependency order. Each step gates the next:

| # | Step | Owner | Files | Done check |
|---|---|---|---|---|
| 1 | Extend `Label` class | Claude | `modelforge/spec/base.py` | Pydantic model accepts all 8 fields |
| 2 | Rewrite `i18n.py` with 7-language coverage | Claude | `modelforge/builder/i18n.py` | All 80 labels have IT + DE + ES + SV + NO + DA + NL |
| 3 | Builder `secondary_lang` parameter | Claude | `modelforge/builder/workbook.py` (or similar entry) | `build_model(..., secondary_lang="de")` works |
| 4 | HGB template stub | Claude | `modelforge/templates/hgb_carveout.py` | Module imports, `list_templates` shows it |
| 5 | Portfolio review template stub | Claude | `modelforge/templates/portfolio_review.py` | Module imports, `list_templates` shows it |
| 6 | Foreign YAML examples (6 files) | Claude | `examples/*.yaml` | Files exist, are valid YAML |
| 7 | Tests (smoke per language + per new template) | Claude | `tests/test_i18n_foreign.py`, `tests/test_hgb_carveout.py`, etc. | `pytest` passes |
| 8 | Version bump + CHANGELOG | Claude | `pyproject.toml`, `CHANGELOG.md` | Version reads 0.10.0 |
| 9 | Commit + push | Claude | `master` branch | `git status` clean, push successful |

---

## 8. Test plan

**Smoke tests (must pass before commit):**
- `pytest tests/` — full existing suite (504/504 passing baseline must stay)
- `modelforge build examples/sponsor_lbo_us_techco.yaml` — produces valid xlsx
- `modelforge build examples/hgb_carveout_dach_chemicals.yaml` — produces valid xlsx
- `modelforge list-templates` — shows 16 templates (14 original + hgb_carveout + portfolio_review)
- `modelforge audit-all examples/` — 0 FAIL violations on the new examples

**Manual verification (post-commit):**
- Open one xlsx per language; eyeball labels — flag anything that looks wrong
- DACH design partner: send `hgb_carveout_dach_chemicals.xlsx` for review

---

## 9. Rollout

1. Commit to `master`, push.
2. Tag `v0.10.0`.
3. GitHub release with CHANGELOG excerpt.
4. PyPI publish (`modelforge-finance==0.10.0`).
5. Update SaaS shell (`modelforge-saas.onrender.com`) to pick up v0.10 from PyPI.
6. Smoke test SaaS shell uploads still work.

**Post-rollout (not gating release):**
- Send hgb_carveout example to 1 DACH accounting contact for review.
- Send SV/NO/DA translations to 1 Nordic finance professional for review.
- Send NL translations to 1 Dutch finance professional for review.
- Update the W1 outreach pitch to reference v0.10 multi-language support.

---

## 10. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| First-cut SV/NO/DA/NL translations contain errors | High | Medium | Mark `# DESIGN PARTNER REVIEW` in code. Disclose in README. v0.11 backfill. |
| HGB preview template generates incorrect numbers | Medium | High | Stamp file with "preview, expert review required". Don't claim production-ready until reviewed. |
| Backward-compatibility break for existing IT users | Low | High | Label class additions are all optional with `""` default. `__str__` unchanged. Test that existing examples still build. |
| Italian-only message in v0.9.x → v0.10 changes alarms an Italian user / employer | Low | Low | The READMEs scrub is the cover. Public communication remains "expanded to multi-jurisdiction." |
| PyPI publish flow breaks (history: 3 failures in v0.9.5–0.9.7) | Medium | High | Run `python -m build` locally and smoke-check artifacts before tag/push. |
| New templates introduce regressions in existing 504-test suite | Medium | Medium | Test plan runs full suite before commit. Block commit if any failure. |

---

## 11. Open questions

1. Are `it` field defaults removing the auto-Italian-fallback the right semantics, or should an empty `it` field still fall back to EN at render time? **Decision: fall back to EN. Implemented in `.get(lang)` accessor.**
2. Do we keep Italian example filenames (`merger_tim_iliad.yaml`) or rename? **Decision: keep (they work and are anonymized references), but balance with 6 new foreign examples.**
3. Does the HGB preview ship as an opt-in feature flag or default-on? **Decision: default-on, with the preview stamp visible in `list-templates` output.**

---

## 12. Out of scope (parking lot for v0.11 / v0.12)

- Multi-currency consolidation depth (FX hedge accounting per IFRS 9 / ASC 815) — flagged by Emma persona.
- Native-speaker validation of all 4 new language packs (SV/NO/DA/NL).
- Allvue / eFront / Investran portfolio import integrations (Sven persona ask).
- LMA-specific covenant package templates (Emma persona ask).
- Bulge-tier Excel-style audit gates for the new HGB template (12-check QC extension).
- Spanish (ES) full coverage in the README marketing copy — currently advertised, validated after v0.10 ship.

---

## 13. Approval

✅ Approved 2026-05-18. Begin implementation immediately. Target: PyPI v0.10.0 published this session.

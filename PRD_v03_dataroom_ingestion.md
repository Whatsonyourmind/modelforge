# PRD — ModelForge v0.3: Data-room PDF → YAML Ingestion

| Field | Value |
|---|---|
| **Feature ID** | MF-v03-002 |
| **Owner** | L. Stanisljevic |
| **Target release** | ModelForge v0.3.1 |
| **Effort** | 5–8 engineering days (MVP); full 2-3 wk for all templates |
| **Priority** | P0 — biggest commercial gap (ModelForge 2/10 vs Rogo 9/10) |
| **Status** | Draft, ready for execution |
| **Depends on** | v0.3.0-pf (shipped 2026-04-16, commit `6583b46`) |
| **Companion** | `PRD_v03_pf_sculpted_amort.md` |

---

## 1. Problem statement

Every engagement starts with 2-4 hours of manual YAML authoring: Luka opens the data room, reads PDFs, transcribes numbers into the spec YAML, attaches source references. This blocks scaling to >3 concurrent engagements.

### 1.1 Commercial evidence

| Benchmark | Source-tracing | Deal-flow onboarding |
|---|---|---|
| **ModelForge v0.3.0-pf** | 9.4/10 (linkage graph) | 2/10 (hand YAML) |
| **Rogo Series C** | 3.6/10 | 9/10 (drag-drop) |
| **Macabacus** | 2.0/10 | 1/10 |

We already lead on quality downstream of the spec; the bottleneck is upstream. Closing this to ≥7/10 unlocks 5-10 concurrent engagements at current staffing (Luka solo).

### 1.2 What good looks like

```
$ modelforge ingest ~/DealRoom_Enfinity/ --template project_finance -o enfinity.yaml
[*] Scanning 14 files ...
    - Enfinity_Press_Release.pdf        [press]        → S-001
    - Terna_Irradiation_Report_2025.pdf [benchmark]    → S-003
    - PPA_Executed_Copy.pdf             [contract]     → S-004
    - FY24_Audited_Financials.xlsx      [financials]   → S-005
    ...
[*] Extracting project_finance spec (Claude Opus 4.6, cached schema) ...
    ✓ target            (4 fields, 4 sourced)
    ✓ sources           (8 entries, 6 verified)
    ✓ construction      (4 assumptions, 3 sourced, 1 needs review)
    ✓ operating         (5 assumptions, 5 sourced)
    ✓ debt              (6 assumptions, 6 sourced)
    ✓ covenant          (20 thresholds, inferred from Green Loan covenant terms)
    ✓ equity            (2 assumptions, 2 sourced)
[*] Wrote enfinity.yaml (valid ProjectFinanceSpec)
[*] Wrote INGESTION_REPORT.md (confidence: 0.82; 3 fields need review)

Next:  modelforge build enfinity.yaml
```

Target: **~30 min** including user review, down from 2-4 hours.

---

## 2. Goals & non-goals

### 2.1 Goals

1. New `modelforge ingest <dataroom_dir>` command that produces a valid Pydantic-validated YAML spec.
2. Supports PDF, XLSX, CSV input. Gracefully skips unsupported types with a warning.
3. Auto-populates Sources registry with `{id, doc, page, publisher, date, url, verified}` for every referenced doc.
4. Every numeric Assumption has a `source_id` pointing to a real doc page; hallucinated citations are structurally impossible.
5. Emits `INGESTION_REPORT.md` with per-field confidence, extraction provenance, and human-review queue.
6. Uses Anthropic SDK with **prompt caching** on the extraction schema (cache hit rate ≥ 80% across sections).
7. MVP scope: `project_finance` template only (perfect round-trip with `real_enfinity_solar_pf.yaml`).
8. Optional ruthlessness: `--strict` flag treats any Pydantic validation error as build-blocking; default is best-effort + review queue.

### 2.2 Non-goals (for this MVP)

- OCR on scanned PDFs (assume text-extractable; warn if not).
- Templates 1–3, 5–8 (follow-up item `v0.3.2-ingest-wide`; same pipeline).
- Multi-document cross-reference resolution ("this number in the IM matches the press release").
- Real-time streaming UI. CLI-only.
- Multi-tenant auth / per-deal audit logs.
- Agentic retry loops with tool use beyond one structured call per section.

---

## 3. Users & user stories

### 3.1 Personas

- **P1 — Luka (primary)**: drops a data-room folder and gets a 90% pre-filled YAML to review.
- **P2 — Client analyst (junior)**: uses ingestion to jumpstart work on their own deals without transcribing.
- **P3 — Rating-agency reader (downstream)**: never sees ingestion directly; reads the final workbook. Their requirement: every extracted number must be citable to a doc page.

### 3.2 Stories

- **US-1**: *As Luka, I want to run one command on a folder of PDFs and get a pre-filled YAML with every number traceable to a doc page, so my 2-4h onboarding collapses to 30 min.*
- **US-2**: *As Luka, I want an explicit review queue ("3 fields need review") so I know exactly where to focus my judgment, rather than checking every line.*
- **US-3**: *As Luka, I want the output to round-trip cleanly — ingest → build → QC 8/8 — so the ingestion pipeline doesn't produce "nearly-valid" YAMLs that fail downstream.*
- **US-4**: *As a rating-agency reader, I want the final workbook cells to trace back to real doc pages, not LLM-fabricated references.*

---

## 4. Functional requirements

### FR-1 — Module layout (`modelforge/ingest/`)

```
modelforge/ingest/
  __init__.py
  cli.py                  # registered under `modelforge ingest`
  pipeline.py             # orchestrator
  readers/
    __init__.py
    pdf_reader.py         # pdfplumber primary, pypdf fallback
    xlsx_reader.py        # openpyxl-based
    csv_reader.py         # pandas or csv stdlib
  classifier.py           # Claude classifies each doc into a type
  extractor.py            # Claude structured-output extraction
  schemas.py              # Pydantic schemas for tool_use
  confidence.py           # scoring rules
  reporter.py             # INGESTION_REPORT.md emitter
  prompts/
    classifier_system.md
    extractor_system.md
    template_project_finance.md   # template-specific guidance
```

### FR-2 — Document readers

Each reader returns a normalized structure:

```python
@dataclass
class DocChunk:
    doc_filename: str
    page: int | None         # 1-based; None for single-page formats
    text: str
    kind: Literal["text", "table", "header"]
    meta: dict               # optional: bbox, sheet_name, etc.

@dataclass
class DocIndex:
    doc_filename: str
    path: Path
    mime: str
    total_pages: int
    chunks: list[DocChunk]
    publisher_hint: str | None      # extracted from header/metadata
    date_hint: date | None
    verified: bool = False           # True if .xlsx audited or .pdf signed
```

**PDF reader**: `pdfplumber` as primary (good table extraction), `pypdf` fallback for text-only. Skip if < 20 characters extracted (likely scanned → warn).

**XLSX reader**: iterate sheets, emit one chunk per sheet with cell values flattened as markdown table.

**CSV reader**: single chunk, full file as markdown table.

### FR-3 — Document classifier (`classifier.py`)

One Claude call per document (cached by doc content hash on re-runs). Returns:

```python
class DocClass(BaseModel):
    doc_filename: str
    doc_type: Literal[
        "press_release", "information_memorandum", "audited_financials",
        "unaudited_financials", "contract_ppa", "contract_loan",
        "market_benchmark", "regulatory_filing", "rating_report",
        "legal_opinion", "operational_report", "other",
    ]
    publisher: str
    date: Optional[date]
    verified: bool           # True if signed/audited/regulatory
    relevance_hint: str      # short: what this doc tells us
    confidence: Literal["H", "M", "L"]
```

Uses Claude with tool_use. System prompt = `classifier_system.md`; user prompt = first 3000 chars of doc + filename.

Prompt caching: system prompt + tool schema cached (80%+ hit rate across docs).

### FR-4 — Extractor (`extractor.py`)

One Claude call per template section (target/construction/operating/debt/covenant/equity). Returns structured data matching the template's Pydantic section.

**Schema approach**: For each template section, derive the Claude `tool_use` schema automatically from the Pydantic model via `Model.model_json_schema()`. Claude is forced to return JSON matching the schema.

**Prompt structure**:
```
SYSTEM: [extractor_system.md — how to produce ModelForge-spec Assumption objects,
         citing source_id, writing rationale, choosing confidence]
USER:   Extract the <section> section for a project_finance template.
        Target template guidance: [template_project_finance.md]
        Available sources:
          S-001: Enfinity press release, 2025-08-15, verified
          S-002: Terna irradiation report, 2026-01-30, verified
          ...
        Relevant doc excerpts (with page refs):
          [S-001 p.1] "€316M financing for 276MW..."
          [S-003 p.22] "Italian solar irradiation 1,500-1,650 kWh/kWp/yr..."
          ...
        Return JSON per the OperatingPhase schema. Every Assumption MUST include
        source_id pointing at a valid S-id and cite the rationale from doc text.
```

Caching: the long SYSTEM + tool schema is cached; USER section is per-call.

**Retry logic**: if Pydantic validation fails, feed the error back into a second call (max 2 retries). After 2 failures, mark section as needs-review and emit placeholder with `confidence: L`.

### FR-5 — Source registry

Auto-assigns `S-001`, `S-002`, ... in order of first reference across all extracted fields. Every doc that contributed a fact gets a `Source` entry.

Pydantic:
```python
class Source(BaseModel):
    id: str = Field(pattern=r"^S-\d{3,}$")
    doc: str        # from DocIndex.doc_filename
    page: int | None
    publisher: str
    date: date
    url: str | None
    verified: bool
    note: str       # one-line summary
```

Notes are auto-generated from the classifier's `relevance_hint`.

### FR-6 — Pipeline orchestration (`pipeline.py`)

```python
def ingest(
    dataroom_dir: Path,
    template: str,
    output_yaml: Path,
    strict: bool = False,
    max_docs: int = 50,
    model: str = "claude-opus-4-6",
) -> IngestionResult:
    # 1. Discover files
    files = discover(dataroom_dir, max_docs=max_docs)

    # 2. Read & index
    indexes = [read_any(f) for f in files]

    # 3. Classify (1 call per doc)
    classes = classify_all(indexes, model=model)

    # 4. Assign S-ids
    sources = assign_source_ids(indexes, classes)

    # 5. Build extraction context (relevant chunks per section)
    context = build_context(indexes, classes, sources)

    # 6. Per-section extraction (1 call per section)
    spec_dict = {"model_type": template, "meta": default_meta(template)}
    for section in SECTIONS[template]:
        spec_dict[section] = extract_section(
            template, section, context, sources, model=model,
        )

    # 7. Validate
    spec_cls = TEMPLATE_REGISTRY[template]
    try:
        spec = spec_cls(**spec_dict)
    except ValidationError as e:
        if strict:
            raise
        spec_dict = repair_or_placeholder(spec_dict, e)
        spec = spec_cls(**spec_dict)  # may still fail → reported, not raised

    # 8. Emit YAML + report
    write_yaml(output_yaml, spec.model_dump(mode="json"))
    write_report(output_yaml.with_suffix(".ingestion.md"), spec, sources, context)
    return IngestionResult(...)
```

### FR-7 — Confidence scoring

Per-field confidence built from:
- **Source quality**: audited/regulatory = H; press/IM = M; inferred/unsourced = L.
- **Number specificity**: exact numbers from doc text = H; estimated from range = M; industry benchmark with no doc = L.
- **LLM self-reported**: the extractor's own `confidence` field is taken as a signal but overridden by source quality if lower.

Overall ingestion confidence = weighted mean of field confidences.

### FR-8 — CLI surface

```
modelforge ingest <dataroom_dir> [OPTIONS]

Options:
  -t, --template TEXT       Target template (default: project_finance)
  -o, --output PATH         Output YAML path (default: <dir_name>.yaml)
  --model TEXT              Anthropic model (default: claude-opus-4-6)
  --max-docs INT            Cap docs scanned (default: 50)
  --strict                  Fail on any Pydantic error (default: best-effort)
  --dry-run                 Classify + report only, no extraction
  --cache/--no-cache        Use Anthropic prompt caching (default: on)
  -v, --verbose             Per-step timing + cache hit stats
```

### FR-9 — INGESTION_REPORT.md

Emitted alongside the YAML. Structure:

```markdown
# Ingestion Report — {dataroom_name}

**Template**: project_finance
**Model**: claude-opus-4-6
**Overall confidence**: 0.82
**Cache hit rate**: 86%
**Elapsed**: 47s
**Cost estimate**: $0.42

## Documents processed
| S-id | Doc | Pages | Type | Verified |
|---|---|---|---|---|
| S-001 | Enfinity_Press.pdf | 2 | press_release | ✓ |
...

## Fields extracted
| Section | Field | Value | S-id | Confidence | Notes |
|---|---|---|---|---|---|
| construction | total_capex | 316.0 | S-001 | H | "€316M financing per press release" |
| operating    | revenue_yr1 | 32.1 | S-003 | M | "1,550 kWh/kWp × 276MW × €75/MWh = 32.1M" |
...

## Review queue (needs human judgment)
- `operating.maintenance_reserve_pct`: no doc mention; defaulted to industry-standard 2%.
- `covenant.dscr_op1`: extrapolated from Green Loan template; verify against signed term sheet.
- `debt.arrangement_fee_pct`: not disclosed; used EIB benchmark 1.25%.

## Cache statistics
- classifier system: 14 calls, 13 hits (93%)
- extractor system: 6 calls, 5 hits (83%)
```

---

## 5. Technical design

### 5.1 Anthropic SDK usage

```python
from anthropic import Anthropic
client = Anthropic()

# Prompt caching: mark long system prompt + tool schema as cached
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": EXTRACTOR_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ],
    tools=[
        {
            "name": "emit_operating_phase",
            "description": "Emit the operating phase of a project_finance spec.",
            "input_schema": OperatingPhase.model_json_schema(),
            "cache_control": {"type": "ephemeral"},
        }
    ],
    tool_choice={"type": "tool", "name": "emit_operating_phase"},
    messages=[{"role": "user", "content": user_prompt}],
)
# Parse response.content[0].input as dict
```

### 5.2 Schema derivation from Pydantic

Every template's section models already exist (`construction: ConstructionPhase`, `operating: OperatingPhase`, etc.). The extractor calls `Section.model_json_schema()` to get a valid JSON schema for `tool_use.input_schema`. This guarantees downstream Pydantic validation parity.

**Known wrinkle**: JSON schema from Pydantic v2 emits `$ref` / `$defs` for nested models. Claude's tool_use expects inline schemas. Use `pydantic.json_schema.models_json_schema(..., ref_template="{model}", mode="serialization")` + post-process to inline `$defs` references.

### 5.3 Context budgeting

Per section, pass ~10-20 most-relevant doc chunks (selected by simple keyword match against field names + LLM classifier hints). Total USER payload ≤ 40k tokens per call.

For MVP: naive keyword retrieval (regex on field names like "revenue", "capex", "DSCR"). Phase 2: embeddings-based retrieval.

### 5.4 Prompt caching strategy

Each cached block = system prompt + tool schema. Since:
- Classifier uses one cached block across all docs (N docs = N-1 cache hits on 2nd+)
- Extractor uses one cached block per SECTION across templates (reused if section appears in multiple templates)

Target: ≥ 80% cache hit rate; verified in INGESTION_REPORT.md.

### 5.5 Failure modes + handling

| Failure | Handling |
|---|---|
| Scanned PDF (no text) | Warn, skip, add to review queue |
| Pydantic validation error | Retry once with error feedback; if fails, emit placeholder + add to review queue |
| Claude API error (rate limit / 5xx) | Exponential backoff, max 3 retries per call |
| No `source_id` for a required Assumption | Use `S-999` ("unsourced"), confidence L, add to review queue |
| Missing API key | Fail fast with clear message pointing to `ANTHROPIC_API_KEY` |
| Empty data room | Fail fast before any API calls |

### 5.6 Testing strategy

```
tests/test_ingest_readers.py     # PDF/XLSX/CSV extraction
tests/test_ingest_classifier.py  # mocked Claude responses
tests/test_ingest_extractor.py   # schema derivation + validation
tests/test_ingest_pipeline.py    # end-to-end with offline fixtures
tests/test_ingest_e2e.py         # real Claude call, marked @pytest.mark.live
tests/fixtures/dataroom_enfinity_synth/  # curated synthetic data room
  enfinity_press.pdf       (generated from public press release text)
  terna_irradiation.pdf    (synthetic)
  ppa_executed.pdf         (synthetic)
  fy24_financials.xlsx     (synthetic)
```

Live e2e test: `pytest -m live` skipped by default; runs manually to verify the real pipeline ships a clean YAML that builds clean via v0.3.0-pf.

---

## 6. Acceptance criteria

| # | Criterion | Verification |
|---|---|---|
| AC-1 | `modelforge ingest --help` registers the new command | CLI smoke test |
| AC-2 | `modelforge ingest tests/fixtures/dataroom_enfinity_synth/ --template project_finance` produces a valid YAML that passes `ProjectFinanceSpec.model_validate` | pytest |
| AC-3 | Resulting YAML builds clean via `modelforge build` (inherits v0.3.0-pf behaviour) | integration test |
| AC-4 | Built workbook passes `modelforge qc` 8/8 | audit script |
| AC-5 | Every numeric Assumption in the YAML has a `source_id` matching a `Source` entry | structural audit |
| AC-6 | INGESTION_REPORT.md emitted with document list, field table, review queue | file-existence + schema check |
| AC-7 | Cache hit rate ≥ 80% across a 5+ doc ingest (verified in report) | pytest assertion |
| AC-8 | Unit tests: readers (3+ cases), classifier (mocked, 2+), extractor (schema derivation, 2+), pipeline (1 e2e offline) | pytest |
| AC-9 | Graceful skip on unsupported file types (no crash) | pytest |
| AC-10 | `--dry-run` completes without calling extraction API | smoke test |
| AC-11 | Missing `ANTHROPIC_API_KEY` produces a clear error (not a stack trace) | pytest |
| AC-12 | No regression: existing 10 workbooks still build + QC 8/8 | full regression |

---

## 7. Risks & mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | LLM hallucinates source_id or page number | Medium | High | Schema-constrained tool_use; Pydantic pattern validation on source_id format; cross-check against Source registry at assembly |
| R-2 | Context-window overflow on large data rooms | Medium | Medium | Keyword-filtered chunk selection; ≤ 40k tok per call; fall back to per-field retrieval |
| R-3 | Prompt cache miss rate > 20% (cost explosion) | Low | Medium | Telemetry in report; unit test with mock counting cache flags |
| R-4 | Pydantic schema → tool_use JSON schema translation has edge cases | High | Medium | Dedicated test file; inline `$defs`; manual override for known-gnarly fields (dates, Literal enums) |
| R-5 | User's data room has scanned PDFs | Medium | Low | Warn + skip; v0.3.2 adds OCR |
| R-6 | Over-spend on Claude API during dev | Medium | Low | `--max-docs` cap; `--dry-run` for iteration; always use cached blocks |
| R-7 | Non-determinism from LLM makes tests flaky | High | Medium | Mock Claude responses in unit tests; separate `@live` marker for real calls |

---

## 8. Out of scope (explicitly)

- OCR on scanned PDFs (queued as v0.3.2).
- Templates other than `project_finance` (queued as v0.3.2-ingest-wide).
- Agentic multi-turn extraction with tool-loop.
- Cross-document reconciliation ("this number in doc A conflicts with doc B").
- Data-room diff detection on re-runs.
- Persistent per-deal extraction cache (beyond Anthropic's 5-min TTL).
- Web UI / drag-drop interface.

---

## 9. Milestones & timeline

| Day | Milestone | Deliverable |
|---|---|---|
| D1 | Module scaffolding + PDF reader | `modelforge/ingest/` skeleton + `pdf_reader.py` returning DocChunks on a sample PDF |
| D2 | XLSX/CSV readers + discovery | `xlsx_reader.py` + `csv_reader.py` + `discover()` |
| D3 | Classifier (real Claude call, cached) + synthetic fixture data room | Classifier passes on ≥ 4 doc types; fixtures committed |
| D4 | Extractor + Pydantic→JSONSchema derivation | Extract `construction` section end-to-end for synthetic PF data room |
| D5 | Pipeline + Source ID assignment + YAML emission | End-to-end ingest → valid YAML that validates against spec |
| D6 | CLI + INGESTION_REPORT.md + confidence scoring | `modelforge ingest` CLI works; report matches PRD §4.9 |
| D7 | Full test suite + cache rate verification | AC-1..AC-11 pass; `pytest -m 'not live'` green in < 10s |
| D8 | Real-deal E2E (Enfinity synthetic data room → YAML → build → QC 8/8) | AC-12 confirmed; commit + tag `v0.3.1-ingest` |

Stretch (D9): broaden to `unitranche` template; update SCORECARD.md ingestion score 2→7.

---

## 10. Success metrics (7 days post-ship)

1. **Round-trip**: ingest → YAML → build → QC 8/8 on the synthetic Enfinity data room. **Target: binary yes.**
2. **Time to YAML**: < 2 minutes wall-clock on 10-doc data room. **Target: ≤ 120s.**
3. **Cache hit rate**: ≥ 80% (verified in report on every run). **Target: ≥ 80%.**
4. **Cost per ingest**: ≤ $1.00 for a 10-doc PF data room. **Target: ≤ $1.**
5. **Source coverage**: ≥ 90% of numeric Assumptions carry a `source_id`. **Target: ≥ 90%.**
6. **Scorecard move**: ingestion criterion 2/10 → 7/10 (MVP); → 9/10 once templates 1,3,5-8 covered in v0.3.2.

---

## 11. Rollout & naming

- Commit: `feat(ingest): v0.3.1 data-room PDF→YAML ingestion (project_finance MVP)`
- Tag: `v0.3.1-ingest`
- New optional dependency group in `pyproject.toml`:
  `[project.optional-dependencies] ingest = ["anthropic>=0.89", "pdfplumber>=0.11", "pypdf>=5.0"]`
- Install: `pip install -e .[ingest]`
- Docs: new `README.md` section; PRD committed alongside.

---

## 12. Follow-up items (post-ship)

- **v0.3.2-ingest-wide**: extend to all 8 templates. Est. 2-3 days (same pipeline, per-template prompt files).
- **v0.3.3-ocr**: Tesseract integration for scanned PDFs. Est. 1 day.
- **v0.3.4-embeddings**: replace keyword retrieval with embeddings (voyage or Cohere). Est. 2 days.
- **v0.3.5-reconcile**: cross-document fact reconciliation with contradiction flagging. Est. 3-5 days.
- **v0.4-web-ui**: drag-drop upload + live extraction progress (Phase 3 of roadmap).

---

**Prepared**: 2026-04-16 · **Author**: L. Stanisljevic + Claude · **Ready for execution.**

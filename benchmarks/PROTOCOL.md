# ModelForge Public Benchmark — Pre-Registered Protocol v1

**Status: PRE-REGISTERED.** This protocol, the three deal briefs, the ground
truth (`harness/ground_truth.py`) and the scorer (`harness/score.py`) are
frozen **before any benchmark arm is run**. Any later change to metrics,
tolerances, briefs, or extraction rules must be recorded in the *Deviations*
section at the bottom of this file with a date and a reason. Results produced
after an undisclosed change are void.

---

## 1. Question

When the *same* frontier-model class authors a financial model two ways —
through ModelForge's spec-driven deterministic compiler vs. free-form Excel
generation with `openpyxl` — how do the artifacts compare on correctness,
auditability, and reproducibility?

## 2. Arms

| Arm | Name | What it is |
|---|---|---|
| **A** | ModelForge spec-driven build | The frozen YAML spec in `specs/` (a faithful restatement of the brief) compiled by `python -m modelforge.cli build` into an `.xlsx`. The spec authoring step is part of the arm: the specs were written once from the briefs and frozen with this protocol. |
| **B** | Frontier-agent free build | A frontier coding agent (same model class as ModelForge's authoring LLM) is given the brief markdown verbatim plus the §5 instruction block below, and writes/runs its own `openpyxl` Python code to produce an `.xlsx`. No ModelForge code, no template, no human edits. |

**Runs:** Arm B = **3 independent runs per brief** (fresh context each run,
no memory of prior runs). Arm A = 1 build per brief, plus a determinism
re-build for metric m4 (the build is deterministic by design; re-running it
is the test, not a sample).

**Briefs (3):** `briefs/lbo_us_saas.md`, `briefs/dcf_industrial.md`,
`briefs/three_statement_mfg.md`. Each brief is fully parameterized and
solvable unambiguously; ground truth is computed clean-room (plain math +
`numpy_financial`, zero ModelForge imports) by `harness/ground_truth.py`.

**Artifact naming (required by the scorer):**
`<brief_id>__arm<A|B>__run<k>.xlsx` — e.g. `lbo_us_saas__armB__run2.xlsx`.

## 3. Honesty caveats (read before citing any result)

1. **Arm B is a raw frontier-agent + openpyxl baseline.** It is **NOT** a
   measurement of Microsoft Copilot, Shortcut.ai, or any other commercial
   Excel-generation product. No claim about those products may be sourced to
   this benchmark.
2. **Same model class.** Arm B must use the same frontier-model class that
   ModelForge's own authoring/ingest path uses. Comparing a strong compiler
   against a weak model would be meaningless; record the exact model ID of
   every arm-B run in `results/results.json` (`model_id` field).
3. **Agents get a fair, explicit quality bar.** The §5 instruction block
   tells arm-B agents exactly what is graded — zero formula errors, live
   formulas rather than pasted constants, labeled headline cells, source
   attribution, completeness items. Nothing in the grading is a hidden
   "gotcha" the agent was never asked for.
4. **The spec author saw the engine.** The arm-A specs were written by people
   who know ModelForge's conventions. That is the product's intended
   workflow, but it means arm A is "expert use of tool A" vs arm B "expert
   prompt of tool B"; it is not a blind A/B of equal effort.
5. **Three briefs is a small N.** Results are directional evidence about
   *these three model types*, not a general theorem about all financial
   modeling.
6. **Conflict of interest.** The benchmark is authored and scored by the
   ModelForge project. Mitigations: pre-registration, clean-room ground
   truth, third-party recalculation engine (`formulas`), deterministic
   scorer, all inputs/outputs published for independent re-runs.

## 4. Metrics (exact definitions)

All metrics are computed by `harness/score.py` deterministically from the
`.xlsx` artifacts. The recalculation engine is the third-party `formulas`
package (clean-room re-evaluation of every formula; cached values are not
trusted), the same approach as `modelforge/qc/workbook_audit.py` — the scorer
re-implements it without importing ModelForge.

### m1 — `formula_error_cells` (lower is better; 0 is the bar)

Count of distinct cells that are Excel errors, found by EITHER:
(a) recalculating every formula with `formulas` and collecting evaluated
results matching `^#(REF|DIV/0|VALUE|NAME|NUM|N/A|NULL)`, or
(b) scanning cached cell values (openpyxl `data_only=True`) for the same
error literals. Cells are deduplicated across (a) and (b). If the `formulas`
engine cannot load a workbook at all, that is recorded in `notes` and the
workbook is scored on (b) only — and m1 is flagged `recalc_failed` (an
artifact a third-party engine cannot even parse cannot demonstrate zero
errors).

### m2 — `headline_accuracy` (higher is better; range 0–1)

Fraction of the brief's headline outputs whose extracted workbook value
matches clean-room ground truth within **0.5% relative tolerance**:
`|got − truth| / |truth| ≤ 0.005`. Exception: `final_balance_check`
(truth = 0) passes iff `|got| ≤ 0.01` (i.e. the balance sheet ties within
$10k on a $500m+ balance sheet). A headline that cannot be located at all
scores 0 (and is listed in `notes`).

Headline sets (defined in the briefs):

| Brief | Headlines |
|---|---|
| lbo_us_saas | `sponsor_irr`, `sponsor_moic`, `exit_equity_proceeds`, `sponsor_equity_cheque` |
| dcf_industrial | `wacc`, `enterprise_value`, `equity_value`, `implied_price_per_share` |
| three_statement_mfg | `final_net_income`, `final_total_assets`, `final_total_liabilities_equity`, `final_balance_check`, `final_cash`, `final_debt` |

**Extraction — arm A (fixed cells via labeled rows):** ModelForge layouts are
deterministic; the scorer locates the labeled row on the known sheet and
reads column D (scalar sections) or the final-year column (grid sections).
Documented exhaustively in `score.py::ARM_A_EXTRACTORS`. Key anchors:
SourcesUses "Strategic sale" returns block (IRR/MoIC), SourcesUses sponsor
cash-flow row at exit-year column (exit proceeds), SourcesUses "Sponsor
equity (new money)" (cheque), WACCBuild "WACC", Valuation "Enterprise
Value"/"Equity Value"/"Implied price per share", Model sheet last-column
P&L/BS rows.

**Extraction — arm B (label search):** the scorer scans every sheet for
string cells matching per-headline regex patterns (with per-headline
exclusion patterns, e.g. `sponsor_irr` excludes `lender|hurdle|blended`),
then takes the nearest numeric value to the right in the same row
(recalculated value preferred, cached value as fallback). For
final-year headlines the **last** numeric cell in the matched row is taken.
Patterns are frozen in `score.py::ARM_B_PATTERNS`. The §5 instruction block
tells agents to label these cells; an unlabeled headline scores 0 by
definition (auditability is the point).

### m3 — `hardcode_rate` (lower is better; range 0–1)

`numeric-constant cells / (numeric-constant cells + formula cells)`,
computed over all sheets EXCEPT input-designated sheets — a sheet is
input-designated iff its name (case-insensitive) contains any of:
`assumption, input, source, cover, readme, instruction, toc, index,
reproducib, redflags, compliance`. Excluded from the numerator and
denominator: booleans, and integer values in `[1900, 2100]` (calendar-year
headers). Identical rule for both arms (this is the Moat-gate
"fully-formulated live outputs" idea applied symmetrically). Note: this
penalizes derived rows pasted as constants; legitimately hardcoded *inputs*
belong on input-designated sheets — which is itself the discipline being
measured.

### m4 — `reproducibility`

*Arm A:* build each spec **twice** in separate processes with
`SOURCE_DATE_EPOCH=1767225600` pinned, writing to the **same filename** in
two different temp directories (the Trust/Moat sheets echo the output
filename, so differing names would trivially break byte-identity without
measuring anything real); metric = `byte_identical` (boolean, SHA-256
equality of the two files). Better = `true`.

*Arm B:* across the 3 runs of each brief: (i) `headline_value_range` — for
each headline, `(max − min) / |mean|` across runs that produced a value
(0 = perfectly stable; lower is better); (ii) `structural_identical` —
boolean: all 3 runs have identical sheet-name sets and identical per-sheet
`(max_row, max_col, formula_count)` triples. Arms are reported side by side
without pretending the two sub-metrics are the same number.

### m5 — `lineage` (boolean; true is better)

`true` iff the workbook carries any input attribution: (a) a sheet whose
name matches `source|lineage|assumption` (case-insensitive) containing at
least 3 non-empty string cells, OR (b) at least 5 cell comments anywhere in
the workbook. This is deliberately a low bar — it asks "is there *any*
sources/assumptions surface", not "is it good".

### m6 — `completeness` (higher is better; range 0–1)

Fraction of the brief's required components present, detected by
case-insensitive regex over all string cells and sheet names:

| Brief | Checklist items (4 / 4 / 3) |
|---|---|
| lbo_us_saas | sources&uses (`sources\s*(&\|and)\s*uses\|uses of funds`); debt schedule (`debt schedule\|debt roll\|amorti[sz]ation schedule` or sheet named `debt`); returns (both `\bIRR\b` and `MoIC\|money multiple\|multiple.*capital`); sensitivity (`sensitivit\|tornado` in sheet name or cells) |
| dcf_industrial | WACC build (`WACC\|cost of capital`); terminal value (`terminal value\|gordon\|perpetuity`); FCFF forecast (`FCFF\|free cash flow\|NOPAT`); sensitivity (as above) |
| three_statement_mfg | P&L (`net income`); balance sheet (`total assets`); cash flow statement (`cash flow\|CFO\|operating activities`); BS tie (extracted `final_balance_check` exists and `\|value\| ≤ 0.01`) |

## 5. Arm-B agent instruction block (verbatim, appended to each brief)

> Build this model as a single `.xlsx` using Python + openpyxl (any version).
> Quality bar your output is graded on:
> 1. Zero Excel formula errors (#REF!, #DIV/0!, #VALUE!, #NAME?, #NUM!,
>    #N/A, #NULL!) — the file is re-evaluated with an independent engine.
> 2. Derived rows must be **live formulas**, not pasted constants. Put
>    hardcoded inputs on a sheet whose name contains "Assumptions" or
>    "Inputs".
> 3. Show each headline output named in the brief in its own clearly labeled
>    cell (label text in the same row, value to the right of the label).
> 4. Include a "Sources" or "Assumptions" sheet attributing every input to
>    the brief.
> 5. Include the components in the brief's completeness checklist.
> 6. The file must open cleanly in Excel/LibreOffice. Use plain formulas
>    (no VBA, no external links, no array spills required).
> Output only the final `.xlsx` artifact.

## 6. Scoring tolerances and tie-breaks (summary)

| Metric | Tolerance / rule | Better |
|---|---|---|
| m1 formula_error_cells | exact count; 0 is the institutional bar | lower |
| m2 headline_accuracy | 0.5% relative; balance check ±0.01 absolute | higher |
| m3 hardcode_rate | exact ratio, rules in §4 | lower |
| m4 reproducibility | A: byte-identity; B: range + structural bool | A: true; B: lower/true |
| m5 lineage | boolean, rule in §4 | true |
| m6 completeness | fraction of checklist | higher |

No aggregate "winner score" is computed. Metrics are reported per brief ×
arm × run in `results/results.json` and `results/RESULTS.md`; readers weigh
them.

## 7. Environment

- Python ≥ 3.12; packages: `openpyxl`, `formulas`, `numpy_financial`, `pyyaml`.
- Arm A built with the ModelForge version recorded in `results/results.json`
  (`modelforge_version`), `SOURCE_DATE_EPOCH=1767225600`.
- Scorer is pure-Python, no network, no LLM calls.

## Deviations

**D-001 (2026-06-12) — scorer numpy-coercion fix, post-arms.** Adversarial
verification of the first scoring pass found that `score.py::_coerce_float` /
`_coerce_error` recursed infinitely on numpy scalars (`np.generic` exposes
`.flatten`, which yields the same scalar back); the swallowed `RecursionError`
silently dropped recalc values, producing false "headline not located" results
on `three_statement_mfg` arm-B runs 2-3 (`final_total_assets`, correct value
529.3622 present under independent recalc). Fixed by unwrapping `ndim == 0`
values via `.item()` before the flatten branch (`_unwrap_numpy_scalar`). The
fix changes value COERCION only — no metric definition, tolerance, label
pattern, or extraction rule was altered. All artifacts re-scored after the
fix; the independent verification pass confirmed m1 = 0 for all 12 artifacts
both before and after the fix.

**D-002 (2026-06-12) — freeze-order disclosure.** File mtimes show `score.py`
was last written AFTER the arm artifacts, and the three arm-A YAML specs
PRECEDE the brief files on disk. The harness was authored in one continuous
session by one builder; the mtime order contradicts a strict "scorer frozen
before any arm ran / specs derived from briefs" reading and is disclosed here
rather than claimed away. The first git commit of `benchmarks/` is the
tamper-evidence anchor going forward; v1 results should be read as
*built-and-scored by the same project in one session* (see §3.4, §3.6).

**D-003 (2026-06-12) — arm-B model identity.** §3.2 requires the arm-B model
ID; it was not captured in-band by the run scripts. Recorded here from the
orchestration layer: all 9 arm-B runs were executed by independent
fresh-context `claude-opus-4-8` agents (the same model class used for arm-A
spec authoring), each with file/Bash tool access and §5 permission to
self-validate. No per-run session transcripts are archived for v1; treat
run-independence as asserted, not proven.

**D-004 (2026-06-12) — 3-statement arm-B m2 framing.** Of the 7 arm-B m2
failures on `three_statement_mfg` in the first pass, 4 were caused by
Assumptions-sheet OPENING balances ("Cash 40", "Debt 180") shadowing the
correct Model-sheet final rows under the frozen first-match label search, and
3 by the D-001 bug. Hand recalculation confirms all three agent 3S models
computed correct final values. Per the frozen rules these still score as
extraction failures, but RESULTS.md must present 3S arm-B m2 as **headline
locatability under the frozen label-search**, not as "the agent got the
numbers wrong".

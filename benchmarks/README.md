# ModelForge Public Benchmark Harness v1

A pre-registered, fully reproducible benchmark comparing two ways of turning
the **same deal brief** into an Excel financial model:

- **Arm A — ModelForge spec-driven build:** frozen YAML spec → deterministic
  compiler → `.xlsx`.
- **Arm B — frontier-agent free build:** a frontier coding agent writes its
  own `openpyxl` code from the brief (3 independent runs per brief).

Everything here is **synthetic**: three fictional US/UK-flavored deals
(fictional companies, frozen numeric inputs). No real company, client, or
counterparty is described.

> Read `PROTOCOL.md` first — it is the pre-registered contract (arms, metric
> definitions, tolerances, honesty caveats). In particular: **arm B is a raw
> frontier-agent + openpyxl baseline, NOT a measurement of any commercial
> Excel-generation product.**

## Layout

```
benchmarks/
├── PROTOCOL.md            # pre-registered protocol (read first)
├── README.md              # this file
├── briefs/                # the three deal briefs (single source of truth)
│   ├── lbo_us_saas.md
│   ├── dcf_industrial.md
│   └── three_statement_mfg.md
├── specs/                 # the SAME briefs as ModelForge YAML specs (arm A)
│   ├── lbo_us_saas.yaml
│   ├── dcf_industrial.yaml
│   └── three_statement_mfg.yaml
├── harness/
│   ├── ground_truth.py    # clean-room headline math (numpy_financial only)
│   └── score.py           # deterministic scorer (m1–m6)
└── results/               # scorer output (results.json + RESULTS.md)
```

## Prerequisites

```bash
pip install "modelforge-finance[export]" formulas numpy_financial openpyxl pyyaml
# or, from a repo checkout:  pip install -e . && pip install formulas numpy_financial
```

Python ≥ 3.12. All commands below run from the **repo root**.

## 1. Ground truth (no ModelForge involved)

```bash
python benchmarks/harness/ground_truth.py
```

Prints the headline outputs of all three briefs as JSON, computed from plain
math + `numpy_financial`. This file imports no ModelForge code and reads no
workbook — it is the briefs restated as arithmetic.

## 2. Build arm A

```bash
mkdir -p benchmarks/results/run1
export SOURCE_DATE_EPOCH=1767225600           # PowerShell: $env:SOURCE_DATE_EPOCH="1767225600"

python -m modelforge.cli build benchmarks/specs/lbo_us_saas.yaml          --out benchmarks/results/run1/lbo_us_saas__armA__run1.xlsx
python -m modelforge.cli build benchmarks/specs/dcf_industrial.yaml       --out benchmarks/results/run1/dcf_industrial__armA__run1.xlsx
python -m modelforge.cli build benchmarks/specs/three_statement_mfg.yaml  --out benchmarks/results/run1/three_statement_mfg__armA__run1.xlsx
```

Sanity gate (all three must print `CERTIFIED`):

```bash
python -m modelforge.cli certify benchmarks/specs/lbo_us_saas.yaml
python -m modelforge.cli certify benchmarks/specs/dcf_industrial.yaml
python -m modelforge.cli certify benchmarks/specs/three_statement_mfg.yaml
```

## 3. Run arm B

For each brief × run k ∈ {1,2,3}:

1. Start a **fresh** agent session (no memory of prior runs).
2. Give the agent: the brief markdown verbatim + the instruction block from
   `PROTOCOL.md` §5 (quality bar: zero formula errors, live formulas, labeled
   headline cells, sources sheet, completeness checklist).
3. The agent must produce a single `.xlsx` with Python + openpyxl — no
   ModelForge code, no templates, no human edits to the artifact.
4. Save it as `benchmarks/results/run1/<brief>__armB__run<k>.xlsx`.
5. Record the exact model ID for `--model-id-b`.

## 4. Score

```bash
python benchmarks/harness/score.py \
    --artifacts benchmarks/results/run1 \
    --out benchmarks/results \
    --repro-arm-a \
    --model-id-b "<exact arm-B model id>"
```

Outputs:

- `benchmarks/results/results.json` — every metric, per artifact, plus the
  ground-truth headline values and the m4 reproducibility block.
- `benchmarks/results/RESULTS.md` — rendered table.

`--repro-arm-a` additionally builds each spec twice (pinned
`SOURCE_DATE_EPOCH`, same output filename in two temp dirs) and reports
SHA-256 byte-identity.

## Metrics at a glance (full definitions in PROTOCOL.md §4)

| Metric | What it measures | Better |
|---|---|---|
| m1 `formula_error_cells` | #REF!/#DIV/0!/… under third-party recalc (`formulas` pkg) + cached scan | lower (0 bar) |
| m2 `headline_accuracy` | extracted headlines vs clean-room ground truth, 0.5% rel tol | higher |
| m3 `hardcode_rate` | numeric constants vs live formulas outside input sheets | lower |
| m4 `reproducibility` | A: byte-identical rebuild; B: cross-run headline range + structural identity | A true / B lower |
| m5 `lineage` | any sources/assumptions attribution surface | true |
| m6 `completeness` | per-brief component checklist | higher |

## Verifying this harness itself

The arm-A path was validated end-to-end when this harness was frozen: all
three specs build `CERTIFIED` (zero formula errors, zero style gaps), every
arm-A headline matches `ground_truth.py` exactly (well inside the 0.5%
tolerance), and the double-build byte-identity check passes for all three
briefs. Re-run steps 1–2 + 4 on an arm-A-only directory to reproduce that
baseline before adding arm-B artifacts.

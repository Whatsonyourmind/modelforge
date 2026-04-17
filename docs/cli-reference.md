# CLI Reference

All commands are exposed under `modelforge`. Run `modelforge --help` for the top-level list.

## `modelforge build`

Emit an Excel workbook from a YAML spec.

```bash
modelforge build <spec.yaml> [--out <path>]
```

Writes `output/<stem>.xlsx` and `output/<stem>.graph.db` by default. Runs sensitivity tornado, Monte Carlo, and reproducibility post-processors automatically.

## `modelforge list-templates`

Print the table of all 11 supported `model_type` values.

## `modelforge qc`

Run the 8-check external QC gate on a built workbook.

```bash
modelforge qc <xlsx>
```

Exits 0 on full pass, 1 on any fail. Prints a rich table with per-check detail.

## `modelforge verify`

Read the Reproducibility sheet metadata and (optionally) verify the spec hash.

```bash
modelforge verify <xlsx> [--spec <yaml>]
```

Without `--spec`, prints stored metadata. With `--spec`, recomputes the SHA-256 from the given YAML bytes and compares. Exit 0 on match, 1 on mismatch.

## `modelforge sources`

List sources used in a workbook, parsed from the Sources sheet.

```bash
modelforge sources <xlsx>
```

## `modelforge lineage`

Walk the linkage graph back from a cell.

```bash
modelforge lineage <graph.db> <cell_id>
# e.g. modelforge lineage out.graph.db "CELL:OperatingModel!D10"
```

## `modelforge stats`

Print node / edge counts per kind from the linkage graph.

```bash
modelforge stats <graph.db>
```

## `modelforge ingest`

Ingest a data room (PDFs / XLSX / CSV) and produce a YAML spec via Claude.

```bash
modelforge ingest <dataroom-dir> -t <template> -o <out.yaml>
    [--model claude-opus-4-7]
    [--backend cli|api]
    [--max-docs 50]
    [--strict]
    [--dry-run]
    [--no-cache]
    [-v]
```

Backends:

- `cli` (default) uses Claude Code's local invocation — no API key required.
- `api` uses the Anthropic SDK with prompt caching — requires `ANTHROPIC_API_KEY`.

All 11 templates are supported; scanned PDFs are OCR'd automatically if the `[ingest-ocr]` extra and system tesseract are installed (see [Quickstart](quickstart.md)).

## `modelforge chat`

REPL for lineage Q&A over a workbook.

```bash
modelforge chat <xlsx>
    [--backend api|dry]
    [--model claude-opus-4-7]
    [--export <conv.md>]
```

Claude cites `A-###` (with confidence) and `S-###` (with page) for every number referenced. Type `history` to print the conversation, `exit` / `quit` to leave.

## `modelforge dossier`

Generate the regulator-grade audit PDF.

```bash
modelforge dossier <xlsx> [-o <out.pdf>]
```

Produces a multi-section PDF: cover + reproducibility, executive summary, assumptions register, source registry, formula inventory, lineage graph summary, QC sign-off with signature lines, bilingual glossary.

## `modelforge` top-level

```bash
modelforge --help
```

Lists everything. Subcommand help: `modelforge <cmd> --help`.

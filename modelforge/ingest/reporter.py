"""Emit INGESTION_REPORT.md alongside the ingested YAML."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


def write_report(
    path: Path,
    *,
    template: str,
    dataroom_dir: Path,
    model: str,
    classifier_results: list,
    extraction_results: list,
    sources: list[dict],
    spec_valid: bool,
    validation_errors: list[str],
    elapsed_seconds: float,
) -> None:
    lines: list[str] = []
    lines.append(f"# Ingestion Report — {dataroom_dir.name}")
    lines.append("")
    lines.append(f"- **Template**: `{template}`")
    lines.append(f"- **Model**: `{model}`")
    lines.append(f"- **Elapsed**: {elapsed_seconds:.1f}s")
    lines.append(f"- **Timestamp**: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- **Spec validation**: {'PASS' if spec_valid else 'FAIL — see bottom'}")

    # Cache stats
    all_calls = list(classifier_results) + list(extraction_results)
    total_calls = len(all_calls)
    cache_hits = sum(1 for r in all_calls if r.cache_hit)
    cache_rate = cache_hits / max(total_calls, 1) * 100
    lines.append(f"- **Cache hit rate**: {cache_rate:.1f}% ({cache_hits}/{total_calls} calls)")

    total_in = sum(getattr(r, "input_tokens", 0) for r in extraction_results)
    total_out = sum(getattr(r, "output_tokens", 0) for r in extraction_results)
    lines.append(f"- **Extractor tokens**: {total_in:,} in / {total_out:,} out")
    lines.append("")

    # Documents
    lines.append("## Documents")
    lines.append("")
    lines.append("| S-id | Doc | Type | Publisher | Date | Verified | Relevance |")
    lines.append("|---|---|---|---|---|---|---|")
    for s, cr in zip(sources, classifier_results):
        lines.append(
            f"| {s['id']} | `{cr.doc_filename}` | {cr.doc_type} | "
            f"{cr.publisher} | {cr.date or '-'} | "
            f"{'✓' if cr.verified else '-'} | {cr.relevance_hint} |"
        )
    lines.append("")

    # Extraction status
    lines.append("## Extraction status")
    lines.append("")
    lines.append("| Section | Validation | Tokens (in/out) | Cache |")
    lines.append("|---|---|---|---|")
    for r in extraction_results:
        status = "✓ valid" if r.validation_ok else "✗ needs review"
        lines.append(
            f"| `{r.section_name}` | {status} | "
            f"{r.input_tokens:,} / {r.output_tokens:,} | "
            f"{'hit' if r.cache_hit else 'miss'} |"
        )
    lines.append("")

    # Per-section validation errors / review queue
    needs_review = [r for r in extraction_results if not r.validation_ok]
    if needs_review:
        lines.append("## Review queue")
        lines.append("")
        for r in needs_review:
            lines.append(f"### `{r.section_name}`")
            lines.append("")
            if r.validation_error:
                lines.append("```")
                lines.append(r.validation_error[:2000])
                lines.append("```")
            lines.append("")

    # Whole-spec validation errors
    if not spec_valid and validation_errors:
        lines.append("## Whole-spec validation errors")
        lines.append("")
        for e in validation_errors:
            lines.append("```")
            lines.append(e[:3000])
            lines.append("```")
            lines.append("")

    # Next steps
    lines.append("## Next steps")
    lines.append("")
    if spec_valid:
        lines.append("1. Review the generated YAML for reasonableness.")
        lines.append("2. Run `modelforge build <yaml>` to produce the workbook.")
        lines.append("3. Run `modelforge qc <xlsx>` to verify the 8-check QC gate.")
    else:
        lines.append("1. Fix the validation errors above in the YAML.")
        lines.append("2. Re-run `modelforge build <yaml>` after patching.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

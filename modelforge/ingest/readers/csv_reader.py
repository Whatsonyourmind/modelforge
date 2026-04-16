"""CSV reader — single-chunk, full file as markdown table.

Uses stdlib csv module (no pandas dependency). Capped at 300 rows for
context budget. If the file has >300 rows we keep first 150 + last 50 +
an ellipsis row — preserves both header data and any summary rows.
"""

from __future__ import annotations

import csv
from pathlib import Path

from modelforge.ingest.readers.base import DocChunk, DocIndex


def read_csv(path: Path, max_rows: int = 300) -> DocIndex:
    path = Path(path)
    with path.open(encoding="utf-8", newline="", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return DocIndex(
            doc_filename=path.name, path=path, mime="text/csv",
            total_pages=1, chunks=[],
        )

    if len(rows) > max_rows:
        head = rows[:150]
        tail = rows[-50:]
        sep = [["..."] * max(len(rows[0]), 1)]
        rows = head + sep + tail

    md = _rows_to_markdown(rows)
    chunk = DocChunk(
        doc_filename=path.name,
        page=None,
        text=md,
        kind="table",
        meta={"nrows": len(rows)},
    )
    return DocIndex(
        doc_filename=path.name, path=path, mime="text/csv",
        total_pages=1, chunks=[chunk],
    )


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    header = rows[0] + [""] * (ncols - len(rows[0]))
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * ncols) + "|"]
    for r in rows[1:]:
        padded = r + [""] * (ncols - len(r))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)

"""Dataroom directory walker + dispatch to typed readers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from modelforge.ingest.readers.base import DocIndex
from modelforge.ingest.readers.csv_reader import read_csv
from modelforge.ingest.readers.pdf_reader import read_pdf
from modelforge.ingest.readers.xlsx_reader import read_xlsx


SUPPORTED_SUFFIXES = {
    ".pdf": read_pdf,
    ".xlsx": read_xlsx,
    ".xlsm": read_xlsx,
    ".csv": read_csv,
}


def discover(dataroom_dir: Path, max_docs: int = 50) -> list[Path]:
    """Walk dataroom_dir and return a list of supported-file paths.

    Sorted alphabetically for deterministic S-id assignment. Caps at
    max_docs to bound API cost.
    """
    dataroom_dir = Path(dataroom_dir)
    if not dataroom_dir.is_dir():
        raise NotADirectoryError(f"{dataroom_dir} is not a directory")
    files = [p for p in sorted(dataroom_dir.rglob("*"))
             if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    if len(files) > max_docs:
        files = files[:max_docs]
    return files


def read_any(path: Path) -> DocIndex:
    """Dispatch to the right reader by suffix."""
    path = Path(path)
    suffix = path.suffix.lower()
    reader = SUPPORTED_SUFFIXES.get(suffix)
    if reader is None:
        raise ValueError(f"Unsupported suffix {suffix!r} for {path.name}")
    return reader(path)


def read_all(dataroom_dir: Path, max_docs: int = 50) -> list[DocIndex]:
    return [read_any(p) for p in discover(dataroom_dir, max_docs=max_docs)]

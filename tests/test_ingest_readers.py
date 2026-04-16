"""Tests for ingestion readers (PDF, XLSX, CSV, discovery)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modelforge.ingest.readers.discovery import discover, read_any, read_all
from modelforge.ingest.readers.pdf_reader import read_pdf
from modelforge.ingest.readers.xlsx_reader import read_xlsx
from modelforge.ingest.readers.csv_reader import read_csv


FIXTURES = Path(__file__).parent / "fixtures" / "dataroom_enfinity_synth"


def test_discover_finds_supported_files():
    files = discover(FIXTURES)
    assert len(files) >= 7  # 7 PDFs + 1 XLSX + 1 CSV
    extensions = {f.suffix.lower() for f in files}
    assert ".pdf" in extensions
    assert ".xlsx" in extensions
    assert ".csv" in extensions


def test_discover_respects_max_docs():
    files = discover(FIXTURES, max_docs=3)
    assert len(files) == 3


def test_discover_rejects_non_directory():
    with pytest.raises(NotADirectoryError):
        discover(FIXTURES / "01_enfinity_press_release.pdf")


def test_read_pdf_extracts_text():
    idx = read_pdf(FIXTURES / "01_enfinity_press_release.pdf")
    assert idx.total_pages >= 1
    assert len(idx.chunks) >= 1
    text = " ".join(c.text for c in idx.chunks)
    assert "316" in text
    assert "Enfinity" in text
    assert "276" in text


def test_read_xlsx_extracts_sheet_as_markdown():
    idx = read_xlsx(FIXTURES / "08_sponsor_projections.xlsx")
    assert len(idx.chunks) >= 1
    text = idx.chunks[0].text
    assert "Sheet: Projections" in text
    assert "32.1" in text  # Y1 revenue
    assert "DSCR" in text


def test_read_csv_extracts_as_markdown_table():
    idx = read_csv(FIXTURES / "09_plant_irradiation_2025.csv")
    assert len(idx.chunks) == 1
    text = idx.chunks[0].text
    assert "|" in text
    assert "Puglia_01" in text


def test_read_any_dispatches_by_suffix():
    idx_pdf = read_any(FIXTURES / "01_enfinity_press_release.pdf")
    idx_xlsx = read_any(FIXTURES / "08_sponsor_projections.xlsx")
    idx_csv = read_any(FIXTURES / "09_plant_irradiation_2025.csv")
    assert idx_pdf.mime == "application/pdf"
    assert idx_xlsx.mime.startswith("application/vnd.")
    assert idx_csv.mime == "text/csv"


def test_read_all_returns_all_indexes():
    indexes = read_all(FIXTURES)
    assert len(indexes) >= 7


def test_read_any_rejects_unknown_extension(tmp_path):
    f = tmp_path / "sample.docx"
    f.write_text("test")
    with pytest.raises(ValueError, match="Unsupported suffix"):
        read_any(f)

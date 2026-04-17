"""Tests for OCR fallback in pdf_reader (v0.4 US-007)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modelforge.ingest.readers.pdf_reader import (
    _ocr_language,
    _ocr_pdf,
    read_pdf,
)


def test_ocr_language_default(monkeypatch):
    monkeypatch.delenv("MODELFORGE_OCR_LANG", raising=False)
    assert _ocr_language() == "ita+eng"


def test_ocr_language_override(monkeypatch):
    monkeypatch.setenv("MODELFORGE_OCR_LANG", "fra+deu")
    assert _ocr_language() == "fra+deu"


def test_ocr_pdf_returns_empty_without_deps(tmp_path):
    """No pytesseract / pdf2image → empty list (graceful degradation)."""
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"%PDF-1.4\nfake")
    # Force ImportError on the conditional imports by patching builtins
    with patch.dict("sys.modules", {"pytesseract": None, "pdf2image": None}):
        result = _ocr_pdf(fake)
    assert result == []


def test_ocr_pdf_happy_path_with_mocks(tmp_path):
    """When deps present, OCR'd chunks carry meta['source']='ocr'."""
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"%PDF-1.4\nfake")

    fake_image = MagicMock()
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = "Extracted via OCR text content."
    fake_pytesseract.TesseractNotFoundError = Exception
    fake_pdf2image = MagicMock()
    fake_pdf2image.convert_from_path.return_value = [fake_image, fake_image]

    with patch.dict("sys.modules", {
        "pytesseract": fake_pytesseract,
        "pdf2image": fake_pdf2image,
    }):
        result = _ocr_pdf(fake)

    assert len(result) == 2
    assert all(c.meta.get("source") == "ocr" for c in result)
    assert all("OCR" in c.text for c in result)
    assert result[0].page == 1
    assert result[1].page == 2


def test_read_pdf_doesnt_call_ocr_when_text_present(tmp_path, monkeypatch):
    """PDF with a real text layer must NOT invoke OCR."""
    # Make a tiny synthetic PDF with text via pypdf
    try:
        from pypdf import PdfWriter
        from pypdf.generic import RectangleObject, NameObject
    except ImportError:
        pytest.skip("pypdf not installed")

    # Easier: create a PDF via reportlab since it's in our deps
    from reportlab.pdfgen import canvas
    p = tmp_path / "withtext.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 750, "Hello, this PDF has plenty of embedded text layer content.")
    c.drawString(100, 700, "Second line of text to ensure total > 20 chars.")
    c.save()

    called = [0]

    def fake_ocr(path):
        called[0] += 1
        return []

    monkeypatch.setattr("modelforge.ingest.readers.pdf_reader._ocr_pdf", fake_ocr)
    idx = read_pdf(p)
    assert idx.total_pages >= 1
    assert called[0] == 0, "OCR should not be called when text layer is populated"


def test_read_pdf_calls_ocr_fallback_when_empty(tmp_path, monkeypatch):
    """Empty PDF triggers OCR; OCR result replaces chunks."""
    from reportlab.pdfgen import canvas
    p = tmp_path / "empty.pdf"
    c = canvas.Canvas(str(p))
    # No drawString — text layer empty
    c.save()

    from modelforge.ingest.readers.base import DocChunk

    def fake_ocr(path):
        return [DocChunk(doc_filename=path.name, page=1,
                         text="OCR'd content here.",
                         kind="text",
                         meta={"source": "ocr", "ocr_lang": "ita+eng"})]

    monkeypatch.setattr("modelforge.ingest.readers.pdf_reader._ocr_pdf", fake_ocr)
    idx = read_pdf(p)
    assert len(idx.chunks) == 1
    assert idx.chunks[0].meta.get("source") == "ocr"

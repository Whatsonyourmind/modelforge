"""Optional OCR backend for scanned-PDF ingestion.

PyTesseract + pdf2image are optional dependencies (install via
``pip install modelforge-finance[ingest-ocr]``). If they're not present,
this module degrades gracefully: ``ocr_available()`` returns False and
calls to ``ocr_pdf_pages`` raise ImportError with a helpful message.

The ingest pipeline calls ``maybe_ocr_pdf`` which:
  1. Tries pdfplumber text extraction first
  2. If extracted text per page < threshold (likely scanned), falls back to OCR
  3. Returns text per page in either case

Use case: Italian datarooms often contain scanned PDFs (notary docs,
older property certifications, regulatory letters). Plain pdfplumber
gets ~0% on these; OCR gets ~90%.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("modelforge.ingest.ocr")

MIN_TEXT_PER_PAGE = 50  # If pdfplumber returns < 50 chars/page, treat as scanned


def ocr_available() -> bool:
    """Check if pytesseract + pdf2image are installed AND tesseract binary is on PATH."""
    try:
        import pytesseract  # noqa: F401
        import pdf2image  # noqa: F401
    except ImportError:
        return False
    # Check tesseract binary itself
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_pdf_pages(pdf_path: Path, *, dpi: int = 200, lang: str = "eng+ita") -> list[str]:
    """OCR a PDF, return list of per-page text.

    Args:
        pdf_path: Path to PDF.
        dpi: Image DPI for OCR; 200 is good balance of speed/accuracy.
        lang: Tesseract language pack(s). Default ``eng+ita`` (English + Italian).
              For other ModelForge regions: ``eng+fra``, ``eng+spa``, ``eng+deu``, ``eng+jpn``.

    Returns:
        List of strings, one per page.

    Raises:
        ImportError: if OCR dependencies are missing.
    """
    if not ocr_available():
        raise ImportError(
            "OCR backend requires `pip install modelforge-finance[ingest-ocr]` "
            "AND the tesseract binary on PATH (https://github.com/tesseract-ocr/tesseract). "
            "Install tesseract from your OS package manager: "
            "Windows: choco install tesseract · Mac: brew install tesseract · "
            "Ubuntu: apt install tesseract-ocr-eng tesseract-ocr-ita ..."
        )

    from pdf2image import convert_from_path
    import pytesseract

    pages = convert_from_path(str(pdf_path), dpi=dpi)
    return [pytesseract.image_to_string(page, lang=lang) for page in pages]


def maybe_ocr_pdf(pdf_path: Path, *, lang: str = "eng+ita") -> tuple[list[str], str]:
    """Smart wrapper: try pdfplumber first, fall back to OCR if scanned.

    Returns (pages_text, backend_used) where backend_used is "pdfplumber"
    or "tesseract" or "tesseract_fallback" (mixed: most pages text, some OCR'd).

    Args:
        pdf_path: PDF path.
        lang: Tesseract language pack for OCR fallback.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "Ingest requires `pip install modelforge-finance[ingest]` "
            "(adds pdfplumber + pypdf + anthropic)."
        )

    pages_text: list[str] = []
    needs_ocr_pages: list[int] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_text.append(text)
            if len(text.strip()) < MIN_TEXT_PER_PAGE:
                needs_ocr_pages.append(i)

    if not needs_ocr_pages:
        return pages_text, "pdfplumber"

    if not ocr_available():
        log.warning(
            "PDF has %d pages with < %d chars (likely scanned), but OCR backend "
            "not installed. Returning pdfplumber output only. Install tesseract "
            "for full coverage.",
            len(needs_ocr_pages),
            MIN_TEXT_PER_PAGE,
        )
        return pages_text, "pdfplumber"

    # Run OCR only on the pages that need it (much faster than whole-PDF OCR)
    from pdf2image import convert_from_path
    import pytesseract

    log.info("Running OCR on %d pages of %s", len(needs_ocr_pages), pdf_path.name)
    images = convert_from_path(str(pdf_path), dpi=200)
    for i in needs_ocr_pages:
        if i < len(images):
            try:
                pages_text[i] = pytesseract.image_to_string(images[i], lang=lang)
            except Exception as e:
                log.warning("OCR failed on page %d: %r", i, e)

    return pages_text, "tesseract_fallback" if len(needs_ocr_pages) < len(pages_text) else "tesseract"


def detect_likely_language(pages_text: list[str]) -> str:
    """Heuristic: guess Tesseract lang pack from sample text.

    Returns one of: ``eng+ita``, ``eng+fra``, ``eng+spa``, ``eng+deu``,
    ``eng+jpn``. Default ``eng+ita`` since the original ModelForge is
    Italian-first.
    """
    sample = " ".join(pages_text[:3]).lower()[:5000]
    # Very rough heuristics — production code would use a real langdetect lib
    if any(w in sample for w in [" della ", " degli ", " sono ", " art. ", " comma "]):
        return "eng+ita"
    if any(w in sample for w in [" société ", " l'entreprise ", " article ", " loi "]):
        return "eng+fra"
    if any(w in sample for w in [" sociedad ", " empresa ", " artículo ", " ley "]):
        return "eng+spa"
    if any(w in sample for w in [" gesellschaft ", " unternehmen ", " gesetz ", " absatz "]):
        return "eng+deu"
    if any(ch in sample for ch in "あいうえおかきくけこさしすせそ"):
        return "eng+jpn"
    return "eng+ita"

"""PDF reader — pdfplumber primary, pypdf fallback.

pdfplumber gives us better table extraction; pypdf is more tolerant of
malformed PDFs. If both fail or return <20 chars total (likely scanned),
we emit a warning chunk so the classifier can flag it.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from modelforge.ingest.readers.base import DocChunk, DocIndex


def read_pdf(path: Path) -> DocIndex:
    """Return a DocIndex from a PDF file.

    Tries pdfplumber first (best for tables + Unicode); falls back to
    pypdf on failure. Warns if extracted text is < 20 chars (scanned PDF
    likely needs OCR — out of scope for v0.3.1).
    """
    path = Path(path)
    chunks: list[DocChunk] = []
    total_pages = 0

    # Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(DocChunk(
                        doc_filename=path.name,
                        page=i,
                        text=text,
                        kind="text",
                    ))
                # Also extract tables as markdown when present
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                for tidx, tbl in enumerate(tables):
                    md = _table_to_markdown(tbl)
                    if md.strip():
                        chunks.append(DocChunk(
                            doc_filename=path.name,
                            page=i,
                            text=md,
                            kind="table",
                            meta={"table_index": tidx},
                        ))
    except Exception as e:
        warnings.warn(f"pdfplumber failed on {path.name}: {e}; trying pypdf")
        chunks = []
        total_pages = 0

    # Fallback: pypdf
    if not chunks:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            total_pages = len(reader.pages)
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(DocChunk(
                        doc_filename=path.name,
                        page=i,
                        text=text,
                        kind="text",
                    ))
        except Exception as e:
            warnings.warn(f"pypdf also failed on {path.name}: {e}")

    # Scanned-PDF detection: if text layer is essentially empty, try
    # OCR fallback (v0.4 US-007). Tagged chunks carry meta['source']='ocr'.
    total_len = sum(len(c.text) for c in chunks)
    if total_len < 20:
        ocr_chunks = _ocr_pdf(path)
        if ocr_chunks:
            chunks = ocr_chunks
            total_pages = max(total_pages, len(chunks))
        else:
            warnings.warn(
                f"{path.name}: extracted only {total_len} chars and OCR "
                "unavailable or yielded nothing. Add to review queue. "
                "Install the `[ingest-ocr]` extra to enable OCR "
                "(`pip install 'modelforge[ingest-ocr]'` + system tesseract)."
            )

    return DocIndex(
        doc_filename=path.name,
        path=path,
        mime="application/pdf",
        total_pages=total_pages,
        chunks=chunks,
    )


def _ocr_pdf(path: Path) -> list[DocChunk]:
    """OCR fallback for scanned PDFs.

    Uses pdf2image (Poppler) + pytesseract if both are installed and a
    system tesseract binary is on PATH. Returns an empty list if any
    dependency is missing or OCR produces no text. Every emitted chunk
    carries ``meta['source'] = 'ocr'`` so downstream code (classifier,
    dossier) can lower confidence / flag for human review.

    Language pack defaults to Italian + English; override with env
    var ``MODELFORGE_OCR_LANG`` (e.g. ``ita+eng+fra``).
    """
    try:
        import pytesseract  # type: ignore
        from pdf2image import convert_from_path  # type: ignore
    except ImportError:
        return []

    try:
        images = convert_from_path(str(path), dpi=250)
    except Exception as e:
        warnings.warn(
            f"{path.name}: OCR conversion failed: {e}. "
            "Ensure Poppler is installed and on PATH."
        )
        return []

    chunks: list[DocChunk] = []
    lang = _ocr_language()
    for i, img in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(img, lang=lang)
        except pytesseract.TesseractNotFoundError:
            warnings.warn(
                f"{path.name}: tesseract binary not found on PATH. "
                "Install system tesseract (brew/apt/choco install tesseract)."
            )
            return []
        except Exception as e:
            warnings.warn(f"{path.name} p.{i}: OCR error: {e}")
            continue
        if text.strip():
            chunks.append(DocChunk(
                doc_filename=path.name,
                page=i,
                text=text,
                kind="text",
                meta={"source": "ocr", "ocr_lang": lang},
            ))
    return chunks


def _ocr_language() -> str:
    import os
    return os.environ.get("MODELFORGE_OCR_LANG", "ita+eng")


def _table_to_markdown(rows: list[list]) -> str:
    """Convert a pdfplumber table (list of row lists) to GitHub-flavored
    markdown. Treats first row as header."""
    if not rows:
        return ""
    cleaned = [[(str(c).strip() if c is not None else "") for c in r] for r in rows]
    ncols = max(len(r) for r in cleaned)
    header = cleaned[0] + [""] * (ncols - len(cleaned[0]))
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * ncols) + "|"]
    for row in cleaned[1:]:
        padded = row + [""] * (ncols - len(row))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)

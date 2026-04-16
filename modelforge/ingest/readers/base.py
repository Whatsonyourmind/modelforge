"""Core dataclasses for the ingestion readers.

DocChunk
    A page- or sheet-level unit of text extracted from a document.
    Source-traceable by (doc_filename, page).

DocIndex
    A document's full extraction: one per file. Contains all chunks +
    document-level metadata (publisher hint, date hint, verified flag).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal, Optional

DocKind = Literal["text", "table", "header"]


@dataclass
class DocChunk:
    """A page- or sheet-level extracted text unit."""

    doc_filename: str
    page: Optional[int]  # 1-based. None for single-page formats like CSV.
    text: str
    kind: DocKind = "text"
    meta: dict = field(default_factory=dict)

    def short(self, n: int = 120) -> str:
        """Truncated preview for logs."""
        t = self.text.replace("\n", " ").strip()
        return t[:n] + ("..." if len(t) > n else "")


@dataclass
class DocIndex:
    """A document's complete extraction + metadata."""

    doc_filename: str
    path: Path
    mime: str  # "application/pdf", "application/vnd.ms-excel", "text/csv"
    total_pages: int
    chunks: list[DocChunk] = field(default_factory=list)
    publisher_hint: Optional[str] = None
    date_hint: Optional[date] = None
    verified: bool = False
    # Filled in later by classifier
    doc_type: Optional[str] = None
    relevance_hint: Optional[str] = None
    classifier_confidence: Optional[str] = None  # "H" / "M" / "L"
    # Assigned after classification
    source_id: Optional[str] = None  # "S-001" etc.

    @property
    def total_text_len(self) -> int:
        return sum(len(c.text) for c in self.chunks)

    def head_text(self, n_chars: int = 3000) -> str:
        """First n chars of concatenated text — used for classifier prompt."""
        buf = []
        remaining = n_chars
        for c in self.chunks:
            if remaining <= 0:
                break
            take = c.text[:remaining]
            buf.append(f"[page {c.page}]\n{take}" if c.page else take)
            remaining -= len(take)
        return "\n\n".join(buf)

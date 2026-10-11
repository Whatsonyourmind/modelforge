"""The dataroom as the gate sees it: per-document, per-page normalised text.

Reuses the ingest readers (PDF / XLSX / CSV), so the gate reads documents
exactly the way the extractor did. Documents are matched to a spec Source by
filename (case-insensitive), then by stem.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from modelforge.evidence.numbers import normalize_text

_TEXT_SUFFIXES = {".txt", ".md", ".html", ".htm"}


@dataclass
class Page:
    number: int | None
    text: str  # normalised


@dataclass
class Document:
    filename: str
    path: Path
    sha256: str
    pages: list[Page] = field(default_factory=list)

    def find(self, quote_norm: str) -> list[int | None]:
        """Pages on which the normalised quote occurs verbatim."""
        return [p.number for p in self.pages if quote_norm and quote_norm in p.text]


class Corpus:
    def __init__(self, docs: list[Document]):
        self.docs = docs
        self._by_name = {d.filename.lower(): d for d in docs}
        self._by_stem = {Path(d.filename).stem.lower(): d for d in docs}

    @classmethod
    def load(cls, dataroom: Path) -> Corpus:
        from modelforge.ingest.readers import discover, read_any
        docs = []
        for path in discover(dataroom, max_docs=500):
            idx = read_any(path)
            pages = [Page(c.page, normalize_text(c.text)) for c in idx.chunks if c.text]
            docs.append(Document(
                filename=path.name, path=path,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), pages=pages,
            ))
        # Plain-text sources the ingest readers do not cover (saved web pages,
        # notes): one page each, tags stripped.
        for path in sorted(Path(dataroom).rglob("*")):
            if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES:
                raw = path.read_text(encoding="utf-8", errors="replace")
                if path.suffix.lower() in (".html", ".htm"):
                    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
                    raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
                docs.append(Document(
                    filename=path.name, path=path,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    pages=[Page(1, normalize_text(raw))],
                ))
        return cls(docs)

    def resolve(self, doc_ref: str) -> Document | None:
        name = Path(doc_ref).name.lower()
        return self._by_name.get(name) or self._by_stem.get(Path(name).stem)

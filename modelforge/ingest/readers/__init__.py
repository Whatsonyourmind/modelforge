"""Document readers — PDF, XLSX, CSV.

Every reader normalizes to a DocIndex containing DocChunks with
source-traceable page numbers.
"""

from modelforge.ingest.readers.base import DocChunk, DocIndex, DocKind
from modelforge.ingest.readers.discovery import discover, read_any

__all__ = ["DocChunk", "DocIndex", "DocKind", "discover", "read_any"]

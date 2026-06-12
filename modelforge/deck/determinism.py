"""Deterministic .pptx finishing — the deck-side analogue of
``modelforge.analytics.reproducibility.finalize_determinism`` (which is
xlsx-bound; this module generalizes the same technique to PPTX archives).

Two sources of wall-clock noise survive a ``python-pptx`` save:

1. every zip member is stamped with ``datetime.now()`` as its mtime;
2. ``docProps/core.xml`` carries whatever creator/created/modified values
   the upstream template shipped (or the wall clock).

``stamp_pptx`` repacks the archive (preserving member order, bytes and
flags), pins every member's ``date_time`` to an instant **derived from the
source workbook's SHA-256** (NOT the wall clock — sentinel epoch
2020-01-01Z + ``int(sha[:8], 16)`` mapped into seconds within calendar
year 2020, so the stamp is always a sane *past* instant, never a future
date), and rewrites ``docProps/core.xml`` canonically with:

* ``dc:creator`` / ``cp:lastModifiedBy`` = ``modelforge``
* ``dcterms:created`` / ``dcterms:modified`` = the derived instant
* ``cp:keywords`` = ``spec_sha256=…; workbook_sha256=…`` (provenance — the
  deck embeds the exact hashes of the spec and workbook it was rendered
  from, verifiable in PowerPoint's file properties)

Same workbook bytes in → byte-identical .pptx out.
"""

from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

__all__ = ["derive_build_datetime", "read_pptx_stamp", "stamp_pptx"]

# Same sentinel as analytics.reproducibility — 2020-01-01T00:00:00Z.
_SENTINEL_EPOCH = 1577836800

_CORE_XML_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<cp:coreProperties "
    'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<dc:title>{title}</dc:title>"
    "<dc:creator>modelforge</dc:creator>"
    "<cp:lastModifiedBy>modelforge</cp:lastModifiedBy>"
    "<cp:keywords>{keywords}</cp:keywords>"
    "<dc:description>{description}</dc:description>"
    '<dcterms:created xsi:type="dcterms:W3CDTF">{iso}</dcterms:created>'
    '<dcterms:modified xsi:type="dcterms:W3CDTF">{iso}</dcterms:modified>'
    "</cp:coreProperties>"
)


def derive_build_datetime(workbook_sha256: str) -> datetime:
    """Deterministic UTC instant derived from the workbook hash.

    Same technique as ``analytics.reproducibility._resolve_build_datetime``'s
    hash-derivation branch, but the offset is clamped into calendar year
    2020 (sentinel epoch + first 8 hex digits mod 366 days of seconds) so
    the derived instant always lands in a fixed *past* window — file
    properties never show a future created/modified date. Same workbook
    hash → same instant, always (purely hash-derived, no wall clock).
    """
    try:
        offset = int(str(workbook_sha256)[:8], 16) % (366 * 24 * 3600)
    except (ValueError, TypeError):
        offset = 0
    return datetime.fromtimestamp(_SENTINEL_EPOCH + offset, tz=timezone.utc)


def _extract_existing_title(core_xml: bytes) -> str:
    m = re.search(rb"<dc:title[^>]*>([^<]*)</dc:title>", core_xml)
    if m:
        return m.group(1).decode("utf-8", errors="replace")
    return ""


def _pin_office_dates(core_xml: bytes, iso_z: bytes) -> bytes:
    """Rewrite dcterms:created/modified text in an OPC core.xml blob."""
    for tag in (b"created", b"modified"):
        core_xml = re.sub(
            rb"(<dcterms:" + tag + rb"[^>]*>)[^<]*(</dcterms:" + tag + rb">)",
            lambda m: m.group(1) + iso_z + m.group(2),
            core_xml,
            count=1,
        )
    return core_xml


def _normalize_embedded_xlsx(blob: bytes, dt_tuple, iso_z: bytes) -> bytes:
    """Deterministically repack a chart-data workbook embedded in the .pptx.

    python-pptx native charts embed an .xlsx (``ppt/embeddings/…``) whose
    inner zip mtimes and ``docProps/core.xml`` created/modified dates are
    wall-clock stamped at render time — the last source of byte noise after
    the outer archive is pinned. Same technique as the outer repack, applied
    one level down.
    """
    import io

    try:
        with zipfile.ZipFile(io.BytesIO(blob), "r") as zin:
            members = [(info, zin.read(info.filename)) for info in zin.infolist()]
    except zipfile.BadZipFile:
        return blob  # not a zip — leave untouched

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in members:
            if info.filename == "docProps/core.xml":
                data = _pin_office_dates(data, iso_z)
            new_info = zipfile.ZipInfo(filename=info.filename, date_time=dt_tuple)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            new_info.internal_attr = info.internal_attr
            new_info.create_system = info.create_system
            zout.writestr(new_info, data)
    return out.getvalue()


def stamp_pptx(
    pptx_path: Path | str,
    workbook_sha256: str,
    spec_sha256: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Path:
    """Pin a rendered .pptx to its source workbook — deterministically.

    Call as the **last** mutation of the deck file. Re-running on the same
    input bytes is idempotent (the derived instant and core.xml are pure
    functions of the hashes/title).
    """
    pptx_path = Path(pptx_path)
    dt = derive_build_datetime(workbook_sha256)
    dt_tuple = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    iso_z = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    keywords = f"spec_sha256={spec_sha256}; workbook_sha256={workbook_sha256}"

    with zipfile.ZipFile(pptx_path, "r") as zin:
        infos = zin.infolist()
        members = [(info, zin.read(info.filename)) for info in infos]

    # Title: explicit arg wins; else preserve whatever the renderer set.
    if title is None:
        for info, data in members:
            if info.filename == "docProps/core.xml":
                title = _extract_existing_title(data)
                break
    title = title or "ModelForge Certified Deck"
    desc = description or (
        "Rendered by modelforge deck from a certified workbook. "
        "Hashes in keywords are verifiable against the build manifest."
    )

    core_xml = _CORE_XML_TEMPLATE.format(
        title=escape(title),
        keywords=escape(keywords),
        description=escape(desc),
        iso=iso_z,
    ).encode("utf-8")

    iso_bytes = iso_z.encode("ascii")
    tmp_path = pptx_path.with_suffix(pptx_path.suffix + ".stamp.tmp")
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in members:
            if info.filename == "docProps/core.xml":
                data = core_xml
            elif (info.filename.startswith("ppt/embeddings/")
                    and info.filename.lower().endswith(".xlsx")):
                data = _normalize_embedded_xlsx(data, dt_tuple, iso_bytes)
            new_info = zipfile.ZipInfo(filename=info.filename, date_time=dt_tuple)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            new_info.internal_attr = info.internal_attr
            new_info.create_system = info.create_system
            zout.writestr(new_info, data)
    os.replace(tmp_path, pptx_path)
    return pptx_path


def read_pptx_stamp(pptx_path: Path | str) -> dict[str, str]:
    """Read back the provenance stamp from a deck's core properties.

    Returns {creator, title, keywords, created, modified, spec_sha256,
    workbook_sha256} (hash keys empty when the deck was not stamped).
    """
    pptx_path = Path(pptx_path)
    with zipfile.ZipFile(pptx_path, "r") as z:
        core = z.read("docProps/core.xml")

    def _grab(pattern: bytes) -> str:
        m = re.search(pattern, core)
        return m.group(1).decode("utf-8", errors="replace") if m else ""

    keywords = _grab(rb"<cp:keywords[^>]*>([^<]*)</cp:keywords>")
    out = {
        "creator": _grab(rb"<dc:creator[^>]*>([^<]*)</dc:creator>"),
        "title": _grab(rb"<dc:title[^>]*>([^<]*)</dc:title>"),
        "keywords": keywords,
        "created": _grab(rb"<dcterms:created[^>]*>([^<]*)</dcterms:created>"),
        "modified": _grab(rb"<dcterms:modified[^>]*>([^<]*)</dcterms:modified>"),
        "spec_sha256": "",
        "workbook_sha256": "",
    }
    for part in keywords.split(";"):
        part = part.strip()
        if part.startswith("spec_sha256="):
            out["spec_sha256"] = part.split("=", 1)[1]
        elif part.startswith("workbook_sha256="):
            out["workbook_sha256"] = part.split("=", 1)[1]
    return out

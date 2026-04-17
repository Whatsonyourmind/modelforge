"""Reproducibility metadata — spec hash, ModelForge version, Python
version, build timestamp.

Every workbook emitted by ``modelforge build`` carries a
``Reproducibility`` sheet plus matching named ranges
(``mf_spec_sha256``, ``mf_version``, ``mf_python_version``,
``mf_build_timestamp``). Auditors and the v0.4 dossier exporter rely on
these to confirm a workbook was built from a known spec and has not
been tampered with.

The spec hash is computed over the *exact bytes* of the YAML spec file
(or over a canonical JSON serialization of the spec if bytes are not
provided). Two workbooks built from identical spec bytes will carry the
same ``mf_spec_sha256`` — useful for "was this the version we
approved?" committee questions.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.worksheet import Worksheet

from modelforge.builder import styles


SHEET_NAME = "Reproducibility"

# Named-range identifiers. Keep the `mf_` prefix so they don't clash
# with business drivers on Assumptions.
NAME_SHA = "mf_spec_sha256"
NAME_VERSION = "mf_version"
NAME_PYTHON = "mf_python_version"
NAME_TIMESTAMP = "mf_build_timestamp"
NAME_SPEC_SOURCE = "mf_spec_source"


def _modelforge_version() -> str:
    try:
        return metadata.version("modelforge")
    except metadata.PackageNotFoundError:
        return "0.0.0+local"


def _canonical_spec_bytes(spec) -> bytes:
    """Fallback hash source when the YAML source bytes are unknown.

    Uses ``spec.model_dump(mode='json')`` with sorted keys and no
    whitespace so a given spec always produces identical bytes.
    """
    payload = spec.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def compute_spec_hash(
    spec,
    spec_source_bytes: Optional[bytes] = None,
) -> tuple[str, str]:
    """Return (sha256_hex, source_descriptor).

    Prefers the raw YAML bytes for deterministic cross-platform hashing.
    Falls back to a canonical JSON serialization of the Pydantic spec.
    """
    if spec_source_bytes is not None:
        return hashlib.sha256(spec_source_bytes).hexdigest(), "yaml_bytes"
    return hashlib.sha256(_canonical_spec_bytes(spec)).hexdigest(), "canonical_json"


def _register_name(wb, name: str, addr: str) -> None:
    if name in wb.defined_names:
        del wb.defined_names[name]
    wb.defined_names[name] = DefinedName(name=name, attr_text=addr)


def _emit_sheet(
    wb,
    sha: str,
    source_descriptor: str,
    spec_source_path: Optional[Path],
) -> Worksheet:
    if SHEET_NAME in wb.sheetnames:
        del wb[SHEET_NAME]
    ws = wb.create_sheet(SHEET_NAME)

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 70

    ws.cell(row=1, column=1, value="Reproducibility").font = styles.font_title
    ws.cell(row=2, column=1, value="Riproducibilità").font = styles.font_label_it
    from modelforge.builder import layout as _layout
    _layout.write_scenario_banner(ws, row=3)
    ws.cell(
        row=4, column=1,
        value=(
            "Every workbook emitted by `modelforge build` carries this "
            "metadata. The spec SHA-256 is deterministic: two workbooks "
            "built from identical spec bytes will match. Use "
            "`modelforge verify <xlsx> --spec <yaml>` to confirm a workbook "
            "was built from a given spec."
        ),
    ).font = styles.font_label_it

    rows = [
        ("Spec SHA-256", sha, NAME_SHA),
        ("ModelForge version", _modelforge_version(), NAME_VERSION),
        ("Python version", platform.python_version(), NAME_PYTHON),
        ("Build timestamp (UTC)",
         datetime.now(timezone.utc).isoformat(timespec="seconds"),
         NAME_TIMESTAMP),
        ("Spec source",
         str(spec_source_path) if spec_source_path else f"({source_descriptor})",
         NAME_SPEC_SOURCE),
        ("Host", f"{platform.system()} {platform.release()}", None),
        ("Python impl", f"{platform.python_implementation()} "
                        f"{sys.version_info.major}.{sys.version_info.minor}", None),
    ]

    r0 = 5
    for i, (label, value, name) in enumerate(rows):
        r = r0 + i
        lbl = ws.cell(row=r, column=1, value=label)
        lbl.font = styles.font_subheader
        v = ws.cell(row=r, column=2, value=value)
        styles.style_input(v, number_format="General")
        if name == NAME_SHA:
            v.font = styles.Font(
                name="Consolas", size=styles.FONT_SIZE_BODY,
            )
        if name is not None:
            addr = f"'{SHEET_NAME}'!$B${r}"
            _register_name(wb, name, addr)

    ws.freeze_panes = "B5"
    ws.print_title_rows = "1:3"
    return ws


def append_reproducibility_block(
    xlsx_path: Path | str,
    spec,
    spec_source_bytes: Optional[bytes] = None,
    spec_source_path: Optional[Path | str] = None,
) -> Path:
    """Append Reproducibility sheet + named ranges to a built workbook.

    Parameters
    ----------
    xlsx_path : Path
        Built workbook.
    spec : BaseModelSpec
        The Pydantic spec used.
    spec_source_bytes : Optional[bytes]
        Raw YAML bytes (preferred) for deterministic hashing.
    spec_source_path : Optional[Path]
        For display on the Reproducibility sheet.
    """
    xlsx_path = Path(xlsx_path)
    sha, descriptor = compute_spec_hash(spec, spec_source_bytes)

    wb = load_workbook(xlsx_path, data_only=False, keep_links=True)
    _emit_sheet(wb, sha, descriptor,
                Path(spec_source_path) if spec_source_path else None)
    wb.save(xlsx_path)
    return xlsx_path


def read_reproducibility(xlsx_path: Path | str) -> dict:
    """Extract stored metadata from a workbook (for `modelforge verify`)."""
    xlsx_path = Path(xlsx_path)
    wb = load_workbook(xlsx_path, data_only=False, keep_links=True)
    if SHEET_NAME not in wb.sheetnames:
        return {}
    ws = wb[SHEET_NAME]
    out: dict[str, str] = {}
    for r in range(5, ws.max_row + 1):
        label = ws.cell(row=r, column=1).value
        value = ws.cell(row=r, column=2).value
        if label and value is not None:
            out[str(label)] = str(value)
    return out


def verify_spec_hash(
    xlsx_path: Path | str,
    spec_source_bytes: bytes,
) -> tuple[bool, str, str]:
    """Compare stored SHA-256 to a recomputed one from given YAML bytes.

    Returns (match, stored, recomputed).
    """
    stored_meta = read_reproducibility(xlsx_path)
    stored = stored_meta.get("Spec SHA-256", "")
    recomputed = hashlib.sha256(spec_source_bytes).hexdigest()
    return stored == recomputed, stored, recomputed


__all__ = [
    "SHEET_NAME",
    "compute_spec_hash",
    "append_reproducibility_block",
    "read_reproducibility",
    "verify_spec_hash",
]

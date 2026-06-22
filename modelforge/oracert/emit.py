"""Emit an OraCert in-toto Statement for a certified ModelForge build.

The matching producer to OraClaw's TS emitter: wraps a built workbook's
manifest into the shared ``oracert.dev/redrivable-result/v1`` envelope. The
subject is the ``.xlsx`` bound by its SHA-256; the witness names the manifest
hashes and which audits the verifier must re-run on the bound artifact.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from modelforge.oracert.schema import (
    METHOD_MODELFORGE_BUILD,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
)


def build_modelforge_statement(
    xlsx_path: str | Path,
    manifest_path: str | Path | None = None,
    audits: tuple[str, ...] = ("schedule",),
) -> dict[str, Any]:
    """Read the build manifest and emit the OraCert statement for the workbook.

    ``audits`` lists the re-derivations the verifier must run on the bound
    artifact (``"schedule"`` and/or ``"conservation"``). Raises ``FileNotFoundError``
    when the workbook or its manifest sidecar is missing.
    """
    from modelforge.analytics.manifest import read_manifest

    xlsx = Path(xlsx_path)
    if not xlsx.exists():
        raise FileNotFoundError(f"workbook not found: {xlsx}")
    mpath = Path(manifest_path) if manifest_path else xlsx.with_suffix(".manifest.json")
    if not mpath.exists():
        raise FileNotFoundError(f"manifest sidecar not found: {mpath}")

    manifest = read_manifest(mpath)
    m = asdict(manifest) if is_dataclass(manifest) else dict(manifest)

    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {"name": xlsx.name, "digest": {"sha256": m["workbook_sha256"]}}
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "method": METHOD_MODELFORGE_BUILD,
            "redrivable": True,
            "producer": {
                "name": "modelforge",
                "version": str(m.get("modelforge_version", "")),
            },
            "witness": {
                "manifest": {
                    "workbook_sha256": m["workbook_sha256"],
                    "spec_sha256": m.get("spec_sha256"),
                    "sources_sha256": m.get("sources_sha256"),
                },
                "audits": list(audits),
            },
        },
    }

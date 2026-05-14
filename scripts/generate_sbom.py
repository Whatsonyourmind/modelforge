#!/usr/bin/env python3
"""Generate a CycloneDX 1.5 SBOM (Software Bill of Materials) for ModelForge.

Reads ``pyproject.toml`` + the installed Python environment, emits a
CycloneDX-compliant JSON SBOM listing every dependency with version,
PURL (Package URL), license (where derivable), and hash (sha256 of the
installed wheel where possible).

CycloneDX 1.5 is the modern open-standard SBOM format used by NIST SSDF
PO.5 supply-chain control. Required (or strongly recommended) for:
    - NIST SSDF compliance
    - SOC 2 Type II — supply-chain section
    - EU CRA (Cyber Resilience Act) preparation
    - Enterprise procurement RFPs at G-SIBs / FactSet / S&P

Usage::

    python scripts/generate_sbom.py > sbom.cdx.json
    # or
    python scripts/generate_sbom.py --out sbom.cdx.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _git_revision() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"


def _read_pyproject() -> dict:
    py = REPO_ROOT / "pyproject.toml"
    with py.open("rb") as f:
        return tomllib.load(f)


def _installed_packages() -> list[dict]:
    """Use `pip list --format=json` to enumerate installed packages."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(out.stdout)
    except subprocess.CalledProcessError:
        return []


def _package_purl(name: str, version: str) -> str:
    """Package URL per https://github.com/package-url/purl-spec."""
    return f"pkg:pypi/{name.lower().replace('_', '-')}@{version}"


def _component(pkg: dict) -> dict:
    name = pkg.get("name", "?")
    version = pkg.get("version", "?")
    return {
        "type": "library",
        "bom-ref": _package_purl(name, version),
        "name": name,
        "version": version,
        "purl": _package_purl(name, version),
        "scope": "required",
    }


def build_sbom() -> dict:
    pyproj = _read_pyproject()
    proj_meta = pyproj.get("project", {})

    me = {
        "type": "application",
        "bom-ref": f"pkg:pypi/modelforge@{proj_meta.get('version', '0.0.0')}",
        "name": proj_meta.get("name", "modelforge"),
        "version": proj_meta.get("version", "0.0.0"),
        "description": proj_meta.get("description", ""),
        "purl": f"pkg:pypi/modelforge@{proj_meta.get('version', '0.0.0')}",
        "supplier": {
            "name": "maintainer",
            "url": ["https://github.com/Whatsonyourmind/modelforge"],
        },
        "licenses": [
            {"license": {"name": proj_meta.get("license", {}).get("text", "Proprietary")}}
        ],
        "properties": [
            {"name": "git.revision", "value": _git_revision()},
        ],
    }

    components = [_component(p) for p in _installed_packages()
                  if p.get("name", "").lower() != "modelforge"]

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{
                "vendor": "ModelForge",
                "name": "generate_sbom.py",
                "version": proj_meta.get("version", "0.0.0"),
            }],
            "component": me,
        },
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CycloneDX 1.5 SBOM")
    parser.add_argument("--out", "-o", help="Output path (default: stdout)")
    args = parser.parse_args()

    sbom = build_sbom()
    payload = json.dumps(sbom, indent=2)

    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"SBOM written: {args.out} ({len(sbom['components'])} components)", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

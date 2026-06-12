"""Tests for the MCP conversational model-building surface.

Covers the full loop an MCP client (Claude Desktop/Code) drives:
list_templates -> spec_guide / get_spec_schema -> validate_spec (no build)
-> certify (build + audit) -> lineage tools availability.

FastMCP's ``@server.tool()`` decorator returns the original function, so the
tools are called directly as plain Python functions here; registration is
verified separately via ``server.list_tools()``.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
import yaml

from modelforge.templates import REGISTRY
from modelforge.mcp_server import (
    certify,
    get_spec_schema,
    server,
    spec_guide,
    validate_spec,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
GOOD_SPEC_PATH = EXAMPLES / "three_statement_cdmo.yaml"
GOOD_SPEC = GOOD_SPEC_PATH.read_text(encoding="utf-8")


# ── validate_spec ────────────────────────────────────────────────────────────


def test_validate_spec_passes_good_example():
    out = validate_spec(GOOD_SPEC)
    assert out["valid"] is True
    assert out["model_type"] == "three_statement"
    assert out["errors"] == []


def test_validate_spec_accepts_file_path():
    out = validate_spec(str(EXAMPLES / "dcf_enel.yaml"))
    assert out["valid"] is True
    assert out["model_type"] == "dcf"


def test_validate_spec_yaml_parse_error_is_friendly():
    out = validate_spec("model_type: dcf\nwacc: [unclosed\n")
    assert out["valid"] is False
    assert out["errors"], "expected at least one error"
    assert "YAML parse error" in out["errors"][0]


def test_validate_spec_non_mapping_document():
    out = validate_spec("- just\n- a\n- list\n")
    assert out["valid"] is False
    assert "YAML mapping" in out["errors"][0]


def test_validate_spec_unknown_model_type_lists_known():
    out = validate_spec("model_type: hedge_fund\n")
    assert out["valid"] is False
    assert "Unknown model_type" in out["errors"][0]
    assert "Known:" in out["errors"][0]
    assert out["model_type"] == "hedge_fund"


def test_validate_spec_missing_fields_have_friendly_paths():
    out = validate_spec("model_type: three_statement\n")
    assert out["valid"] is False
    missing = [e for e in out["errors"] if e.startswith("Missing required field:")]
    assert missing, f"expected friendly missing-field errors, got: {out['errors']}"
    # Paths are dotted, not raw Pydantic loc tuples.
    assert not any("loc=" in e for e in out["errors"])


def test_validate_spec_dangling_source_id_is_error():
    bad = GOOD_SPEC.replace(
        "historical_net_debt_source_id: S-001",
        "historical_net_debt_source_id: S-999",
    )
    assert bad != GOOD_SPEC  # guard: the fixture field must exist
    out = validate_spec(bad)
    assert out["valid"] is False
    joined = " ".join(out["errors"])
    assert "S-999" in joined
    assert "not defined" in joined


def test_validate_spec_unknown_top_level_key_is_warning_not_error():
    out = validate_spec(GOOD_SPEC + "\nrisk_free_ratee: 0.03\n")
    assert out["valid"] is True
    assert any("risk_free_ratee" in w for w in out["warnings"])


def test_validate_spec_model_type_param_fills_missing_declaration():
    raw = yaml.safe_load(GOOD_SPEC)
    raw.pop("model_type")
    text = yaml.safe_dump(raw, sort_keys=False)
    out = validate_spec(text, model_type="three_statement")
    assert out["valid"] is True
    assert out["model_type"] == "three_statement"


def test_validate_spec_conflicting_model_type_warns():
    out = validate_spec(GOOD_SPEC, model_type="dcf")
    # Spec's own declaration wins; the conflict is surfaced as a warning.
    assert out["model_type"] == "three_statement"
    assert any("declares model_type" in w for w in out["warnings"])


# ── spec_guide ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("model_type", sorted(REGISTRY))
def test_spec_guide_covers_every_registered_template(model_type):
    g = spec_guide(model_type)
    assert "error" not in g
    assert g["model_type"] == model_type
    assert g["required_blocks"], "every template has required top-level blocks"
    assert g["example_yaml"] and f"model_type: {model_type}" in g["example_yaml"]
    assert len(g["common_errors"]) == 3
    assert all("error" in ce and "fix" in ce for ce in g["common_errors"])
    assert "S-001" in g["id_discipline"] and "A-001" in g["id_discipline"]
    assert any("validate_spec" in step for step in g["workflow"])
    assert isinstance(g["example_is_stub"], bool)


def test_spec_guide_unknown_model_type():
    g = spec_guide("nope")
    assert "Unknown model_type" in g["error"]


def test_spec_guide_seeded_example_validates():
    """The guide's example for a seeded template must pass validate_spec —
    that is the whole point of handing it to an LLM client."""
    g = spec_guide("three_statement")
    assert g["example_is_stub"] is False
    out = validate_spec(g["example_yaml"])
    assert out["valid"] is True, out["errors"]


# ── get_spec_schema ──────────────────────────────────────────────────────────


def test_get_spec_schema_returns_json_schema():
    out = get_spec_schema("dcf")
    assert out["model_type"] == "dcf"
    schema = out["schema"]
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert schema["$id"] == "modelforge://dcf.schema.json"
    assert "properties" in schema


def test_get_spec_schema_unknown_model_type():
    out = get_spec_schema("nope")
    assert "Unknown model_type" in out["error"]


# ── certify ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def certified(tmp_path_factory):
    """Build + audit one small example once; reused by several tests."""
    out_dir = tmp_path_factory.mktemp("mcp_certify")
    return certify(spec_yaml=GOOD_SPEC, output_dir=str(out_dir)), out_dir


def test_certify_small_example_is_certified(certified):
    result, _ = certified
    assert "error" not in result, result.get("error")
    assert result["verdict"] == "CERTIFIED"
    assert result["formula_error_count"] == 0
    assert result["formula_errors"] == []
    assert result["style_gap_count"] == 0
    assert Path(result["xlsx"]).exists()
    assert Path(result["graph_db"]).exists()


def test_certify_writes_valid_manifest_sha(certified):
    result, _ = certified
    assert result["manifest_sha"] is not None
    assert re.fullmatch(r"[0-9a-f]{64}", result["manifest_sha"])


def test_certify_workbook_path_mode(certified):
    result, _ = certified
    again = certify(workbook_path=result["xlsx"])
    assert again["verdict"] == "CERTIFIED"
    assert again["manifest_sha"] == result["manifest_sha"]
    assert "graph_db" not in again  # audit-only mode builds nothing


def test_certify_requires_exactly_one_input(certified):
    result, _ = certified
    assert "exactly one" in certify()["error"]
    both = certify(spec_yaml=GOOD_SPEC, workbook_path=result["xlsx"])
    assert "exactly one" in both["error"]


def test_certify_invalid_spec_short_circuits(tmp_path):
    out = certify(spec_yaml="model_type: three_statement\n",
                  output_dir=str(tmp_path))
    assert out["verdict"] == "INVALID_SPEC"
    assert any(e.startswith("Missing required field:") for e in out["errors"])
    assert not list(tmp_path.glob("*.xlsx"))  # nothing was built


def test_certify_missing_workbook():
    out = certify(workbook_path="does_not_exist_anywhere.xlsx")
    assert "workbook not found" in out["error"]


# ── server registration + smoke ──────────────────────────────────────────────


def test_server_exposes_conversational_loop_tools():
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    for required in (
        "list_templates", "spec_guide", "get_spec_schema", "validate_spec",
        "build_model", "certify", "qc_workbook", "list_sources", "lineage_walk",
    ):
        assert required in names, f"tool {required!r} not registered"
    # Docstring pass: every tool ships a non-empty description.
    assert all((t.description or "").strip() for t in tools)


def test_mcp_server_importable_and_runnable():
    import modelforge.mcp_server as m
    assert callable(m.main)
    assert hasattr(m.server, "run")

"""Tests for v0.4 US-006 — ingestion coverage across all 11 templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from modelforge.ingest.pipeline import (
    TEMPLATE_SECTIONS,
    _default_horizon,
)
from modelforge.templates import REGISTRY

ROOT = Path(__file__).resolve().parent.parent


def test_all_template_types_registered_for_ingest():
    """Every template in REGISTRY must have an ingest section builder."""
    missing = set(REGISTRY) - set(TEMPLATE_SECTIONS)
    assert not missing, (
        f"Templates missing ingest support: {missing}. "
        "Add to TEMPLATE_SECTIONS in modelforge/ingest/pipeline.py."
    )


@pytest.mark.parametrize("template", list(TEMPLATE_SECTIONS))
def test_section_builder_returns_valid_shape(template):
    spec_cls, sections = TEMPLATE_SECTIONS[template]()
    # model_type field literal must match the key
    mt_field = spec_cls.model_fields.get("model_type")
    assert mt_field is not None, f"{template} has no model_type field"
    assert len(sections) >= 1
    # First section is always 'target' for consistency
    assert sections[0][0] == "target", (
        f"{template} first section should be 'target', got {sections[0][0]}"
    )


@pytest.mark.parametrize("template", list(TEMPLATE_SECTIONS))
def test_prompt_file_exists_per_template(template):
    """Every template should have template_*.md prompt guidance."""
    p = ROOT / "modelforge" / "ingest" / "prompts" / f"template_{template}.md"
    assert p.exists(), f"Missing prompt file: {p}"
    content = p.read_text(encoding="utf-8")
    assert len(content) > 200, f"Prompt file {p} too short"


@pytest.mark.parametrize("template", list(TEMPLATE_SECTIONS))
def test_default_horizon_is_dict(template):
    h = _default_horizon(template)
    assert isinstance(h, dict)

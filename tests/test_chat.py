"""Tests for modelforge.chat (US-008)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from modelforge.chat import ChatSession, build_system_prompt, workbook_summary
from modelforge.chat.context import workbook_summary as ws_fn
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def built_unitranche(tmp_path_factory):
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("chat") / "u.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    return out


def test_workbook_summary_non_empty(built_unitranche):
    s = workbook_summary(built_unitranche)
    assert len(s) > 500
    assert "Sheets:" in s
    assert "## Sources" in s
    assert "## Assumptions" in s


def test_system_prompt_has_rules(built_unitranche):
    p = build_system_prompt(built_unitranche)
    # Must describe citation format and rule set
    assert "A-###" in p and "S-###" in p
    assert "primary_output" in p or "Primary output" in p or "Sheets:" in p


def test_chat_session_history_tracking(built_unitranche):
    s = ChatSession(xlsx_path=built_unitranche, backend="dry")
    r1 = s.ask("What is A-001?")
    r2 = s.ask("Follow-up")
    assert len(s.history) == 4  # 2 user + 2 assistant
    assert s.history[0].role == "user"
    assert s.history[1].role == "assistant"
    assert "dry-run" in r1
    assert "dry-run" in r2


def test_to_markdown_format(built_unitranche):
    s = ChatSession(xlsx_path=built_unitranche, backend="dry")
    s.ask("test question one")
    s.ask("test question two")
    md = s.to_markdown()
    assert "**You:**" in md
    assert "**ModelForge:**" in md
    assert "test question one" in md
    assert "test question two" in md


def test_api_backend_without_key_raises(monkeypatch, built_unitranche):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = ChatSession(xlsx_path=built_unitranche, backend="api")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        s.ask("hello")


def test_summary_deterministic(built_unitranche):
    """Same workbook → same summary (ensures prompt caches hit)."""
    s1 = workbook_summary(built_unitranche)
    s2 = workbook_summary(built_unitranche)
    assert s1 == s2


def test_summary_mentions_sources_and_assumptions(built_unitranche):
    s = workbook_summary(built_unitranche)
    # Unitranche CDMO spec has A- and S- IDs
    assert "A-" in s
    assert "S-" in s


def test_chat_session_accepts_string_xlsx_path(built_unitranche):
    """Regression: ChatSession constructed with a string path must
    still expose .name in to_markdown() (previously AttributeError)."""
    s = ChatSession(xlsx_path=str(built_unitranche), backend="dry")
    s.ask("question")
    md = s.to_markdown()
    assert built_unitranche.name in md

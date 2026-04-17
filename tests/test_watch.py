"""Tests for modelforge.watch (US-030 — data-room watcher)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from modelforge.cli import main
from modelforge.watch import FolderBaseline, scan_folder


# ── Core scanner ───────────────────────────────────────────────────────────


def test_first_scan_all_files_added(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"content-a")
    (tmp_path / "b.xlsx").write_bytes(b"content-b")
    change, _ = scan_folder(tmp_path)
    assert len(change.added) == 2
    assert not change.modified
    assert not change.removed
    assert not change.clean


def test_second_scan_after_persist_is_clean(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"content-a")
    # First scan persists
    scan_folder(tmp_path, persist=True)
    # Second scan: no changes
    change, _ = scan_folder(tmp_path)
    assert change.clean
    assert len(change.unchanged) == 1


def test_modified_file_detected(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"v1")
    scan_folder(tmp_path, persist=True)
    time.sleep(0.01)
    f.write_bytes(b"v2-longer-content")
    change, _ = scan_folder(tmp_path)
    assert len(change.modified) == 1
    old, new = change.modified[0]
    assert old.sha256 != new.sha256
    assert old.size != new.size


def test_removed_file_detected(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"v1")
    (tmp_path / "b.pdf").write_bytes(b"v2")
    scan_folder(tmp_path, persist=True)
    (tmp_path / "a.pdf").unlink()
    change, _ = scan_folder(tmp_path)
    assert len(change.removed) == 1
    assert change.removed[0].path == "a.pdf"


def test_mixed_change_set(tmp_path):
    (tmp_path / "keep.pdf").write_bytes(b"k")
    (tmp_path / "gone.pdf").write_bytes(b"g")
    (tmp_path / "modify.pdf").write_bytes(b"m1")
    scan_folder(tmp_path, persist=True)
    (tmp_path / "gone.pdf").unlink()
    (tmp_path / "modify.pdf").write_bytes(b"m2-changed")
    (tmp_path / "new.pdf").write_bytes(b"n")
    change, _ = scan_folder(tmp_path)
    assert len(change.added) == 1
    assert len(change.modified) == 1
    assert len(change.removed) == 1
    assert change.n_changes == 3


def test_non_directory_raises(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        scan_folder(f)


def test_baseline_roundtrips_on_disk(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"hello")
    scan_folder(tmp_path, persist=True)
    # Baseline file exists with expected schema
    assert (tmp_path / ".modelforge" / "baseline.json").exists()
    # Re-loadable
    bl = FolderBaseline.load_or_empty(tmp_path)
    assert "a.pdf" in bl.files
    assert bl.files["a.pdf"].sha256


def test_baseline_ignores_itself(tmp_path):
    """The baseline JSON file must not appear as a tracked file."""
    (tmp_path / "a.pdf").write_bytes(b"x")
    scan_folder(tmp_path, persist=True)
    change, new_baseline = scan_folder(tmp_path, persist=False)
    # baseline.json shouldn't be in the tracked files
    assert "baseline.json" not in new_baseline.files
    assert ".modelforge/baseline.json" not in new_baseline.files


def test_non_persist_leaves_baseline_unchanged(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"x")
    scan_folder(tmp_path, persist=True)
    mtime_before = (tmp_path / ".modelforge" / "baseline.json").stat().st_mtime
    time.sleep(0.05)
    (tmp_path / "b.pdf").write_bytes(b"y")
    scan_folder(tmp_path, persist=False)
    mtime_after = (tmp_path / ".modelforge" / "baseline.json").stat().st_mtime
    assert mtime_before == mtime_after


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_scan_cli_reports_added(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"x")
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 1
    assert "added" in result.output


def test_scan_cli_exits_0_when_clean(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"x")
    runner = CliRunner()
    # First scan with --persist establishes baseline
    runner.invoke(main, ["scan", str(tmp_path), "--persist"])
    # Second with no changes → exit 0
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "no changes" in result.output


def test_scan_cli_markdown_export(tmp_path):
    (tmp_path / "new_doc.pdf").write_bytes(b"x")
    md = tmp_path / "changes.md"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path), "-o", str(md)])
    assert result.exit_code == 1
    assert md.exists()
    text = md.read_text(encoding="utf-8")
    assert "Added" in text
    assert "new_doc.pdf" in text

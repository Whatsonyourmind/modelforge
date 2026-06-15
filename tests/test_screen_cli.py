"""Tests for the `modelforge screen` CLI subcommand (deal-screening wiring).

Covers: filter + rank ordering, top-N truncation, --glob discovery, friendly
empty/missing-dir messages, and key=val parse errors. Uses a temp directory of
tiny synthetic specs so it never touches the shipped examples.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from modelforge.cli import main


def _write_spec(directory: Path, name: str, **screening) -> Path:
    """Write a minimal screenable spec (only the screening block matters here).

    The screener parses YAML at the spec layer and reads only the optional
    top-level `screening:` block, so these specs need nothing else to be
    screenable — they are intentionally tiny and synthetic.
    """
    import yaml

    path = directory / name
    path.write_text(
        yaml.safe_dump({"model_type": "dcf", "screening": screening},
                       sort_keys=False),
        encoding="utf-8",
    )
    return path


def _make_dir(tmp_path: Path) -> Path:
    d = tmp_path / "deals"
    d.mkdir()
    _write_spec(d, "alpha.yaml", deal_id="ALPHA", sector="industrials",
                geography="EU", deal_size_eur_m=200, vintage=2026,
                irr_base=0.18, leverage_x=4.5, ebitda_margin=0.22)
    _write_spec(d, "bravo.yaml", deal_id="BRAVO", sector="industrials",
                geography="EU", deal_size_eur_m=120, vintage=2025,
                irr_base=0.25, leverage_x=3.8, ebitda_margin=0.28)
    _write_spec(d, "charlie.yaml", deal_id="CHARLIE", sector="tech",
                geography="US", deal_size_eur_m=90, vintage=2026,
                irr_base=0.12, leverage_x=5.5, ebitda_margin=0.19)
    return d


def test_screen_filter_and_rank_orders_by_irr(tmp_path):
    """Filter to industrials, rank by irr_base — BRAVO (0.25) beats ALPHA (0.18),
    CHARLIE (tech) is filtered out entirely."""
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--filter", "sector=industrials",
        "--rank", "irr_base=1.0",
    ])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "BRAVO" in out
    assert "ALPHA" in out
    assert "CHARLIE" not in out  # filtered out (tech)
    # Highest-IRR deal must rank first.
    assert out.index("BRAVO") < out.index("ALPHA")


def test_screen_negative_weight_is_lower_is_better(tmp_path):
    """A negative weight on leverage_x makes lower leverage rank higher."""
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--filter", "sector=industrials",
        "--rank", "leverage_x=-1.0",
    ])
    assert result.exit_code == 0, result.output
    out = result.output
    # BRAVO leverage 3.8 < ALPHA 4.5, so BRAVO ranks first under lower-is-better.
    assert out.index("BRAVO") < out.index("ALPHA")


def test_screen_top_n_truncates(tmp_path):
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--rank", "irr_base=1.0",
        "--top", "1",
    ])
    assert result.exit_code == 0, result.output
    out = result.output
    # Top-1 by IRR across all three is BRAVO (0.25).
    assert "BRAVO" in out
    assert "ALPHA" not in out
    assert "CHARLIE" not in out


def test_screen_min_max_filters(tmp_path):
    """_min / _max suffix filters compare numerically."""
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--filter", "irr_base_min=0.20",
    ])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "BRAVO" in out          # irr 0.25 >= 0.20
    assert "ALPHA" not in out      # irr 0.18 < 0.20
    assert "CHARLIE" not in out    # irr 0.12 < 0.20


def test_screen_in_filter_comma_list(tmp_path):
    """_in suffix accepts a comma list for membership."""
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--filter", "geography_in=US,APAC",
    ])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "CHARLIE" in out        # geography US in {US, APAC}
    assert "ALPHA" not in out      # EU not in list
    assert "BRAVO" not in out


def test_screen_empty_dir_friendly(tmp_path):
    """A directory with no screenable specs exits 0 with a friendly hint."""
    d = tmp_path / "empty"
    d.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["screen", str(d)])
    assert result.exit_code == 0, result.output
    assert "No screenable deals" in result.output
    assert "screening:" in result.output  # points at the convention


def test_screen_missing_dir_errors(tmp_path):
    runner = CliRunner()
    missing = tmp_path / "does_not_exist"
    result = runner.invoke(main, ["screen", str(missing)])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_screen_bad_filter_syntax_errors(tmp_path):
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--filter", "sectorindustrials",  # no '='
    ])
    assert result.exit_code == 2
    assert "key=value" in result.output


def test_screen_bad_rank_weight_errors(tmp_path):
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--rank", "irr_base=high",  # not a number
    ])
    assert result.exit_code == 2
    assert "must be a number" in result.output


def test_screen_glob_restricts_discovery(tmp_path):
    """--glob limits which spec files are discovered."""
    d = _make_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, [
        "screen", str(d),
        "--glob", "alpha.yaml",
    ])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "ALPHA" in out
    assert "BRAVO" not in out
    assert "CHARLIE" not in out

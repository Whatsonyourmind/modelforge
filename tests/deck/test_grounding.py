"""Tests for the deterministic deck numeric-grounding gate.

Two load-bearing guarantees:

* **Zero false positives** — on the REAL certified sponsor_lbo decks (ic_memo
  + teaser) every rendered token reconciles to a fact or whitelisted
  derivation, so ``ground_numbers=True`` never blocks a legitimate deck.
* **Catches a real scale bug** — a millions→units (x1000) format error in the
  composer makes the gate fail closed (the falsifier), proving it is not
  vacuous.

Plus numparse unit coverage and the vacuous-skip contract for un-whitelisted
(template, deck_type) surfaces.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from modelforge.deck.qa.numparse import extract_numeric_tokens

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "examples" / "sponsor_lbo_us_saas.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# numparse unit tests
# ─────────────────────────────────────────────────────────────────────────────


def _one(text: str):
    toks = extract_numeric_tokens(text)
    assert len(toks) == 1, f"{text!r} -> {toks}"
    return toks[0]


class TestNumparse:
    def test_currency_millions(self):
        t = _one("Entry EV €1,234.5M certified")
        assert t.kind == "currency" and t.value == 1234.5 and t.scale == "m"
        assert t.value_in_millions() == pytest.approx(1234.5)
        assert t.decimals == 1

    def test_currency_thousands_reduces_to_millions(self):
        t = _one("ask $500k")
        assert t.scale == "k" and t.value_in_millions() == pytest.approx(0.5)

    def test_currency_billions(self):
        t = _one("12.5B enterprise value")
        assert t.scale == "b" and t.value_in_millions() == pytest.approx(12_500.0)

    def test_percent_and_fraction(self):
        t = _one("IRR 18.0%")
        assert t.kind == "percent" and t.fraction() == pytest.approx(0.18)

    def test_multiple(self):
        t = _one("MoIC 2.69x on the series")
        assert t.kind == "multiple" and t.value == pytest.approx(2.69)

    def test_bps(self):
        t = _one("spread 250bps")
        assert t.kind == "bps" and t.value == pytest.approx(250.0)

    def test_plain_table_number(self):
        t = _one("Total 87.3")
        assert t.kind == "plain" and t.value == pytest.approx(87.3)

    def test_year_is_not_a_token(self):
        assert extract_numeric_tokens("Valuation date 2026") == []

    def test_iso_date_emits_no_tokens(self):
        # 2026 is a year; -04 / -15 are date separators, not signed financials.
        assert extract_numeric_tokens("US · 2026-04-15") == []

    def test_identifier_digits_ignored(self):
        assert extract_numeric_tokens("Project DEMO-LBO-USTECH-01") == []

    def test_units_suffix_not_misread_as_millions(self):
        # "mo" / trailing letters must NOT parse as an €M figure.
        assert extract_numeric_tokens("Runway 18.5mo") == []

    def test_sha256_fragment_not_misread_as_currency(self):
        # A truncated build-manifest digest must not yield financial tokens: the
        # hex run "…1f3b…" previously parsed as a currency "3b" (3 billion),
        # tripping the ic_memo grounding gate. The failure was interpreter-
        # specific only because the manifest sha differs per build, so a "<digit>b"
        # boundary surfaced on some runs and not others — the real defect is the
        # suffixed-token path not guarding numbers welded into an alnum run.
        text = "Mitigant: Bytes verified against build manifest (sha256 5e04a6621f3b…)."
        assert extract_numeric_tokens(text) == []

    def test_currency_welded_to_letters_is_not_a_figure(self):
        # Belt-and-suspenders: a bare scaled number glued to a leading letter or
        # digit (no separator) is part of a larger token, not a standalone figure.
        assert extract_numeric_tokens("ref9f3b done") == []
        # …but a properly separated figure still parses.
        t = _one("ref 9.0M done")
        assert t.kind == "currency" and t.value_in_millions() == pytest.approx(9.0)

    def test_display_ulp_scales_with_decimals(self):
        assert _one("250.0").display_ulp() == pytest.approx(0.05)
        assert _one("2.69x").display_ulp() == pytest.approx(0.005)


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end: real decks pass, scale bug is caught
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def built_workbook(tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("grounding")
    from modelforge.cli import _inject_trust_moat_and_finish, _load_spec_class
    from modelforge.templates import build_model

    spec_bytes = SPEC_PATH.read_bytes()
    raw = yaml.safe_load(spec_bytes)
    spec = _load_spec_class(raw["model_type"]).model_validate(raw)
    xlsx_out = out_dir / "sponsor_lbo_us_saas.xlsx"
    xlsx, _ = build_model(
        spec, xlsx_out, spec_source_bytes=spec_bytes, spec_source_path=SPEC_PATH)
    _inject_trust_moat_and_finish(xlsx, spec, spec_bytes, SPEC_PATH, quiet=True)
    return Path(xlsx)


class TestGroundingEndToEnd:
    @pytest.mark.parametrize("deck_type", ["ic_memo", "teaser"])
    def test_real_deck_grounds_with_zero_unreconciled(self, built_workbook, deck_type):
        from modelforge.deck.pipeline import build_deck_from_workbook

        res = build_deck_from_workbook(
            built_workbook,
            deck_type=deck_type,
            out_path=built_workbook.with_name(f"ground_{deck_type}.pptx"),
            ground_numbers=True,
        )
        assert res.grounding_ok is True
        assert res.unreconciled_count == 0
        assert res.summary()["grounding_ok"] is True

    def test_default_off_does_not_compute_grounding(self, built_workbook):
        from modelforge.deck.pipeline import build_deck_from_workbook

        res = build_deck_from_workbook(
            built_workbook,
            deck_type="ic_memo",
            out_path=built_workbook.with_name("ground_off.pptx"),
        )
        assert res.grounding_ok is None
        assert res.unreconciled_count is None

    def test_scale_bug_is_caught_fail_closed(self, built_workbook, monkeypatch):
        """Falsifier: a millions→units (x1000) format bug must block the deck."""
        import modelforge.deck.compose.ic_memo as icm
        from modelforge.deck.pipeline import (
            DeckAdapterError,
            build_deck_from_workbook,
        )

        monkeypatch.setattr(icm, "_format_eur", lambda v: f"€{v * 1000:,.1f}M")
        with pytest.raises(DeckAdapterError, match="grounding FAILED"):
            build_deck_from_workbook(
                built_workbook,
                deck_type="ic_memo",
                out_path=built_workbook.with_name("ground_bug.pptx"),
                ground_numbers=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Vacuous-skip contract for un-whitelisted surfaces
# ─────────────────────────────────────────────────────────────────────────────


class TestGroundingSkip:
    def test_unsupported_template_skips_vacuously(self):
        from modelforge.deck.qa.checkers.grounding import NumericGroundingChecker

        wf = SimpleNamespace(template="dcf", facts={})
        prs = SimpleNamespace(slides=[])
        rep = NumericGroundingChecker().check(prs, wf, SimpleNamespace(), "ic_memo")
        assert rep.skipped is True
        assert rep.passed is True
        assert rep.unreconciled_count == 0

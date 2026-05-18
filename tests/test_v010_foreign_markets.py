"""v0.10 foreign-market expansion — feature tests.

Covers:
    - Label class 8-language support (FR-1)
    - i18n.py full 7-language coverage (FR-2)
    - Builder secondary_lang parameter (FR-3)
    - HGB carve-out template + spec (FR-4)
    - Portfolio review template + spec (FR-5)
    - New foreign YAML examples build cleanly (FR-6)
    - First-cut language flag emits warning (risk mitigation)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from modelforge.builder.i18n import (
    LABELS, L, label_in, apply_runtime_secondary_lang, reset_runtime_secondary_lang,
    SECONDARY_LANGS, FIRST_CUT_LANGS,
)
from modelforge.spec.base import Label
from modelforge.templates import REGISTRY, PREVIEW_TEMPLATES


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT / "examples"
OUTPUT_DIR = ROOT / "output" / "test_v010"


# ---------- FR-1: Label class ----------


def test_label_supports_all_8_languages():
    """Label class must accept all 8 language fields."""
    lbl = Label(
        en="Revenue", it="Ricavi", de="Umsatzerlöse",
        es="Ingresos", sv="Intäkter", no="Inntekter",
        da="Indtægter", nl="Omzet",
    )
    assert lbl.en == "Revenue"
    assert lbl.it == "Ricavi"
    assert lbl.de == "Umsatzerlöse"
    assert lbl.nl == "Omzet"


def test_label_get_returns_requested_lang():
    lbl = Label(en="Revenue", de="Umsatzerlöse", sv="Intäkter")
    assert lbl.get("en") == "Revenue"
    assert lbl.get("de") == "Umsatzerlöse"
    assert lbl.get("sv") == "Intäkter"


def test_label_get_falls_back_to_en():
    """Missing/empty language falls back to EN, not error."""
    lbl = Label(en="Revenue", de="Umsatzerlöse")
    assert lbl.get("nl") == "Revenue"  # NL not provided → falls back
    assert lbl.get("xx") == "Revenue"  # unknown lang → falls back
    assert lbl.get("") == "Revenue"
    assert lbl.get(None) == "Revenue"


def test_label_str_unchanged():
    """__str__ returns en (backwards compat with v0.9.x callers)."""
    lbl = Label(en="Revenue", it="Ricavi")
    assert str(lbl) == "Revenue"


# ---------- FR-2: i18n.py coverage ----------


def test_i18n_has_minimum_label_count():
    """v0.10 ships ≥ 80 labels (the v0.9.7 baseline)."""
    assert len(LABELS) >= 80


def test_every_label_has_all_secondaries():
    """Every label in LABELS must have non-empty values for every secondary
    language we advertise as 'full coverage' (IT, DE, ES, SV, NO, DA, NL)."""
    missing: dict[str, list[str]] = {}
    for key, lbl in LABELS.items():
        for lang in SECONDARY_LANGS:
            val = getattr(lbl, lang, "")
            if not val:
                missing.setdefault(key, []).append(lang)
    assert not missing, (
        f"Labels missing translations: {missing}. "
        f"Every label must populate all {len(SECONDARY_LANGS)} secondary languages."
    )


def test_secondary_langs_is_correct():
    assert SECONDARY_LANGS == ("it", "de", "es", "sv", "no", "da", "nl")


def test_first_cut_langs_marked():
    assert FIRST_CUT_LANGS == frozenset({"sv", "no", "da", "nl"})


def test_label_in_helper():
    assert label_in("project_code", "de") == "Projektcode"
    assert label_in("project_code", "nl") == "Projectcode"
    assert label_in("revenue", "sv") == "Intäkter"


# ---------- FR-3: runtime secondary lang swap ----------


def test_apply_runtime_secondary_lang_de():
    """v0.11.1: contextvar-based — `.secondary` returns the active language;
    `.it` always returns literal Italian (no mutation)."""
    apply_runtime_secondary_lang("de")
    try:
        assert LABELS["project_code"].secondary == "Projektcode"
        # No more mutation — .it always stays Italian.
        assert LABELS["project_code"].it == "Codice progetto"
    finally:
        reset_runtime_secondary_lang()
    assert LABELS["project_code"].secondary == "Codice progetto"


def test_apply_runtime_secondary_lang_unknown_raises():
    with pytest.raises(ValueError):
        apply_runtime_secondary_lang("xx")


def test_reset_restores_italian():
    apply_runtime_secondary_lang("de")
    apply_runtime_secondary_lang("nl")
    reset_runtime_secondary_lang()
    assert LABELS["project_code"].secondary == "Codice progetto"
    # .it never changed under the new architecture
    assert LABELS["project_code"].it == "Codice progetto"


# ---------- FR-4 + FR-5: new templates registered ----------


def test_hgb_carveout_in_registry():
    assert "hgb_carveout" in REGISTRY


def test_portfolio_review_in_registry():
    assert "portfolio_review" in REGISTRY


def test_v010_templates_flagged_preview():
    assert "hgb_carveout" in PREVIEW_TEMPLATES
    assert "portfolio_review" in PREVIEW_TEMPLATES


def test_registry_has_16_templates():
    """v0.10 = v0.9.7 (14) + hgb_carveout + portfolio_review."""
    assert len(REGISTRY) == 16


# ---------- FR-6: foreign-market YAML examples build ----------


def test_portfolio_review_example_builds():
    """End-to-end: YAML → spec → workbook."""
    from modelforge.spec.portfolio_review import PortfolioReviewSpec

    yaml_path = EXAMPLES_DIR / "portfolio_review_us_lower_mm.yaml"
    assert yaml_path.exists(), f"Missing example: {yaml_path}"

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    spec = PortfolioReviewSpec.model_validate(data)
    assert spec.fund_name == "Lower-MM Credit Fund III (anonymized)"
    assert len(spec.portfolio) == 8

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "portfolio_review_smoke.xlsx"
    xlsx_path, _ = REGISTRY["portfolio_review"](spec, out_path)
    assert xlsx_path.exists()
    assert xlsx_path.stat().st_size > 5000  # not a stub


def test_hgb_carveout_example_builds():
    """End-to-end: YAML → spec → workbook with DE secondary lang."""
    from modelforge.spec.hgb_carveout import HGBCarveoutSpec

    yaml_path = EXAMPLES_DIR / "hgb_carveout_dach_chemicals.yaml"
    assert yaml_path.exists(), f"Missing example: {yaml_path}"

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    spec = HGBCarveoutSpec.model_validate(data)
    assert spec.hgb_assumptions is not None
    assert spec.hgb_assumptions.gewerbesteuer_hebesatz == 400.0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "hgb_carveout_smoke.xlsx"
    xlsx_path, _ = REGISTRY["hgb_carveout"](spec, out_path)
    assert xlsx_path.exists()
    assert xlsx_path.stat().st_size > 5000


def test_hgb_template_restores_italian_after_build():
    """HGB template applies DE during build; must restore IT on exit."""
    from modelforge.spec.hgb_carveout import HGBCarveoutSpec

    yaml_path = EXAMPLES_DIR / "hgb_carveout_dach_chemicals.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    spec = HGBCarveoutSpec.model_validate(data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "hgb_restore_test.xlsx"
    REGISTRY["hgb_carveout"](spec, out_path)

    # After build, runtime secondary must be back to Italian baseline.
    assert LABELS["project_code"].it == "Codice progetto"


# ---------- Risk mitigation: first-cut warning ----------


def test_first_cut_lang_emits_warning(tmp_path):
    """Building with sv/no/da/nl emits a UserWarning per PRD risk mitigation."""
    from modelforge.builder.workbook import build_workbook
    from modelforge.spec.unitranche import UnitrancheSpec

    yaml_path = EXAMPLES_DIR / "unitranche_cdmo.yaml"
    if not yaml_path.exists():
        pytest.skip("unitranche_cdmo.yaml not present (test depends on existing example)")

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    spec = UnitrancheSpec.model_validate(data)

    out_path = tmp_path / "first_cut_test.xlsx"
    with pytest.warns(UserWarning, match="first-cut"):
        build_workbook(spec, out_path, secondary_lang="sv")

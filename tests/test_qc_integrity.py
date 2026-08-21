"""QC-sheet integrity: every model must *derive* its own pass, not assert it.

Three defects motivated this module, all found by building the example corpus
and recomputing it rather than by reading the templates:

1. ``merger`` and ``fairness`` wrote a literal ``1`` into the ALL CHECKS PASS
   aggregator, so the workbook claimed a clean bill of health that no check
   supported.
2. ``project_finance`` and ``structured_credit`` passed ``"=1"`` as a check
   formula — a placeholder that cannot fail. One of them was masking a genuine
   result: the shipped ``real_enfinity_solar_pf`` project returns 5.4% equity
   IRR against a 10% target.
3. ``ipo``, ``restructuring`` and ``portfolio_review`` evaluated their checks
   in Python at build time and wrote the *word* "PASS" into the sheet. Nothing
   was recomputed, and the conservation gate saw no QC sheet at all.

The gate itself was blind to all three: it read recomputed *values*, where a
hardcoded 1 and a real aggregation are indistinguishable. Overwriting every QC
formula in a workbook with ``1`` produced ``status=PASS``.

These tests are the regression barrier. They are marked ``slow`` because each
one recalculates a full workbook with the ``formulas`` engine.
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import pytest
import yaml

from modelforge.cli import _load_spec_class
from modelforge.qc.conservation_audit import _is_derived_formula, audit_conservation
from modelforge.templates import REGISTRY, build_model

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted(
    p for p in (REPO_ROOT / "examples").glob("*.yaml") if not p.name.startswith("_")
)


def _build(spec_path: Path, out_dir: Path) -> Path:
    raw = yaml.safe_load(spec_path.read_bytes())
    spec = _load_spec_class(raw["model_type"]).model_validate(raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xlsx, _ = build_model(spec, out_dir / f"{spec_path.stem}.xlsx")
    return xlsx


# ── the derivation predicate ────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value,expected",
    [
        ("=IF(SUM($C$7,$C$8)=2,1,0)", True),
        ("='Operating'!C7>0", True),
        ("=ecl_weighted_pd_multiplier", True),   # named range
        ("=1", False),                           # constant wearing a formula
        ("=SUM(1,2)", False),                    # constant expression
        ("=TRUE", False),
        (1, False),
        ("PASS", False),
        (None, False),
    ],
)
def test_is_derived_formula(value, expected):
    """A verdict counts only when it depends on something outside its own cell."""
    assert _is_derived_formula(value) is expected


# ── every registered template must be exercised by the corpus ───────────────

def test_every_registered_model_type_has_an_example():
    """A template with no example is a template nothing ever builds.

    ``ipo`` and ``restructuring`` were registered, buildable model types with no
    example spec. Nothing constructed them, so their QC sheets sat dead and
    their calculation sheets shipped as pasted constants without anyone
    noticing.
    """
    covered = set()
    for path in EXAMPLES:
        covered.add(yaml.safe_load(path.read_bytes())["model_type"])
    missing = sorted(set(REGISTRY) - covered)
    assert not missing, f"registered model types with no example spec: {missing}"


# ── the corpus itself ───────────────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.parametrize("spec_path", EXAMPLES, ids=lambda p: p.stem)
def test_example_qc_is_live_and_passes(spec_path, tmp_path):
    """Build, recompute, and require a clean conservation PASS.

    ``hardcoded`` findings are called out separately from ordinary failures:
    a check that recomputes to 0 is a model that disagrees with itself, while a
    hardcoded one is a model that never asked the question.
    """
    pytest.importorskip("formulas")
    report = audit_conservation(_build(spec_path, tmp_path))

    hardcoded = [f for f in report.findings if f.status == "hardcoded"]
    assert not hardcoded, "QC cells that assert a verdict instead of deriving it: " + ", ".join(
        f"{f.ref} ({f.label}) = {f.recomputed!r}" for f in hardcoded
    )
    assert report.n_checks > 0, (
        f"{spec_path.stem}: QC sheet declares no live checks — "
        f"an ALL CHECKS PASS over nothing. Notes: {report.notes}"
    )
    assert report.status == "PASS", (
        f"{spec_path.stem}: conservation {report.status}. "
        f"Findings: {[(f.ref, f.label, f.recomputed) for f in report.findings[:5]]}. "
        f"Notes: {report.notes}"
    )


# ── the gate must still be able to fail ─────────────────────────────────────

@pytest.mark.slow
def test_forged_qc_sheet_is_rejected(tmp_path):
    """Overwriting every QC formula with a literal 1 must FAIL the gate.

    This is the exact forgery the gate used to bless. It is the detection-power
    half of the suite: without it, the tests above would still pass if
    ``audit_conservation`` were quietly weakened to return PASS for everything.
    """
    pytest.importorskip("formulas")
    from openpyxl import load_workbook

    genuine = _build(REPO_ROOT / "examples" / "npl_mixed_portfolio.yaml", tmp_path)
    assert audit_conservation(genuine).status == "PASS", "baseline must be clean"

    forged = tmp_path / "forged.xlsx"
    shutil.copy(genuine, forged)
    wb = load_workbook(forged, data_only=False)
    ws = wb[audit_conservation(genuine).qc_sheet]
    overwritten = 0
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.value = 1
                overwritten += 1
    wb.save(forged)
    assert overwritten, "no QC formulas found to forge — has the layout moved?"

    report = audit_conservation(forged)
    assert report.status == "FAIL", (
        "a QC sheet of hardcoded 1s must not certify clean "
        f"(got {report.status}, n_checks={report.n_checks})"
    )
    assert any(f.status == "hardcoded" for f in report.findings)

"""Regression test: a probability of default must stay inside [0, 1].

Background. The IFRS 9 ECL sheet had **no test coverage at all** — no hardtest
and no pytest module referenced ``IFRS9ECL``, ``ifrs9_ecl`` or
``ecl_weighted_pd_multiplier``. The stage-adjusted PD was computed as::

    =IF(B14="POCI",D14,J14)*ecl_weighted_pd_multiplier

with no upper bound. For an NPL portfolio the POCI/Stage-3 lifetime PD is
legitimately 1.00, so the downside macro multiplier (1.80) or even the weighted
one (1.1375) pushes it above unity. The shipped ``npl_mixed_portfolio`` example
recalculated to a **113.75% probability of default**, which then propagated into
ECL — overstating it by 12.1% on that example.

Every gate in the product certified that workbook: Trust, Moat, ``certify``,
``audit-conservation``, ``audit-perturb`` and ``audit-schedule`` all passed. They
check conservation, formula density, formula errors and perturbation stability —
none of them checks whether a *bounded quantity* is inside its bounds. This test
closes that specific gap for PD.

It recalculates the workbook rather than reading cached values, because the
builder writes formulas and openpyxl's cached values are empty on a fresh build.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest
import yaml

from modelforge.cli import _load_spec_class
from modelforge.templates import build_model

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = REPO_ROOT / "examples" / "npl_mixed_portfolio.yaml"

# IFRS9ECL!K is the stage-adjusted PD column; L is the resulting ECL.
PD_COLUMN = "K"


def _cell_value(entry):
    """Unwrap a `formulas` solution entry to a scalar."""
    try:
        return entry.value[0, 0]
    except Exception:
        return entry


@pytest.mark.slow
def test_stage_adjusted_pd_never_exceeds_one(tmp_path):
    formulas = pytest.importorskip("formulas")
    out = _build(tmp_path)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        solution = formulas.ExcelModel().loads(str(out)).finish().calculate()

    pds = {}
    for key, entry in solution.items():
        key_upper = key.upper()
        if "IFRS9" not in key_upper:
            continue
        match = re.search(rf"!({PD_COLUMN}\d+)>?$", key_upper)
        if match:
            pds[match.group(1)] = _cell_value(entry)

    assert pds, "no IFRS9ECL!K* cells found — did the sheet or column layout move?"

    offenders = []
    for ref, value in pds.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue  # header/label rows
        if value < 0 or value > 1:
            offenders.append((ref, value))

    assert not offenders, (
        "stage-adjusted PD outside [0, 1] — a probability cannot exceed 1: "
        + ", ".join(f"{ref}={value}" for ref, value in offenders)
    )


def _build(tmp_path: Path) -> Path:
    """Build the NPL example workbook into ``tmp_path``."""
    if not SPEC.exists():
        pytest.skip("example spec not present")
    raw = yaml.safe_load(SPEC.read_bytes())
    spec = _load_spec_class(raw["model_type"]).model_validate(raw)
    xlsx, _ = build_model(spec, tmp_path / "npl.xlsx")
    return xlsx

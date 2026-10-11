"""Collect the ``hardtest_*.py`` numerical suites into pytest.

These 18 scripts are the only layer that verifies ModelForge's *numbers* rather
than its plumbing: ~1,580 checks that reconcile the emitted workbook against an
independently recomputed clean-room result, and — in
``hardtest_external_groundtruth.py`` — against ``numpy_financial``, a separate
implementation, at 1e-9. Until now nothing collected them, so they passed only
when someone ran them by hand.

They are executed as **subprocesses** rather than imported, deliberately:

* several call ``sys.exit()`` at module level (e.g. ``hardtest_lbo_full.py``),
  which raises ``SystemExit`` during collection and errors the whole session;
* running them out-of-process leaves the scripts byte-for-byte unmodified. The
  code that proves the models are correct is the last code that should be
  edited to satisfy a test runner.

Each script signals success with exit code 0 and prints its own tally.

Five scripts read a workbook from ``output/`` without building it. ``output/``
is gitignored, so on a clean checkout (CI) they failed on a missing file, and
locally they silently graded whatever stale workbook was lying there — which
hid a convention change for months. :data:`PREBUILT` maps each of them to its
spec, and the harness rebuilds the workbook fresh before every run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

HARDTESTS = sorted(p.name for p in REPO_ROOT.glob("hardtest_*.py"))

# Scripts that grade ``output/<workbook>`` but do not build it themselves.
PREBUILT = {
    "hardtest_comps_fairness.py": ("examples/fairness_amplifon.yaml", "output/hardtest_comps_fairness.xlsx"),
    "hardtest_credit_leverage.py": ("examples/credit_memo_cdmo.yaml", "output/hardtest_credit_leverage.xlsx"),
    "hardtest_minibond.py": ("examples/minibond_logistics.yaml", "output/hardtest_minibond.xlsx"),
    "hardtest_mna_accretion.py": ("examples/merger_tim_iliad.yaml", "output/hardtest_mna_accretion.xlsx"),
    "hardtest_unitranche.py": ("examples/unitranche_uk_servicesco.yaml", "output/hardtest_unitranche.xlsx"),
}


def test_prebuilt_map_matches_scripts():
    """Every PREBUILT entry names a real script and spec, and the script reads that workbook."""
    for script, (spec, workbook) in PREBUILT.items():
        assert script in HARDTESTS, f"PREBUILT names a missing script: {script}"
        assert (REPO_ROOT / spec).is_file(), f"{script}: spec not found: {spec}"
        source = (REPO_ROOT / script).read_text(encoding="utf-8")
        assert Path(workbook).name in source, f"{script} does not read {workbook}"


def _build_workbook(script: str, env: dict) -> None:
    spec, workbook = PREBUILT[script]
    out = REPO_ROOT / workbook
    out.parent.mkdir(exist_ok=True)
    out.unlink(missing_ok=True)  # never grade a stale workbook
    proc = subprocess.run(
        [sys.executable, "-m", "modelforge.cli", "build", spec, "--out", str(out)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    if proc.returncode != 0 or not out.is_file():
        pytest.fail(
            f"building {workbook} from {spec} for {script} failed "
            f"(exit {proc.returncode})\n"
            f"--- stdout ---\n{(proc.stdout or '')[-2000:]}\n"
            f"--- stderr ---\n{(proc.stderr or '')[-2000:]}"
        )


def test_hardtests_are_discovered():
    """Guard the guard: if a rename or move hides the suites, fail loudly.

    Without this, deleting every ``hardtest_*.py`` would make the parametrised
    test below collect zero cases and the run would still be green.
    """
    assert len(HARDTESTS) >= 18, (
        f"expected at least 18 hardtest_*.py in {REPO_ROOT}, found "
        f"{len(HARDTESTS)}: {HARDTESTS}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("script", HARDTESTS)
def test_hardtest_passes(script: str):
    """Run one hardtest suite; a non-zero exit means a numerical check failed."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if script in PREBUILT:
        _build_workbook(script, env)
    proc = subprocess.run(
        [sys.executable, script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout or "").splitlines()[-40:])
        pytest.fail(
            f"{script} exited {proc.returncode}\n"
            f"--- stdout (last 40 lines) ---\n{tail}\n"
            f"--- stderr ---\n{(proc.stderr or '')[-2000:]}"
        )

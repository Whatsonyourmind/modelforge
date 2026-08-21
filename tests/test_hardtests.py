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
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

HARDTESTS = sorted(p.name for p in REPO_ROOT.glob("hardtest_*.py"))


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
    proc = subprocess.run(
        [sys.executable, script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout or "").splitlines()[-40:])
        pytest.fail(
            f"{script} exited {proc.returncode}\n"
            f"--- stdout (last 40 lines) ---\n{tail}\n"
            f"--- stderr ---\n{(proc.stderr or '')[-2000:]}"
        )

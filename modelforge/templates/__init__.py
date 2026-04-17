"""Template registry.

Each template contributes a builder function. Dispatch by model_type.

``build_model`` also applies the post-build analytics layer (sensitivity
tornado) so every template ships with a SensitivityAnalysis sheet by
default. Callers that don't want it (e.g. unit tests on the bare
skeleton) can call the template builder directly or pass
``with_sensitivity=False``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from modelforge.templates import (
    unitranche, minibond, credit_memo, project_finance, real_estate, npl,
    structured_credit, three_statement,
)

REGISTRY: dict[str, Callable] = {
    "unitranche": unitranche.build,
    "minibond": minibond.build,
    "credit_memo": credit_memo.build,
    "project_finance": project_finance.build,
    "real_estate": real_estate.build,
    "npl": npl.build,
    "structured_credit": structured_credit.build,
    "three_statement": three_statement.build,
}


def build_model(spec, out_path, graph_db_path=None, with_sensitivity: bool = True):
    """Dispatch to the right template builder based on spec.model_type.

    After the core template build, applies the sensitivity tornado
    post-processor unless ``with_sensitivity`` is False.
    """
    mt = spec.model_type
    if mt not in REGISTRY:
        raise ValueError(
            f"Unknown model_type {mt!r}. Known: {list(REGISTRY)}"
        )
    xlsx_path, graph_path = REGISTRY[mt](spec, out_path, graph_db_path)

    if with_sensitivity:
        try:
            from modelforge.analytics.sensitivity import append_sensitivity_sheet
            append_sensitivity_sheet(xlsx_path, spec)
        except Exception:
            # Sensitivity is a nice-to-have; never block the build.
            # Upstream CLI will still surface issues via QC if the
            # sheet is malformed.
            pass

    return Path(xlsx_path), Path(graph_path)

"""Template registry.

Each template contributes a builder function. Dispatch by model_type.
"""

from __future__ import annotations

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


def build_model(spec, out_path, graph_db_path=None):
    """Dispatch to the right template builder based on spec.model_type."""
    mt = spec.model_type
    if mt not in REGISTRY:
        raise ValueError(
            f"Unknown model_type {mt!r}. Known: {list(REGISTRY)}"
        )
    return REGISTRY[mt](spec, out_path, graph_db_path)

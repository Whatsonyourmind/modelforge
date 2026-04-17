"""Shadow engine registry.

Add a new engine by registering its compute function here (see
modelforge/shadow/dcf.py and unitranche.py for examples).
"""

from __future__ import annotations

from typing import Callable, Optional


def _get_engines() -> dict[str, Callable]:
    from modelforge.shadow.dcf import dcf_primary_output
    from modelforge.shadow.unitranche import unitranche_primary_output
    from modelforge.shadow.project_finance import pf_primary_output
    from modelforge.shadow.merger import merger_primary_output
    return {
        "dcf": dcf_primary_output,
        "unitranche": unitranche_primary_output,
        "credit_memo": unitranche_primary_output,  # same primary output
        "project_finance": pf_primary_output,
        "merger": merger_primary_output,
    }


# Cached on first access
_CACHED: dict[str, Callable] | None = None


def _engines() -> dict[str, Callable]:
    global _CACHED
    if _CACHED is None:
        _CACHED = _get_engines()
    return _CACHED


SHADOW_ENGINES: dict[str, Callable] = {}  # populated lazily by wrapper accessors


def has_shadow_engine(model_type: str) -> bool:
    return model_type in _engines()


def compute_primary_output(spec, overrides: Optional[dict[str, float]] = None) -> Optional[float]:
    """Compute the primary output via the template's shadow engine.

    Returns None if no shadow engine is registered for this model_type,
    or if the engine raises — caller should fall back to elasticity
    approximation.

    Parameters
    ----------
    spec : BaseModelSpec
        A validated Pydantic spec.
    overrides : Optional[dict[str, float]]
        Maps Assumption.name → overridden base value. Drivers not in
        the dict use their spec.base value.
    """
    mt = getattr(spec, "model_type", "")
    engines = _engines()
    if mt not in engines:
        return None
    try:
        return float(engines[mt](spec, overrides or {}))
    except Exception:
        return None


__all__ = ["SHADOW_ENGINES", "compute_primary_output", "has_shadow_engine"]

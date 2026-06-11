"""Human-friendly rendering of Pydantic spec-validation errors.

Pydantic's native ``ValidationError`` dumps 20+ lines of nested ``loc``
tuples, repeated ``[type=...]`` tags, and a docs URL — useful for library
authors, hostile to a finance analyst editing a YAML spec by hand. The CLI
``validate`` command routes every spec error through
:func:`format_validation_error` so the user instead sees a short, sorted
list of plain-language fixes, e.g.::

    Missing required field: operating.ebitda_margin_by_year
    Wrong type for wacc.beta_levered: expected a number

This module deliberately has no dependency beyond ``pydantic`` so it can be
imported cheaply by the CLI without dragging in the whole template stack.
"""

from __future__ import annotations

from typing import Iterable

try:  # pydantic is a hard dependency of every spec, but keep the import soft
    from pydantic import ValidationError
except Exception:  # pragma: no cover - pydantic is always installed in prod
    ValidationError = Exception  # type: ignore[assignment,misc]


def _dotted(loc: Iterable[object]) -> str:
    """Render a Pydantic ``loc`` tuple as a dotted, array-indexed path.

    ``("operating", "ebitda_margin_by_year", 2, "base")`` ->
    ``operating.ebitda_margin_by_year[2].base``. Integer indices become
    ``[i]`` so the path reads like the YAML the analyst is editing.
    """
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts) if parts else "(root)"


def _friendly_line(err: dict) -> str:
    """Turn one Pydantic error dict into a single plain-language line."""
    loc = _dotted(err.get("loc", ()))
    etype = str(err.get("type", ""))
    msg = str(err.get("msg", "")).strip()

    if etype == "missing":
        return f"Missing required field: {loc}"
    if etype == "extra_forbidden":
        return f"Unknown field (remove it): {loc}"
    if etype.startswith("int_") or etype == "int_parsing":
        return f"Wrong type for {loc}: expected a whole number"
    if etype.startswith("float_") or etype == "float_parsing":
        return f"Wrong type for {loc}: expected a number"
    if etype.startswith("bool_"):
        return f"Wrong type for {loc}: expected true/false"
    if etype.startswith("string_"):
        return f"Wrong type for {loc}: expected text"
    if etype in ("list_type", "dict_type", "model_type", "model_attributes_type"):
        return f"Wrong shape for {loc}: {msg}"
    if etype.startswith("greater_than") or etype.startswith("less_than"):
        return f"Out of range at {loc}: {msg}"
    # Fallback: keep the path + Pydantic's own message, drop the URL noise.
    return f"{loc}: {msg}" if msg else f"Invalid value at {loc}"


def format_validation_error(exc: "ValidationError", *, limit: int = 5) -> str:
    """Render a ``ValidationError`` as a short, friendly, sorted summary.

    Returns a multi-line string: a header counting the total problems, then
    up to ``limit`` one-line fixes (sorted by field path for stability), and
    a final "...and N more" footer when truncated. ``missing`` errors are
    surfaced first because a hand-edited spec most often fails on a forgotten
    section.
    """
    try:
        raw_errors = list(exc.errors())
    except Exception:  # not actually a ValidationError — show the str()
        return str(exc)

    # Stable order: missing fields first, then by dotted path.
    def _key(err: dict):
        is_missing = 0 if err.get("type") == "missing" else 1
        return (is_missing, _dotted(err.get("loc", ())))

    ordered = sorted(raw_errors, key=_key)
    total = len(ordered)
    shown = ordered[:limit]

    lines = [
        f"Spec validation failed — {total} problem"
        f"{'s' if total != 1 else ''} found:"
    ]
    for err in shown:
        lines.append(f"  - {_friendly_line(err)}")
    remaining = total - len(shown)
    if remaining > 0:
        lines.append(f"  ...and {remaining} more (fix the above first).")
    return "\n".join(lines)

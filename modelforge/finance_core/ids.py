"""Stable assumption / source ID allocation + validation.

Every ModelForge template assigns ``A-001`` / ``S-001`` -style IDs to its
assumptions and sources. Templates currently re-implement the allocation
separately; this module centralises it so Aither / CreditAI wrappers can
also produce valid spec payloads without re-implementing the ID rules.

ID rules (enforced):
    - ``A-NNN`` for assumptions, ``S-NNN`` for sources, NNN ≥ 3 digits.
    - Numeric suffix starts at 1, monotonically increasing within a spec.
    - Unique per category (no duplicate A-001 across the same workbook).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

_A_PATTERN = re.compile(r"^A-(\d{3,})$")
_S_PATTERN = re.compile(r"^S-(\d{3,})$")

Kind = Literal["A", "S"]


class IdAllocationError(ValueError):
    """Raised on duplicate or malformed IDs."""


def validate_id(id_value: str, kind: Kind) -> int:
    """Return the numeric part of a well-formed ID.

    Raises :class:`IdAllocationError` on a malformed ID.
    """
    pattern = _A_PATTERN if kind == "A" else _S_PATTERN
    match = pattern.match(id_value)
    if not match:
        raise IdAllocationError(
            f"Invalid {kind}-ID {id_value!r}; expected format "
            f"{kind}-NNN with 3+ digits"
        )
    return int(match.group(1))


def format_id(kind: Kind, number: int, *, width: int = 3) -> str:
    """Compose an ID: ``format_id("A", 7)`` → ``"A-007"``."""
    if number < 1:
        raise IdAllocationError("Numeric part must be ≥ 1")
    return f"{kind}-{number:0{width}d}"


@dataclass
class IdAllocator:
    """Mutable allocator that vends monotonically increasing IDs.

    Maintain two counters (``A-`` and ``S-``). Call :meth:`next_assumption`
    or :meth:`next_source` to allocate. Also supports :meth:`register` to
    claim an externally-chosen ID (and keep the counter ahead of it).
    """

    _a_counter: int = 0
    _s_counter: int = 0
    _a_used: set[int] = field(default_factory=set)
    _s_used: set[int] = field(default_factory=set)

    def next_assumption(self) -> str:
        self._a_counter += 1
        while self._a_counter in self._a_used:
            self._a_counter += 1
        self._a_used.add(self._a_counter)
        return format_id("A", self._a_counter)

    def next_source(self) -> str:
        self._s_counter += 1
        while self._s_counter in self._s_used:
            self._s_counter += 1
        self._s_used.add(self._s_counter)
        return format_id("S", self._s_counter)

    def register(self, id_value: str) -> None:
        """Claim an externally-supplied ID and bump the counter past it."""
        if id_value.startswith("A-"):
            number = validate_id(id_value, "A")
            if number in self._a_used:
                raise IdAllocationError(
                    f"Duplicate assumption ID: {id_value}"
                )
            self._a_used.add(number)
            self._a_counter = max(self._a_counter, number)
        elif id_value.startswith("S-"):
            number = validate_id(id_value, "S")
            if number in self._s_used:
                raise IdAllocationError(f"Duplicate source ID: {id_value}")
            self._s_used.add(number)
            self._s_counter = max(self._s_counter, number)
        else:
            raise IdAllocationError(
                f"Cannot register {id_value!r}: must start with A- or S-"
            )

    def all_assumption_ids(self) -> list[str]:
        return sorted(format_id("A", n) for n in self._a_used)

    def all_source_ids(self) -> list[str]:
        return sorted(format_id("S", n) for n in self._s_used)


def assert_unique_ids(
    ids: Iterable[str], *, kind: Kind, context: str = ""
) -> None:
    """Raise if any duplicates are detected in ``ids``."""
    seen: dict[str, int] = {}
    for id_value in ids:
        validate_id(id_value, kind)
        seen[id_value] = seen.get(id_value, 0) + 1
    duplicates = [k for k, v in seen.items() if v > 1]
    if duplicates:
        ctx = f" in {context}" if context else ""
        raise IdAllocationError(
            f"Duplicate {kind}-IDs{ctx}: {sorted(duplicates)}"
        )

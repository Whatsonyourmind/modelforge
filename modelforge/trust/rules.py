"""TrustRule base class + WorkbookProbe (formula-resolved cell access)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from modelforge.trust.violations import Severity, TrustViolation


class WorkbookProbe:
    """Read-only view of a workbook with its formulas already resolved.

    Wraps the third-party `formulas` package so rules can ask for cell
    values by name (named range, or `Sheet!Cell`) without re-implementing
    Excel arithmetic. Lazy: opens the workbook on first access.
    """

    def __init__(self, xlsx_path: Union[str, Path]) -> None:
        self.path = Path(xlsx_path)
        self._sol = None
        self._named_to_cell: dict[str, str] = {}

    def _ensure_loaded(self) -> None:
        if self._sol is not None:
            return
        try:
            import formulas
            xl = formulas.ExcelModel().loads(str(self.path)).finish()
            self._sol = xl.calculate()
        except Exception as e:
            raise RuntimeError(f"Trust probe could not load {self.path.name}: {e}") from e

        # Build named-range -> sheet!cell lookup
        try:
            from openpyxl import load_workbook
            wb = load_workbook(self.path, data_only=False)
            for nm in wb.defined_names:
                d = wb.defined_names[nm]
                self._named_to_cell[nm.lower()] = d.value
        except Exception:
            pass

    @staticmethod
    def _coerce(v: Any) -> Optional[float]:
        if v is None:
            return None
        if hasattr(v, "flatten"):
            try:
                vl = list(v.flatten())
                if not vl:
                    return None
                v = vl[0]
            except Exception:
                return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _candidate_keys(self, cell_or_named: str) -> list[str]:
        """Return possible formulas-package keys for a `Sheet!Cell` or named range."""
        ref = cell_or_named.strip()
        # Named range → resolve to "'Sheet'!$X$Y"
        nm_lookup = ref.lower()
        if nm_lookup in self._named_to_cell:
            ref = self._named_to_cell[nm_lookup].lstrip("=")

        # formulas keys look like: '[file.xlsx]SHEET'!CELL
        # Strip the absolute-prefix dollar signs and uppercase the cell coord.
        ref = ref.replace("$", "").upper()
        sheet_part = None
        cell_part = ref
        if "!" in ref:
            sheet_part, cell_part = ref.split("!", 1)
            sheet_part = sheet_part.strip("'\"")

        prefix = f"'[{self.path.name.lower()}]"
        if sheet_part:
            return [
                f"{prefix}{sheet_part.upper()}'!{cell_part}",
                f"{prefix}{sheet_part}'!{cell_part}",
            ]
        # No sheet → search across all sheets
        return []

    def get(self, cell_or_named: str) -> Optional[float]:
        """Best-effort numeric read. Returns None if not found / not numeric."""
        self._ensure_loaded()
        for key in self._candidate_keys(cell_or_named):
            v = self._sol.get(key)
            if v is not None:
                num = self._coerce(v.value if hasattr(v, "value") else v)
                if num is not None:
                    return num
        # Fallback: case-insensitive scan (slower)
        nm_lookup = cell_or_named.strip().lower()
        if nm_lookup in self._named_to_cell:
            ref = self._named_to_cell[nm_lookup].lstrip("=").replace("$", "").upper()
            for k in self._sol.keys():
                if k.upper().endswith(ref):
                    num = self._coerce(self._sol[k].value)
                    if num is not None:
                        return num
        return None

    def has(self, cell_or_named: str) -> bool:
        return self.get(cell_or_named) is not None

    def all_keys(self) -> list[str]:
        self._ensure_loaded()
        return list(self._sol.keys()) if self._sol else []


class TrustRule(ABC):
    """Base class — subclasses implement check()."""

    name: str = "abstract_rule"
    description: str = ""
    template_types: tuple[str, ...] = ()  # empty = applies to all
    severity: Severity = "warn"

    def applies_to(self, template_type: str) -> bool:
        return not self.template_types or template_type in self.template_types

    @abstractmethod
    def check(self, probe: WorkbookProbe, spec: Any) -> Iterable[TrustViolation]:
        ...


class FunctionalRule(TrustRule):
    """Convenience: TrustRule built from a callable. Avoids subclass boilerplate."""

    def __init__(
        self,
        name: str,
        description: str,
        template_types: tuple[str, ...],
        severity: Severity,
        check_fn,
    ) -> None:
        self.name = name
        self.description = description
        self.template_types = template_types
        self.severity = severity
        self._check_fn = check_fn

    def check(self, probe: WorkbookProbe, spec: Any) -> Iterable[TrustViolation]:
        return self._check_fn(probe, spec, self)

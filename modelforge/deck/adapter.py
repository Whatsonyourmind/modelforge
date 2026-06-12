"""Certified workbook → deck Facts adapter (the deck pipeline's trust gate).

Turns a **built, certified** ModelForge workbook into the typed Facts models
the deck composers consume (``DealFacts`` for the IC memo, ``TeaserFacts``
for the teaser), with full lineage: every numeric fact carries the
``Sheet!Cell`` reference it was read from.

FAIL-CLOSED contract (in order):

1. The workbook's manifest sidecar (``<stem>.manifest.json``) must exist and
   ``verify_manifest`` must pass — a missing or stale manifest means the
   bytes on disk are not the bytes that were built, so no deck is produced.
2. The QC workbook audit (``modelforge.qc.workbook_audit``) must return
   verdict ``CERTIFIED`` (zero formula-error cells AND zero styling gaps).
   ``WARN``/``FAIL`` workbooks are refused.
3. Only templates with a verified field mapping are adapted. Anything else
   raises a friendly "not deck-mappable yet" error naming the supported set.

Numeric facts that live in formula cells are recomputed with the same
third-party ``formulas`` engine the certification audit uses — the adapter
never trusts a cached value it cannot recompute.

THREAT MODEL (v1): the manifest sidecar is *self-attested* SHA-256 —
``verify_manifest`` protects against drift and accidental edits (a workbook
whose bytes changed after build no longer matches its recorded hashes), NOT
against an adversary who can rewrite the sidecar alongside the workbook.
There is no signature or HMAC in v1; treat the manifest as an integrity
checksum, not an authenticity proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from openpyxl import load_workbook

__all__ = [
    "CellFact",
    "DeckAdapterError",
    "SUPPORTED_DECK_TEMPLATES",
    "WorkbookFacts",
    "adapt_workbook",
    "detect_template",
]


SUPPORTED_DECK_TEMPLATES: tuple[str, ...] = ("sponsor_lbo",)


class DeckAdapterError(Exception):
    """Friendly, fail-closed error raised anywhere along the deck chain."""


# ─────────────────────────────────────────────────────────────────────────────
# Data shapes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CellFact:
    """A numeric fact plus the workbook cell(s) it was read from."""

    value: Any
    ref: str  # "Sheet!D10" (or a composite like "SourcesUses!D75 × OperatingModel!K13")

    def __float__(self) -> float:  # convenience
        return float(self.value)


@dataclass
class WorkbookFacts:
    """Everything the deck pipeline needs, extracted from ONE certified workbook."""

    workbook: Path
    template: str
    manifest: Any  # analytics.manifest.BuildManifest
    audit_verdict: str
    audit_summary: dict[str, Any]
    red_flags: list[dict[str, str]] = field(default_factory=list)
    facts: dict[str, CellFact] = field(default_factory=dict)

    @property
    def source_refs(self) -> dict[str, str]:
        """fact name → sheet!cell lineage map (for stamping/footnotes)."""
        return {k: v.ref for k, v in self.facts.items()}

    # Composed lazily so the adapter has no import-time dependency on compose.
    def deal_facts(self):
        """Build the ``DealFacts`` model (IC-memo composer input)."""
        return _to_deal_facts(self)

    def teaser_facts(self):
        """Build the ``TeaserFacts`` model (teaser composer input)."""
        return _to_teaser_facts(self)


# ─────────────────────────────────────────────────────────────────────────────
# Formula-engine evaluation (cached per workbook content hash)
# ─────────────────────────────────────────────────────────────────────────────

_ENGINE_CACHE: dict[str, dict[tuple[str, str], Any]] = {}
_AUDIT_CACHE: dict[str, Any] = {}
_CACHE_MAX = 4


def _sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _scalarize(raw: Any) -> Any:
    """Collapse a `formulas` engine value (possibly a numpy array) to a scalar."""
    if raw is None:
        return None
    flatten = getattr(raw, "flatten", None)
    if flatten is not None:
        try:
            flat = raw.flatten()
            return _scalarize(flat[0]) if len(flat) else None
        except Exception:
            return None
    return raw


def _evaluate_workbook(xlsx_path: Path, wb_sha: str) -> dict[tuple[str, str], Any]:
    """Recompute every formula with the `formulas` engine.

    Returns {(SHEET_UPPER, CELL): value}. Cached on workbook content hash so
    repeated deck builds from the same bytes do not pay the engine twice.
    """
    cached = _ENGINE_CACHE.get(wb_sha)
    if cached is not None:
        return cached
    try:
        import formulas  # type: ignore
    except ImportError as e:  # pragma: no cover - dep ships with modelforge
        raise DeckAdapterError(
            "The deck adapter needs the `formulas` package to recompute "
            "workbook values (pip install formulas)."
        ) from e

    from modelforge.qc.workbook_audit import _split_engine_key

    try:
        xl = formulas.ExcelModel().loads(str(xlsx_path)).finish()
        sol = xl.calculate()
    except Exception as e:
        raise DeckAdapterError(
            f"Formula engine could not recompute {xlsx_path.name}: {e}"
        ) from e

    out: dict[tuple[str, str], Any] = {}
    for key, val in sol.items():
        sheet, cell = _split_engine_key(key)
        if sheet is None or cell is None:
            continue
        raw = val.value if hasattr(val, "value") else val
        out[(sheet.upper(), cell.upper())] = _scalarize(raw)

    if len(_ENGINE_CACHE) >= _CACHE_MAX:
        _ENGINE_CACHE.pop(next(iter(_ENGINE_CACHE)))
    _ENGINE_CACHE[wb_sha] = out
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Workbook reading helpers
# ─────────────────────────────────────────────────────────────────────────────


def _find_label_rows(ws, label: str, col: int = 1) -> list[int]:
    """All row numbers whose column-`col` text equals `label` (stripped)."""
    target = label.strip()
    rows: list[int] = []
    for row in ws.iter_rows(min_col=col, max_col=col):
        c = row[0]
        if isinstance(c.value, str) and c.value.strip() == target:
            rows.append(c.row)
    return rows


def _find_label_row(ws, label: str, col: int = 1) -> Optional[int]:
    rows = _find_label_rows(ws, label, col=col)
    return rows[0] if rows else None


class _Reader:
    """Bound reader over (workbook, engine solution) producing CellFacts."""

    def __init__(self, wb, solution: dict[tuple[str, str], Any]):
        self.wb = wb
        self.solution = solution

    def cell_fact(self, sheet: str, coord: str) -> CellFact:
        """Value of sheet!coord — raw input cells read directly, formula
        cells via the recompute engine (never the cached value)."""
        ws = self.wb[sheet]
        coord = coord.replace("$", "").upper()
        raw = ws[coord].value
        ref = f"{sheet}!{coord}"
        if isinstance(raw, str) and raw.startswith("="):
            val = self.solution.get((sheet.upper(), coord))
            if val is None:
                raise DeckAdapterError(
                    f"Could not recompute formula cell {ref} — the deck "
                    f"adapter refuses to guess. Re-run `modelforge certify` "
                    f"on the workbook."
                )
            return CellFact(value=val, ref=ref)
        return CellFact(value=raw, ref=ref)

    def labeled_fact(self, sheet: str, label: str, value_col: str = "D",
                     occurrence: int = 0) -> CellFact:
        ws = self.wb[sheet]
        rows = _find_label_rows(ws, label)
        if not rows or occurrence >= len(rows):
            raise DeckAdapterError(
                f"Could not locate the labeled row {label!r} on sheet "
                f"{sheet!r} — the workbook layout does not match the "
                f"{'sponsor_lbo'} template this adapter was verified against."
            )
        return self.cell_fact(sheet, f"{value_col}{rows[occurrence]}")

    def named_fact(self, name: str) -> CellFact:
        dn = self.wb.defined_names.get(name) if hasattr(self.wb.defined_names, "get") else None
        if dn is None and name in self.wb.defined_names:
            dn = self.wb.defined_names[name]
        if dn is None:
            raise DeckAdapterError(
                f"Named range {name!r} not found in the workbook."
            )
        m = re.match(r"'?([^'!]+)'?!\$?([A-Z]+)\$?(\d+)", dn.attr_text or "")
        if not m:
            raise DeckAdapterError(
                f"Named range {name!r} has an unsupported reference "
                f"({dn.attr_text!r})."
            )
        sheet, col, row = m.group(1), m.group(2), m.group(3)
        return self.cell_fact(sheet, f"{col}{row}")


# ─────────────────────────────────────────────────────────────────────────────
# Template detection
# ─────────────────────────────────────────────────────────────────────────────


def detect_template(wb) -> str:
    """Best-effort model_type detection for a built workbook.

    Primary source: the Trust Layer ``RedFlags`` sheet carries a literal
    ``Template: <model_type>`` line. Fallback: discriminating sheet names.
    """
    if "RedFlags" in wb.sheetnames:
        ws = wb["RedFlags"]
        for row in ws.iter_rows(min_row=1, max_row=6, min_col=1, max_col=1):
            v = row[0].value
            if isinstance(v, str) and v.strip().lower().startswith("template:"):
                return v.split(":", 1)[1].strip()
    sheets = set(wb.sheetnames)
    if "SourcesUses" in sheets:
        return "sponsor_lbo"
    if {"NOI", "EquityWaterfall"} & sheets or "REModel" in sheets:
        return "real_estate"
    if "CreditOpinion" in sheets:
        return "unitranche"
    if "DCFValuation" in sheets:
        return "dcf"
    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def adapt_workbook(
    xlsx_path: Path | str,
    manifest_path: Optional[Path | str] = None,
) -> WorkbookFacts:
    """Certified workbook (+ manifest sidecar) → :class:`WorkbookFacts`.

    Raises :class:`DeckAdapterError` (fail-closed) when the manifest is
    missing/stale, when the certification audit is not CERTIFIED, or when
    the template has no verified deck mapping.
    """
    xlsx = Path(xlsx_path)
    if not xlsx.exists():
        raise DeckAdapterError(f"Workbook not found: {xlsx}")

    # ── 1. Manifest sidecar must exist and verify ─────────────────────────
    from modelforge.analytics.manifest import read_manifest, verify_manifest

    mpath = Path(manifest_path) if manifest_path else xlsx.with_suffix(".manifest.json")
    if not mpath.exists():
        raise DeckAdapterError(
            f"Manifest sidecar not found: {mpath.name} (expected next to "
            f"{xlsx.name}). A certified deck can only be generated from a "
            f"workbook built by `modelforge build`, which writes the "
            f"manifest. Rebuild the workbook, or pass the manifest path "
            f"explicitly."
        )
    verdict = verify_manifest(xlsx, manifest_path=mpath)
    if not verdict.ok:
        issues = "; ".join(verdict.issues) or "hash mismatch"
        raise DeckAdapterError(
            f"Manifest verification FAILED for {xlsx.name}: {issues}. The "
            f"workbook bytes on disk are not the bytes that were built — "
            f"refusing to generate a deck from an unverified workbook."
        )
    manifest = read_manifest(mpath)

    wb_sha = verdict.workbook_actual or _sha256_file(xlsx)

    # ── 2. Certification audit must be CERTIFIED ──────────────────────────
    from modelforge.qc.workbook_audit import audit_workbook

    report = _AUDIT_CACHE.get(wb_sha)
    if report is None:
        report = audit_workbook(xlsx)
        if len(_AUDIT_CACHE) >= _CACHE_MAX:
            _AUDIT_CACHE.pop(next(iter(_AUDIT_CACHE)))
        _AUDIT_CACHE[wb_sha] = report
    if report.verdict != "CERTIFIED":
        first = ", ".join(e.ref for e in report.error_cells[:5])
        gaps = ", ".join(g.ref for g in report.style_gaps[:5])
        detail = (f"formula errors at {first}" if report.error_cells
                  else f"styling gaps at {gaps}")
        raise DeckAdapterError(
            f"Workbook {xlsx.name} audit verdict is {report.verdict}, not "
            f"CERTIFIED ({detail}). The deck pipeline is fail-closed: fix "
            f"the workbook (`modelforge certify {xlsx.name}`) before "
            f"exporting a deck."
        )

    # ── 3. Template must have a verified deck mapping ─────────────────────
    wb = load_workbook(xlsx, data_only=False, keep_links=True)
    template = detect_template(wb)
    if template not in SUPPORTED_DECK_TEMPLATES:
        raise DeckAdapterError(
            f"template {template!r} not deck-mappable yet; supported: "
            f"{list(SUPPORTED_DECK_TEMPLATES)}. Build the deck from a "
            f"supported template, or use `modelforge export` paths for "
            f"other templates."
        )

    # ── 4. Recompute + extract facts ──────────────────────────────────────
    solution = _evaluate_workbook(xlsx, wb_sha)
    reader = _Reader(wb, solution)

    facts = _extract_sponsor_lbo(reader)
    red_flags = _read_red_flags(wb)

    return WorkbookFacts(
        workbook=xlsx,
        template=template,
        manifest=manifest,
        audit_verdict=report.verdict,
        audit_summary=report.summary(),
        red_flags=red_flags,
        facts=facts,
    )


# ─────────────────────────────────────────────────────────────────────────────
# RedFlags sheet reader
# ─────────────────────────────────────────────────────────────────────────────


def _read_red_flags(wb) -> list[dict[str, str]]:
    """Parse Trust-Layer entries from the RedFlags sheet (header at row 7)."""
    if "RedFlags" not in wb.sheetnames:
        return []
    ws = wb["RedFlags"]
    flags: list[dict[str, str]] = []
    for r in range(8, ws.max_row + 1):
        severity = ws.cell(row=r, column=2).value
        rule = ws.cell(row=r, column=3).value
        if severity is None and rule is None:
            continue
        if str(severity).strip().upper() == "ALL CLEAR":
            return []
        flags.append({
            "severity": str(severity or "").strip(),
            "rule": str(rule or "").strip(),
            "cell": str(ws.cell(row=r, column=4).value or "").strip(),
            "message": str(ws.cell(row=r, column=7).value or "").strip(),
        })
    return flags


# ─────────────────────────────────────────────────────────────────────────────
# sponsor_lbo extraction
# ─────────────────────────────────────────────────────────────────────────────

_SU = "SourcesUses"

# Exact col-A labels emitted by builder/sheets/sources_uses.py (v0.8+).
_LBL_SENIOR = "Senior debt (Term Loan B / unitranche)"
_LBL_MEZZ = "Mezzanine / subordinated debt"
_LBL_RCF = "Revolver facility (drawn at close)"
_LBL_SPONSOR_EQ = "Sponsor equity (new money)"
_LBL_ROLLOVER = "Management rollover equity"
_LBL_TOTAL_SOURCES = "Total sources"
_LBL_TOTAL_USES = "Total uses"
_LBL_MA_FEES = "M&A advisory fees (expensed)"
_LBL_FIN_FEES = "Financing fees (capitalized + amortized)"
_LBL_REFI = "Refinance target net debt"
_LBL_MIN_CASH = "Minimum cash to balance sheet"
_LBL_EQ_PP = "Equity purchase price"
_LBL_EXIT_STRATEGIC = "Exit — strategic sale (EV/EBITDA ×)"
_LBL_IRR = "IRR (on cash-flow series)"
_LBL_MOIC = "MoIC (cash-on-cash)"
_LBL_BREACHES = "Total breaches (projection window)"

_HURDLE_RE = re.compile(
    r"=\(D\d+\*(?P<ebitda>'?[A-Za-z0-9_ ]+'?![A-Z]+\d+)"
    r"-(?P<debt>'?[A-Za-z0-9_ ]+'?![A-Z]+\d+|0)\)"
)


def _ref_fact(reader: _Reader, ref: str) -> CellFact:
    """CellFact from a cross-sheet ref string like ``'DebtSchedule'!K60``."""
    m = re.match(r"'?([^'!]+)'?!([A-Z]+\d+)", ref)
    if not m:
        raise DeckAdapterError(f"Unparseable cell reference {ref!r}.")
    return reader.cell_fact(m.group(1), m.group(2))


def _cover_value(reader: _Reader, label: str) -> CellFact:
    return reader.labeled_fact("Cover", label, value_col="C")


def _extract_sponsor_lbo(reader: _Reader) -> dict[str, CellFact]:
    wb = reader.wb
    for required in (_SU, "Cover", "OperatingModel", "Covenants"):
        if required not in wb.sheetnames:
            raise DeckAdapterError(
                f"Sheet {required!r} missing — this workbook does not match "
                f"the sponsor_lbo layout the deck adapter was verified "
                f"against."
            )

    f: dict[str, CellFact] = {}

    # Cover identity block (labels in col A, values in col C)
    f["deal_name"] = _cover_value(reader, "Target")
    f["sector"] = _cover_value(reader, "Sector")
    f["country"] = _cover_value(reader, "Country")
    f["currency"] = _cover_value(reader, "Currency")
    f["project_code"] = _cover_value(reader, "Project code")
    f["analyst"] = _cover_value(reader, "Analyst")
    f["valuation_date"] = _cover_value(reader, "Valuation date")

    # Sources & Uses
    f["senior_debt"] = reader.labeled_fact(_SU, _LBL_SENIOR)
    f["mezz_debt"] = reader.labeled_fact(_SU, _LBL_MEZZ)
    f["rcf_drawn"] = reader.labeled_fact(_SU, _LBL_RCF)
    f["sponsor_equity"] = reader.labeled_fact(_SU, _LBL_SPONSOR_EQ)  # S&U plug
    f["mgmt_rollover"] = reader.labeled_fact(_SU, _LBL_ROLLOVER)
    f["total_sources"] = reader.labeled_fact(_SU, _LBL_TOTAL_SOURCES)
    f["total_uses"] = reader.labeled_fact(_SU, _LBL_TOTAL_USES)
    f["ma_fees"] = reader.labeled_fact(_SU, _LBL_MA_FEES)
    f["financing_fees"] = reader.labeled_fact(_SU, _LBL_FIN_FEES)
    f["refi_net_debt"] = reader.labeled_fact(_SU, _LBL_REFI)
    f["min_cash"] = reader.labeled_fact(_SU, _LBL_MIN_CASH)
    f["equity_purchase_price"] = reader.labeled_fact(_SU, _LBL_EQ_PP)

    # Entry EV — prefer the registered named range
    f["entry_ev"] = reader.named_fact("purchase_price_eur_m")
    f["exit_year"] = reader.named_fact("exit_year_input")
    f["exit_multiple_strategic"] = reader.labeled_fact(_SU, _LBL_EXIT_STRATEGIC)

    # Returns block: IRR/MoIC rows appear in scenario order
    # strategic / IPO / secondary — take occurrence 0 (strategic).
    f["irr_strategic"] = reader.labeled_fact(_SU, _LBL_IRR, occurrence=0)
    f["moic_strategic"] = reader.labeled_fact(_SU, _LBL_MOIC, occurrence=0)
    f["irr_ipo"] = reader.labeled_fact(_SU, _LBL_IRR, occurrence=1)
    f["irr_secondary"] = reader.labeled_fact(_SU, _LBL_IRR, occurrence=2)

    # Exit-year EBITDA + debt outstanding at exit: the hurdle reverse-solve
    # formula embeds the canonical cross-sheet refs — parse them rather than
    # hard-coding column math.
    su = wb[_SU]
    hurdle_row = None
    for row in su.iter_rows(min_col=1, max_col=1):
        v = row[0].value
        if isinstance(v, str) and v.startswith("Hurdle IRR"):
            hurdle_row = row[0].row
            break
    if hurdle_row is None:
        raise DeckAdapterError(
            "Hurdle-analysis block not found on SourcesUses — cannot locate "
            "the exit-year EBITDA/debt references."
        )
    hurdle_formula = str(su.cell(row=hurdle_row, column=4).value or "")
    m = _HURDLE_RE.match(hurdle_formula)
    if not m:
        raise DeckAdapterError(
            f"Could not parse the hurdle formula {hurdle_formula!r} for "
            f"exit EBITDA/debt references."
        )
    exit_ebitda = _ref_fact(reader, m.group("ebitda"))
    f["exit_ebitda"] = exit_ebitda
    if m.group("debt") == "0":
        f["exit_net_debt"] = CellFact(value=0.0, ref=f"{_SU}!D{hurdle_row} (no debt ref)")
    else:
        f["exit_net_debt"] = _ref_fact(reader, m.group("debt"))

    exit_mult = float(f["exit_multiple_strategic"].value)
    exit_ev_val = exit_mult * float(exit_ebitda.value)
    f["exit_ev"] = CellFact(
        value=exit_ev_val,
        ref=f"{f['exit_multiple_strategic'].ref} × {exit_ebitda.ref}",
    )
    f["exit_equity"] = CellFact(
        value=exit_ev_val - float(f["exit_net_debt"].value),
        ref=f"{f['exit_ev'].ref} − {f['exit_net_debt'].ref}",
    )

    # Last-actual revenue / EBITDA from OperatingModel (header row 5 carries
    # "A YYYY"/"E YYYY"; last "A" column = last historical FY).
    om = wb["OperatingModel"]
    last_actual_col = None
    for c in om[5]:
        if isinstance(c.value, str) and c.value.strip().startswith("A "):
            last_actual_col = c.column_letter
    if last_actual_col is not None:
        rev_row = _find_label_row(om, "Revenue")
        ebitda_row = _find_label_row(om, "EBITDA")
        if rev_row:
            f["revenue_last_fy"] = reader.cell_fact(
                "OperatingModel", f"{last_actual_col}{rev_row}")
        if ebitda_row:
            f["ebitda_last_fy"] = reader.cell_fact(
                "OperatingModel", f"{last_actual_col}{ebitda_row}")

    # Covenant summary: every "<name> — threshold" row; first projection-year
    # threshold + same-column actual from the row above.
    cov = wb["Covenants"]
    first_proj_col = None
    for c in cov[5]:
        if isinstance(c.value, str) and c.value.strip().startswith("E "):
            first_proj_col = c.column_letter
            break
    covenant_idx = 0
    if first_proj_col is not None:
        for row in cov.iter_rows(min_col=1, max_col=1):
            v = row[0].value
            if not (isinstance(v, str) and v.strip().endswith("— threshold")):
                continue
            name = v.strip()[: -len("— threshold")].strip(" —")
            r = row[0].row
            try:
                thr = reader.cell_fact("Covenants", f"{first_proj_col}{r}")
                act = reader.cell_fact("Covenants", f"{first_proj_col}{r - 1}")
            except DeckAdapterError:
                continue
            if thr.value is None or act.value is None:
                continue
            f[f"covenant_{covenant_idx}_name"] = CellFact(name, f"Covenants!A{r}")
            f[f"covenant_{covenant_idx}_threshold"] = thr
            f[f"covenant_{covenant_idx}_actual"] = act
            covenant_idx += 1
    breach_row = _find_label_row(cov, _LBL_BREACHES)
    if breach_row:
        f["covenant_breaches"] = reader.cell_fact("Covenants", f"C{breach_row}")

    return f


# ─────────────────────────────────────────────────────────────────────────────
# Facts → composer models
# ─────────────────────────────────────────────────────────────────────────────


def _fnum(facts: dict[str, CellFact], key: str, default: float = 0.0) -> float:
    cf = facts.get(key)
    if cf is None or cf.value is None:
        return default
    try:
        return float(cf.value)
    except (TypeError, ValueError):
        return default


def _fstr(facts: dict[str, CellFact], key: str, default: str = "") -> str:
    cf = facts.get(key)
    return str(cf.value) if cf is not None and cf.value is not None else default


def _fdate(facts: dict[str, CellFact], key: str) -> date:
    cf = facts.get(key)
    raw = cf.value if cf is not None else None
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
    return date(2026, 1, 1)


def _covenant_lines(facts: dict[str, CellFact]) -> list[str]:
    lines: list[str] = []
    i = 0
    while f"covenant_{i}_name" in facts:
        name = _fstr(facts, f"covenant_{i}_name")
        thr = _fnum(facts, f"covenant_{i}_threshold")
        act = _fnum(facts, f"covenant_{i}_actual")
        lines.append(
            f"Covenant {name}: threshold {thr:.2f}x vs first-year "
            f"{act:.2f}x ({facts[f'covenant_{i}_actual'].ref})"
        )
        i += 1
    return lines


def _to_deal_facts(wf: WorkbookFacts):
    """sponsor_lbo facts → ``DealFacts`` (IC-memo composer input)."""
    from modelforge.deck.compose.ic_memo import DealFacts

    f = wf.facts
    currency = _fstr(f, "currency", "EUR")
    equity = _fnum(f, "sponsor_equity")
    senior = _fnum(f, "senior_debt")
    mezz = _fnum(f, "mezz_debt")
    rcf = _fnum(f, "rcf_drawn")
    rollover = _fnum(f, "mgmt_rollover")
    debt_total = senior + mezz + rcf
    entry_ev = _fnum(f, "entry_ev")
    exit_ev = _fnum(f, "exit_ev")
    exit_net_debt = _fnum(f, "exit_net_debt")
    exit_equity = _fnum(f, "exit_equity")
    irr = _fnum(f, "irr_strategic")
    moic = _fnum(f, "moic_strategic")
    ebitda = _fnum(f, "ebitda_last_fy")

    thesis = [
        f"Entry EV {entry_ev:,.1f}m ({currency}) — certified purchase-price "
        f"build ({f['entry_ev'].ref})",
        f"Strategic-exit IRR {irr:.1%} / MoIC {moic:.2f}x on the live "
        f"sponsor cash-flow series ({f['irr_strategic'].ref})",
    ]
    if ebitda:
        thesis.append(
            f"Debt at close {debt_total:,.1f}m = "
            f"{debt_total / ebitda:.1f}x LTM EBITDA {ebitda:,.1f}m "
            f"({f['senior_debt'].ref})"
        )
    thesis.extend(_covenant_lines(f)[:2])

    stack_pairs = [
        ("Senior", senior), ("Mezzanine", mezz), ("Revolver (drawn)", rcf),
        ("Rollover equity", rollover), ("Sponsor equity", equity),
    ]
    stack_pairs = [(n, v) for n, v in stack_pairs if abs(v) > 1e-9]

    if wf.red_flags:
        risks = [
            f"[{rf['severity']}] {rf['rule']}: {rf['message']}"
            for rf in wf.red_flags[:5]
        ]
    else:
        risks = ["No Trust-Layer red flags raised at build time (ALL CLEAR)."]
    breaches = int(_fnum(f, "covenant_breaches"))
    if breaches:
        risks.append(
            f"{breaches} covenant breach period(s) flagged in the projection "
            f"window ({f['covenant_breaches'].ref})."
        )
    mitigants = [
        f"Workbook certified: zero formula errors (verdict "
        f"{wf.audit_verdict}).",
        f"Bytes verified against build manifest "
        f"(sha256 {wf.manifest.workbook_sha256[:12]}…).",
    ]

    return DealFacts(
        deal_name=_fstr(f, "deal_name", "Certified Deal"),
        sector=_fstr(f, "sector", "Private Markets"),
        vertical="pe",
        country=_fstr(f, "country", "IT"),
        deal_date=_fdate(f, "valuation_date"),
        author=_fstr(f, "analyst", "Deal Team"),
        company=_fstr(f, "project_code", "ModelForge"),
        confidentiality="confidential",
        total_size_eur_m=_fnum(f, "total_uses"),
        equity_required_eur_m=equity,
        debt_eur_m=debt_total,
        hold_period_years=max(1, int(_fnum(f, "exit_year", 5))),
        investment_thesis_bullets=thesis,
        target_irr_pct=irr,
        target_moic=moic,
        waterfall_categories=[
            "Sponsor Equity (Y0)", "Exit EV (strategic)",
            "Net Debt at Exit", "Net Equity to Sponsor",
        ],
        waterfall_values=[-equity, exit_ev, -exit_net_debt, exit_equity],
        capital_stack_tranches=[n for n, _ in stack_pairs],
        capital_stack_values=[v for _, v in stack_pairs],
        risks=risks,
        mitigants=mitigants,
        recommendation="approve",
        recommendation_rationale=(
            f"All figures extracted from the certified workbook "
            f"{wf.workbook.name} (audit verdict {wf.audit_verdict}, "
            f"0 formula errors); returns from the live IRR/MoIC block on "
            f"SourcesUses. Workbook currency: {currency} millions."
        ),
        ask_eur_m=equity,
        sector_metrics={
            "entry_ev": entry_ev,
            "exit_ev": exit_ev,
            "exit_year": int(_fnum(f, "exit_year", 5)),
            "currency": currency,
            "covenants": _covenant_lines(f),
        },
    )


def _to_teaser_facts(wf: WorkbookFacts):
    """sponsor_lbo facts → ``TeaserFacts`` (teaser composer input)."""
    from modelforge.deck.compose.teaser import TeaserFacts

    f = wf.facts
    revenue = _fnum(f, "revenue_last_fy") or None
    ebitda = _fnum(f, "ebitda_last_fy") or None
    margin = (ebitda / revenue) if (revenue and ebitda) else None
    irr = _fnum(f, "irr_strategic")
    moic = _fnum(f, "moic_strategic")
    currency = _fstr(f, "currency", "EUR")

    return TeaserFacts(
        project_codename=_fstr(f, "project_code", "Project Forge"),
        company_real_name=_fstr(f, "deal_name") or None,
        anonymized=True,
        sector=_fstr(f, "sector", "Private Markets"),
        vertical="pe",
        country=_fstr(f, "country", "IT"),
        deal_date=_fdate(f, "valuation_date"),
        author=_fstr(f, "analyst", "Advisor"),
        company=_fstr(f, "project_code", "ModelForge"),
        confidentiality="confidential",
        one_line_thesis=(
            f"Certified LBO model: {irr:.0%} strategic-exit IRR / "
            f"{moic:.1f}x MoIC ({currency} millions)."
        ),
        revenue_eur_m=revenue,
        ebitda_eur_m=ebitda,
        ebitda_margin_pct=margin,
        ask_eur_m=_fnum(f, "sponsor_equity") or None,
        enterprise_value_eur_m=_fnum(f, "entry_ev") or None,
        investment_highlights=[
            f"Strategic-exit IRR {irr:.1%} / MoIC {moic:.2f}x "
            f"({f['irr_strategic'].ref})",
            f"Entry EV {_fnum(f, 'entry_ev'):,.1f}m "
            f"({f['entry_ev'].ref})",
            "Every figure recomputed and certified — zero formula errors "
            "(ModelForge Trust Layer).",
        ],
        contact_name=_fstr(f, "analyst", "Deal Team"),
        contact_role="Deal Team",
    )

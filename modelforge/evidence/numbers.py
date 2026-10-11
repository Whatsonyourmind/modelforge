"""Find numeric mentions in text and normalise them to a field's declared unit.

Deterministic and dependency-free. A *mention* is a number as written, plus
whatever the text says about it: currency, scale word ("million", "M", "bn"),
and unit ("%", "percent", "bps", "x", "years"). Normalisation answers one
question: "expressed in this field's unit, what value does this mention state?"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Relative tolerance for "the same number". 0.5% absorbs presentation rounding
# (32.085 shown as 32.1) without letting a different figure through.
REL_TOL = 0.005

_CURRENCY = r"(?:EUR|USD|GBP|CHF|€|\$|£)"
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_SCALE = (r"billion|bn|million|mln|mn|thousand|k|m|b")
_UNIT = (r"%|percent|per\s+cent|bps|bp|basis\s+points|x\b|×|years?|yrs?")

_MENTION_RE = re.compile(
    rf"(?P<cur>{_CURRENCY})?\s?"
    rf"(?P<num>{_NUM})"
    rf"(?:\s?(?P<scale>{_SCALE})\b)?"
    rf"(?:\s?(?P<unit>{_UNIT}))?",
    re.IGNORECASE,
)
# "150-200 bps", "20 to 25 percent", "1,500-1,650 kWh"
_RANGE_RE = re.compile(
    rf"(?P<lo>{_NUM})\s?(?:-|–|—|to)\s?(?P<cur>{_CURRENCY})?\s?(?P<hi>{_NUM})"
    rf"(?:\s?(?P<scale>{_SCALE})\b)?(?:\s?(?P<unit>{_UNIT}))?",
    re.IGNORECASE,
)

_SCALE_MULT = {
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mln": 1e6, "mn": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}

CURRENCY_UNITS = {"eur_m": 1e6, "eur_k": 1e3, "eur": 1.0}

# Physical / count units that make a bare number *not* a money amount or a
# plain ratio ("276 MW", "428 GWh", "8 plants").
_OTHER_UNIT_RE = re.compile(
    r"\s?(mwdc|mwac|mwp|mwh|mw|gwh|gw|kwh|kwp|kw|twh|sqm|m2|ha|km|tonnes|plants?|units?|loans?|"
    r"months?|days?|employees|mwh/yr)\b",
    re.IGNORECASE,
)


def normalize_text(s: str) -> str:
    """NFKC, unify quotes/dashes/spaces, collapse whitespace, lowercase."""
    s = unicodedata.normalize("NFKC", s)
    s = (s.replace("’", "'").replace("‘", "'")
          .replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-")
          .replace(" ", " ").replace("&amp;", "&"))
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass(frozen=True)
class Mention:
    raw: str
    value: float          # the number as written, separators removed
    currency: bool
    scale: float          # 1.0 when no scale word
    unit: str             # currency | pct | bps | x | years | plain
    start: int
    end: int
    decimals: int


def _unit_of(unit_tok: str | None, has_currency: bool, has_scale: bool) -> str:
    u = (unit_tok or "").lower().strip()
    if u in ("%", "percent") or u.startswith("per"):
        return "pct"
    if u in ("bps", "bp") or u.startswith("basis"):
        return "bps"
    if u in ("x", "×"):
        return "x"
    if u.startswith("year") or u.startswith("yr"):
        return "years"
    if has_currency:
        return "currency"
    return "plain"


def find_mentions(text: str) -> list[Mention]:
    """Every numeric mention in `text`, left to right."""
    out: list[Mention] = []
    for m in _MENTION_RE.finditer(text):
        num = m.group("num")
        # Skip digits that are part of a word/identifier (e.g. "S-001", "A1", "FY25").
        if m.start("num") > 0 and (text[m.start("num") - 1].isalpha() or text[m.start("num") - 1] == "-"):
            if not m.group("cur"):
                continue
        val = float(num.replace(",", ""))
        scale_tok = (m.group("scale") or "").lower()
        # A bare "m"/"b"/"k" only counts as a scale word right after a currency
        # amount ("€316M"); otherwise "276 MW" would read as 276 million.
        if scale_tok in ("m", "b", "k") and not m.group("cur"):
            scale_tok = ""
        scale = _SCALE_MULT.get(scale_tok, 1.0)
        unit = _unit_of(m.group("unit"), bool(m.group("cur")), bool(scale_tok))
        if unit == "plain" and scale_tok:
            unit = "currency" if m.group("cur") else "plain"
        if unit == "plain" and not scale_tok and _OTHER_UNIT_RE.match(text, m.end()):
            unit = "other"
        decimals = len(num.split(".")[1]) if "." in num else 0
        out.append(Mention(m.group(0).strip(), val, bool(m.group("cur")), scale,
                           unit, m.start(), m.end(), decimals))
    return out


def find_ranges(text: str) -> list[tuple[float, float, str, float]]:
    """Numeric ranges as (lo, hi, unit, scale)."""
    out = []
    for m in _RANGE_RE.finditer(text):
        lo = float(m.group("lo").replace(",", ""))
        hi = float(m.group("hi").replace(",", ""))
        scale_tok = (m.group("scale") or "").lower()
        if scale_tok in ("m", "b", "k") and not m.group("cur"):
            scale_tok = ""
        unit = _unit_of(m.group("unit"), bool(m.group("cur")), bool(scale_tok))
        if lo <= hi:
            out.append((lo, hi, unit, _SCALE_MULT.get(scale_tok, 1.0)))
    return out


def close(a: float, b: float, rel: float = REL_TOL) -> bool:
    if a == b:
        return True
    return abs(a - b) <= rel * max(abs(a), abs(b))


def to_field_unit(m: Mention, field_unit: str) -> float | None:
    """The value this mention states, expressed in `field_unit`; None if the
    mention's unit cannot express that kind of quantity."""
    if field_unit in CURRENCY_UNITS:
        if m.unit in ("currency",) or (m.unit == "plain" and m.scale != 1.0):
            return m.value * m.scale / CURRENCY_UNITS[field_unit]
        if m.unit == "plain":
            return m.value  # a bare number in a quote is read in the field's unit
        return None
    if field_unit == "pct":
        if m.unit == "pct":
            return m.value / 100.0
        if m.unit == "bps":
            return m.value / 10000.0
        if m.unit == "plain":
            return m.value if m.value < 1 else None
        return None
    if field_unit == "bps":
        if m.unit == "bps":
            return m.value
        if m.unit == "pct":
            return m.value * 100.0
        if m.unit == "plain":
            return m.value
        return None
    if field_unit == "x":
        return m.value if m.unit in ("x", "plain") else None
    if field_unit == "years":
        return m.value if m.unit in ("years", "plain") else None
    if field_unit == "count":
        return m.value if m.unit in ("plain", "other") else None
    # ratio
    return m.value if m.unit == "plain" else None


def alternative_readings(m: Mention, field_unit: str) -> list[tuple[float, str]]:
    """Readings of the same digits under a *wrong* unit or scale, used to tell
    "the number is there but at a different scale/unit" from "not there"."""
    alts: list[tuple[float, str]] = []
    if field_unit in CURRENCY_UNITS:
        absolute = m.value * m.scale
        for unit, div in CURRENCY_UNITS.items():
            if unit != field_unit:
                alts.append((absolute / div, f"reads as {absolute / div:g} {unit}"))
        if m.scale != 1.0:
            alts.append((m.value, f"'{m.raw}' is {absolute:,.0f}, not {m.value:g} {field_unit}"))
        if m.unit in ("pct", "bps", "x"):
            alts.append((m.value, f"'{m.raw}' is a {m.unit} figure, not a currency amount"))
    elif field_unit == "pct":
        if m.unit == "pct":
            alts.append((m.value, f"'{m.raw}' is {m.value / 100:g} as a fraction"))
        if m.unit == "bps":
            alts.append((m.value / 100.0, f"'{m.raw}' is basis points, i.e. {m.value / 10000:g}"))
        if m.unit in ("currency", "x"):
            alts.append((m.value, f"'{m.raw}' is not a percentage"))
    elif field_unit == "bps":
        if m.unit == "pct":
            alts.append((m.value, f"'{m.raw}' is {m.value * 100:g} bps, not {m.value:g}"))
    elif field_unit == "x" and m.unit in ("pct", "currency", "bps"):
        alts.append((m.value, f"'{m.raw}' is not a multiple"))
    return alts

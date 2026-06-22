"""Inverse of the deck composers' numeric format strings.

The certified-deck composers render numbers with a small, fixed family of
format strings — ``f"€{x:,.1f}M"``, ``f"{x*100:.1f}%"``, ``f"{x:.2f}x"``,
``f"{x:,.0f}k"``, the bare ``f"{x:,.1f}"`` in tables, and the
:class:`~modelforge.deck.finance.formatter.FinancialFormatter` outputs
(``$12.5M``, ``15.0%``, ``2.5x``, ``250bps``). This module parses those
rendered tokens back into a numeric value *plus* the display semantics needed
to ground them: the magnitude scale (millions / thousands / billions), the
quantity kind (currency / percent / multiple / plain), and the number of
displayed decimals (so the grounding gate can size a display-ulp tolerance).

It is deliberately conservative: it extracts only tokens that match the
composer format family, and it does NOT treat bare four-digit years, ISO
dates, or digits embedded in alphanumeric identifiers (project codes) as
financial numbers — those are the dominant false-positive sources when
scanning free-form slide text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["NumericToken", "extract_numeric_tokens"]


# Magnitude suffix → multiplier into the canonical "millions" space the deck
# works in (every eur_m fact and every currency token reduces to millions).
_SCALE_TO_MILLIONS: dict[str, float] = {
    "m": 1.0,
    "b": 1000.0,
    "bn": 1000.0,
    "k": 0.001,
}


@dataclass(frozen=True)
class NumericToken:
    """A numeric token parsed from rendered slide text.

    Attributes
    ----------
    raw:
        The exact substring matched (e.g. ``"€1,234.5M"``).
    value:
        The displayed numeric value with sign, as written, BEFORE any
        scale/percent normalization (``1234.5`` for ``"€1,234.5M"``;
        ``18.0`` for ``"18.0%"``).
    kind:
        One of ``"currency"``, ``"percent"``, ``"multiple"``, ``"bps"``,
        ``"plain"``.
    decimals:
        Count of fractional digits shown (``1`` for ``"1,234.5"``), used to
        size a display-rounding tolerance.
    scale:
        Magnitude suffix lowercased (``"m"``/``"k"``/``"b"``/``"bn"``) or
        ``""`` when none was shown.
    """

    raw: str
    value: float
    kind: str
    decimals: int
    scale: str

    def value_in_millions(self) -> float:
        """Currency/plain value reduced to the canonical millions space."""
        return self.value * _SCALE_TO_MILLIONS.get(self.scale, 1.0)

    def fraction(self) -> float:
        """Percent value as a fraction (``0.18`` for ``"18.0%"``)."""
        return self.value / 100.0

    def display_ulp(self) -> float:
        """Half the last displayed decimal place, in the token's OWN units.

        ``"250.0"`` → 0.05; ``"18.00%"`` → 0.005 (percentage points);
        ``"2.69x"`` → 0.005. Grounding converts this into the comparison
        space alongside :meth:`value`.
        """
        return 0.5 * (10.0 ** (-self.decimals))


# A signed decimal number with optional thousands separators: 1,234.5 / 18 / -3.0
_NUM = r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+-]?\d+(?:\.\d+)?"

# currency: optional symbol, number, mandatory magnitude suffix (M/B/bn/k).
# Also matches the lp_quarterly "12.3 €M" / "12.3 $M" trailing-symbol form.
_CURRENCY_RE = re.compile(
    rf"(?P<sym>[€$£])?\s?(?P<num>{_NUM})\s?(?:(?P<sym2>[€$£])\s?)?(?P<scale>bn|[MmBbKk])\b"
)
# percent: number immediately followed by %
_PERCENT_RE = re.compile(rf"(?P<num>{_NUM})\s?%")
# bps: number followed by 'bps'
_BPS_RE = re.compile(rf"(?P<num>{_NUM})\s?bps\b")
# multiple: number followed by lowercase x at a word boundary (2.69x, 3.5x)
_MULTIPLE_RE = re.compile(rf"(?P<num>{_NUM})x\b")


def _decimals(num_text: str) -> int:
    return len(num_text.split(".", 1)[1]) if "." in num_text else 0


def _to_float(num_text: str) -> float:
    return float(num_text.replace(",", ""))


def _is_year_or_id(text: str, start: int, end: int) -> bool:
    """True when the bare number at [start,end) is a 4-digit year or a digit
    run welded into an alphanumeric identifier (project code, e.g. ``P-2026-014``).

    Years (1900–2099) and identifier-embedded digits are NOT financial tokens.
    """
    tok = text[start:end]
    if tok.isdigit() and len(tok) == 4 and 1900 <= int(tok) <= 2099:
        return True
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    # Welded to a letter, or to a '-'/'/' that itself sits next to alnum → id-like.
    if before.isalpha() or after.isalpha():
        return True
    if before in "-/" and start >= 2 and text[start - 2].isalnum():
        return True
    if after in "-/" and end + 1 < len(text) and text[end + 1].isalnum():
        return True
    return False


def extract_numeric_tokens(text: str) -> list[NumericToken]:
    """Parse every composer-family numeric token out of one slide string.

    Overlapping spans are resolved by priority (currency/percent/bps/multiple
    consume their suffix first); the remaining bare numbers are emitted as
    ``"plain"`` unless they are years or identifier digits.
    """
    if not text:
        return []

    tokens: list[NumericToken] = []
    claimed: list[tuple[int, int]] = []

    def _overlaps(s: int, e: int) -> bool:
        return any(s < ce and cs < e for cs, ce in claimed)

    for rx, kind in (
        (_CURRENCY_RE, "currency"),
        (_PERCENT_RE, "percent"),
        (_BPS_RE, "bps"),
        (_MULTIPLE_RE, "multiple"),
    ):
        for m in rx.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps(s, e):
                continue
            num = m.group("num")
            scale = ""
            if kind == "currency":
                scale = (m.group("scale") or "").lower()
            tokens.append(
                NumericToken(
                    raw=m.group(0).strip(),
                    value=_to_float(num),
                    kind=kind,
                    decimals=_decimals(num),
                    scale=scale,
                )
            )
            claimed.append((s, e))

    # Bare plain numbers in whatever is left (table cells, chart labels).
    for m in re.finditer(_NUM, text):
        s, e = m.start(), m.end()
        if _overlaps(s, e):
            continue
        num = m.group(0)
        # A leading +/- welded to a preceding alphanumeric is a date/range
        # separator ("2026-04-15", "FY-15"), not a sign — drop the spurious
        # negative rather than treat it as a financial figure.
        if num[0] in "+-" and s > 0 and text[s - 1].isalnum():
            continue
        if _is_year_or_id(text, s, e):
            continue
        tokens.append(
            NumericToken(
                raw=num,
                value=_to_float(num),
                kind="plain",
                decimals=_decimals(num),
                scale="",
            )
        )
        claimed.append((s, e))

    return tokens

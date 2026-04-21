"""Currency converters + formatters used across ModelForge + consumers.

Consistent EUR_M / EUR_K / EUR ↔ ``Decimal`` converters and display
formatters (for compliance sheets, cover pages, IC memo decks, etc.).
Supports EUR by default but is parameterised so GBP / USD / CHF can be
added without forking the module.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Union

Number = Union[float, int, Decimal, str]


MILLION = Decimal("1000000")
THOUSAND = Decimal("1000")


def _as_decimal(value: Number) -> Decimal:
    """Coerce to Decimal without losing precision on str inputs."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:  # noqa: PERF203
        raise ValueError(f"Cannot coerce {value!r} to Decimal") from exc


# ── Unit converters ────────────────────────────────────────────────────


def eur_m_to_eur(amount_eur_m: Number) -> Decimal:
    """€1.25M → €1,250,000."""
    return _as_decimal(amount_eur_m) * MILLION


def eur_k_to_eur(amount_eur_k: Number) -> Decimal:
    """€250k → €250,000."""
    return _as_decimal(amount_eur_k) * THOUSAND


def eur_to_eur_m(amount_eur: Number) -> Decimal:
    """€1,250,000 → 1.25 (M). Result is dimensionless 'millions'."""
    return _as_decimal(amount_eur) / MILLION


def eur_to_eur_k(amount_eur: Number) -> Decimal:
    """€250,000 → 250 (k)."""
    return _as_decimal(amount_eur) / THOUSAND


# ── Formatters ─────────────────────────────────────────────────────────


def format_eur_m(
    amount_eur_m: Number,
    *,
    decimals: int = 1,
    currency: str = "€",
) -> str:
    """€1.25M → ``"€1.3M"`` (1 decimal by default)."""
    value = _as_decimal(amount_eur_m)
    return f"{currency}{value:,.{decimals}f}M"


def format_eur_k(
    amount_eur_k: Number, *, decimals: int = 0, currency: str = "€"
) -> str:
    value = _as_decimal(amount_eur_k)
    return f"{currency}{value:,.{decimals}f}k"


def format_eur(
    amount_eur: Number, *, decimals: int = 2, currency: str = "€"
) -> str:
    value = _as_decimal(amount_eur)
    return f"{currency}{value:,.{decimals}f}"


def format_smart(amount_eur: Number, *, currency: str = "€") -> str:
    """Pick the best unit automatically.

    >= €1M → format_eur_m (1 dp)
    >= €1k → format_eur_k (0 dp)
    otherwise  → format_eur (0 dp)
    """
    value = _as_decimal(amount_eur)
    abs_value = abs(value)
    if abs_value >= MILLION:
        return format_eur_m(eur_to_eur_m(value), decimals=1, currency=currency)
    if abs_value >= THOUSAND:
        return format_eur_k(eur_to_eur_k(value), decimals=0, currency=currency)
    return format_eur(value, decimals=0, currency=currency)


def format_pct(value: Number, *, decimals: int = 1) -> str:
    """0.175 → ``"17.5%"``."""
    v = _as_decimal(value)
    return f"{v * Decimal('100'):.{decimals}f}%"


def format_bps(value: Number, *, decimals: int = 0) -> str:
    """0.025 → ``"250 bps"``."""
    v = _as_decimal(value)
    return f"{v * Decimal('10000'):,.{decimals}f} bps"


def format_multiple(value: Number, *, decimals: int = 1) -> str:
    """2.35 → ``"2.4x"``."""
    v = _as_decimal(value)
    return f"{v:.{decimals}f}x"

"""Unified provider interface for market data adapters.

The pattern lets ModelForge — and the MCP layer — call the same method
on Bloomberg, Refinitiv, FactSet, S&P, FMP, Polygon, Finnhub, Tiingo,
or Yahoo without caring which one. Adapters that don't support a method
raise :class:`NotSupported` so the registry can fall back transparently.

Quotes, bars, and fundamentals are normalized into provider-agnostic
dataclasses (``Quote``, ``Bar``, ``Fundamentals``) — the same shape an
analyst would expect on a Bloomberg Terminal screen, regardless of who
provided the bytes underneath.

Naming conventions
------------------
* ``symbol``         vendor-native ticker as a single string ("AAPL", "BNP.PA").
* ``cik``            10-digit SEC CIK (for EDGAR).
* ``lei``            20-char Legal Entity Identifier (GLEIF).
* ``figi``           12-char Bloomberg FIGI (OpenFIGI).
* ``as_of``          ISO-8601 UTC date or datetime string.
* ``currency``       ISO-4217 (USD, EUR, GBP).

Tier taxonomy
-------------
* **bulge-bracket**  — Bloomberg, Refinitiv, FactSet, S&P Capital IQ.
                       Real-time, mission-critical, $$$.
* **institutional**  — Polygon, Tiingo, Finnhub paid, IEX paid.
                       Quant-grade reliability at retail price.
* **free / public**  — Yahoo, FRED, ECB, World Bank, EDGAR, OpenFIGI,
                       GLEIF, Damodaran. Zero-cost, may be rate-limited.

Adapters declare their tier so callers can prefer a higher-tier source
when available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


Tier = Literal["bulge", "institutional", "free"]


class NotSupported(NotImplementedError):
    """Adapter does not implement this capability."""


class ProviderError(RuntimeError):
    """Adapter could not fulfil the request (network, auth, parse)."""


class AuthRequired(ProviderError):
    """Adapter requires a credential that wasn't supplied."""


# ───────────────────────────── normalised data ──────────────────────────────


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    currency: Optional[str] = None
    previous_close: Optional[float] = None
    change_pct: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    exchange: Optional[str] = None
    as_of: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class Bar:
    date: str          # ISO date or datetime
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float] = None


@dataclass
class Fundamentals:
    """Income-statement / balance-sheet / cash-flow snapshot."""
    symbol: str
    period: str                            # "FY2025" or "Q3 2025"
    period_end: Optional[str] = None       # ISO date
    currency: Optional[str] = None
    revenue: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    total_assets: Optional[float] = None
    total_debt: Optional[float] = None
    cash: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    free_cash_flow: Optional[float] = None
    shares_diluted: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None


@dataclass(frozen=True)
class Filing:
    cik: str
    accession_number: str
    form: str                              # 10-K, 10-Q, 8-K, S-1
    filed_date: str                        # ISO date
    primary_document: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class Entity:
    """Legal entity / instrument cross-reference."""
    name: str
    lei: Optional[str] = None
    figi: Optional[str] = None
    isin: Optional[str] = None
    cusip: Optional[str] = None
    sedol: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    country: Optional[str] = None


# ───────────────────────────── base provider ────────────────────────────────


class Provider(ABC):
    """Base class every market-data adapter implements."""

    name: str = "abstract"
    tier: Tier = "free"
    requires_auth: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """True if dependencies installed and credentials present."""

    # — capabilities (override what you support, otherwise NotSupported)

    def quote(self, symbol: str) -> Quote:
        raise NotSupported(f"{self.name} does not implement quote()")

    def history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 250,
    ) -> list[Bar]:
        raise NotSupported(f"{self.name} does not implement history()")

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        raise NotSupported(f"{self.name} does not implement fundamentals()")

    def filings(
        self,
        cik: str,
        *,
        form: Optional[str] = None,
        limit: int = 20,
    ) -> list[Filing]:
        raise NotSupported(f"{self.name} does not implement filings()")

    def entity_lookup(
        self,
        *,
        lei: Optional[str] = None,
        figi: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> Entity:
        raise NotSupported(f"{self.name} does not implement entity_lookup()")

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        raise NotSupported(f"{self.name} does not implement search()")

    # — uniform helpers

    def supports(self, capability: str) -> bool:
        """Probe-without-calling: returns True if the capability is overridden."""
        method = getattr(type(self), capability, None)
        base_method = getattr(Provider, capability, None)
        return method is not None and method is not base_method

    def __repr__(self) -> str:
        return f"<Provider {self.name} tier={self.tier} auth={self.requires_auth}>"

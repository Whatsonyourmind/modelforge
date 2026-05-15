"""Provider registry — tier-aware auto-discovery + fallback routing.

Single entry point for any consumer (templates, MCP server, web app)
to call::

    from modelforge.feeds import registry
    q = registry.quote("AAPL")              # auto-route to best available
    q = registry.quote("AAPL", prefer="bloomberg")
    q = registry.fundamentals("AAPL", period="annual", limit=5)

Routing rules
-------------
1. If ``prefer=`` is supplied and that provider ``is_available()``,
   use it.
2. Otherwise iterate adapters in tier order: ``bulge → institutional → free``
   and use the first one that supports the requested capability AND
   is available.
3. If no provider is available, raise :class:`NoProviderAvailable` with
   the install/auth hint for each candidate.

This is the markets-standard pattern Bloomberg's BQuant, FactSet's
Codebook, and Refinitiv's Codebook all follow internally — abstract
the data plumbing so the model code is provider-agnostic.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Literal, Optional

from modelforge.feeds.provider import (
    AuthRequired,
    Bar,
    Entity,
    Filing,
    Fundamentals,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
    Tier,
)


class NoProviderAvailable(RuntimeError):
    """No registered adapter could fulfil the call."""


_TIER_ORDER: list[Tier] = ["bulge", "institutional", "free"]


def _build_default() -> list[Provider]:
    """Construct the default adapter stack.

    Order within a tier doesn't matter — registry sorts by ``tier``
    then by ``is_available()``. Adapters are instantiated lazily so
    importing the registry doesn't cost anything.
    """
    out: list[Provider] = []
    # Bulge tier
    try:
        from modelforge.feeds.bloomberg import BloombergProvider
        out.append(BloombergProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.refinitiv import RefinitivProvider
        out.append(RefinitivProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.factset import FactSetProvider
        out.append(FactSetProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.spcapiq import SPCapitalIQProvider
        out.append(SPCapitalIQProvider())
    except Exception:
        pass
    # Institutional tier
    try:
        from modelforge.feeds.polygon import PolygonProvider
        out.append(PolygonProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.fmp import FMPProvider
        out.append(FMPProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.finnhub import FinnhubProvider
        out.append(FinnhubProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.tiingo import TiingoProvider
        out.append(TiingoProvider())
    except Exception:
        pass
    # Free tier
    try:
        from modelforge.feeds.edgar import EdgarProvider
        out.append(EdgarProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.openfigi import OpenFIGIProvider
        out.append(OpenFIGIProvider())
    except Exception:
        pass
    try:
        from modelforge.feeds.gleif import GLEIFProvider
        out.append(GLEIFProvider())
    except Exception:
        pass
    return out


class Registry:
    """Holds a stack of providers and routes calls."""

    def __init__(self, providers: Optional[Iterable[Provider]] = None) -> None:
        self._providers: list[Provider] = list(providers) if providers else _build_default()

    # — introspection

    def list(self) -> list[Provider]:
        return list(self._providers)

    def available(self) -> list[Provider]:
        return [p for p in self._providers if p.is_available()]

    def by_name(self, name: str) -> Optional[Provider]:
        for p in self._providers:
            if p.name == name:
                return p
        return None

    def status(self) -> list[dict[str, Any]]:
        """Diagnostic table: who's installed, who's authenticated, what tier."""
        return [
            {
                "name": p.name,
                "tier": p.tier,
                "requires_auth": p.requires_auth,
                "available": p.is_available(),
                "supports": [
                    cap for cap in (
                        "quote", "history", "fundamentals", "filings",
                        "entity_lookup", "search",
                    )
                    if p.supports(cap)
                ],
            }
            for p in self._providers
        ]

    def register(self, provider: Provider) -> None:
        # Replace if same name already registered
        self._providers = [p for p in self._providers if p.name != provider.name]
        self._providers.append(provider)

    # — routing

    def _candidates(self, capability: str, prefer: Optional[str]) -> list[Provider]:
        # Preferred provider always tried first if it supports the capability
        ordered: list[Provider] = []
        if prefer:
            p = self.by_name(prefer)
            if p and p.supports(capability):
                ordered.append(p)
        # Then by tier order
        for tier in _TIER_ORDER:
            for p in self._providers:
                if p in ordered:
                    continue
                if p.tier == tier and p.supports(capability):
                    ordered.append(p)
        return ordered

    def _call(
        self,
        capability: str,
        *,
        prefer: Optional[str],
        operation,
    ):
        candidates = self._candidates(capability, prefer)
        if not candidates:
            raise NoProviderAvailable(
                f"No registered provider implements {capability!r}. "
                f"Registered: {[p.name for p in self._providers]}"
            )
        last_err: Optional[Exception] = None
        skipped: list[str] = []
        for p in candidates:
            if not p.is_available():
                skipped.append(p.name)
                continue
            try:
                return operation(p)
            except (NotSupported, AuthRequired) as e:
                last_err = e
                continue
            except ProviderError as e:
                last_err = e
                continue
        skipped_msg = f" (skipped unavailable: {', '.join(skipped)})" if skipped else ""
        raise NoProviderAvailable(
            f"No available provider for {capability}: {last_err}{skipped_msg}"
        )

    # — public API mirroring Provider

    def quote(self, symbol: str, *, prefer: Optional[str] = None) -> Quote:
        return self._call("quote", prefer=prefer, operation=lambda p: p.quote(symbol))

    def history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 250,
        prefer: Optional[str] = None,
    ) -> list[Bar]:
        return self._call(
            "history",
            prefer=prefer,
            operation=lambda p: p.history(
                symbol, interval=interval, start=start, end=end, limit=limit,
            ),
        )

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
        prefer: Optional[str] = None,
    ) -> list[Fundamentals]:
        return self._call(
            "fundamentals",
            prefer=prefer,
            operation=lambda p: p.fundamentals(
                symbol, statement=statement, period=period, limit=limit,
            ),
        )

    def filings(
        self,
        cik: str,
        *,
        form: Optional[str] = None,
        limit: int = 20,
        prefer: Optional[str] = None,
    ) -> list[Filing]:
        return self._call(
            "filings",
            prefer=prefer,
            operation=lambda p: p.filings(cik, form=form, limit=limit),
        )

    def entity_lookup(
        self,
        *,
        lei: Optional[str] = None,
        figi: Optional[str] = None,
        ticker: Optional[str] = None,
        prefer: Optional[str] = None,
    ) -> Entity:
        return self._call(
            "entity_lookup",
            prefer=prefer,
            operation=lambda p: p.entity_lookup(lei=lei, figi=figi, ticker=ticker),
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        prefer: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            "search",
            prefer=prefer,
            operation=lambda p: p.search(query, limit=limit),
        )


# ─── module-level singleton + facade ────────────────────────────────────────

_REGISTRY: Optional[Registry] = None


def registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = Registry()
    return _REGISTRY


def quote(symbol: str, *, prefer: Optional[str] = None) -> Quote:
    return registry().quote(symbol, prefer=prefer)


def history(symbol: str, **kwargs) -> list[Bar]:
    return registry().history(symbol, **kwargs)


def fundamentals(symbol: str, **kwargs) -> list[Fundamentals]:
    return registry().fundamentals(symbol, **kwargs)


def filings(cik: str, **kwargs) -> list[Filing]:
    return registry().filings(cik, **kwargs)


def entity_lookup(**kwargs) -> Entity:
    return registry().entity_lookup(**kwargs)


def search(query: str, **kwargs) -> list[dict[str, Any]]:
    return registry().search(query, **kwargs)


def status() -> list[dict[str, Any]]:
    return registry().status()

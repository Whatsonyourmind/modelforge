"""Refinitiv (LSEG) adapter — Eikon Data API + Refinitiv Data Library.

Refinitiv (now LSEG Workspace post-2024 rebrand) is the #2 institutional
terminal after Bloomberg. ~190k seats, especially dominant in EMEA buy-
side and FX markets. The Python SDK has two flavors:

* Legacy: ``eikon`` package (still works, requires Eikon desktop running)
* Modern: ``refinitiv-data`` (LSEG Data Library v1+, supports cloud)

We try both, prefer the modern one. Without either installed the
adapter raises :class:`AuthRequired` with an actionable message.

Identifier conventions (RIC):
    AAPL.O    — Apple on Nasdaq
    BNPP.PA   — BNP Paribas on Paris Euronext
    .SPX      — S&P 500 index

Activation: install ``refinitiv-data`` and set ``REFINITIV_APP_KEY``.
Or install ``eikon`` and run Refinitiv Workspace locally with the API
proxy enabled.
"""

from __future__ import annotations

import os
from typing import Any, Literal, Optional

from modelforge.feeds.provider import (
    AuthRequired,
    Bar,
    Fundamentals,
    NotSupported,
    Provider,
    ProviderError,
    Quote,
)


_INSTALL_HINT = (
    "Refinitiv requires either `refinitiv-data` (modern LSEG Data Library) "
    "or `eikon` (legacy). Install: pip install refinitiv-data. "
    "Set REFINITIV_APP_KEY (cloud) or run LSEG Workspace locally."
)


def _have_modern() -> bool:
    try:
        import refinitiv.data as rd  # noqa: F401
        return True
    except ImportError:
        return False


def _have_legacy() -> bool:
    try:
        import eikon  # noqa: F401
        return True
    except ImportError:
        return False


def _open_session() -> Any:
    """Return an opened Refinitiv session. Caller is responsible for closing."""
    if _have_modern():
        import refinitiv.data as rd
        app_key = os.environ.get("REFINITIV_APP_KEY")
        if not app_key:
            raise AuthRequired(
                "REFINITIV_APP_KEY not set. Get one at "
                "https://developers.lseg.com/en/api-catalog"
            )
        try:
            rd.open_session(name="default")
        except Exception as e:
            raise ProviderError(f"Refinitiv session.open failed: {e}") from e
        return rd
    if _have_legacy():
        import eikon as ek
        app_key = os.environ.get("REFINITIV_APP_KEY") or os.environ.get("EIKON_APP_KEY")
        if not app_key:
            raise AuthRequired(_INSTALL_HINT)
        ek.set_app_key(app_key)
        return ek
    raise AuthRequired(_INSTALL_HINT)


# ─── Provider adapter ───────────────────────────────────────────────────────


class RefinitivProvider(Provider):
    name = "refinitiv"
    tier = "bulge"
    requires_auth = True

    QUOTE_FIELDS = ["TR.PriceClose", "TR.Volume", "TR.PriceClose.currency", "TR.PriceClosePctChange"]
    FUND_FIELDS = [
        "TR.Revenue", "TR.EBIT", "TR.EBITDA", "TR.NetIncome", "TR.EPSDiluted",
        "TR.TotalAssetsReported", "TR.LTDebt", "TR.Cash",
        "TR.CashFromOperations", "TR.CapitalExpenditures",
    ]

    def is_available(self) -> bool:
        if not (_have_modern() or _have_legacy()):
            return False
        return bool(
            os.environ.get("REFINITIV_APP_KEY")
            or os.environ.get("EIKON_APP_KEY")
        )

    def quote(self, symbol: str) -> Quote:
        sess = _open_session()
        try:
            if _have_modern():
                import refinitiv.data as rd
                df = rd.get_data(symbol, fields=self.QUOTE_FIELDS)
            else:
                df, _ = sess.get_data(symbol, self.QUOTE_FIELDS)
        except Exception as e:
            raise ProviderError(f"Refinitiv quote failed: {e}") from e
        if df is None or len(df) == 0:
            raise ProviderError(f"Refinitiv: no quote for {symbol}")
        row = df.iloc[0].to_dict() if hasattr(df, "iloc") else df[0]
        price = row.get("Price Close") or row.get("TR.PriceClose")
        return Quote(
            symbol=symbol,
            price=float(price) if price is not None else 0.0,
            volume=row.get("Volume"),
            currency=row.get("Currency"),
            change_pct=row.get("Price Close % Change"),
            source="refinitiv",
        )

    def history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 250,
    ) -> list[Bar]:
        _open_session()
        try:
            if _have_modern():
                import refinitiv.data as rd
                interval_map = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}
                df = rd.get_history(
                    symbol,
                    fields=["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
                    interval=interval_map.get(interval, "daily"),
                    start=start,
                    end=end,
                )
            else:
                import eikon as ek
                interval_map = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}
                df = ek.get_timeseries(
                    symbol,
                    fields=["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
                    interval=interval_map.get(interval, "daily"),
                    start_date=start,
                    end_date=end,
                )
        except Exception as e:
            raise ProviderError(f"Refinitiv history failed: {e}") from e
        out: list[Bar] = []
        if df is None:
            return out
        for ts, row in df.iterrows():
            out.append(Bar(
                date=ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
                open=row.get("OPEN") or row.get("open"),
                high=row.get("HIGH") or row.get("high"),
                low=row.get("LOW") or row.get("low"),
                close=row.get("CLOSE") or row.get("close"),
                volume=row.get("VOLUME") or row.get("volume"),
            ))
        return out[:limit]

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        sess = _open_session()
        params = {"Period": "FY0" if limit == 1 else f"FY-{limit}:FY0"}
        if period == "quarter":
            params = {"Period": "FQ0" if limit == 1 else f"FQ-{limit}:FQ0"}
        try:
            if _have_modern():
                import refinitiv.data as rd
                df = rd.get_data(symbol, fields=self.FUND_FIELDS, parameters=params)
            else:
                df, _ = sess.get_data(symbol, self.FUND_FIELDS, parameters=params)
        except Exception as e:
            raise ProviderError(f"Refinitiv fundamentals failed: {e}") from e
        if df is None or len(df) == 0:
            raise ProviderError(f"Refinitiv: no fundamentals for {symbol}")
        out: list[Fundamentals] = []
        for _, row in df.iterrows() if hasattr(df, "iterrows") else []:
            r = row.to_dict()
            ocf = r.get("Cash From Operations")
            capex = r.get("Capital Expenditures")
            fcf = (ocf + capex) if ocf is not None and capex is not None else None
            out.append(Fundamentals(
                symbol=symbol,
                period=str(r.get("Period") or "TTM"),
                revenue=r.get("Revenue"),
                ebit=r.get("EBIT"),
                ebitda=r.get("EBITDA"),
                net_income=r.get("Net Income"),
                eps=r.get("EPS Diluted"),
                total_assets=r.get("Total Assets, Reported"),
                total_debt=r.get("LT Debt"),
                cash=r.get("Cash"),
                operating_cash_flow=ocf,
                capex=capex,
                free_cash_flow=fcf,
                source="refinitiv",
            ))
        return out

"""FactSet adapter — bridge to fds.sdk and FQL Workstation.

FactSet is the #3 institutional terminal (~190k seats), especially
strong in IB and PE — exactly ModelForge's wedge buyers. Adapter wraps
``fds.sdk.*`` (the modern REST SDKs) which can be used with either a
Workstation auth (analyst credential) or a Server-side Programmatic
Access auth (machine credential).

Activation:
    1. Pip-install the FactSet SDK packages you need:
       ``pip install fds.sdk.FactSetFundamentals fds.sdk.FactSetPrices``
       (FactSet ships one PyPI package per data domain)
    2. Set ``FACTSET_USERNAME_SERIAL`` and ``FACTSET_API_KEY``
       (provided by your FactSet rep)

Without those, every method raises :class:`AuthRequired`.

Identifier conventions (FactSet):
    AAPL-US        — Apple primary US listing
    BNP-FR         — BNP Paribas, primary FR listing
    AAPL.US        — same as above (alt syntax)
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
    "FactSet requires fds.sdk packages. Install the modules you need: "
    "pip install fds.sdk.FactSetFundamentals fds.sdk.FactSetPrices. "
    "Provision FACTSET_USERNAME_SERIAL + FACTSET_API_KEY via your "
    "FactSet account team."
)


def _have_prices() -> bool:
    try:
        import fds.sdk.FactSetPrices  # noqa: F401
        return True
    except ImportError:
        return False


def _have_fundamentals() -> bool:
    try:
        import fds.sdk.FactSetFundamentals  # noqa: F401
        return True
    except ImportError:
        return False


def _have_any() -> bool:
    return _have_prices() or _have_fundamentals()


def _credentials() -> tuple[str, str]:
    user = os.environ.get("FACTSET_USERNAME_SERIAL")
    key = os.environ.get("FACTSET_API_KEY")
    if not user or not key:
        raise AuthRequired(
            "FactSet requires FACTSET_USERNAME_SERIAL and FACTSET_API_KEY env vars."
        )
    return user, key


def _config(module):
    """Build a fds.sdk.* Configuration with HTTP-basic auth from env."""
    user, key = _credentials()
    cfg_cls = getattr(module, "Configuration")
    cfg = cfg_cls(username=user, password=key)
    return cfg


# ─── Provider adapter ───────────────────────────────────────────────────────


class FactSetProvider(Provider):
    name = "factset"
    tier = "bulge"
    requires_auth = True

    # FactSet metric ids
    FUND_METRICS = [
        "FF_SALES",            # revenue
        "FF_EBIT_OPER",        # EBIT (operating)
        "FF_EBITDA_OPER",      # EBITDA
        "FF_NET_INC",          # net income
        "FF_EPS_DIL",          # diluted EPS
        "FF_ASSETS",           # total assets
        "FF_DEBT_LT",          # LT debt
        "FF_CASH_GEN",         # cash & equivalents
        "FF_OPER_CF",          # operating cash flow
        "FF_CAPEX",            # capex
    ]

    def is_available(self) -> bool:
        if not _have_any():
            return False
        try:
            _credentials()
            return True
        except AuthRequired:
            return False

    def quote(self, symbol: str) -> Quote:
        if not _have_prices():
            raise AuthRequired(
                "Install fds.sdk.FactSetPrices for quote(): "
                "pip install fds.sdk.FactSetPrices"
            )
        from fds.sdk import FactSetPrices  # type: ignore
        from fds.sdk.FactSetPrices.api import prices_api  # type: ignore
        from fds.sdk.FactSetPrices.models import (  # type: ignore
            PricesRequest, PricesRequestData, IdsBatchMax2000,
        )
        cfg = _config(FactSetPrices)
        try:
            with FactSetPrices.ApiClient(cfg) as client:
                api = prices_api.PricesApi(client)
                body = PricesRequest(data=PricesRequestData(ids=IdsBatchMax2000([symbol])))
                resp = api.get_security_prices_for_list(prices_request=body)
        except Exception as e:
            raise ProviderError(f"FactSet quote failed: {e}") from e
        rows = (resp.to_dict() or {}).get("data") or []
        if not rows:
            raise ProviderError(f"FactSet: no quote for {symbol}")
        r = rows[0]
        return Quote(
            symbol=symbol,
            price=float(r.get("price") or 0.0),
            currency=r.get("currency"),
            volume=r.get("volume"),
            source="factset",
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
        if not _have_prices():
            raise AuthRequired(
                "Install fds.sdk.FactSetPrices for history(): "
                "pip install fds.sdk.FactSetPrices"
            )
        from fds.sdk import FactSetPrices  # type: ignore
        from fds.sdk.FactSetPrices.api import prices_api  # type: ignore
        cfg = _config(FactSetPrices)
        period_map = {"1d": "D", "1wk": "W", "1mo": "M"}
        try:
            with FactSetPrices.ApiClient(cfg) as client:
                api = prices_api.PricesApi(client)
                resp = api.get_security_prices(
                    ids=[symbol],
                    start_date=start,
                    end_date=end,
                    frequency=period_map.get(interval, "D"),
                )
        except Exception as e:
            raise ProviderError(f"FactSet history failed: {e}") from e
        rows = (resp.to_dict() or {}).get("data") or []
        out = [
            Bar(
                date=str(r.get("date") or "")[:10],
                open=r.get("open"),
                high=r.get("high"),
                low=r.get("low"),
                close=r.get("price") or r.get("close"),
                volume=r.get("volume"),
            )
            for r in rows[:limit]
        ]
        return out

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        if not _have_fundamentals():
            raise AuthRequired(
                "Install fds.sdk.FactSetFundamentals for fundamentals(): "
                "pip install fds.sdk.FactSetFundamentals"
            )
        from fds.sdk import FactSetFundamentals  # type: ignore
        from fds.sdk.FactSetFundamentals.api import fundamentals_api  # type: ignore
        cfg = _config(FactSetFundamentals)
        period_code = "ANN" if period == "annual" else "QTR"
        try:
            with FactSetFundamentals.ApiClient(cfg) as client:
                api = fundamentals_api.FundamentalsApi(client)
                resp = api.get_fds_fundamentals(
                    ids=[symbol],
                    metrics=self.FUND_METRICS,
                    periodicity=period_code,
                    fiscal_period_start="0",
                    fiscal_period_end=str(-(limit - 1)) if limit > 1 else "0",
                )
        except Exception as e:
            raise ProviderError(f"FactSet fundamentals failed: {e}") from e
        rows = (resp.to_dict() or {}).get("data") or []
        # FactSet returns long-form rows: {fsymId, metric, value, fiscalYear, ...}
        # Pivot to one Fundamentals per fiscalYear/period.
        bucket: dict[str, dict[str, Any]] = {}
        for r in rows:
            yr = str(r.get("fiscal_year") or r.get("period_end") or "?")
            bucket.setdefault(yr, {"period": yr})
            bucket[yr][r["metric"]] = r["value"]
        out = []
        for yr, b in sorted(bucket.items(), reverse=True)[:limit]:
            ocf = b.get("FF_OPER_CF")
            capex = b.get("FF_CAPEX")
            fcf = (ocf + capex) if ocf is not None and capex is not None else None
            out.append(Fundamentals(
                symbol=symbol,
                period=f"FY{yr}" if period == "annual" else yr,
                revenue=b.get("FF_SALES"),
                ebit=b.get("FF_EBIT_OPER"),
                ebitda=b.get("FF_EBITDA_OPER"),
                net_income=b.get("FF_NET_INC"),
                eps=b.get("FF_EPS_DIL"),
                total_assets=b.get("FF_ASSETS"),
                total_debt=b.get("FF_DEBT_LT"),
                cash=b.get("FF_CASH_GEN"),
                operating_cash_flow=ocf,
                capex=capex,
                free_cash_flow=fcf,
                source="factset",
            ))
        return out

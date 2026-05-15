"""Bloomberg adapter — bridge to the BLPAPI SDK.

Bloomberg is THE bulge-bracket data tier. ~325k Terminal seats,
$24-30k/seat/yr. BLPAPI is the official Python/C++ SDK that Goldman,
Morgan Stanley, and every IB use to pipe live and historical data into
in-house systems.

Why ship this even without a Terminal: the *interface* matters for
ModelForge's procurement story. A regulated bank that adopts ModelForge
needs to see "Bloomberg = first-class supported" in the docs. Even
without a Bloomberg seat, every model spec can name BBG tickers (e.g.
``IBM US Equity``, ``ISP IM Equity``) and ModelForge will be ready the
day the buyer flips on a Terminal connection.

Activation:
    1. Install ``blpapi`` from Bloomberg
       (`https://www.bloomberg.com/professional/support/api-library/`)
    2. Be inside a Bloomberg Terminal session OR run B-PIPE / Server API
    3. Set ``BLOOMBERG_HOST`` (default 'localhost') and ``BLOOMBERG_PORT``
       (default 8194).

Without those, every method raises :class:`AuthRequired` with an
actionable message — never silently degrades to bad data.

Reference fields (BBG conventions):
    PX_LAST           — last trade price
    OPEN, HIGH, LOW, CLOSE
    PX_BID / PX_ASK
    VOLUME
    SALES_REV_TURN    — total revenue
    EBIT, EBITDA, NET_INCOME
    BS_TOT_ASSET, BS_LT_BORROW
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
    "Bloomberg requires the official `blpapi` SDK. "
    "Install: pip install blpapi (after registering at "
    "https://www.bloomberg.com/professional/support/api-library/). "
    "An active Bloomberg Terminal session, B-PIPE, or Server API is "
    "required for the SDK to connect."
)


def _have_blpapi() -> bool:
    try:
        import blpapi  # noqa: F401
        return True
    except ImportError:
        return False


def _session():
    if not _have_blpapi():
        raise AuthRequired(_INSTALL_HINT)
    import blpapi
    opts = blpapi.SessionOptions()
    opts.setServerHost(os.environ.get("BLOOMBERG_HOST", "localhost"))
    opts.setServerPort(int(os.environ.get("BLOOMBERG_PORT", "8194")))
    sess = blpapi.Session(opts)
    if not sess.start():
        raise ProviderError("Bloomberg: session.start() failed (Terminal not running?)")
    if not sess.openService("//blp/refdata"):
        raise ProviderError("Bloomberg: could not open //blp/refdata")
    return sess, blpapi


def reference_data(securities: list[str], fields: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch reference fields for a basket of BBG identifiers.

    Returns ``{security: {field: value}}``.
    """
    sess, blpapi = _session()
    try:
        svc = sess.getService("//blp/refdata")
        req = svc.createRequest("ReferenceDataRequest")
        for sec in securities:
            req.append("securities", sec)
        for f in fields:
            req.append("fields", f)
        sess.sendRequest(req)
        out: dict[str, dict[str, Any]] = {}
        while True:
            ev = sess.nextEvent(5000)
            for msg in ev:
                items = msg.getElement("securityData")
                for i in range(items.numValues()):
                    sd = items.getValueAsElement(i)
                    sec = sd.getElementAsString("security")
                    fd = sd.getElement("fieldData")
                    row: dict[str, Any] = {}
                    for f in fields:
                        if fd.hasElement(f):
                            row[f] = fd.getElement(f).getValue()
                    out[sec] = row
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        return out
    finally:
        sess.stop()


def historical_data(
    securities: list[str],
    fields: list[str],
    *,
    start_date: str,
    end_date: str,
    periodicity: Literal["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"] = "DAILY",
) -> dict[str, list[dict[str, Any]]]:
    """Fetch historical fields for a basket. Dates must be ``YYYYMMDD``."""
    sess, blpapi = _session()
    try:
        svc = sess.getService("//blp/refdata")
        req = svc.createRequest("HistoricalDataRequest")
        for sec in securities:
            req.append("securities", sec)
        for f in fields:
            req.append("fields", f)
        req.set("startDate", start_date.replace("-", ""))
        req.set("endDate", end_date.replace("-", ""))
        req.set("periodicitySelection", periodicity)
        sess.sendRequest(req)
        out: dict[str, list[dict[str, Any]]] = {}
        while True:
            ev = sess.nextEvent(5000)
            for msg in ev:
                sd = msg.getElement("securityData")
                sec = sd.getElementAsString("security")
                fd = sd.getElement("fieldData")
                rows: list[dict[str, Any]] = []
                for i in range(fd.numValues()):
                    row_el = fd.getValueAsElement(i)
                    row: dict[str, Any] = {}
                    for k in range(row_el.numElements()):
                        el = row_el.getElement(k)
                        row[str(el.name())] = el.getValue()
                    rows.append(row)
                out[sec] = rows
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        return out
    finally:
        sess.stop()


# ─── Provider adapter ───────────────────────────────────────────────────────


class BloombergProvider(Provider):
    name = "bloomberg"
    tier = "bulge"
    requires_auth = True

    # Default field maps — overridable per call by power users
    QUOTE_FIELDS = ["PX_LAST", "PX_BID", "PX_ASK", "PX_VOLUME", "CHG_PCT_1D", "CRNCY"]
    HIST_FIELDS = ["PX_OPEN", "PX_HIGH", "PX_LOW", "PX_LAST", "PX_VOLUME"]
    FUND_FIELDS = [
        "SALES_REV_TURN", "EBIT", "EBITDA", "NET_INCOME", "EPS",
        "BS_TOT_ASSET", "BS_LT_BORROW", "BS_CASH_NEAR_CASH_ITEM",
        "CF_CASH_FROM_OPER", "CF_CAP_EXPEND_INC_FIX_AST",
    ]

    def is_available(self) -> bool:
        if not _have_blpapi():
            return False
        # Don't try to open a session here — too slow for is_available().
        # If the SDK is installed, declare available.
        return True

    def quote(self, symbol: str) -> Quote:
        data = reference_data([symbol], list(self.QUOTE_FIELDS))
        d = data.get(symbol, {})
        if not d:
            raise ProviderError(f"Bloomberg: no quote for {symbol}")
        return Quote(
            symbol=symbol,
            price=float(d.get("PX_LAST") or 0.0),
            currency=d.get("CRNCY"),
            bid=d.get("PX_BID"),
            ask=d.get("PX_ASK"),
            volume=d.get("PX_VOLUME"),
            change_pct=d.get("CHG_PCT_1D"),
            source="bloomberg",
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
        from datetime import date, timedelta
        end = end or date.today().isoformat()
        if not start:
            start = (date.fromisoformat(end) - timedelta(days=int(limit * 1.5))).isoformat()
        period_map = {"1d": "DAILY", "1wk": "WEEKLY", "1mo": "MONTHLY", "1q": "QUARTERLY"}
        rows = historical_data(
            [symbol],
            list(self.HIST_FIELDS),
            start_date=start,
            end_date=end,
            periodicity=period_map.get(interval, "DAILY"),  # type: ignore[arg-type]
        ).get(symbol, [])[:limit]
        out: list[Bar] = []
        for r in rows:
            d = r.get("date")
            out.append(Bar(
                date=d.isoformat() if hasattr(d, "isoformat") else str(d),
                open=r.get("PX_OPEN"),
                high=r.get("PX_HIGH"),
                low=r.get("PX_LOW"),
                close=r.get("PX_LAST"),
                volume=r.get("PX_VOLUME"),
            ))
        return out

    def fundamentals(
        self,
        symbol: str,
        *,
        statement: Literal["income", "balance", "cashflow"] = "income",
        period: Literal["annual", "quarter"] = "annual",
        limit: int = 5,
    ) -> list[Fundamentals]:
        # BBG fundamentals via reference_data with FUND_PER override
        # would be ideal — for v1 we fetch latest TTM.
        if period != "annual" or limit != 1:
            raise NotSupported(
                "Bloomberg adapter v1 supports only annual TTM fundamentals; "
                "history requires FUND_PER overrides — open a ticket if needed."
            )
        d = reference_data([symbol], list(self.FUND_FIELDS)).get(symbol, {})
        if not d:
            raise ProviderError(f"Bloomberg: no fundamentals for {symbol}")
        ocf = d.get("CF_CASH_FROM_OPER")
        capex = d.get("CF_CAP_EXPEND_INC_FIX_AST")
        fcf = (ocf + capex) if ocf is not None and capex is not None else None
        return [Fundamentals(
            symbol=symbol,
            period="TTM",
            revenue=d.get("SALES_REV_TURN"),
            ebit=d.get("EBIT"),
            ebitda=d.get("EBITDA"),
            net_income=d.get("NET_INCOME"),
            eps=d.get("EPS"),
            total_assets=d.get("BS_TOT_ASSET"),
            total_debt=d.get("BS_LT_BORROW"),
            cash=d.get("BS_CASH_NEAR_CASH_ITEM"),
            operating_cash_flow=ocf,
            capex=capex,
            free_cash_flow=fcf,
            source="bloomberg",
        )]

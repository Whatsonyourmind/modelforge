"""Built-in plausibility rules (25+) for ModelForge templates.

Each rule returns 0..N TrustViolations. Rules are pure: they probe the
workbook, compare against spec or hard-coded plausibility bands, and
emit violations. No mutation.

The bands are drawn from market-standard practice:

* WACC: 3% (low rates + low-beta utility) to 25% (deep-distressed PE)
* Terminal growth: ≤ ~3.5% (above implies perpetual outperformance vs GDP)
* Terminal growth < WACC (else infinite TV — basic math)
* DCF EV vs market cap: ±100% is "valuation disagreement", >100% is
  worth flagging as a unit/scale check
* LBO leverage: 3-8x EBITDA at entry is the standard band
* DSCR (project finance): ≥ 1.0 every year, otherwise default
* LTV (real estate): ≤ 100% (above means debt > value)
* NPL recovery: cumulative ≤ 100% of EAD
* IRR: -100% (total loss) to +100% (sanity max for any one investment)
"""

from __future__ import annotations

from typing import Any, Iterable

from modelforge.trust.rules import FunctionalRule, TrustRule, WorkbookProbe
from modelforge.trust.violations import TrustViolation


# ─── helpers ────────────────────────────────────────────────────────────────


def _violation(rule, message, **kwargs) -> TrustViolation:
    return TrustViolation(
        rule_name=rule.name,
        severity=rule.severity,
        template=kwargs.pop("template", "unknown"),
        message=message,
        **kwargs,
    )


def _band_check(actual: float, low: float, high: float) -> bool:
    """True if actual is INSIDE the band [low, high]. NaN-safe."""
    if actual is None:
        return True
    try:
        return low - 1e-9 <= actual <= high + 1e-9
    except (TypeError, ValueError):
        return True


def _rule(name, desc, templates, severity, fn) -> FunctionalRule:
    return FunctionalRule(name, desc, templates, severity, fn)


# ─── DCF rules ──────────────────────────────────────────────────────────────


def _dcf_wacc_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """WACC must be in [3%, 25%] for any going-concern equity model."""
    wacc = probe.get("wacc_rate") or probe.get("WACCBuild!D18")
    if wacc is None:
        return
    if not _band_check(wacc, 0.03, 0.25):
        yield _violation(
            rule,
            f"WACC {wacc:.2%} outside [3%, 25%] band — implies risk-free rate or extreme distress",
            template=spec.model_type,
            cell="WACCBuild!D18",
            actual=wacc,
            expected_low=0.03,
            expected_high=0.25,
            recommendation="Re-check beta, ERP, and cost of debt inputs.",
        )


def _dcf_wacc_above_rfr(probe, spec, rule) -> Iterable[TrustViolation]:
    """WACC must exceed the risk-free rate (else cost of equity ≤ rfr, impossible)."""
    wacc = probe.get("wacc_rate") or probe.get("WACCBuild!D18")
    rfr = probe.get("risk_free_rate") or probe.get("WACCBuild!D5")
    if wacc is None or rfr is None:
        return
    if wacc < rfr - 1e-6:
        yield _violation(
            rule,
            f"WACC {wacc:.2%} below risk-free rate {rfr:.2%} — implies negative ERP × beta. Impossible.",
            template=spec.model_type,
            cell="WACCBuild!D18",
            actual=wacc,
            expected_low=rfr,
            expected_high=0.25,
            recommendation="Beta likely zero (look for empty-cell formula references in ComparableBetas).",
        )


def _dcf_terminal_growth_below_wacc(probe, spec, rule) -> Iterable[TrustViolation]:
    """Terminal growth < WACC, else Gordon TV is infinite."""
    g = probe.get("terminal_growth_pct")
    wacc = probe.get("wacc_rate") or probe.get("WACCBuild!D18")
    if g is None or wacc is None:
        return
    if g >= wacc - 0.005:
        yield _violation(
            rule,
            f"Terminal g {g:.2%} ≥ WACC {wacc:.2%} (less 50bps). Gordon TV blows up.",
            template=spec.model_type,
            cell="terminal_growth_pct",
            actual=g,
            expected_high=wacc - 0.005,
            recommendation="Set terminal growth ≤ WACC − 100bps; for utilities, ≤ 2% is typical.",
        )


def _dcf_terminal_growth_below_gdp(probe, spec, rule) -> Iterable[TrustViolation]:
    """Terminal growth ≤ ~3.5% (long-run nominal GDP for DM economies)."""
    g = probe.get("terminal_growth_pct")
    if g is None:
        return
    if g > 0.035:
        yield _violation(
            rule,
            f"Terminal g {g:.2%} above long-run nominal GDP (~3.5%). Implies firm outgrows the economy forever.",
            template=spec.model_type,
            cell="terminal_growth_pct",
            actual=g,
            expected_high=0.035,
            recommendation="Cap at 3.5% for DM economies, lower for slow-growth markets.",
        )


def _dcf_market_cap_deviation(probe, spec, rule) -> Iterable[TrustViolation]:
    """Implied premium vs current price within ±100%."""
    premium_x = probe.get("Valuation!D26")  # implied premium %
    if premium_x is None:
        return
    if abs(premium_x) > 1.0:
        yield _violation(
            rule,
            f"DCF premium vs current price = {premium_x:+.0%}. >±100% is implausible without a special situation.",
            template=spec.model_type,
            cell="Valuation!D26",
            actual=premium_x,
            expected_low=-1.0,
            expected_high=1.0,
            recommendation="Re-check WACC, terminal growth, exit multiple, and that revenue/EBITDA units match the spec's unit_scale.",
        )


def _dcf_implied_equity_vs_market_cap(probe, spec, rule) -> Iterable[TrustViolation]:
    """Live external check: DCF-implied equity value vs current market cap.

    Requires ``spec.target.ticker`` to be set (e.g. "ENEL.MI", "AAPL").
    Pulls market cap via the YahooProvider (free, no auth) and compares
    to the workbook's implied equity (``Valuation!D21``, in millions).

    Severity:
        * WARN at ≥25% absolute deviation
        * FAIL at ≥100% absolute deviation

    This is the rule that catches "Enel DCF says €553B equity but real
    market cap is €95B (+7x)" — exactly what internal review
    flagged as the unresolved priority item.
    """
    ticker = getattr(getattr(spec, "target", None), "ticker", None)
    if not ticker:
        return
    implied_equity_m = probe.get("Valuation!D21")
    if implied_equity_m is None:
        return
    try:
        from modelforge.feeds.yahoo import _market_cap as _live_market_cap
        market_cap = _live_market_cap(ticker)
    except Exception:
        return  # Network down / rate-limited — never block the build
    if market_cap is None or market_cap <= 0:
        return
    # Workbook is in spec.meta.unit_scale; default 'millions' → convert to absolute
    unit_scale = getattr(getattr(spec, "meta", None), "unit_scale", "millions")
    multiplier = {"actual": 1.0, "thousands": 1_000.0, "millions": 1_000_000.0}.get(
        unit_scale, 1_000_000.0
    )
    implied_equity_abs = implied_equity_m * multiplier
    deviation = (implied_equity_abs - market_cap) / market_cap
    if abs(deviation) >= 1.0:
        yield _violation(
            rule,
            f"DCF implied equity {implied_equity_abs/1e9:.1f}B vs live market cap "
            f"{market_cap/1e9:.1f}B for {ticker} ({deviation:+.0%}). "
            f">±100% deviation is a unit/scale or assumption error, not a valuation gap.",
            template=spec.model_type,
            cell="Valuation!D21",
            actual=implied_equity_abs,
            expected_low=market_cap * 0.5,
            expected_high=market_cap * 2.0,
            recommendation=(
                f"Likely causes: (a) revenue/EBITDA units don't match meta.unit_scale, "
                f"(b) WACC too low / terminal-growth too high, (c) exit multiple unrealistic. "
                f"Cross-check against {ticker} on Yahoo Finance."
            ),
        )
    elif abs(deviation) >= 0.25:
        # Soft warn — within ±25% to ±100% is "valuation disagreement", not a bug
        yield _violation(
            rule,
            f"DCF implied equity {implied_equity_abs/1e9:.1f}B vs live market cap "
            f"{market_cap/1e9:.1f}B for {ticker} ({deviation:+.0%}). "
            f"Above ±25%: defensible but flag for IC.",
            template=spec.model_type,
            cell="Valuation!D21",
            actual=implied_equity_abs,
            expected_low=market_cap * 0.75,
            expected_high=market_cap * 1.25,
            recommendation=(
                f"Document the thesis explaining why {ticker} should re-rate "
                f"by {deviation:+.0%} (e.g., catalyst, peer mispricing, "
                f"forecast vs. consensus delta)."
            ),
        )


# ─── LBO rules (sponsor_lbo) ────────────────────────────────────────────────


def _lbo_leverage_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """Entry leverage 2-8x EBITDA. Below 2x = under-levered; above 8x = covenant-busting."""
    lev = probe.get("entry_leverage") or probe.get("entry_leverage_x")
    if lev is None:
        return
    if not _band_check(lev, 2.0, 8.0):
        yield _violation(
            rule,
            f"Entry leverage {lev:.2f}x outside 2-8x EBITDA band",
            template=spec.model_type,
            actual=lev,
            expected_low=2.0,
            expected_high=8.0,
            recommendation="Most leveraged buyouts close at 5-7x; >8x would breach typical sponsor covenants.",
        )


def _lbo_irr_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """Sponsor IRR -50% (full loss-ish) to +50% (home run). Outside means a calculation error."""
    irr = probe.get("sponsor_irr") or probe.get("equity_irr")
    if irr is None:
        return
    if not _band_check(irr, -0.5, 0.5):
        yield _violation(
            rule,
            f"Sponsor IRR {irr:.1%} outside [-50%, +50%] sanity band",
            template=spec.model_type,
            actual=irr,
            expected_low=-0.5,
            expected_high=0.5,
            recommendation="IRR > 50% almost always means a sign error or missed exit multiple cap.",
        )


# ─── Project finance rules ──────────────────────────────────────────────────


def _pf_dscr_above_one(probe, spec, rule) -> Iterable[TrustViolation]:
    """DSCR (min) must be > 1.0; else principal cannot be repaid."""
    dscr = probe.get("min_dscr") or probe.get("dscr_min")
    if dscr is None:
        return
    if dscr < 1.0 - 1e-6:
        yield _violation(
            rule,
            f"Minimum DSCR {dscr:.2f}x below 1.0 — debt service uncovered, default certain",
            template=spec.model_type,
            actual=dscr,
            expected_low=1.0,
            recommendation="Increase tariff / haircut debt; senior PF lenders typically require ≥1.20x.",
        )


def _pf_dscr_lender_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """DSCR base-case ≥ 1.20x is the institutional norm."""
    dscr = probe.get("min_dscr") or probe.get("dscr_min")
    if dscr is None:
        return
    if dscr < 1.20 and dscr >= 1.0:
        yield _violation(
            rule,
            f"Min DSCR {dscr:.2f}x below 1.20x lender norm (loan likely uncatable for an IG financing)",
            template=spec.model_type,
            actual=dscr,
            expected_low=1.20,
            recommendation="Standard PF covenants call for ≥1.20x base / ≥1.10x downside.",
        )


# ─── Real estate rules ─────────────────────────────────────────────────────


def _re_ltv_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """LTV ≤ 85% (above implies negative equity at deal close)."""
    ltv = probe.get("ltv") or probe.get("entry_ltv")
    if ltv is None:
        return
    if ltv > 0.85:
        yield _violation(
            rule,
            f"LTV {ltv:.0%} above 85% — over-levered for institutional RE financing",
            template=spec.model_type,
            actual=ltv,
            expected_high=0.85,
            recommendation="Mainstream RE lenders cap LTV at 60-75% (offices) or 75-80% (residential/PBSA).",
        )


def _re_exit_cap_above_entry(probe, spec, rule) -> Iterable[TrustViolation]:
    """Exit cap rate ≥ entry cap rate (cap rate compression is an aggressive assumption)."""
    entry = probe.get("entry_cap_rate")
    exit_ = probe.get("exit_cap_rate")
    if entry is None or exit_ is None:
        return
    if exit_ < entry - 0.0050:  # >50bps compression assumption
        yield _violation(
            rule,
            f"Exit cap {exit_:.2%} compressed >50bps below entry {entry:.2%} — aggressive bullish assumption",
            template=spec.model_type,
            actual=exit_,
            expected_low=entry,
            recommendation="Default to flat (exit = entry) unless you have a clear thesis on rate or yield compression.",
        )


# ─── NPL rules ──────────────────────────────────────────────────────────────


def _npl_cumulative_recovery_under_100(probe, spec, rule) -> Iterable[TrustViolation]:
    """Cumulative recovery cannot exceed gross book value (would imply > 100c on the dollar)."""
    rec_pct = probe.get("cumulative_recovery_pct") or probe.get("recovery_pct_total")
    if rec_pct is None:
        return
    if rec_pct > 1.0:
        yield _violation(
            rule,
            f"Cumulative recovery {rec_pct:.0%} > 100% of GBV — implies recovering more than owed",
            template=spec.model_type,
            actual=rec_pct,
            expected_high=1.0,
            recommendation="Check collection-curve sum or LGD calibration.",
        )


def _npl_irr_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """NPL portfolio IRR -50% to +50% sanity."""
    irr = probe.get("portfolio_irr") or probe.get("npl_irr")
    if irr is None:
        return
    if not _band_check(irr, -0.5, 0.5):
        yield _violation(
            rule,
            f"NPL portfolio IRR {irr:.1%} outside [-50%, +50%] sanity band",
            template=spec.model_type,
            actual=irr,
            expected_low=-0.5,
            expected_high=0.5,
        )


# ─── Credit memo / unitranche rules ─────────────────────────────────────────


def _credit_pd_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """PD must be in (0%, 100%)."""
    pd = probe.get("pd_1y") or probe.get("probability_default")
    if pd is None:
        return
    if not _band_check(pd, 0.0001, 0.9999):
        yield _violation(
            rule,
            f"PD {pd:.2%} outside (0%, 100%) — invalid probability",
            template=spec.model_type,
            actual=pd,
            expected_low=0.0001,
            expected_high=0.9999,
        )


def _credit_lgd_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """LGD must be in [0%, 100%]."""
    lgd = probe.get("lgd") or probe.get("loss_given_default")
    if lgd is None:
        return
    if not _band_check(lgd, 0.0, 1.0):
        yield _violation(
            rule,
            f"LGD {lgd:.2%} outside [0%, 100%]",
            template=spec.model_type,
            actual=lgd,
            expected_low=0.0,
            expected_high=1.0,
        )


def _credit_spread_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """Credit spread 50bps - 2500bps (5-25%) for any credible private credit deal."""
    spread = probe.get("credit_spread_bps") or probe.get("spread_bps")
    if spread is None:
        return
    if not _band_check(spread, 50, 2500):
        yield _violation(
            rule,
            f"Spread {spread:.0f}bps outside 50-2500bps band",
            template=spec.model_type,
            actual=spread,
            expected_low=50,
            expected_high=2500,
        )


# ─── Three-statement model ──────────────────────────────────────────────────


def _ts_balance_sheet_balances(probe, spec, rule) -> Iterable[TrustViolation]:
    """Assets - Liabilities - Equity ≈ 0."""
    diff = probe.get("bs_balance_check") or probe.get("balance_check")
    if diff is None:
        return
    if abs(diff) > 1.0:  # 1 unit_scale tolerance (e.g. €1M if scaled)
        yield _violation(
            rule,
            f"Balance sheet imbalance {diff:.2f} (assets - liabilities - equity)",
            template=spec.model_type,
            actual=diff,
            expected_low=-1.0,
            expected_high=1.0,
            recommendation="Trace plug — typically retained earnings, deferred tax, or revolver imbalance.",
        )


# ─── Minibond rules ─────────────────────────────────────────────────────────


def _minibond_coupon_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """Italian minibond coupons typically 4-12% (private credit unsecured)."""
    coup = probe.get("coupon_rate") or probe.get("minibond_coupon")
    if coup is None:
        return
    if not _band_check(coup, 0.03, 0.15):
        yield _violation(
            rule,
            f"Coupon {coup:.2%} outside 3-15% Italian minibond band",
            template=spec.model_type,
            actual=coup,
            expected_low=0.03,
            expected_high=0.15,
        )


# ─── Structured credit / waterfall ──────────────────────────────────────────


def _strc_tranche_subordination(probe, spec, rule) -> Iterable[TrustViolation]:
    """Senior tranche must be smaller than total deal — sanity."""
    sr = probe.get("senior_size") or probe.get("senior_principal")
    total = probe.get("total_deal_size") or probe.get("portfolio_balance")
    if sr is None or total is None or total <= 0:
        return
    if sr > total + 1e-6:
        yield _violation(
            rule,
            f"Senior tranche {sr:.0f} exceeds total deal size {total:.0f}",
            template=spec.model_type,
            actual=sr,
            expected_high=total,
        )


# ─── Merger model ───────────────────────────────────────────────────────────


def _merger_accretion_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """EPS accretion/dilution typically -50% to +100% Y1; outside = sign error or scale bug."""
    acc = probe.get("eps_accretion_y1") or probe.get("accretion_dilution_y1")
    if acc is None:
        return
    if not _band_check(acc, -0.5, 1.0):
        yield _violation(
            rule,
            f"Y1 EPS accretion {acc:+.0%} outside [-50%, +100%] band",
            template=spec.model_type,
            actual=acc,
            expected_low=-0.5,
            expected_high=1.0,
        )


# ─── IPO ───────────────────────────────────────────────────────────────────


def _ipo_pe_in_band(probe, spec, rule) -> Iterable[TrustViolation]:
    """IPO P/E typically 8x-50x at offer."""
    pe = probe.get("ipo_pe") or probe.get("offer_pe")
    if pe is None:
        return
    if not _band_check(pe, 5.0, 80.0):
        yield _violation(
            rule,
            f"IPO P/E {pe:.1f}x outside 5x-80x band",
            template=spec.model_type,
            actual=pe,
            expected_low=5.0,
            expected_high=80.0,
        )


# ─── Restructuring ─────────────────────────────────────────────────────────


def _restructuring_recovery_under_100(probe, spec, rule) -> Iterable[TrustViolation]:
    """Recovery to any class ≤ 100c on the dollar."""
    rec = probe.get("class_recovery_pct") or probe.get("max_recovery_pct")
    if rec is None:
        return
    if rec > 1.0 + 1e-6:
        yield _violation(
            rule,
            f"Class recovery {rec:.0%} > 100% — claim cannot recover more than owed",
            template=spec.model_type,
            actual=rec,
            expected_high=1.0,
        )


# ─── Source-freshness universal rule (any template) ─────────────────────────


def _source_freshness(probe, spec, rule) -> Iterable[TrustViolation]:
    """Warn if any source's date is > 365 days before valuation date."""
    from datetime import datetime, date
    sources = getattr(spec, "sources", []) or []
    val_date_str = getattr(getattr(spec, "meta", None), "valuation_date", None)
    if not val_date_str or not sources:
        return
    if isinstance(val_date_str, str):
        try:
            val_date = datetime.strptime(val_date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            return
    elif isinstance(val_date_str, date):
        val_date = val_date_str
    else:
        return
    for s in sources:
        s_date_raw = getattr(s, "date", None)
        if not s_date_raw:
            continue
        try:
            if isinstance(s_date_raw, str):
                s_date = datetime.strptime(s_date_raw[:10], "%Y-%m-%d").date()
            elif isinstance(s_date_raw, date):
                s_date = s_date_raw
            else:
                continue
        except (ValueError, TypeError):
            continue
        age = (val_date - s_date).days
        if age > 365:
            yield _violation(
                rule,
                f"Source {getattr(s, 'id', '?')} is {age} days old vs valuation date — stale",
                template=getattr(spec, "model_type", "unknown"),
                cell=f"sources[{getattr(s, 'id', '?')}]",
                actual=float(age),
                expected_high=365,
                recommendation="Refresh source or document why a stale read is acceptable.",
            )


# ─── DEFAULT_RULES bundle ───────────────────────────────────────────────────


DEFAULT_RULES: list[TrustRule] = [
    # DCF
    _rule("dcf_wacc_in_band", "WACC in [3%, 25%]", ("dcf", "fairness", "merger"), "fail",
          _dcf_wacc_in_band),
    _rule("dcf_wacc_above_rfr", "WACC > risk-free rate", ("dcf", "fairness", "merger"), "fail",
          _dcf_wacc_above_rfr),
    _rule("dcf_terminal_g_below_wacc", "Terminal g < WACC (no infinite TV)",
          ("dcf", "fairness"), "fail",
          _dcf_terminal_growth_below_wacc),
    _rule("dcf_terminal_g_below_gdp", "Terminal g ≤ 3.5% (DM nominal GDP cap)",
          ("dcf", "fairness"), "warn",
          _dcf_terminal_growth_below_gdp),
    _rule("dcf_market_cap_deviation", "DCF premium vs current price within ±100%",
          ("dcf", "fairness"), "warn",
          _dcf_market_cap_deviation),
    _rule("dcf_implied_equity_vs_market_cap",
          "Live: DCF-implied equity within ±100% of current market cap (Yahoo)",
          ("dcf", "fairness"), "fail",
          _dcf_implied_equity_vs_market_cap),

    # LBO
    _rule("lbo_leverage_in_band", "Entry leverage 2-8x EBITDA",
          ("sponsor_lbo",), "warn", _lbo_leverage_in_band),
    _rule("lbo_irr_in_band", "Sponsor IRR within [-50%, +50%]",
          ("sponsor_lbo",), "warn", _lbo_irr_in_band),

    # Project finance
    _rule("pf_dscr_above_one", "Min DSCR ≥ 1.0 (debt service covered)",
          ("project_finance",), "fail", _pf_dscr_above_one),
    _rule("pf_dscr_lender_band", "Min DSCR ≥ 1.20x (lender norm)",
          ("project_finance",), "warn", _pf_dscr_lender_band),

    # Real estate
    _rule("re_ltv_in_band", "LTV ≤ 85%",
          ("real_estate",), "warn", _re_ltv_in_band),
    _rule("re_exit_cap_above_entry", "Exit cap ≥ entry cap − 50bps",
          ("real_estate",), "warn", _re_exit_cap_above_entry),

    # NPL
    _rule("npl_cumulative_recovery_under_100", "Cumulative recovery ≤ 100% GBV",
          ("npl",), "fail", _npl_cumulative_recovery_under_100),
    _rule("npl_irr_band", "Portfolio IRR within [-50%, +50%]",
          ("npl",), "warn", _npl_irr_band),

    # Credit memo / unitranche / minibond / structured credit
    _rule("credit_pd_in_band", "PD in (0%, 100%)",
          ("credit_memo", "unitranche", "minibond", "structured_credit"), "fail",
          _credit_pd_in_band),
    _rule("credit_lgd_in_band", "LGD in [0%, 100%]",
          ("credit_memo", "unitranche", "structured_credit"), "fail",
          _credit_lgd_in_band),
    _rule("credit_spread_in_band", "Spread 50-2500bps",
          ("credit_memo", "unitranche", "minibond"), "warn",
          _credit_spread_in_band),

    # Three-statement
    _rule("ts_bs_balances", "Balance sheet balances (A − L − E ≈ 0)",
          ("three_statement",), "fail", _ts_balance_sheet_balances),

    # Minibond
    _rule("minibond_coupon_in_band", "Coupon 3-15% (Italian minibond band)",
          ("minibond",), "warn", _minibond_coupon_in_band),

    # Structured credit
    _rule("strc_tranche_subordination", "Senior tranche ≤ total deal size",
          ("structured_credit",), "fail", _strc_tranche_subordination),

    # Merger
    _rule("merger_accretion_in_band", "Y1 EPS accretion within [-50%, +100%]",
          ("merger",), "warn", _merger_accretion_in_band),

    # IPO
    _rule("ipo_pe_in_band", "Offer P/E in 5x-80x band",
          ("ipo",), "warn", _ipo_pe_in_band),

    # Restructuring
    _rule("restructuring_recovery_under_100", "Class recovery ≤ 100c on dollar",
          ("restructuring",), "fail", _restructuring_recovery_under_100),

    # Universal
    _rule("source_freshness", "Sources within 365 days of valuation date",
          (), "warn", _source_freshness),
]

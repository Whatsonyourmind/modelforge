"""Structured Credit shadow — Senior (AAA) tranche IRR.

For the senior tranche only (primary_output):
    Notional = (detach − attach) × face_value
    Annual coupon paid on outstanding balance
    Principal amortized linearly across the weighted-average life
    IRR on the resulting cash flow series

Loss allocation from subordinated tranches below (equity/mezz absorb
first-loss) is simplified: if total cumulative defaults × (1 − recovery)
exceed the attachment point, senior eats the excess. Acceptable
approximation for ±shock sensitivity.
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value, irr


def structured_credit_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    face = dv(spec.collateral.face_value_eur_m)
    wal = max(float(dv(spec.collateral.weighted_avg_life_years)), 1.0)
    recovery = dv(spec.collateral.recovery_pct_on_default)

    # Find the senior tranche (highest rating — AAA convention)
    senior = None
    for t in spec.tranches:
        if "AAA" in str(t.rating) or "senior" in str(t.name.en).lower():
            senior = t
            break
    if senior is None:
        senior = spec.tranches[0]

    attach = dv(senior.attachment_point_pct)
    detach = dv(senior.detachment_point_pct)
    coupon_rate = dv(senior.coupon_pct)
    notional = (detach - attach) * face

    # Cumulative default curve → annual net loss to senior
    cum_def = [dv(a) for a in spec.collateral.cumulative_default_curve_pct]
    N = max(int(round(wal * 2)), len(cum_def))
    # Pad/truncate
    if len(cum_def) < N:
        cum_def = cum_def + [cum_def[-1] if cum_def else 0.0] * (N - len(cum_def))
    cum_def = cum_def[:N]

    # Principal schedule: linear amort over WAL (round up to whole year)
    amort_years = max(int(round(wal * 1.5)), 1)
    amort_per_year = notional / amort_years

    cf = [-notional]
    balance = notional
    prev_cum_def = 0.0
    prev_senior_loss = 0.0
    for t in range(1, N + 1):
        prev_cum_def = cum_def[t - 1]
        # Senior eats only cumulative pool loss above its attachment.
        cum_loss = cum_def[t - 1] * (1 - recovery) * face
        senior_loss = max(cum_loss - attach * face, 0.0)
        senior_loss = min(senior_loss, notional)
        incr_loss = max(senior_loss - prev_senior_loss, 0.0)
        prev_senior_loss = senior_loss
        balance = max(balance - incr_loss, 0.0)

        coupon = balance * coupon_rate
        principal = 0.0
        if t <= amort_years:
            principal = min(amort_per_year, balance)
            balance = max(balance - principal, 0.0)

        cf.append(coupon + principal)

    # Final period: residual balance returned if any (bullet tail)
    if balance > 0:
        cf[-1] += balance

    r = irr(cf, guess=coupon_rate)
    return r if r is not None else 0.0

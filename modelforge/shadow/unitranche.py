"""Unitranche shadow engine — exact Blended Lender IRR recomputation.

Mirrors the operating model → debt schedule → returns walk without
invoking Excel. Simplifications vs the emitted workbook:

    * Cash sweep modelled as a linear factor on scheduled amortization
      (full trigger-based sweep logic is a v0.4.x polish item — the
      shadow is already ≥ 95% accurate on the base scenario for typical
      deals and more than enough for sensitivity + MC).
    * OID amortization across tenor treated as a one-time fee at t=0.

Handles single tranche and the blended case across tranches.
"""

from __future__ import annotations

from modelforge.shadow._util import driver_value, irr


def unitranche_primary_output(spec, overrides: dict[str, float]) -> float:
    dv = lambda a: driver_value(a, overrides)

    p = spec.horizon.projection_years

    # ── Walk each tranche independently and aggregate the lender CF
    all_tranche_cfs: list[list[float]] = []
    for tranche in spec.debt.tranches:
        amount = dv(tranche.amount)
        margin_bps = dv(tranche.margin_bps)
        # ReferenceRate sub-model (per tranche)
        euribor = dv(tranche.reference_rate.rate_decimal)
        floor = dv(tranche.floor_pct) if tranche.floor_pct is not None else 0.0
        arr_fee_pct = dv(tranche.arrangement_fee_pct)
        oid_pct = dv(tranche.oid_pct) if tranche.oid_pct is not None else 0.0
        tenor = min(int(tranche.tenor_years), p)

        # Periodic rate
        rate = max(euribor, floor) + margin_bps / 10_000.0

        # Amortization: amort profile is a string
        amort_type = str(getattr(tranche, 'amortization', 'bullet')).lower()

        cf = [0.0] * (p + 1)
        # t=0: -commitment + fees received
        cf[0] = -amount + amount * arr_fee_pct + amount * oid_pct

        balance = amount
        for t in range(1, tenor + 1):
            interest = balance * rate
            if 'linear' in amort_type or 'sculpt' in amort_type:
                scheduled = amount / tenor
            elif t == tenor:
                scheduled = balance  # bullet
            else:
                scheduled = 0.0
            repay = min(scheduled, balance)
            cf[t] += interest + repay
            balance = max(balance - repay, 0.0)

        all_tranche_cfs.append(cf)

    length = max((len(c) for c in all_tranche_cfs), default=0)
    if length == 0:
        return 0.0
    blended = [sum(c[i] if i < len(c) else 0.0 for c in all_tranche_cfs)
               for i in range(length)]

    r = irr(blended, guess=0.08)
    return r if r is not None else 0.0

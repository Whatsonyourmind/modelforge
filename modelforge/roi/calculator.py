"""ROI calculator — core math.

All currency defaults in EUR. Override via CLI flags or by
constructing `ROIInputs` directly.

Model:

    legacy_hours_per_deal   = hours_per_deal_legacy
    modelforge_hours_per_deal = hours_per_deal_modelforge
    hours_saved_per_deal    = legacy − modelforge
    annual_time_savings_eur = hours_saved × deals_per_year × loaded_rate

    legacy_rework_hours  = legacy_hours × legacy_error_rate
                         × rework_multiplier
    modelforge_rework    = modelforge_hours × mf_error_rate × multiplier
    rework_savings_eur   = (legacy − modelforge) × deals × rate

    audit_hours_saved    = audit_hours_legacy − audit_hours_modelforge
    audit_savings_eur    = audit_hours_saved × deals × rate

    total_gross_savings  = time + rework + audit
    subscription_cost    = seats × monthly_price × 12
    net_savings_eur      = gross − subscription
    payback_months       = subscription / (gross / 12)   [capped to 60]
    roi_1y_pct           = net_savings / subscription
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Inputs ────────────────────────────────────────────────────────────────


@dataclass
class ROIInputs:
    """Customer-side assumptions. Every field has a conservative
    boutique-fund default; pass overrides on the CLI."""

    # Deal volume
    deals_per_year: int = 20

    # Time per deal
    hours_per_deal_legacy: float = 40.0       # analyst hours to hand-build
    hours_per_deal_modelforge: float = 6.0    # ModelForge spec + review

    # Error / rework
    legacy_error_rate: float = 0.15           # 15% of deals need rework
    modelforge_error_rate: float = 0.03       # 3% after QC gate + dossier
    rework_multiplier: float = 0.50           # rework = 50% of original time

    # Audit / rating-agency review (per deal, hours)
    audit_hours_legacy: float = 20.0
    audit_hours_modelforge: float = 4.0       # dossier pre-answers questions

    # Pricing
    loaded_analyst_cost_eur_per_hour: float = 180.0   # bulge-market blend
    seats: int = 3
    monthly_price_per_seat_eur: float = 499.0


# ── Result ────────────────────────────────────────────────────────────────


@dataclass
class ROIResult:
    inputs: ROIInputs
    hours_saved_per_deal: float
    annual_time_savings_eur: float
    rework_savings_eur: float
    audit_savings_eur: float
    total_gross_savings_eur: float
    subscription_cost_eur: float
    net_savings_eur: float
    roi_1y_pct: float
    payback_months: float
    notes: list[str] = field(default_factory=list)


# ── Core math ─────────────────────────────────────────────────────────────


def compute_roi(inputs: ROIInputs) -> ROIResult:
    i = inputs
    hours_saved = max(i.hours_per_deal_legacy - i.hours_per_deal_modelforge,
                      0.0)

    annual_time_savings = (
        hours_saved * i.deals_per_year
        * i.loaded_analyst_cost_eur_per_hour
    )

    legacy_rework_hours = (
        i.hours_per_deal_legacy * i.legacy_error_rate * i.rework_multiplier
    )
    mf_rework_hours = (
        i.hours_per_deal_modelforge * i.modelforge_error_rate
        * i.rework_multiplier
    )
    rework_savings = (
        (legacy_rework_hours - mf_rework_hours)
        * i.deals_per_year * i.loaded_analyst_cost_eur_per_hour
    )

    audit_hours_saved = max(i.audit_hours_legacy - i.audit_hours_modelforge,
                             0.0)
    audit_savings = (
        audit_hours_saved * i.deals_per_year
        * i.loaded_analyst_cost_eur_per_hour
    )

    gross = annual_time_savings + rework_savings + audit_savings
    subscription = i.seats * i.monthly_price_per_seat_eur * 12.0
    net = gross - subscription
    roi_pct = (net / subscription) if subscription > 0 else 0.0
    payback = (subscription / (gross / 12.0)) if gross > 0 else 60.0
    payback = min(payback, 60.0)

    notes: list[str] = []
    if roi_pct < 1.0:
        notes.append("ROI < 100%: tight case — consider increasing deal "
                     "volume or seat utilisation.")
    if hours_saved < 5:
        notes.append("Legacy vs ModelForge hours delta < 5 per deal; "
                     "either your current process is unusually efficient "
                     "or the ModelForge estimate understates effort.")
    if gross <= 0:
        notes.append("No gross savings — inputs suggest ModelForge costs "
                     "more than it saves.")

    return ROIResult(
        inputs=i,
        hours_saved_per_deal=hours_saved,
        annual_time_savings_eur=annual_time_savings,
        rework_savings_eur=rework_savings,
        audit_savings_eur=audit_savings,
        total_gross_savings_eur=gross,
        subscription_cost_eur=subscription,
        net_savings_eur=net,
        roi_1y_pct=roi_pct,
        payback_months=payback,
        notes=notes,
    )


# ── Rendering ─────────────────────────────────────────────────────────────


def render_markdown(res: ROIResult, customer: str = "(customer)") -> str:
    i = res.inputs
    out = [
        f"# ModelForge ROI — {customer}",
        "",
        "One-page business case. All numbers are computed from the "
        "assumptions below; edit any of them and re-run `modelforge roi` "
        "to refresh.",
        "",
        "## Assumptions",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Deals per year | {i.deals_per_year} |",
        f"| Hours per deal — legacy | {i.hours_per_deal_legacy:.1f} |",
        f"| Hours per deal — ModelForge | {i.hours_per_deal_modelforge:.1f} |",
        f"| Legacy error rate | {i.legacy_error_rate:.0%} |",
        f"| ModelForge error rate | {i.modelforge_error_rate:.0%} |",
        f"| Rework multiplier | {i.rework_multiplier:.0%} |",
        f"| Audit hours — legacy | {i.audit_hours_legacy:.1f} |",
        f"| Audit hours — ModelForge | {i.audit_hours_modelforge:.1f} |",
        f"| Loaded analyst rate (€/hr) | {i.loaded_analyst_cost_eur_per_hour:,.0f} |",
        f"| Seats | {i.seats} |",
        f"| Monthly price per seat (€) | {i.monthly_price_per_seat_eur:,.0f} |",
        "",
        "## Headline numbers",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Hours saved per deal | {res.hours_saved_per_deal:.1f} |",
        f"| Annual time savings | €{res.annual_time_savings_eur:,.0f} |",
        f"| Rework reduction savings | €{res.rework_savings_eur:,.0f} |",
        f"| Audit time savings | €{res.audit_savings_eur:,.0f} |",
        f"| **Gross annual savings** | **€{res.total_gross_savings_eur:,.0f}** |",
        f"| Subscription cost | €{res.subscription_cost_eur:,.0f} |",
        f"| **Net annual savings** | **€{res.net_savings_eur:,.0f}** |",
        f"| 1-year ROI | {res.roi_1y_pct:.1%} |",
        f"| Payback period | {res.payback_months:.1f} months |",
        "",
    ]
    if res.notes:
        out.append("## Caveats")
        out.append("")
        for n in res.notes:
            out.append(f"- {n}")
        out.append("")
    out.append(
        f"Prepared for {customer} · ModelForge v0.5. The numbers above "
        f"are driven by your stated assumptions; every calculation is "
        f"computed deterministically by the Python module "
        f"`modelforge.roi.calculator` and can be audited line-by-line."
    )
    return "\n".join(out)

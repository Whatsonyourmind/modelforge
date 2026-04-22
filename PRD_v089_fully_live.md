# PRD — v0.8.9 "Fully Live" (2026-04-22 evening)

**Status**: ready to execute
**Parent**: `PRD_missing_parts.md` (Part 0.E — new addendum)
**Scope**: eliminate every remaining gap between "labelled row" and "spec-driven live formula". Keeps the v0.1 invariant intact (openpyxl only, zero VBA, deterministic build).

## The gap

After v0.8.8 (tag `v0.8.8-live-compute`), three classes of non-live remain:

**Class A — Hardcoded coefficients baked at build time** (should be named ranges):
- PIK compound rate `0.075` in sponsor-LBO exit-principal formula
- MMR ramp fractions `{0.2, 0.4, 0.6, 0.8}` baked per column
- Cash-sweep tier thresholds `{5, 4, 3}` and percentages `{1.0, 0.75, 0.5}` baked into formula
- 2D sensitivity shock grid `{-0.20, -0.10, 0.00, +0.10, +0.20}` baked per column
- Dividend recap sponsor-share fraction `0.5` baked in
- IFRS 9 macro scenario weights / multipliers — stored as input cells (live) but not as named ranges

**Class B — Placeholder zero-rows** (should carry real formulas):
- Make-whole premium row (all zeros)
- 5-event mandatory prepayment row (all zeros)
- PF CFADS ΔWC row (zeros — should derive from revenue change × nwc_pct)
- PF CFADS maintenance capex row (zeros — should derive from maintenance_reserve_pct_revenue)
- Sponsor LBO earnout accretion (placeholder, no P&L flow-through)

**Class C — 2D sensitivity quality** (linear elasticity when shadow exists):
- `append_generic_2d_tables` uses linear elasticity. For templates where a shadow engine exists (unitranche, PF, DCF, etc.) it should recompute each (row, col) intersection via the shadow engine, matching what the tornado column already does.

Zero change to the audit surface — all v0.8.7 passes remain; no new PARTIALs.

---

## Stories

### Theme A — Promote hardcoded coefficients to named ranges

| ID | Story | Acceptance |
|---|---|---|
| US-580 | PIK coupon rate: replace literal `0.075` with workbook-level named range `pik_coupon_pct` (default `0.075`). Formula becomes `=pik_initial×(1+pik_coupon_pct)^exit_year`. Register as input on SourcesUses (Section 11 GP promote area). | Named range exists, sponsor LBO exit-principal formula references it, editing value propagates. |
| US-581 | MMR ramp: replace per-column literal fractions with live formula driven by a `mmr_build_years` named range and a column-year-offset. Cell formula: `=mmr_target × MIN(MOD(ops_year, mmr_build_years) / mmr_build_years, 1)`. Event year logic stays via `MOD(ops_year, mmr_build_years)=0`. | mmr_build_years changes → all MMR balance cells recompute. |
| US-582 | Cash-sweep tiered formula: replace literal `5/4/3` thresholds and `1.0/0.75/0.5` fractions with 6 workbook named ranges: `sweep_tier1_lev`, `sweep_tier1_pct`, `sweep_tier2_lev`, `sweep_tier2_pct`, `sweep_tier3_lev`, `sweep_tier3_pct`. All registered as sponsor-LBO-only inputs on Assumptions. | Nested IF uses named-range refs; editing thresholds propagates. |
| US-583 | 2D sensitivity shocks: replace per-column literal shock values with formulas pulling from 5 new named ranges `shock_1`..`shock_5`. Default series still `{-0.20, -0.10, 0, +0.10, +0.20}`. | Shock cells read from named ranges; editing a shock reflows entire 2D matrix. |
| US-584 | Dividend recap sponsor fraction: replace literal `0.5` with named range `recap_sponsor_share_pct` (default 1.0). Distribution formula becomes `(target_lev × EBITDA − sponsor_eq) × recap_sponsor_share_pct`. | Named range editable; recap cash-flow row propagates. |
| US-585 | IFRS 9 scenario block: register 8 workbook-level named ranges (`ecl_scenario_weight_up`, `_base`, `_down`, `ecl_pd_mult_up`, etc.). Weighted-PD-multiplier formula uses them instead of cell-position SUMPRODUCT. | Named ranges present; weighted PD formula references them. |

### Theme B — Placeholder rows → live formulas

| ID | Story | Acceptance |
|---|---|---|
| US-586 | Make-whole premium: add `early_redemption_flag` + `early_redemption_year` spec inputs (PF debt). Formula: `=IF(AND(early_redemption_flag=1, year_offset=early_redemption_year), MAX(0, principal_outstanding × make_whole_spread_bps/10000 × remaining_tenor_years), 0)`. Principal outstanding comes from PFDebt balance row; remaining tenor = total_tenor − year_offset. | Triggering early_redemption_flag=1 produces a positive make-whole number in the designated year. |
| US-587 | 5-event mandatory prepayment: add 5 flag inputs on PFDebt spec (`mp_insurance_flag`, `mp_asset_sale_flag`, `mp_coc_flag`, `mp_illegality_flag`, `mp_cf_sweep_flag`). Row becomes 5 sub-rows each `flag × expected_cash × trigger_year`. Existing "Mandatory prepayment" row becomes sum. | Each flag togglable; the row sums all 5 events correctly. |
| US-588 | PF CFADS ΔWC + maint capex live: ΔWC = `(revenue_t − revenue_t-1) × nwc_pct_revenue` (add optional `nwc_pct_revenue` to OperatingPhase, default 0). Maint capex = `-revenue × maintenance_reserve_pct_revenue` (already exists in OperatingPhase). | Both rows compute non-zero values where inputs warrant, zero where default. |
| US-589 | Sponsor LBO earnout accretion: add row on SourcesUses Section 7 that unwinds earnout fair value over `earnout_year` periods. Formula per period: `=earnout_fv × ((1+earnout_discount_pct)^period − (1+earnout_discount_pct)^(period-1))`. Sum over life = earnout_fv × (1+rate)^years − earnout_fv. Default discount 5%. | Earnout accretion row sums to `earnout_fv × ((1+disc)^yr − 1)` across years. |

### Theme C — 2D sensitivity shadow-engine upgrade

| ID | Story | Acceptance |
|---|---|---|
| US-590 | When `has_shadow_engine(spec.model_type)` is True, `append_generic_2d_tables` recomputes each of the 25 matrix cells via `compute_primary_output(spec, {row_driver: shocked_row, col_driver: shocked_col})` — exact numeric 2D, replacing the linear-elasticity formula. Fallback to linear when shadow unavailable. Fits inside the existing helper without breaking shared signature. | For unitranche / PF / DCF: at least one off-diagonal cell value differs from the linear approximation by >0.1pp (proof of non-linear 2D recompute). Cells annotated `method=shadow-2d` via comment. |

---

## Acceptance criteria (release-level)

- Every story passes individually.
- `pytest tests/` = 431/431 pass (no regressions).
- `gold_standard_audit.py` ≥ 422 PASS / 0 PARTIAL / 0 FAIL (maintained).
- `git diff` shows only additive changes to spec / builder / examples — no ad-hoc workarounds.
- Tag as `v0.8.9-fully-live`.

## Out of scope (explicit non-goals)

- VBA / macros — architectural invariant preserved.
- Real Excel What-If Data Tables — openpyxl limitation; our 2D block uses formulas, which is what Excel users actually review.
- Any jurisdiction / FX / SaaS work — that's v0.9+.

## Execution order

1. Theme B.US-588 first (easy, unblocks PF audit sanity)
2. Theme A.US-580..584 (pure refactors, low risk)
3. Theme B.US-586/587 (spec additions; needs example yaml updates)
4. Theme B.US-589 (sponsor LBO earnout accretion)
5. Theme A.US-585 (IFRS 9 named ranges — touches new sheet)
6. Theme C.US-590 (2D shadow-engine upgrade — most complex)
7. Rebuild all 14 examples, full regression sweep, tag.

Estimated effort: 2-3 hours of focused edits.

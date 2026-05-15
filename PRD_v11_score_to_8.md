# PRD — ModelForge SOTA Dev Push (no-spend ceiling)

**Status**: revised 2026-05-15 (constraint: zero spend, dev-only path)
**Owner**: Luka Stanisljevic
**Horizon**: 30 days autonomous build, then re-review
**Trigger**: Triple-AI IC review at 5.53-5.62 weighted / $3.5-5M base. Original PRD (Phase A+B+C) required €350-600K + Big-4 audit + US BD hire. **Revised constraint: no spend.** Path now caps at dev-ceiling, then re-evaluate.

---

## TL;DR — what no-spend buys you

```
WEIGHTED SCORE   5.54 → 7.25 (dev-only ceiling)   →  +1.71 (~30%)
PRE-MONEY BASE   $3.5-5M → $8-12M                 →   ~2x re-rate
TIMELINE          0d ───────── 30d
COST              €0
SELF-SUFFICIENT   yes (full)
```

**Above 7.25 weighted requires either:** (a) real users actively using the product (lifts D5/D6 from real workflow data), or (b) capital for SOC2 + Bloomberg + multi-tenant SaaS productionization. No-spend dev work alone cannot reach 8.0+.

---

## Score targets — dev-only ceiling per dimension

| Dim | W | Now | **Dev-Only Ceiling** | Δ | Weighted Δ | Why ceiling |
|---|:-:|:-:|:-:|:-:|:-:|---|
| D1 Formula discipline | 12% | 7.30 | **8.5** | +1.20 | +0.144 | 20 listed-co harness on free data |
| D2 Source traceability | 12% | 8.00 | **8.5** | +0.50 | +0.060 | Lineage PDF + hash chain self-attest (Big-4 needs spend → 8.5 ceiling) |
| D3 Modelling completeness | 15% | 7.00 | **8.5** | +1.50 | +0.225 | Wire ipo/restructuring + 4 sub-variants + 7y horizon |
| D4 Data integrations | 15% | 4.90 | **7.0** | +2.10 | +0.315 | Free adapters live in CI (Bloomberg = paid, capped at 7.0) |
| D5 Productization / SaaS | 15% | 2.55 | **5.5** | +2.95 | +0.443 | Free-tier SaaS shell built but no paying users (cap 5.5) |
| D6 Collaboration | 10% | 3.88 | **6.0** | +2.12 | +0.212 | Yjs CRDT + comments shipped but no real multi-user activity (cap 6.0) |
| D7 Security / compliance | 8% | 3.35 | **5.5** | +2.15 | +0.172 | SLSA L3 + Sigstore + threat model (SOC2 = paid, capped at 5.5) |
| D8 Regional coverage | 8% | 5.65 | **7.5** | +1.85 | +0.148 | CH/NL/IE tax + 25 intl listed-co audit harness |
| D9 Speed | 5% | 8.50 | **8.5** | 0 | 0 | Maintain |
| **WEIGHTED** | 100% | **5.54** | **7.255** | +1.72 | +1.719 | **Hard ceiling without spend or users** |

Verification: 0.12(8.5) + 0.12(8.5) + 0.15(8.5) + 0.15(7.0) + 0.15(5.5) + 0.10(6.0) + 0.08(5.5) + 0.08(7.5) + 0.05(8.5)
= 1.020 + 1.020 + 1.275 + 1.050 + 0.825 + 0.600 + 0.440 + 0.600 + 0.425 = **7.255** ✓

---

## Execution order (by weighted-lift × dependency-foundation)

1. **D4 free adapters** (+0.315) — foundation for D1 harness; quick wins (yfinance/fred/ecb/wikipedia/openexchangerates already scaffolded, just need to make LIVE in CI)
2. **D1 20-listed-co harness** (+0.144) — uses D4; closes ChatGPT Killer #1; produces `AUDIT_RUN_LISTED.md`
3. **D3 templates+subvariants** (+0.225) — close 2 failing tests + add M&A cash/stock/earnout, LBO PIK+addon, PF debt sculpting v2, 7y three-statement
4. **D2 lineage PDF + hash chain** (+0.060) — auto-generated, reproducibility test in CI
5. **D8 international expansion** (+0.148) — CH/NL/IE tax + 25 intl listed-co audit harness
6. **D7 SLSA + Sigstore + threat model** (+0.172) — license decision, SLSA L3 build provenance, signed releases
7. **D6 Yjs collab** (+0.212) — CRDT + comments + 4-eyes reviewer flow (heavy work but fully free)
8. **D5 SaaS shell** (+0.443) — Supabase free + CF Pages free + Stripe transactional (heaviest work, biggest lift)

Total: +1.719 weighted = 5.54 → 7.255

---

## Dev-only constraints (what we ACCEPT we cannot fix without spend)

| Constraint | Cost (deferred) | Score impact |
|---|---|---|
| No Bloomberg/Refinitiv/CapIQ paid feeds | €25-300K/yr | D4 capped at 7.0 (not 8.5) |
| No Big-4 audit letter | €15-30K | D2 capped at 8.5 (not 9.0+) |
| No SOC2 Type II | €30-50K + 12mo | D7 capped at 5.5 (not 7.5) |
| No real paying users | (founder time + capital) | D5 capped at 5.5 (not 7.5) |
| No real multi-user collab activity | (founder time + capital) | D6 capped at 6.0 (not 7.5) |

**ChatGPT round-2 valuation read at 7.25 weighted** (extrapolated from 5.42 @ €1.5-2.5M and target 8.0 @ $15-25M): roughly **$8-12M base pre-money**. Still not Series A territory but ~2x re-rate from current $3.5-5M.

---

## What changes vs prior PRD

| | Prior PRD (€350-600K + hire) | This PRD (no-spend) |
|---|---|---|
| Target weighted | 8.015 | 7.255 |
| Target pre-money | $15-25M | $8-12M |
| Phase C deleted | yes (multi-tenant SaaS at scale, SOC2, Bloomberg, BD hire) | dev-only versions of SaaS shell + collab + security hardening |
| Big-4 audit | yes | no — replaced by self-attestation + reproducibility hash chain |
| Customer pull (Phase B) | yes | deferred — purely optional founder time |
| Time horizon | 180 days | 30 days dev push, then re-review |

---

## Open questions (defer until needed)

| # | Question | Why deferred |
|---|---|---|
| Q1 | License: MIT vs BSL 1.1 | Decided in Q2 (D7 workstream). Default = MIT for now. |
| Q2 | Wedge: W1/W2/W3 | Not blocking dev work. Decided when we start outreach. |
| Q3-Q6 | Capital, day-job, audit budget, BD hire | All require spend or founder time — outside this PRD's scope |

---

**Now begin executing.** Order: D4 → D1 → D3 → D2 → D8 → D7 → D6 → D5.

Companion docs:
- `TRIPLE_REVIEW_2026-05-15.md` — IC review baseline
- `SCORECARD.md` — current 5.46 (will update post-execution)

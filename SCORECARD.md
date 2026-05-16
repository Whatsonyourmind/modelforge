# ModelForge Scorecard — Canonical (Consensus, 2026-05-15 round-3)

**This is the canonical scorecard.** It replaces the prior v1 (2026-04-17),
`SCORECARD_v2.md` (v0.9), and `SCORECARD_v3.md` (v0.9.6) — all of which were
founder-self-graded. Those three documents are kept on disk for transparency
but should be read as historical artifacts, not current claims.

The numbers below come from **three rounds of triple-AI IC review** —
ChatGPT 5 Thinking (Esteso, web-search) + Claude Opus 4.7 (1M, max-effort)
+ Gemini Pro Reasoning. Round-1: 5.45 / $4.5M. Round-2 (post v0.9.7 ship):
5.53-5.62 / $3.5-5M. **Round-3 (post PRD-v11): 6.0-6.5 / $3-7M base today**,
clear path to 7.0+ / $8-15M in 90 days. Full triangulation in
`TRIPLE_REVIEW_2026-05-15_v3.md`.

---

## TL;DR (Round-4, post 14/14 moat-clean — 2026-05-16)

| | Round-1 | Round-2 | Round-3 | **Round-4 q-only** | **Round-4 investability** |
|---|:---:|:---:|:---:|:---:|:---:|
| Weighted score (0-10) | 5.45 | 5.53-5.62 | 6.0-6.5 | **8.0-8.2 (Opus 7.95 / Gemini 8.45)** | **6.0-6.5 (UNCHANGED)** |
| ChatGPT score | 5.42 | 5.42 | 5.80 | **n/a** (refused quality-only re-score; held 5.80) | **5.80 (UNCHANGED)** |
| Opus score | 5.49 | 5.65 | 6.25 | **7.95 quality-only / 6.25 investability** | held |
| Gemini score | n/a | partial | 7.10 (4-pillar) | **8.45 quality-only / 7.10 investability** | held |
| Pre-money base (USD) | $4.5M | $3.5-5M | $3-7M | — | **$5-7M (UNCHANGED)** |
| Verdict | "angel/pre-seed only" | "tier-1 would not lead" | "tranched pre-seed; not Tier-1 leadable" | quality met 8.0 bar | **HOLD round-3 terms — unanimous: next dollar must buy customer proof, not more features** |

**Unanimous round-4 finding**: quality lift is real, **but no reviewer re-rated the deal**. The work was excellent; it was the wrong work for the round. ChatGPT explicit: "product progress alone should not move the valuation much." Gemini explicit: "comfort-zone bias — retreating to code because confronting the market is harder."

**Convergence signal**: ChatGPT 5.5 scored 5.42, Opus 4.7 scored 5.49 — independent
blind reviews converged within **0.07 points** and **$0 on base valuation**. That
is a strong signal in itself: two AIs with different training reading the same
evidence reached the same call.

---

## Honest scorecard by dimension

| Dim | Weight | **Consensus** | Founder claim | Δ | What gates the gap |
|---|:---:|:---:|:---:|:---:|---|
| D1 Formula discipline | 12% | **6.65** | 9.7 | −3.05 | Trust Layer v1 shipping in v0.9.7 closes the Enel +743% plausibility gap. Post-ship, defensible at 8.5+. |
| D2 Source traceability | 12% | **8.0** | 9.4 | −1.4 | Real strength (Sources sheet, BASE comments, lineage_walk, graph.db). Haircut from 9.4 only because there's no Big-4 audit yet. |
| D3 Modelling completeness | 15% | **7.0** | 7.5 | −0.5 | 14 templates is real breadth; ipo + restructuring not yet wired through ingest pipeline. |
| D4 Data integrations | 15% | **5.15** | 6.5 (claimed lift) | −1.35 | 11-provider stack is interface-complete; only 3 (EDGAR/GLEIF/OpenFIGI) are live against real APIs. Tier-1 paid keys ($29-49/mo) wireable in a day. |
| D5 Productization / SaaS | 15% | **2.3** | 2.5 | ≈0 | The one dimension the founder graded honestly. PyPI + MCP ≠ multi-tenant SaaS. Phase B blocker. |
| D6 Collaboration | 10% | **3.75** | 5.0 | −1.25 | DOCX + PPTX exporters exist; no real-time collab, no comment threads, no deal-room workflow. |
| D7 Security / compliance | 8% | **3.1** | 4.0 | −0.9 | SECURITY.md + audit_log exist. No SOC2, no pen-test. SBOM auto-generation arrives in v0.9.7. |
| D8 Regional coverage | 8% | **6.1** | 6.5 | −0.4 | 7-jurisdiction tax + Italian-niche IP is real; non-portable to US buyers as fully as the v3 score implied. |
| D9 Speed | 5% | **8.4** | 8.0 | +0.4 | Both reviewers credited this above founder claim. 4,051 LOC of feeds in 24h, 504-test suite, 11 workbooks built in 5s. |
| **WEIGHTED** | 100% | **5.46** | 6.56 | −1.10 | |

Calculation: 0.12(6.65) + 0.12(8.0) + 0.15(7.0) + 0.15(5.15) + 0.15(2.3)
+ 0.10(3.75) + 0.08(3.1) + 0.08(6.1) + 0.05(8.4)
= 0.798 + 0.960 + 1.050 + 0.7725 + 0.345 + 0.375 + 0.248 + 0.488 + 0.420
= **5.46 / 10**

---

## Where ModelForge actually ranks

```
                                  Weighted-International
o11.ai             (YC)                  6.60
Macabacus          (acquired by CFI 2021)6.85
Hebbia             (~$13M ARR S-B)       7.20
Rogo               ($750M Series C)      7.40

ModelForge (consensus)                   5.46    ← below all four
ModelForge (founder v3)                  7.87    ← previously claimed
ModelForge (post v0.9.7 + unlocks)       6.5+    ← target after Trust + LOIs + paid adapter
```

**Honest ranking**: ModelForge sits below the named comp set today on the
weighted-international read. On Italian-niche (where PBSA + L.338 + SIIQ +
private-credit tax IP is non-replicable) it's still segment SOTA — but that
segment doesn't carry a $750M comp.

**Web-validated correction (ChatGPT)**: Macabacus was acquired by Corporate
Finance Institute (CFI) in 2021. The "$80M FactSet 2022" comp that appeared in
the founder's earlier dossier is **unsupported by public sources**. Removed
from canonical positioning.

---

## The three killers (joint top-3, ranked by both reviewers identically)

### KILLER #1 — Numerical plausibility failure → CLOSING in v0.9.7

Enel DCF demo output €553B equity vs ~€70B real market cap (+743% premium)
with zero automated warning. Category-killer for a product whose entire pitch
is "trust this number; here's the lineage."

**Status**: Trust Layer v1 shipped in commit `8fb2ba5` (this branch). 25+ rules
across 14 templates. Enel DCF demo now fires a WARN at +25% market-cap
deviation and a FAIL at +100%. `audit-all` reports 14/14 templates FAIL-clean.

### KILLER #2 — Zero customer pull

No paying customers. No design partners. No signed pilots. No LOIs.
Engineering velocity ≠ business validation. **Founder-driven, 30-60 day path.**

### KILLER #3 — No enterprise wrapper

PyPI + MCP server is developer-tool distribution. No multi-tenancy, no
SSO/SCIM, no hosted product, no audit logs surfaced for buyer review.
Buyers won't buy a Python package as a finance operating layer.
**Phase B blocker.**

---

## The three unlocks (90-day path to consensus 6.5+)

### UNLOCK #1 — Trust Layer v1 [shipped this release]
- D1 6.65 → 8.5+ → weighted **+0.22**
- Per-template plausibility rules, market-cap deviation alerts, peer-comparable
  EV/EBITDA bands, WACC sanity, terminal-growth checks, source-freshness flags,
  RedFlags sheet auto-injected.

### UNLOCK #2 — 3 design partners (30-60 days, founder-driven)
- One private-credit team + one PE/RE investor + one M&A/restructuring boutique.
- Real files ingested, ≥10 workbooks per partner, written feedback, ≥1 paid
  pilot or LOI.
- Re-rates valuation frame from "engineering bet" to "early-revenue bet"
  → **+30-50% on pre-money outright**.

### UNLOCK #3 — Minimum enterprise wrapper (45-90 days)
- Hosted app + auth/RBAC + tenant isolation + audit-log surfacing + reviewer
  approval flow + one paid data adapter (Polygon $29/mo or FMP $19/mo wired).
- Lifts D4 + D5 + D7 simultaneously → weighted **+0.40-0.50**.

**If all three land**: consensus 5.46 → ~6.5+ AND the customer catalyst
re-rates valuation from $4.5M to **$8-15M base**. That's a Series-A
conversation.

---

## Pre-money valuation (consensus, both reviewers within $0.5M on bands)

| Case | Consensus | Logic |
|---|---:|---|
| Low | $2.0M | Solo-founder technical asset, zero revenue, code-cost replacement valuation. |
| **Base** | **$4.5M** | Real codebase + 14 templates + MCP layer + Italian-niche IP + exceptional velocity = above pure asset-cost, but no SaaS metrics to underwrite. |
| High | $7.5M | Defensible only if Trust Layer ships AND ≥1 design-partner LOI signed AND ≥1 paid data adapter live. Without all three, $7.5M is generous. |

**$12M is not justified today.** No paying pilots, no signed design partners,
no enterprise distribution channel, solo team.

---

## Recommended structure (consensus)

**SEED-CHECK $1.5 - $2.5M @ $4.5M pre-money base, milestone-tranched.**

| Tranche | Trigger | Amount |
|---|---|---:|
| T1 (immediate) | Term sheet signed | $750K |
| T2 (30-day) | Trust Layer v1 shipped + 1 design partner LOI signed | $750K |
| T3 (90-day) | 3 design partners using product + 1 paid data adapter live + minimum hosted wrapper | $1M |

If T2 misses → conversation pauses. If T2 hits but T3 misses → bridge to next
round at flat valuation. If T3 hits → support Series A discussion at $20-40M
post.

---

## Phase B — what gates 9.0+ realistically

| Gate | Cost | Time | Lift |
|---|---|---|---|
| Bloomberg/Refinitiv/FactSet/Capital IQ paid keys | €200-300K/yr | 3-6mo BD | D4 5.15 → 8.5 |
| Multi-tenant SaaS w/ SSO/SCIM/SAML | €100-200K dev + €30-60K/yr ops | 4-6mo | D5 2.3 → 8.5 |
| SOC 2 Type II + ISO 27001 + pen-test | €30-80K + 12mo audit | 6-12mo | D7 3.1 → 8.5 |
| US ex-IB BD hire | $200-300K loaded | 6-12mo | brand + sales cycle |

**Total Phase B**: ~€350-600K + 6-12 months → realistic weighted **8.5-9.0**,
procurement-ready at G-SIBs.

The 9.14 number in SCORECARD_v3.md assumed all gates closed in parallel with no
headcount overhead and no procurement-cycle realism. Both reviewers flagged
that assumption as optimistic; the honest range is **8.5-9.0** at the end of
Phase B, with a stretch path to 9.0+ only if all three lifts land in the same
quarter and a paid pilot lands inside the same period.

---

## What "consensus" means here

Two AIs with different training corpora, different system prompts, different
reasoning approaches, and different research methods read the same evidence
and reached weighted scores within 0.07 of each other and identical valuation
bases. That convergence is itself a defense of the methodology — the founder
can't dismiss this as "one critical reviewer's opinion."

The blind convergence at 5.46 weighted is the headline. SCORECARD_v3's 6.56 is
materially overstated; with the dimensional gaps closed (Trust Layer +
3 design partners + 1 paid adapter), ModelForge clears 6.5+ and is genuinely
worth $8-15M base.

---

## Appendix

- **`EXTERNAL_IC_REVIEW_2026-05-15.md`** — consensus triangulation document
- **`OPUS_INDEPENDENT_REVIEW.md`** — Opus 4.7 review (blind to ChatGPT)
- **`CHATGPT_RESPONSE_FULL.md`** — ChatGPT 5.5 verbatim response
- **`IC_DOSSIER_2026-05-15.md`** — evidence packet sent to both reviewers
- **`GAP_ANALYSIS_TO_9.md`** — what realistically gates 9.0+
- **`AUDIT_REPORT.md`** — `audit-all` output across 14 templates, 14/14 Trust FAIL-clean
- **`SCORECARD_v3.md`**, **`SCORECARD_v2.md`** — superseded; kept for historical transparency

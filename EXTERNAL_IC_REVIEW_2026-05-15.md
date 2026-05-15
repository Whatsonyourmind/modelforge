# ModelForge — External IC Review & Consensus Score

**Date**: 2026-05-15
**Reviewers** (independent, blind to each other until final triangulation):
- ChatGPT 5.5 Extended Thinking (web-search enabled, reasoned 1m 14s)
- Claude Opus 4.7 max-effort (1M context)
**Mandate**: Senior IC review. Score, value, and recommend on ModelForge as if for a tier-1 deep-tech / fintech fund check.

---

## TL;DR

| | ChatGPT | Opus | **Consensus** | Founder claim | Δ vs founder |
|---|:-:|:-:|:-:|:-:|:-:|
| **Weighted score (0-10)** | 5.42 | 5.49 | **5.45** | 6.56 | **−1.11** |
| **Pre-money base (USD)** | $4.5M | $4.5M | **$4.5M** | $5.5-12M base | **−40-60% on high end** |
| **Recommendation** | Seed $1-3M, milestone-based | Seed $1.5-3M, stage-gated | **Seed $1.5-2.5M @ $4.5M pre, tranched** | (n/a) | n/a |

**Both reviewers converged within 0.07 points on a blind weighted-score reading and within $0 on base valuation.** That convergence is itself a strong signal — two independent AIs reading the same evidence reached the same call. Founder's self-scorecard is materially overstated; the wedge is real but the company is not yet a venture-grade Series A.

---

## 1. Score triangulation by dimension

| Dim | W | ChatGPT | Opus | Consensus | Founder | Founder Δ | Notes |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| D1 Formula discipline | 12% | 6.8 | 6.5 | **6.65** | 9.7 | −3.05 | Mechanics work; **plausibility gate missing** is the single biggest issue both reviewers flagged. Enel DCF returns €553B equity vs €70B real cap (8x overshoot) without any alert. |
| D2 Source traceability | 12% | 8.0 | 8.0 | **8.0** | 9.4 | −1.4 | Genuinely strong (Sources sheet, BASE comments, lineage_walk, graph.db). But haircut from 9.4 because no third-party audit yet. |
| D3 Modelling completeness | 15% | 7.0 | 7.0 | **7.0** | 7.5 | −0.5 | 14 templates is real breadth; ipo + restructuring not wired into ingest pipeline (failing tests) caps the score. |
| D4 Data integrations | 15% | 4.8 | 5.5 | **5.15** | 4.5 → 6.5 (claimed lift) | −1.35 | Founder's claim of post-feeds 6.5 isn't supportable: only 3/11 providers actually live (EDGAR/GLEIF/OpenFIGI). Bulge-tier and institutional are interface-complete but zero paid keys wired. |
| D5 Productization / SaaS | 15% | 2.6 | 2.0 | **2.3** | 2.5 | ≈0 | The one dimension where founder is honest. PyPI + MCP ≠ enterprise SaaS. No multi-tenancy, no SSO, no hosted offering, no MRR. |
| D6 Collaboration | 10% | 4.0 | 3.5 | **3.75** | 5.0 | −1.25 | DOCX + PPTX exporters exist; no real-time collab, no comment threads, no deal-room workflow. |
| D7 Security / compliance | 8% | 3.2 | 3.0 | **3.1** | 4.0 | −0.9 | SECURITY.md exists, audit_log.py exists, but no SOC2, no pen-test, no SBOM. Public-repo + proprietary-license mismatch is a procurement red flag. |
| D8 Regional coverage | 8% | 5.2 | 7.0 | **6.1** | 6.5 | −0.4 | Reviewers split: ChatGPT marked recent expansion / thin live data; Opus credited 7-jurisdiction tax + Italian-niche IP. Consensus midpoint. |
| D9 Speed | 5% | 8.3 | 8.5 | **8.4** | 8.0 | +0.4 | Both agree: 4,051 LOC of feeds in 24h, 11 workbooks built in 5s, 473-test suite in 157s. Velocity is the strongest single signal. |

**Consensus weighted total**: 0.12(6.65) + 0.12(8.0) + 0.15(7.0) + 0.15(5.15) + 0.15(2.3) + 0.10(3.75) + 0.08(3.1) + 0.08(6.1) + 0.05(8.4)
= 0.798 + 0.960 + 1.050 + 0.7725 + 0.345 + 0.375 + 0.248 + 0.488 + 0.420
= **5.46 / 10**

This places ModelForge **below o11.ai (founder-quoted 6.60)** and **below Macabacus (6.85)** on the consensus weighted score, and **substantially below Rogo (7.40)**. The competitive ranking changes materially when the score is honest.

---

## 2. Where the reviewers disagreed (and why it matters)

| Point | ChatGPT | Opus | Resolution |
|---|---|---|---|
| D8 regional | 5.2 | 7.0 | Opus over-weighted Italian-niche IP (PBSA / L.338 / SIIQ) which is real but **non-portable to international buyers**. ChatGPT's 5.2 is closer to what a tier-1 US fund actually credits. **Take the lower number.** |
| D4 lift from feeds | 4.8 | 5.5 | ChatGPT was harsher on "interfaces ≠ integrations" — defensible. Opus gave partial credit for the architecture pattern. **Take the midpoint 5.15.** |
| Macabacus comp | $80M FactSet 2022 (per dossier) | (used dossier number) | **ChatGPT web-corrected**: Macabacus was acquired by CFI (Corporate Finance Institute) in 2021, **not FactSet $80M 2022**. Founder's comp set has at least one fabricated data point. This itself is a yellow flag for the diligence packet. |

---

## 3. Killers (joint top-3, ranked)

Both reviewers independently identified the same three killers, just phrased differently:

### KILLER #1 — Numerical plausibility failure
The Enel DCF demo outputs **€553B equity value vs ~€70B real Enel SpA market cap** (+743% premium) with no automated warning. For a product whose entire pitch is "trust this number, here's the lineage," this is a category-killer. Founder's D1 self-rating of 9.7 is indefensible until shipped.

### KILLER #2 — Zero customer pull
No paying customers. No design partners. No signed pilots. No LOIs. Every metric in the dossier is engineering-quality, not business-quality. We don't fund engineering portfolios.

### KILLER #3 — No enterprise wrapper
PyPI + MCP server is developer-tool distribution. No multi-tenancy, no SSO/SCIM, no hosted product, no audit logs surfaced for buyer review, no SOC2 path. Buyers won't buy a Python package as a finance operating layer.

---

## 4. Unlocks (consensus 90-day plan)

### UNLOCK #1 — Ship "Model Trust Layer v1" (5-7 days, both reviewers' #1 ask)
Per-template plausibility rules, market-cap deviation alerts, peer-comparable EV/EBITDA bands, WACC sanity (3-25%), terminal-growth checks (≤ GDP growth + 1%), source-freshness flags, "Red flag" sheet auto-injected in every workbook. **D1: 6.65 → 8.5+. Worth +0.20-0.30 weighted.**

### UNLOCK #2 — Convert 3 design partners (30-60 days, founder-driven)
Target: one private-credit team + one PE/RE investor + one M&A/restructuring boutique. Real files ingested, ≥10 workbooks per partner, written feedback, ≥1 paid pilot or LOI signed. **Re-rates the entire valuation frame from "engineering bet" to "early-revenue bet" — worth +30-50% on pre-money outright.**

### UNLOCK #3 — Build minimum enterprise wrapper (45-90 days)
Hosted app + auth/RBAC + tenant isolation + audit log + reviewer approval flow + one real paid data provider (Polygon $29/mo or FMP $19/mo wired) + basic security memo. **Lifts D4 + D5 + D7 simultaneously, worth +0.40-0.50 weighted.**

If all three land, consensus weighted score moves from **5.46 → ~6.5+** AND the customer catalyst re-rates valuation from $4.5M to **$8-15M base.** That's a Series-A-conversation outcome.

---

## 5. Pre-money valuation (consensus)

Both reviewers converged on the same $4.5M base case, with low/high bands within $0.5M of each other:

| Case | Consensus | Logic |
|---|---:|---|
| **Low** | $2.0M | Solo-founder technical asset, zero revenue, plausibility gap unfixed. Effectively a code-cost replacement valuation. |
| **Base** | **$4.5M** | Real codebase + 14 templates + MCP layer + Italian-niche IP + exceptional velocity = above pure asset-cost, but no SaaS metrics to underwrite. |
| **High** | $7.5M | Defensible only if: (a) Trust Layer ships AND (b) at least one design-partner LOI signed AND (c) one paid data adapter live. Without all three, $7.5M is generous. |

**Founder's $5.5-12M range**: $5.5M is arguable on the low end if you give heavy weight to founder velocity. **$12M is not justified today.** No paying pilots, no signed design partners, no enterprise distribution channel, no team beyond solo founder.

Comp anchoring (web-validated by ChatGPT):
- **Rogo $750M post-Series-C** is a market-validation comp, not a valuation comp — different stage, different motion (multi-tenant SaaS vs Python package).
- **Hebbia ~$700M Series B** had ~$13M ARR at the time. ModelForge has $0.
- **o11** is the closest direct competitor by product surface; YC profile says "used by hundreds of companies" — ModelForge has no comparable usage proof. **This is a more concerning competitive read than the founder scorecard suggests.**
- **Macabacus → FactSet $80M 2022** in the founder's comp set is **not validated** by public sources (Macabacus actually acquired by CFI in 2021). Recommend founder remove this comp from the deck.

---

## 6. Final recommendation (consensus)

**SEED-CHECK $1.5 - $2.5M @ $4.5M pre-money base, milestone-tranched.**

Not Series A (no SaaS metrics to underwrite, no team, no design partners).
Not pass (the wedge is real, the velocity is exceptional, the Italian-niche IP is non-replicable).

### Tranche structure (recommended)

| Tranche | Trigger | Amount |
|---|---|---:|
| T1 (immediate) | Term sheet signed | $750K |
| T2 (30-day) | Trust Layer v1 shipped + 1 design partner LOI signed | $750K |
| T3 (90-day) | 3 design partners using product + 1 paid data adapter live + minimum hosted wrapper | $1M |

If T2 misses → conversation pauses. If T2 hits but T3 misses → bridge to next round at flat valuation. If T3 hits → support Series A discussion at $20-40M post.

### Operating notes if we fund

1. **Hire one US-based BD in 60 days** — Italian-niche distribution alone can't reach US IB pricing tier.
2. **Migrate Italian IP into a separate productized vertical** ("ModelForge Italia") so it doesn't dilute the international story.
3. **External audit of formula library** before any institutional pilot — Big-4 or EY-equivalent, ~€20K, derisks D2 in real procurement.
4. **Fix license mismatch** — pick MIT (then OSS distribution) or genuinely close-source the repo (private GitHub + paywalled binaries on PyPI). Public + proprietary is a procurement red flag.
5. **Remove the Macabacus $80M FactSet comp** from any pitch deck until it can be sourced.

### Alternative paths

- **Strategic partnership with Big-4 / FactSet / S&P** — license the formula engine + graph.db sidecar pattern for $2-5M one-time + revenue share. Trades ownership for distribution.
- **License-only deal with a regulated Italian bank** — Aither-adjacent IP genuinely is unique vertical; one specific bank could be willing to pay €100-500K/yr for exclusivity in Italian private credit.

---

## 7. The two-reviewer convergence as a signal

When two AIs with different training, different priors, and different research methods converge to within **0.07 weighted points** and **$0 on base valuation** from a blind read of the same dossier, the consensus is more reliable than either individual estimate would be. The methodology itself is also a defense: the founder can't dismiss this as "one critical reviewer's opinion."

**The blind convergence at 5.45 weighted is the headline number. SCORECARD_v3's 6.56 is materially overstated; with the dimensional gaps closed (Trust Layer + 3 design partners + 1 paid adapter), ModelForge clears 6.5+ and is genuinely worth $8-15M base.**

---

## Appendix — files

- `IC_DOSSIER_2026-05-15.md` — evidence packet sent to ChatGPT
- `CHATGPT_RESPONSE_FULL.md` — verbatim ChatGPT 5.5 extended thinking response
- `OPUS_INDEPENDENT_REVIEW.md` — independent Opus 4.7 review (written before reading ChatGPT)
- `EXTERNAL_IC_REVIEW_2026-05-15.md` — this consensus document

## Appendix — methodology

1. Built 11 of 14 templates end-to-end (today, 2026-05-15)
2. Ran 473-test suite (471 pass)
3. Independently recalculated the Enel DCF via the third-party `formulas` Python package (1,288 cells)
4. Inspected workbook output cell-by-cell for hardcode/formula ratio
5. Live-tested 3 free-tier providers (EDGAR + GLEIF + OpenFIGI) against real APIs
6. Sent structured 6,194-character IC dossier to ChatGPT 5.5 Extended Thinking
7. ChatGPT reasoned for 1 min 14 sec and used web search to verify comp data
8. Opus 4.7 wrote independent review BEFORE reading ChatGPT's output
9. Triangulated final scores in this document

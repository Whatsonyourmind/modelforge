# ModelForge — Global GTM Strategy (2026-05-14)

**Owner**: Luka Stanisljevic
**Horizon**: 18 months (May 2026 → Nov 2027)
**Premise**: ModelForge is already **9.15/10 weighted on Italian credit/structured finance** but **5.05/10 weighted internationally**. The gap to Rogo (7.40) is in distribution, productization, data integrations — not output quality. This document is the plan to close that gap **without raising capital**, by riding the MCP / AI-agent distribution wave instead of building an enterprise sales motion from scratch.

---

## 1. The thesis in three sentences

1. **Distribution > breadth in 2026.** Rogo built $1.5-2B on a Bloomberg-style sales motion. We can reach the same analysts via MCP — every Goldman / Morgan Stanley / JPM analyst running Claude Code or ChatGPT Enterprise can invoke a ModelForge tool inside their existing IDE, no procurement required.
2. **Output quality is the moat, not the GTM channel.** Our 9.7 formula discipline + 9.4 source traceability + 0 PARTIAL/0 FAIL audit beat Rogo's value-based generation (which still fails WSP's 2026 quality benchmark vs Shortcut/Claude). Quality compounds with each citation and case study; distribution catches up.
3. **Italian regulatory IP is the wedge, not the ceiling.** We open the door with Italian credit/structured finance where we already lead 9.15. International deals come from existing Italian customers asking for German/French/UK extensions, plus inbound from the MCP catalog.

---

## 2. Positioning — what we sell vs what we say

### What we sell
A **deterministic financial-model builder** that:
- Reads a typed YAML spec (or auto-ingested from PDFs)
- Emits a bulge-tier Excel workbook (every cell live-formulated, every number source-traced to doc page)
- Persists the entire model as a queryable SQLite linkage graph
- Exports to PowerPoint / Word for committee delivery
- Available as: CLI · Python package · MCP server · web UI

### What we say
> *"The only Excel model factory where every cell is live, every number is sourced, and every change is diffed — bulge-tier output in minutes, not days. Auditable by design."*

### What we do NOT say
- "AI replaces analysts" (wrong — analysts use it)
- "Faster than Excel" (Excel is fine; bad models are the problem)
- "Better than Rogo" (different category; we let buyers conclude)
- "Italian" (in international pitches — it's the wedge, not the lead)

---

## 3. ICP — who actually buys

### Tier 1 — beachhead (highest fit, lowest friction)
1. **European MM PE / private credit funds** (€50M-2B AUM) — DD packs + IC memos. Pricing: €25-100K/engagement.
2. **Italian / Spanish / Greek NPL servicers** — portfolio valuation, recovery modeling. Pricing: €50-250K/engagement.
3. **Independent consulting boutiques serving IBs** — model factory outsource. Pricing: €10-50K per deal.
4. **Solo deal advisors / ex-MD-led shops** — replace €40-80h of analyst work per deal. Pricing: €5-25K per model.

### Tier 2 — expansion targets (after first 5 Tier-1 wins)
5. **Bulge-bracket IBs analyst pools** (Goldman Italy, Morgan Stanley EMEA, Lazard Italy, Rothschild, BNP Paribas) — through analyst-led adoption + MCP catalog. Pricing: $10-50K seat/yr.
6. **Sovereign wealth fund credit teams** — KIA, GIC, ADIA — long-cycle DD-heavy. Pricing: $100-500K/yr enterprise.
7. **G-SIB risk desks** — DFAST / IFRS 9 / pillar 2 stress models. Pricing: €50-250K/yr.
8. **Quant fund credit pods** — Citadel, Millennium, Bridgewater credit teams. Pricing: €100-500K/yr.

### Tier 3 — long-tail (post-product-market-fit)
9. **Corporate development teams** at F500 — M&A merger modeling
10. **Big-4 transaction services groups** — model review + audit
11. **NPL secondary investors** — Cerved, doValue analyst seats
12. **Boutique research firms** — independent IC vendors

### Anti-ICP — DO NOT chase
- Fortune 500 corporate FP&A (that's Anaplan / Pigment / Causal territory)
- Solo retail traders (insufficient willingness-to-pay)
- Academia / university courses (zero margin, infinite support)
- Bulge-bracket procurement (too long-cycle, won't beat Rogo head-to-head)

---

## 4. Channel strategy

### Channel A — MCP / AI agent catalog (highest leverage, zero CAC)
**Thesis**: every IB analyst now has Claude Code / ChatGPT Enterprise / Cursor / Cline. If we're discoverable as an MCP tool in their workflow, they invoke us without any procurement decision.

**Tactics**:
1. Ship `@modelforge/mcp-server` to npm + MCP registry (this session)
2. List on Glama, Smithery, MobinX/awesome-mcp-list, MCP marketplace
3. Tool-level discoverability: "build_lbo", "stress_test", "valuation_dcf", "ingest_dataroom"
4. Dev.to articles: "I built bulge-tier LBO models with one MCP call"
5. Show HN once we have 3+ paying users (not before)

**Conversion path**: MCP user discovers tool → free tier (5 models/mo) → paid tier ($99/$499/$2K-$10K) → enterprise contact.

### Channel B — Fiverr / Upwork deal-modeling gigs (proof + cash)
**Thesis**: every paid deal = real case study. Use Fiverr's audience (already set up at @lukestani for DeckForge) to deliver one-off models at €500-3K each. Each delivery becomes a public testimonial.

**Tactics**:
1. Set up Fiverr gig: "Bulge-tier LBO model with source-traced cells, delivered in 24h" — €500-1500
2. Same for: project finance, NPL portfolio valuation, M&A merger model, DCF + sensitivity tornado
3. Upwork: longer engagements (€5-25K) for deal advisors
4. Each delivery → ask permission to anonymize + publish case study

### Channel C — LinkedIn thought leadership (audience, not transactions)
**Thesis**: LinkedIn is where IB MDs read. Three posts/week with technical content (not marketing) builds inbound pipeline over 6-12 months.

**Tactics**:
1. Three posts/week — Mon (technical breakdown), Wed (industry commentary), Fri (case study)
2. Topics: source traceability vs LLM hallucination, IFRS 9 EIR mechanics, sculpted amortization solver, NPL recovery curves
3. CTA on every post: link to ModelForge GitHub + free MCP install
4. Comment substantively on competitor / FactSet / Macabacus posts to siphon attention

### Channel D — Direct cold outreach (qualified targets)
**Thesis**: ~100 named targets with warm-intro paths from `INVENTION_BACKLOG.md` Top-30 ranking. Direct outreach when MCP discovery isn't enough.

**Tactics**:
1. 30 cold emails/month, 3 templates A/B/C tested
2. Open with: technical insight specific to their portfolio (not a pitch)
3. Offer: free 60-min model review of one of their deals
4. Convert: scope into a paid engagement at €15-50K

### Channel E — Academic / regulator track (slow-cycle, large)
**Thesis**: Research Lab's papers + regulator memos build credibility that converts the longest-cycle buyers (G-SIBs, sovereign wealth, regulators).

**Tactics**:
1. K-A-T Live Monitor referenced as ModelForge-powered in regulator memos
2. SSRN papers cite ModelForge replication packages
3. Talks at SUERF, ESRB, BIS, Bocconi, INSEAD private capital conferences

### NOT a channel
- ❌ Paid Google/LinkedIn ads (B2B finance ads cost €100-300 CPC, terrible CAC)
- ❌ Conference booths (€5-20K each, low ROI without 3-person team)
- ❌ Outbound BDR hire (premature; founder must own first 10 deals)

---

## 5. Pricing ladder

### Self-serve tier (MCP + CLI)
- **Free**: 5 models/month · Italian + project_finance templates · CLI + MCP server access · no PPT/Word export
- **Starter $99/mo**: 50 models/month · all 8 templates · PPT/Word export · email support
- **Pro $499/mo**: 200 models/month · data-room ingestion · sensitivity tornado + Monte Carlo · web UI access · priority support
- **Team $2,000/mo (5 seats)**: 1000 models · multi-user · comments · revision history · SAML SSO · phone support

### Enterprise tier (manual sale)
- **Enterprise $10K-50K/yr**: unlimited models · on-prem option · custom templates · SLA · dedicated CSM
- **White-label $100K-500K/yr**: rebrand for BB / FactSet / Refinitiv reseller · SLA + audit report
- **Project-based €15-100K**: bespoke deal-by-deal modeling + delivery

### Pricing reference (don't undersell)
- Rogo lists "talk to sales" — actual prices via leaks: $60-80K/seat at bulge banks
- Macabacus subscribed to FactSet at $20-40K/seat blended
- Hebbia: $50-200K/yr enterprise
- ModelForge can target: **Team $24K/yr (5-seat)** = $4.8K/seat — undercut Rogo 10-15× on per-seat for similar quality

### Key principle
> **Premium pricing requires premium positioning.** Don't price like commodity tools. Price like Macabacus / Rogo. Italian credit-pack delivery is $25-100K/engagement. Don't take €1K engagements except as Fiverr lead-gen.

---

## 6. The 90-day plan (May 14 → August 14 2026)

### Week 1-2 (this session + immediate)
- ✅ GTM_STRATEGY.md (this doc)
- ✅ Build `modelforge-mcp` server wrapper
- ✅ Add `exporters/pptx.py` + `exporters/docx.py`
- ✅ Updated SCORECARD_v2.md with international + Italian dual view
- ✅ Public landing page HTML
- ☐ Publish `@modelforge/mcp-server` to npm
- ☐ Submit to MCP registry · Glama · Smithery · awesome-mcp-list
- ☐ Resume commit cadence ≥3/week (kills 22-day idle red flag)

### Week 3-4 (May 28 - June 11)
- ☐ Public marketing site at modelforge.dev (Vercel deploy)
- ☐ First dev.to article: "Bulge-tier LBO models via one MCP call"
- ☐ Fiverr gig live (€500 entry, €1500 LBO+PPT bundle)
- ☐ LinkedIn campaign starts (3 posts/week)
- ☐ Send first 30 cold emails (Tier-1 targets)
- ☐ Resume commit cadence: weekly v0.9.x releases

### Week 5-8 (June 11 - July 9)
- ☐ Ship US GAAP 3-statement + LBO templates (closes D8 international gap)
- ☐ First Fiverr delivery — convert to public case study
- ☐ First paid engagement target — €5-25K
- ☐ Second dev.to article: "How we measure SOTA in financial modeling" (the SCORECARD as content)
- ☐ Web UI v0.1 deployed (no auth, demo mode)

### Week 9-12 (July 9 - August 14)
- ☐ Second paid engagement target — €15-50K
- ☐ Comparison page live (vs Rogo, Macabacus, Hebbia)
- ☐ Restructuring template + IPO model
- ☐ Day-90 review: ≥3 paying customers OR pivot channel mix
- ☐ Begin OSS contribution to one major MCP host (Cursor / Cline) to seed cross-promo

### Day-90 milestones (P50 targets)
- 3+ MCP installs / week tracked via npm downloads
- 1+ paid engagement closed (€15-50K)
- 1+ Fiverr delivery completed (€500-1500)
- 5+ LinkedIn posts published
- 30+ cold emails sent, ≥3 first-call conversions
- Public landing page + comparison page live
- 1 case study published (anonymized)

---

## 7. Capital-blocked items (Phase B — needs €750K-1.5M raise)

These ARE the difference between 5.05 and 7.40 weighted internationally. They cannot be closed solo / autonomously and gate the upper tier of buyers:

| Gap | Cost | Buyer-tier unlocked |
|---|---|---|
| Bloomberg / FactSet / Capital IQ / Refinitiv licenses | $150-300K/yr | BB IBs, G-SIB risk desks |
| SOC 2 Type II audit | $30-80K + 6-12mo cycle | Bank-grade engagements |
| ISO 27001 | $20-50K + 6-12mo | EU enterprise |
| Multi-tenant SaaS with SSO/SCIM | €100-250K dev | Team-tier customers >5 seats |
| US ex-IB associate hire (credibility + Americas BD) | $200-300K loaded | US market entry |
| Penetration testing (annual) | $15-40K | Required by bank procurement |
| Salesforce + RevOps tooling | $50-100K/yr | Pipeline at $1M+ ARR |
| EU GDPR DPA infrastructure | $20-40K legal | EU bank engagements |

**Total Phase-B**: ~$0.6-1.5M Year-1 if pursued aggressively.

**Trigger**: pursue Phase B after closing first €100K in cumulative engagement revenue OR a CreditAI funding round provides bridge capital.

---

## 8. KPIs (weekly)

### Acquisition
- npm `@modelforge/mcp-server` weekly downloads
- MCP registry queries / Glama page views
- LinkedIn impressions + post engagement
- Cold-email reply rate (target ≥10% by Day 90)

### Activation
- Free-tier signups / MCP installs
- Web demo runs (when live)
- Fiverr orders received

### Revenue
- Paid Starter/Pro/Team conversions
- One-time engagement close rate
- MRR / ARR

### Authority
- Dev.to article views + reactions
- GitHub stars
- SCORECARD citations / inbound links

### Stop conditions
- If MCP weekly installs <10 by Week 8 → revise pricing or positioning
- If LinkedIn engagement <2% by Week 12 → switch from technical to case-study content
- If Fiverr orders are 0 by Week 8 → adjust gig copy / pricing / category

---

## 9. Competitive positioning matrix

We don't compete head-on. We pick our spot.

| Competitor | What they win on | How we differentiate |
|---|---|---|
| **Rogo** | Distribution + breadth + brand | Source traceability + formula discipline + Italian regulatory IP + 10x cheaper per-seat |
| **Hebbia** | Doc-to-model pipeline at enterprise scale | We're MCP-native + Italian/EU credit + open-core licensing |
| **o11.ai** | Equity research live-formula | We're credit/structured finance + provenance graph |
| **Macabacus / FactSet** | Excel-add-in mature install base + brand | We're AI-native + spec-driven + zero hallucination |
| **FAST Standard** | Methodology authority | We're the tool that enforces FAST + adds traceability |
| **Bulge human analyst** | Domain judgment + relationships | We're 10× faster, 100% reproducible, audit-ready |

Key message: **"We are not Rogo for Europe. We are the auditable, source-traced, MCP-native alternative — with Italian/EU credit as our beachhead."**

---

## 10. Sale-readiness implication

Per Apr 28 valuation: ModelForge base $4.5-9.0M.

Each GTM milestone moves the valuation:
- First paying customer: +$1-3M (collapses pre-revenue discount, activates ARR multiple)
- 5 paying customers: +$3-7M (proves the motion)
- $250K cumulative engagement revenue: +$5-15M (Series A territory at 10-15x ARR)
- 1 BB IB paying enterprise tier: +$10-25M (acquisition target for FactSet/S&P/Bloomberg)
- $1M ARR: $15-50M valuation (Rogo's trajectory at 1/30th the scale)

The path is: **ship MCP → land first 3 customers via Fiverr+MCP → enterprise pilot in Q4 2026 → $500K ARR by mid-2027 → strategic acquisition or Series A**.

---

## 11. The bottom line

We are **already SOTA on output quality**. We are **not** SOTA on distribution. The gap closes via MCP (zero-CAC distribution) + Fiverr (zero-CAC proof) + LinkedIn (zero-CAC audience). Capital-intensive moves (Bloomberg, SOC 2, SaaS multi-tenant, US hire) come *after* the first €100K cumulative revenue, not before.

**Within 90 days of executing this plan, ModelForge should be at:**
- 100+ MCP weekly installs
- 3+ paying customers totaling €30-100K
- 1+ public case study
- LinkedIn pipeline of ≥50 inbound leads
- Comparison page that converts at ≥10% to demo-request
- Updated valuation: $7-12M base (vs $4.5-9.0M today)

Capital-blocked Phase B unlocks the next 10x (from $12M → $50-150M).

---

*Last updated: 2026-05-14. Maintainer: Luka Stanisljevic.*
*Companion docs: `SCORECARD_v2.md`, `BUSINESS_PLAN.md` (Research Lab), `_strategy/funding/DRAFT_PLAN.md`.*
*Reviewer cadence: monthly against KPIs.*

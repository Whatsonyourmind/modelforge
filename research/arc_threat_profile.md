---
title: Arc Intelligence / F2 — Threat Profile vs ModelForge
date: 2026-04-18
type: research
---

# Threat profile: Arc Intelligence (now F2.ai)

## 0. Identity correction (load-bearing)

"Arc Intelligence" was the AI-for-private-credit product line of Arc Technologies (Don Muir, ex-PE, Stanford GSB, YC). On 2025-09-16 it **spun out as F2 AI, Inc.** with a $10M seed (NFX, Left Lane, Y Combinator, ~50 Arc angels) — Arc kept the cash-management/CFO-agent business (rebranded "Archie"). Arc + F2 cumulative funding is ~$200M, **not a fresh $180M round into the AI product** ([PRNewswire 2025-09-16](https://www.prnewswire.com/news-releases/f2-spins-out-of-arc-with-10-million-equity-round-emerging-as-the-ai-leader-in-private-markets-302557013.html), [NFX investment memo](https://www.nfx.com/post/why-nfx-invested-f2)). The actual competitor is **F2** with $10M of fresh capital — much smaller war chest than the headline implies.

## 1. Product reality (what F2 actually ships, April 2026)

F2 is positioned as an "AI-native Bloomberg terminal for private markets" but the substance is narrower ([AI Journal](https://aijourn.com/f2-launches-with-10m-to-build-ai-native-bloomberg-terminal-for-private-markets/)):

- **LLMExcel engine** — server-side runtime that opens .xlsx files, evaluates real formulas (VLOOKUP, INDEX/MATCH, SUMIFS, circular refs), exposes 50+ deterministic ops. Scored **95.25% on SpreadsheetBench Verified** (claimed world record) ([F2 vs Hebbia](https://f2.ai/blog/f2-vs-hebbia-ai-underwriting-comparison)).
- **Audit Mode** (launched 2026-02-17) — "Databook" is a live source-linked Excel workbook; clicking any number reveals formula + precedent cells + highlighted link to source PDF. Persists when exported to .xlsx ([BriefGlance](https://briefglance.com/articles/f2s-audit-mode-brings-defensible-ai-to-private-markets-investing)).
- Data-room ingestion → spreading → IC memo generation, with FactSet + PitchBook integrations.

**Direct answers to the diligence questions:**

| Capability | F2 ships? | Source |
|---|---|---|
| Builds Excel models with live formulas from scratch | **No** — explicitly "computes within existing workbooks; Rogo generates new outputs" | [F2 vs Rogo](https://f2.ai/blog/f2-vs-rogo-buy-side-vs-sell-side-ai-comparison) |
| Project finance (sculpted amort, DSCR solver, DSRA) | **No mention anywhere** — corporate credit/EBITDA/leverage only | F2 site, blog corpus |
| Reverse modeling of legacy bank/competitor models | **No** — analyzes data-room artifacts, not legacy models | F2 vs Rogo, F2 vs Hebbia |
| Drift detection vs ECB/Damodaran/live market feeds | **No mention** — no live market-data layer surfaced | All F2 marketing reviewed |
| Source-traceability to specific PDF page | **Yes** — three-layer chain (claim → formula → source cell), Audit Mode highlights source doc location | [F2 vs Hebbia](https://f2.ai/blog/f2-vs-hebbia-ai-underwriting-comparison), [BriefGlance](https://briefglance.com/articles/f2s-audit-mode-brings-defensible-ai-to-private-markets-investing) |

## 2. Pricing / GTM

**Hosted SaaS only.** SOC 2 Type II, zero data retention. **No public pricing tier**, no self-serve signup, no free trial visible — enterprise sales motion only. Customer base described as "dozens of leading private credit funds, commercial banks, PE firms" with "hundreds of active users"; only **named logo is RevTek Capital** plus anonymized testimonials from a $65B AUM credit/equity fund, $70B AUM RIA, and $18B AUM credit manager ([F2 launch](https://www.f2.ai/blog/launch-announcement)). Claimed traction: 7x MoM usage growth, 60x ARR growth since spin-out.

## 3. Team

**~20 people, NYC-headquartered** ([Y Combinator profile](https://www.ycombinator.com/companies/f2)). Leadership skews ex-PE + ex-engineer, not ex-banker:
- **Don Muir** — Co-founder/CEO. Ex-PE (Apollo), Stanford GSB. Founded Arc 2021.
- **Nick Lombardo** — Co-founder/President. Stanford GSB classmate.
- **Raven Jiang** — Co-founder/CTO.
- **Emre Kazdagli** — Founding Principal Engineer (was Arc CTO before spin-out).
- 3 open roles (engineering + ops) per YC. Some Tel Aviv presence noted on third-party portals but unverified.

**No senior MD-level credit hires from bulge-bracket structured finance** are publicly visible. Ex-banker bench is thin — they're betting on engineering depth (the SpreadsheetBench score is real signal).

## 4. Geography

**US-only signal.** Headquartered NYC, all named investors US-based, all marketing in English, all named/anonymized customers appear US-domiciled. **Zero mentions of: Italy, EU, AIFMD II, IFRS 9, GACS, legge 130, Solvency II, ECB, data residency, on-prem, sovereign cloud** across the F2 site, blog (22 posts reviewed), launch coverage, and competitive comparison pages. F2's competitive frame mentions only Rogo, Hebbia, BlueFlame, Claude Cowork — all US/English-language. EU expansion is **not** a stated 2026 priority based on public artifacts.

## 5. What F2 does NOT ship — ModelForge moat

Confirmed gaps in F2 today:

1. **Project finance entire vertical** — no sculpted amortization, no DSCR-target solver, no DSRA mechanics. F2 is corporate credit (EBITDA, leverage, covenant). ModelForge's v0.3 PF module is a clean white-space win.
2. **Model authoring from scratch** — F2 by its own admission only computes *within* existing data-room workbooks. ModelForge's deterministic cell-write builds new bulge-tier models (8-template suite) from a YAML spec. Different product category.
3. **Reverse modeling of legacy/competitor models** — not in F2's surface area at all.
4. **Live-feed drift detection** — no ECB/Damodaran/market-data layer. F2 is point-in-time analysis of static data rooms.
5. **On-prem / air-gapped deployment** — hosted-only. No BYOC, no sovereign-cloud option, no data-residency story for EU.
6. **EU regulatory depth** — zero AIFMD II / IFRS 9 / GACS / legge 130 footprint. Italian/EU credit funds get no native support.
7. **CLI-first / dev-native workflow** — F2 is a UI-driven analyst tool, not a scriptable engine.

## 6. Counter-positioning — three angles for ModelForge

Evaluating the candidates against Arc/F2's actual posture, the **three highest-leverage** counters are:

1. **"Project finance + structured credit specialist, not corporate credit generalist."** F2 does EBITDA/leverage. ModelForge does sculpted amort, DSCR-target solver, DSRA, GACS-style waterfalls. This is a genuine product-category gap, not a marketing claim — F2 would need 6+ months and PF-domain hires to close it.

2. **"On-prem / data-sovereign for EU credit funds with AIFMD II + legge 130 + IFRS 9 native."** F2 is hosted-only US SaaS with no EU regulatory artifacts. Italian boutique credit funds with sovereign-data constraints (your three-fund pitch list) literally cannot buy F2 if procurement requires on-prem or EU data residency. This is the pitch — not a feature comparison.

3. **"Builds new models, doesn't just read existing ones."** F2 explicitly limits itself to computing within data-room workbooks. ModelForge generates bulge-tier models from a spec via deterministic cell-write. Pair this with "reverse-engineer the bank's legacy model into our linkage graph" — that's a workflow F2 cannot do today and hasn't signaled they will.

**Deprioritize:** "deterministic / zero-hallucination" (F2 owns this narrative now with the 95.25% SpreadsheetBench score and Audit Mode — head-to-head loss on their home turf), and "formula-fidelity vs memo-generation" (F2 just shipped exactly that with Audit Mode in February — too late to claim).

## 7. Net assessment

F2 is a real, well-engineered, well-funded competitor on US corporate-credit underwriting — but they have **no overlap** with ModelForge on (a) project finance, (b) model authoring, (c) reverse modeling, (d) live-feed drift, (e) on-prem/EU, (f) CLI-native workflow. The threat is **future drift into adjacent verticals** if F2 raises a Series A and adds PF + EU. Watch their hiring page for Project Finance Lead / EU GM postings as the leading indicator. Today, ModelForge's defensible wedge is the **PF + EU + on-prem + reverse-modeling combo** — none of which is on F2's roadmap as published.

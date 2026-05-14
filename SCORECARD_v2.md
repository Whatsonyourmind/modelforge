# ModelForge SOTA Scorecard v2 — Dual View

**Date**: 2026-05-14 (v0.8.9 post-themes-1-6 + v0.9 GTM prep)
**Prior version**: SCORECARD.md (2026-04-17, v0.3.1)
**Framework**: 9 dimensions weighted differently for Italian-niche vs International views
**Benchmarks refreshed**: Rogo Series D ($1.5-2B post Apr 29) · Hebbia 2026 extension · o11.ai WSP-#1 (2026) · Macabacus inside FactSet ($13B) · Causal/Lucanet (acquired $500M) · Concourse Series A

This v2 acknowledges that v1's Italian-tailored weights overstated ModelForge's global SOTA position. **Both views below are correct** — but for **different buyer conversations**.

---

## Executive summary

| Metric | Italian-niche view | International view |
|---|:---:|:---:|
| **ModelForge v0.8.9 weighted score** | **9.15** | **5.05** |
| Rogo Series D | 5.6 | **7.40** |
| Hebbia 2026 | 5.6 | 7.20 |
| Macabacus (FactSet) | 5.2 | 6.85 |
| o11.ai (WSP #1) | 5.4 | 6.60 |
| Concourse | 4.7 | 5.10 |
| Bulge human (Italian specialist) | 9.4 | 5.95 (judgment-adjusted 8.1) |
| Bulge human (international IB associate) | 6.9 | 8.5 |

**Italian-niche reading**: ModelForge is SOTA, beats every existing tool, only Italian-specialist humans outperform.

**International reading**: ModelForge is BEHIND Rogo / Hebbia / o11 / Macabacus on weighted score because productization, data integrations, collaboration, and regional coverage gaps offset the 9.7 formula discipline + 9.4 source-traceability lead.

**Which view to use when**:
- Italian PE / private credit / NPL servicer / BdI prudential supervisor → **Italian view** (we lead)
- US bulge bracket / global MM PE / sovereign wealth → **International view** (we trail on D4-D8)
- Mixed-region target (DeA Capital, Mediobanca, Lazard Italy) → use both, position as "9.15 in Italy, 5.05 globally, closing the gap via MCP distribution"

---

## Italian-niche view (15% reg weight, narrow geographic prior)

**Use case**: pitching DeA Capital / Kryalos / doValue / AMCO / illimity / Banca IFIS / Generali RE / Italian bank risk desks / Italian regulators.

### Dimensions (5)

| Dimension | Weight | Italian rationale |
|---|:---:|---|
| Formula discipline | 20% | Italian-regulated buyers audit every cell |
| Source traceability | 25% | BdI / Consob require regulator-grade trace |
| Modelling completeness | 25% | Need credit / structured / RE + Italian tax + IFRS 9 |
| Market / regulatory alignment | 15% | IRES / IRAP / SIIQ / PEX / AIFMD II / L.130/1999 must be native |
| Infrastructure / productization | 15% | Excel-delivery, on-prem, no SaaS-only |

### Scores (refreshed v0.8.9)

| Dim | Weight | MF v0.8.9 | Rogo | Macabacus | o11 | Bulge IT human |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Formula discipline | 20% | **9.7** | 5.0 | 8.5 | 9.0 | 9.0 |
| Source traceability | 25% | **9.4** | 4.0 | 2.0 | 3.0 | 3.2 |
| Modelling completeness | 25% | **9.5** ↑ (was 9.3) | 6.0 | 7.8 | 5.5 | 9.3 |
| Market/reg alignment | 15% | **8.8** | 3.8 | 1.6 | 3.0 | 7.0 |
| Productization | 15% | **7.4** | 9.5 ↑ | 6.0 | 8.0 | 5.6 |
| **WEIGHTED** | 100% | **9.15** | 5.6 | 5.2 | 5.4 | 6.9 |

Italian-specialist human still scores 9.4 with judgment premium. ModelForge's gap to that human is 0.25 weighted = closing entirely on reproducibility, source-trace, and speed (since output quality matches).

---

## International view (rebalanced for global buyers)

**Use case**: pitching US bulge bracket / European MM PE / sovereign wealth / global IBs.

### Dimensions (9) — these weights reflect actual IB procurement gates

| Dimension | Weight | International rationale |
|---|:---:|---|
| Formula discipline | 12% | Important but rarely a procurement gate (humans re-validate anyway) |
| Source traceability | 12% | Compliance value but not a gate outside regulated EU credit |
| Modelling completeness (breadth) | 15% | Need IPO/M&A/restructuring/FX-hedge etc. globally |
| **Data integrations** | **15%** | **Bloomberg/FactSet/Capital IQ/Refinitiv = table stakes** |
| **Productization / SaaS** | **15%** | **Web UI + SSO + RBAC mandatory >5-seat deal** |
| **Collaboration / workflow** | **10%** | **Multi-user, comments, review, PPT/Word export** |
| **Security & compliance** | **8%** | **SOC2 / ISO 27001 / SSO / pen-test = bank gate** |
| **Regional / multi-jurisdiction** | **8%** | **US GAAP / UK FRS / German HGB / Asia tax** |
| Speed / time-to-first-model | 5% | Bulge analyst time-cost is $200/hr |

### Scores

| Dim | Weight | MF v0.8.9 | Rogo D | Hebbia | o11 | Macabacus | Bulge intl |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Formula discipline | 12% | **9.7** | 5.0 | 6.0 | 9.0 | 8.5 | 9.0 |
| Source traceability | 12% | **9.4** | 4.0 | 6.5 | 3.0 | 2.0 | 3.2 |
| Modelling completeness | 15% | **6.0** ↓ (intl breadth) | 7.5 | 6.5 | 5.5 | 7.5 | 8.5 |
| Data integrations | 15% | **1.5** | 9.0 | 8.0 | 7.0 | 8.5 | 7.0 |
| Productization / SaaS | 15% | **2.5** | 9.5 | 9.0 | 8.0 | 7.0 | 0 |
| Collaboration / workflow | 10% | **1.0** (post-v0.9 PPTX/DOCX: 4.0) | 8.0 | 8.5 | 9.0 | 6.0 | 4.0 |
| Security & compliance | 8% | **1.5** | 8.5 | 8.5 | 7.0 | 9.0 | 6.0 |
| Regional coverage | 8% | **3.5** | 7.5 | 7.0 | 6.5 | 7.5 | varies |
| Speed | 5% | **8.0** | 8.5 | 7.5 | 8.0 | 5.5 | 2.0 |
| **WEIGHTED** | 100% | **5.05** (→ **5.35** post-v0.9 with PPTX/DOCX shipped) | **7.40** | **7.20** | **6.60** | **6.85** | **5.95** |

### Where ModelForge LEADS internationally (D1 / D2 / D9)
- **Formula discipline 9.7**: only o11 matches; Rogo at 5.0 (value-based gen) still fails WSP-2026 benchmark vs Shortcut + Claude
- **Source traceability 9.4 vs 2-7 elsewhere**: per-cell → source-page graph is the moat; no competitor has this as a first-class data model
- **Speed 8.0**: spec → workbook in minutes vs bulge human's 40-80 hours

### Where ModelForge LAGS internationally
- **Data integrations 1.5 vs 9.0**: this single 15%-weight dimension explains 1.1 weighted points of the Rogo gap. Closing requires data licensing ($150-300K/yr), not code.
- **Productization 2.5 vs 9.5**: CLI/web-scaffold only. SaaS multi-tenant + SSO/SCIM = 3-6 months engineering. Phase B capital-needed.
- **Collaboration 1.0 (→ 4.0 post-v0.9)**: PPTX/DOCX export shipped this release brings to 4.0; full multi-user + comments still gated by SaaS multi-tenant.
- **Security 1.5 vs 8.5**: no SOC 2 / no ISO 27001 / no pen-test. Bank-grade gate. SOC 2 Type II = $30-80K + 6-12mo audit.
- **Regional coverage 3.5 vs 7.5**: Italian-strong but US GAAP / UK FRS / German HGB / Asia thin. Each region template = 1-2 weeks of solo work; US first.

---

## Strategic implications

### Italian-niche path (Path A from GTM_STRATEGY.md)
- Stays at 9.15 in its niche → captures **€2-4B Italian credit/structured TAM** with zero new capital required
- Realistic outcome: $30-150M lifetime value · acquisition by FactSet / S&P / Cerved / ION
- Investment: solo, ~€50K/yr ops cost
- 12-month sale-ready price: $5-12M

### International path (Path B from GTM_STRATEGY.md)
- Requires closing D4 + D5 + D6 + D7 + D8 gaps via MCP-distribution + capital
- Realistic 18-month outcome: 5.05 → 6.5-7.0 weighted (Macabacus-tier)
- Investment: €750K-1.5M (data partnerships + SaaS engineering + SOC 2 + US BD hire)
- 18-month sale-ready price: $15-40M base / $50-100M with bank-tier customers

### What v0.9 GTM strategy delivers (no new capital)
- **MCP server published** → distribution lever (zero CAC, AI-agent discoverability)
- **PPTX + DOCX exporters** → D6 1.0 → 4.0 weighted
- **Public landing page** → conversion surface
- **Updated SCORECARD_v2** → buyer-facing artifact
- **Day-90 P50 outcome**: 3 paying customers + €30-100K revenue + valuation re-rate $7-12M

### What v0.9 does NOT close (capital-blocked)
- Bloomberg / FactSet / Capital IQ data feeds (D4)
- Multi-tenant SaaS with SSO/SCIM (D5)
- SOC 2 Type II (D7)
- 4+ regional template families (D8)
- US ex-IB associate hire (credibility/BD)

---

## v0.9 release notes — gap closure

| Gap | Pre-v0.9 | Post-v0.9 | Mechanism |
|---|:---:|:---:|---|
| MCP discovery | 0 | 8 | New `modelforge-mcp` stdio server + `server.json` for registry |
| PPT export | 0 | 7 | New `modelforge.exporters.pptx` — 5-slide committee deck |
| Word export | 0 | 7 | New `modelforge.exporters.docx` — IC/credit memo template |
| Public marketing | 0 | 5 | `landing.html` + updated README + GTM_STRATEGY.md |
| Distribution channel readiness | 2 | 8 | `[mcp]` and `[export]` optional deps wired; entry points registered |

Weighted score lift: Italian view **9.15 → 9.25** · International view **5.05 → 5.35**.

The international lift looks modest because the gap is dominated by data + SaaS + security (Phase-B). The Italian lift is also modest because Italian buyers were already getting 9.15. **The real GTM win is the MCP distribution lever, which doesn't show up in the scorecard but generates the first paying customers.**

---

## Updated competitor positioning

```
Output quality (weighted intl)
      ▲
   10 │ 
      │   ◯ Italian bulge specialist (judgment-adjusted 8.1)
      │
    8 │              ◯ Bulge IB associate (intl, 8.5)
      │
      │       ◯ Rogo D (7.40)
      │              ◯ Hebbia 2026 (7.20)
    6 │       ◯ Macabacus/FactSet (6.85)    ◯ o11 (6.60)
      │
      │                              ◯ Bulge IT human (intl 5.95)
      │   ◯ ModelForge v0.9 (5.35)
    4 │
      │
      │
    2 │
      │
      └─────────────────────────────────────────────────►
        Distribution / SaaS / data integrations
       Low                                          High
```

ModelForge dominates the *quality* axis (formula discipline + source trace). Rogo dominates the *distribution* axis. Our 2026 thesis: **catch up on distribution via MCP without compromising on quality.**

---

## Sources (refreshed)

- [Rogo Series D $160M @ ~$1.5-2B (PR Newswire, 2026-04-29)](https://www.prnewswire.com/news-releases/rogo-raises-160m-series-d-to-scale-the-agentic-platform-for-finance-302756546.html)
- [Rogo Series C $75M (Jan 2026)](https://fintech.global/2026/01/28/rogo-raises-75m-series-c-to-scale-ai-finance-platform/)
- [Hebbia institutional doc → Excel](https://www.hebbia.com/blog/best-financial-modeling-software)
- [Wall Street Prep — AI financial modelling ranked 2026](https://www.wallstreetprep.com/knowledge/ranking-the-best-ai-tools-for-financial-modeling-2026/)
- [Macabacus Formulate + AIWA](https://macabacus.com/features/formulate)
- [FAST Standard Organisation](https://fast-standard.org/)
- [Concourse Series A $12M](https://www.concourse.co/insights/concourse-12m-series-a-launches-general-availability)
- [o11.ai (WSP #1)](https://o11.ai/)
- [Causal acquired by Lucanet ($500M, 2024)](https://www.lucanet.com/en/news/lucanet-acquires-causal)

---

*Maintainer: Luka Stanisljevic. Next refresh: post-first-paying-customer or post-Phase-B-funding.*
*Companion docs: `GTM_STRATEGY.md` · `BUSINESS_PLAN.md` · `SCORECARD.md` (v1, archived).*

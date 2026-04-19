---
title: "ModelForge vs. the AI Modeling Field: A 5-Deal Benchmark on Italian Private Credit & Structured Finance"
date: 2026-04-18
type: research
status: outline
author: Luka Stanisljevic
target_word_count: 7000
target_publish: 2026-05-02
us_id: US-034
related: ["modelforge_v05_shipped.md", "competitor_landscape_2026q2.md"]
---

# Whitepaper Outline & Methodology — US-034

## 1. Thesis (the defensible claim)

> **On Italian private credit and structured finance deliverables that require committee-grade source traceability and real-cell formula fidelity, ModelForge outperforms the four leading generalist AI modeling tools (Rogo, Arc Intelligence, Shortcut AI, Anthropic Claude for Financial Services) on 7 of 8 measured dimensions — most decisively on PF sculpted-amortization correctness, cell→doc-page audit trail depth, and deterministic regeneration. The single dimension where generalists win (raw English narrative quality) is the dimension a credit committee never scores.**

Three load-bearing words:
- **Committee-grade** — the bar is "would a Banca Finint / Anthilia IC accept this without a banker rebuild?", not "is the prose pretty?"
- **Italian** — AIFMD II (operative since Apr 2026), legge 130, GACS, IFRS 9 ECL — generalist tools have no native handling.
- **Deterministic** — bit-for-bit regeneration from the same inputs. LLM-generated value cells fail this categorically.

Falsifiability: if any single competitor beats ModelForge on >=5 of 8 dimensions on >=3 of 5 deals, the thesis is dead and we say so. Pre-registered.

---

## 2. The 5 benchmark deals (chosen from the 8-template suite)

Selection criterion: each deal must (a) be a real or near-real Italian transaction we can defend with public data, (b) exercise a distinct ModelForge moat, (c) have a public-record analog so competitors have a fair shot.

| # | Deal | Template | Italian moat exercised | Public anchor |
|---|------|----------|------------------------|---------------|
| 1 | **Stevanato unitranche LBO** (€220M, mid-market healthcare CDMO) | `unitranche_lbo` | DSCR-target solver, PIK toggle, leverage covenants | Stevanato 2024 IPO filings + CDMO comp set already in `output/credit_memo_cdmo.xlsx` |
| 2 | **Project Finance: Enfinity solar 240 MW Sicily** (€316M senior + €40M mezz) | `pf_solar` | **Sculpted amortization to 1.30x DSCR floor + DSRA + cash sweep** — the v0.3 crown jewel | Enfinity Global press releases, MISE PNRR allocations, Damodaran solar WACC feeds |
| 3 | **Banca Finint Minibond pricing** (€15M industrial issuer, BBB-, 6Y bullet) | `minibond_pricing` | Spread-grid vs ELTIF eligibility, Italian withholding, ExtraMOT Pro listing fees | Banca Finint 2025 minibond observatory + AIFI reports |
| 4 | **NPL portfolio recovery waterfall** (€500M secured GBV, legge 130 SPV, GACS-eligible senior) | `npl_recovery` | Italian recovery curves (Banca IFIS data), GACS guarantee mechanics, Vintage adjustments, IFRS 9 stage-3 ECL | doValue / illimity / Banca IFIS public NPL outcome data |
| 5 | **PMI structured-credit securitization** (€150M, 6 tranches A1/A2/B/C/D/Equity) | `structured_credit_tranche` | Tranche allocation, AIFMD II Article 26-Quinquies retention, IFRS 9 lifetime ECL on retained equity, EBA STS scoring | EBA STS register + Banca d'Italia 2025 securitization stats |

**Why not the other 3 templates** (DCF, comps, three-statement): these are commodified — generalists do them adequately. Including them would dilute the thesis and let competitors win cheap dimensions.

---

## 3. Scoring rubric — 8 dimensions, 0-5 ordinal scale

Pre-registered rubric (must be locked before running competitors, otherwise it's not a benchmark).

| # | Dimension | What we measure | 0 score | 5 score |
|---|-----------|-----------------|---------|---------|
| D1 | **Formula fidelity** | % of value cells that are live formulas vs hardcoded numbers (auto-detected via openpyxl) | <20% live | >=98% live |
| D2 | **Source traceability depth** | Avg # of clicks from any value cell to source doc + page number | No traceability | Every cell links to (doc, page, snippet) in <=2 clicks |
| D3 | **PF sculpting correctness** | DSCR floor maintained every period? Sculpted principal solves to target? Tail risk handled? | DSCR breached or solver doesn't converge | Solver converges, DSCR within 1bp of target every period, DSRA mechanic correct |
| D4 | **Drift detection** | Re-run vs live ECB / Damodaran feeds 30 days later — are stale assumptions flagged? | No drift mechanism | Per-cell drift report with red/amber/green + suggested refresh action |
| D5 | **Deterministic reproducibility** | Run twice with same inputs — bit-for-bit identical workbook? (sha256 on .xlsx) | Different output every run | sha256 stable across runs and across machines |
| D6 | **Italian regulatory fit** | AIFMD II Art.26 retention, legge 130 SPV mechanics, GACS guarantee, IFRS 9 ECL stages | Generic US/UK template | Italian-native fields, citations to the regulations, correct calc |
| D7 | **Committee-grade audit trail** | Dossier PDF: assumption log, source table, change log, sensitivity grid, sign-off page | No dossier | Single PDF a credit committee can sign without supplementary docs |
| D8 | **QC gate rigor** | # of automated checks (bal-sheet ties, debt-service coverage sanity, formula consistency, circular-ref guard) | 0 checks | 50+ checks with structured pass/fail report |

**Total possible: 40 points per deal × 5 deals = 200 points per tool.** Report % score per tool per dimension and aggregate.

**One eliminable dimension** (we will publish but not aggregate): D9 narrative-quality — generalists win this by design and we want to be honest about it.

---

## 4. Methodology — how to test fairly (and where we honestly can't)

### 4.1 Test protocol

For each of the 5 deals:

1. **Build a single sealed data-room** (PDFs, CIM, financials, term sheet, regulatory annexes). Hash and version it.
2. **Standardise the prompt**: "Build the [unitranche LBO / PF solar / minibond / NPL / structured credit] model and supporting credit memo from this data room. Deliver in Excel + a PDF dossier."
3. **Run each tool with the same prompt and same data.**
4. **Score blind** where possible: I (Luka) score; one external Italian credit professional cross-scores 1 deal as a calibration check.
5. **Pre-register the rubric and deal selection on GitHub** (commit hash in the paper) before running competitors. This kills any "you tuned the rubric to win" objection.

### 4.2 Honest competitor-access limitations

| Tool | Access status | How we handle it |
|------|---------------|------------------|
| **Rogo** ($75M Series C, bulge-IB SaaS) | No external data-room ingestion in public tier; produces pitchbooks not models | Use their published demo outputs + WSJ/Reuters reproductions. Score what's verifiable. **Flag unscorable dimensions explicitly.** |
| **Arc Intelligence** ($180M, "first AI for private credit", hosted) | Closed beta, LP-only access, no public sandbox | Score from their published whitepapers + Bain Capital Credit blog references. Acknowledge this is partial coverage. Reach out for trial; document refusal if any. |
| **Shortcut AI** ($49/mo, Excel-native) | Open trial — full access | Run all 5 deals at full fidelity. This is the **fairest comparison** — Shortcut is the closest peer. |
| **Anthropic Claude for Financial Services** (Excel plugin Q1 2026) | Public — full access via Claude.ai + Excel plugin | Run all 5 deals. Banker-in-the-loop assumed (per Anthropic positioning). |
| **Macabacus Formulate** (Excel add-in incumbent) | Trial available | Run all 5; expect strong on D1 (formula fidelity), weak on D6/D7 (Italian regs, dossier). |

### 4.3 What "fair" means

We will (a) not score dimensions a tool was never designed for in absolute terms — we'll mark "N/A" and reduce the denominator, (b) publish raw screenshots / file hashes for every score, (c) invite each vendor to challenge any score with a 14-day right-of-reply window before publication. Two of those vendors will be emailed personally.

---

## 5. Section outline (~7000 words)

### 5.1 Executive summary (300w)
- Thesis sentence
- Headline result table (5 tools × 8 dims, color-coded)
- Single-chart recap (radar plot, ModelForge vs best generalist)
- Invitation to challenge / replicate

### 5.2 Why this benchmark matters NOW (500w)
- AIFMD II operative April 2026 — Italian private credit funds need committee-defensible models, not pitchbooks
- Italian private credit AUM +53% YoY (Banca d'Italia 2025), boutique IC capacity is the binding constraint
- The 2026 wave: Rogo $75M, Arc $180M, Shortcut WSP win — money is flowing into AI modeling but **none of these are Italian-private-credit-native**
- The committee-grade gap: a model your IC will actually sign vs. a model your associate has to rebuild

### 5.3 Methodology (800w)
- Rubric derivation (why these 8 dimensions, what we excluded and why)
- Deal selection logic
- Pre-registration mechanic
- Scoring protocol + cross-check by external reviewer
- Limitations and access caveats — front-and-center, not buried

### 5.4 Results per deal (5 × 600w = 3000w)
Each section follows identical structure (helps comparison, helps skim):
1. Deal one-pager (€size, structure, why this deal exercises which moat)
2. ModelForge output: screenshot of formula bar showing live cell, dossier excerpt, drift report
3. Best generalist output for the same deal — what it got right, what it got wrong
4. Per-dimension scores in a single table
5. The "killer cell" — one specific cell where the gap is starkest (e.g., the DSCR-sculpted principal in Enfinity solar, or the GACS guarantee fair-value haircut in NPL)

Order matters — lead with **Enfinity PF solar** (biggest moat = biggest gap = most photogenic finding).

### 5.5 Cross-cutting findings (1000w)
- Pattern 1: **LLM-generated value cells are the root failure mode.** Quantify: Rogo / Shortcut produce X% hardcoded values, drift detection then impossible.
- Pattern 2: **Source traceability is binary, not gradient.** Either every cell links to a doc page or none do; competitors mostly cluster at none.
- Pattern 3: **Italian regulatory fit cannot be retrofitted by prompting.** Show one example where a generalist got AIFMD II Art. 26 retention wrong by structuring the SPV as a US Reg-D vehicle.
- Pattern 4: **Determinism = audit defensibility.** Show two runs of same prompt to a generalist producing materially different DSCR floors. Show ModelForge sha256 stability.
- Pattern 5: **Where generalists win** — narrative summarisation, English-language CIM drafting, comp-set screening from natural language. Acknowledge openly.

### 5.6 Limitations & honest threats to validity (400w)
- Sample size 5, not 50 — this is a directional benchmark, not a meta-analysis
- I built ModelForge — explicit conflict of interest, mitigated by pre-registration + external cross-score
- Three of five tools tested without full access — partial coverage flagged per dimension
- 6-month tool-evolution window: results dated Apr 2026, will degrade
- Italian focus — does not generalise to US sponsor-finance or UK direct lending without retesting
- Potential for adversarial prompt engineering on ModelForge's side — we'll publish prompts verbatim

### 5.7 Conclusion & call-to-action (400w)
- Restate thesis + headline numbers
- The strategic claim: **CLI-first deterministic tools beat hosted SaaS chat for committee-grade work**, and for Italian private credit specifically the moat is durable through 2027
- CTA #1: replicate — repo + data-room hash + rubric all public
- CTA #2 (commercial, soft): Italian credit funds wanting to pilot — email me
- CTA #3 (community): submit a 6th deal you'd like benchmarked

---

## 6. Publication strategy

| Venue | Reach to ICs | Credibility signal | Effort | Risk | Verdict |
|-------|--------------|-------------------|--------|------|---------|
| **SSRN (q-fin)** | Low (academics + a few quants) | High (citable) | Medium (formatting + abstract) | Low | Useful as cite-target, not the main horse |
| **arXiv q-fin** | Low — wrong audience | Medium | Medium | Low | Skip unless we want academic flag |
| **LinkedIn long-form** | **High — Luka's network is exactly the buyer**: Italian credit fund partners, Banca Finint, doValue, illimity, Anthilia, Tikehau Italia | Medium-high (founder voice) | Low | Medium (algorithm capricious) | **Run this — but as the amplifier, not the canonical** |
| **Personal Substack** | Medium — builds owned audience over time | Medium | Low setup | Low | Use as canonical home (own the URL) |
| **BeBeez.it** (Italian PE/credit trade press) | **VERY HIGH for the exact buyer** | High in IT market | Low (pitch the editor) | Low | **Pitch as exclusive coverage** of the launch |
| **Private Debt Investor** (PEI Media) | High among UK/EU LPs | High | Medium (editorial cycle) | Medium | Pitch the EU editor; longer lead time |
| **AIFI newsletter** | High among Italian PE/VC, medium among credit | High in IT market | Low | Low | Distribute via AIFI mailing — Luka likely already a member |
| **Banca Finint research notes** | Surgical (boutique credit ICs) | Very high | Medium (need partner relationship) | Low | Long-term play, not week-2 |

### Recommended stack (highest leverage, week 1):

**Primary**: own canonical PDF on personal Substack + GitHub repo (hash-citable, replicable).
**Tier-1 amplifier**: **BeBeez.it exclusive** — pitch editor on day 8 with embargo for publication day 14. BeBeez is the watering hole for Italian PE/credit; an exclusive places the paper directly in front of every IC partner in Milano.
**Tier-2 amplifier**: LinkedIn long-form post on publication day, tagging Banca Finint, AIFI, Anthilia, Tikehau Italia, and the named comparables (Rogo et al. — controversy = reach).
**Tier-3** (week 4): SSRN upload for permanent citability.

### The single best-leverage venue: **BeBeez.it exclusive**.

Reasoning: every Italian credit fund GP reads BeBeez. An exclusive feature converts the whitepaper from "white paper Luka wrote" to "BeBeez covered Luka's benchmark," which is what gets the meeting. Reach × precision × credibility per hour spent dominates LinkedIn (broad but noisy) and SSRN (citable but invisible to the actual buyer).

---

## 7. The realistic 2-week solo-founder sprint

Sprint window: **Mon Apr 20 – Fri May 1, 2026.** Publication target: **Sat May 2.**

### Days 1-3 (Mon-Wed Apr 20-22): Lock the rubric, generate ModelForge outputs

- Mon AM: **Pre-register rubric + deal list** as `research/whitepaper_us034_preregistration.md` and tag a git commit `whitepaper-prereg-2026-04-20`. (Anti-tuning credibility.)
- Mon PM: Assemble the 5 sealed data rooms (~3hrs/deal — use existing output/ artifacts where they exist; build CDMO + Enfinity solar from scratch).
- Tue: Run `modelforge build` on all 5 deals → run `modelforge dossier` → run `modelforge drift` → archive outputs + sha256 hashes under `research/outputs/mf/`.
- Wed: Self-score ModelForge on the 8 dimensions with screenshots. **Deliverable end of day 3: ModelForge baseline locked.**

### Days 4-7 (Thu-Sun Apr 23-26): Competitor outputs (this is the painful part)

- Thu: **Shortcut AI** — sign up, run all 5 deals at full fidelity. Score live. Capture screenshots. (~6 hrs)
- Fri: **Anthropic Claude for FS Excel plugin** — run all 5 deals. Score. (~4 hrs)
- Sat AM: **Macabacus Formulate** trial — run all 5. (~3 hrs)
- Sat PM: **Rogo** — pull every public demo, white paper, WSJ reproduction. Score what's verifiable. **Document explicitly what isn't.** Email Rogo for sandbox access; record refusal/silence.
- Sun: **Arc Intelligence** — same approach (Bain Credit references, Left Lane portfolio notes). Email request. **End of day 7: scoring matrix complete with N/A flags where access blocked.**

### Days 8-10 (Mon-Wed Apr 27-29): Write + self-score audit

- Mon: Executive summary + Methodology + Section 1 (Stevanato LBO). Word count target 2000.
- Tue: Sections 2-3 (Enfinity solar — the showcase, give it the most polish — + Banca Finint minibond). Target 4000 cumulative.
- Wed: Sections 4-5 (NPL waterfall, PMI structured credit) + cross-cutting findings. Target 6500 cumulative.

### Days 11-14 (Thu Apr 30 – Sat May 2): Edit, design, publish

- Thu: External cross-scorer reviews 1 deal (Enfinity solar). Capture their score + 30-min written feedback. Adjust ONLY if methodology disputed, not if score disputed (don't rebuild rubric to win).
- Thu PM: Pitch BeBeez editor with executive summary + offer of embargo to May 2.
- Fri: Final edit pass, build PDF dossier (use ModelForge's own dossier engine — meta-demo), prep LinkedIn carousel (5 slides, one per deal), Substack post draft.
- Fri PM: Email vendor right-of-reply notice (14-day window starts; we'll publish reply addenda if any).
- Sat: **Publish.** Substack live, BeBeez piece live, LinkedIn post live, GitHub repo public, SSRN upload queued.

### Sprint risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Competitor access blocked (Rogo, Arc) | High | Medium | Pre-committed N/A protocol; honest disclosure becomes a credibility *asset* |
| Self-score bias inflates ModelForge | High | High | External cross-scorer + pre-registered rubric + raw artifact publication |
| Scope creep (10 deals instead of 5) | Medium | High | Hard stop at 5; "v2 with 10 deals" becomes the natural follow-up paper |
| BeBeez editor doesn't bite | Medium | Medium | Tier-2 LinkedIn + AIFI fallback already wired in |
| Vendor right-of-reply produces a damaging counter | Low | Medium | Pre-registration kills "you cherry-picked"; honest scoring kills "you misrepresented us" |
| Luka burns out by day 10 | Medium | High | Day 8-10 word targets are aggressive; budget 50% buffer; Sundays off |

---

## 8. Success criteria (post-publication, 30-day window)

- 1+ Italian credit fund GP requests a pilot conversation
- 500+ qualified LinkedIn views (defined as: title contains "Credit / Private Debt / Direct Lending / Structured Finance" + Italy)
- 1 BeBeez or AIFI feature
- 1 vendor public response (any tone — engagement = legitimacy)
- 50+ GitHub stars on the benchmark repo
- 1 inbound from a competitor's investor (early-warning signal of impact)

If 3 of 6 hit, the paper served its strategic function and seeds the v0.6 commercial wedge.

---

## 9. Open questions before sprint kickoff

1. Who is the external cross-scorer? Need to identify by Apr 19. **Candidates**: a senior associate at Anthilia or a former Banca Finint analyst; an academic at Bocconi finance dept.
2. Do we want a co-author (Italian credit professional) for credibility, or does that dilute the founder-voice?
3. Should the BeBeez pitch include a quote from a named Italian GP, or stay solo? (Probably solo — adding a quote requires another permission gate and another week.)
4. Does ModelForge dossier engine handle Italian-language dossier? If not, English-only for v1, Italian translation for v2.

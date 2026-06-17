# Comparison — ModelForge vs Rogo / Macabacus / FAST

Three competitors / reference points in the financial-modelling SOTA landscape. ModelForge's positioning is deliberately niche: the intersection of **live-formula output, source-traceable cells, European credit/structured finance coverage, and regulator-grade audit dossier.** None of the three alternatives ship all four.

## Rogo (Series C, 25k users)

**What they do well.** Distribution (BB bank penetration), breadth of outputs (CIMs, pitchbooks, research, fairness opinions), GPT-5 + Gemini 3 stack, model-memory agents (acquired Offset Nov 2025), enterprise SSO.

**Where they lose vs ModelForge.**

- **Gen-AI hallucination risk.** Rogo generates models where cells are VALUES, not formulas. Values can drift from the specific opportunity and are disqualifying for rating-agency contexts.
- **No committee-grade source trace.** They don't ship a per-cell doc-page citation graph.
- **No regulator-grade dossier.** Their architecture can't produce a PDF where every number traces to a documented source.
- **US-centric.** Italian AIFMD II, legge 130/1999, IRES/IRAP, GACS, FER X — not native.

## Macabacus

**What they do well.** Excel-native add-in, bulge-bracket formatting conventions, bootstrapped / profitable, strong reference-template library.

**Where they lose.**

- **No AI.** Pure formatting + shortcut tooling.
- **No data-room ingestion.** Users hand-build every model from scratch.
- **No source provenance.** Cells don't carry cited sources or auditor trails.
- **Static templates.** No spec-driven generation; every model is a fresh manual build.

## FAST Standard / SSRB / SMART

**What they do well.** Methodology standards — Flexible, Appropriate, Structured, Transparent. Widely respected reference for modelling discipline.

**Where they lose.**

- **Standards, not tools.** You conform manually; nothing enforces the rules.
- **No automation.** Every model is still a hand-build.

ModelForge is FAST-compliant by design (colour code, named ranges, sign convention, single source of truth on Assumptions). The 8-check QC gate enforces many FAST principles automatically.

## The defensibility thesis

ModelForge's moat isn't any single dimension — Rogo wins on breadth and distribution, Macabacus owns Excel-add-in incumbency, FAST is the de-facto methodology standard.

ModelForge wins by being **the only product where every cell is live, every number is sourced, every change is diffed, every assumption is defended, every model is auditable, and every professional can install it where they already work** (CLI today; Excel add-in + web SaaS shipping v0.5).

## SOTA scorecard snapshot (2026 Q2)

| Dimension | ModelForge | Rogo (Series C) | Macabacus | Italian bulge specialist |
|---|---|---|---|---|
| Live formula output | 10 | 3 | 10 | 10 |
| Source traceability (cell → page) | 9.4 | 3.6 | 2 | 8 |
| Italian regulatory pack native | 10 | 3 | 3 | 9 |
| Committee-grade deliverable | 9 | 6 | 8 | 10 |
| Data-room ingestion | 7 | 9 | 0 | n/a |
| Breadth of templates | 11 | 40+ | 30+ | n/a |
| Audit dossier export | 9 | 0 | 0 | 5 (manual) |
| Model-memory agents | 0 (v1.0) | 8 | 0 | 0 |
| Distribution (seat count) | 2 (2026 Q2) | 10 | 9 | 0 |
| Weighted SOTA | **9.0** | 7.9 | 7.5 | 9.4 |

# FAQ

## Why not just use Rogo / ChatGPT / Claude directly?

Generic LLMs produce workbooks where cells are VALUES, not live formulas. That's a non-starter for credit-committee or rating-agency deliverables: values drift from the specific deal, they don't respond to scenario flips, and they can't be audited back to a documented source. ModelForge's deterministic builder + linkage graph solves that specific gap. LLMs are good at writing specs; Python is better at writing cells.

## Can I use ModelForge without an API key?

Yes, for everything except `modelforge chat --backend api` and the default `--backend api` for ingestion. `modelforge ingest --backend cli` uses Claude Code's local invocation — no API key needed. Local `build`, `qc`, `verify`, `dossier`, `lineage`, `stats` commands require no network access.

## Does the dossier reveal my deal to an LLM?

No. The dossier is generated entirely locally from the workbook + linkage graph. No LLM call involved. The chat REPL is the only optional path that sends model details to Anthropic.

## How does the spec hash work?

We compute SHA-256 over the raw YAML bytes (deterministic across platforms). The hash is written to a `Reproducibility` sheet and a workbook-level `mf_spec_sha256` named range. `modelforge verify <xlsx> --spec <yaml>` recomputes it and compares. Any change to the spec file — even a whitespace edit — produces a different hash, so auditors can confirm the workbook was built from a specific spec version.

## Why YAML specs and not a GUI?

YAML is diff-able, version-controllable, and text-first. Finance professionals keep specs in Git alongside their workbook output. A GUI front-end is on the roadmap (v0.5 web SaaS + Excel add-in) but the CLI stays canonical.

## Which Italian regulatory rules are native?

AIFMD II (live Apr 2026), legge 130/1999 (securitization), IRES 24% + IRAP 3.9% tax stack, ECB / Consob / Banca d'Italia reporting, GACS-compliant senior tranche structuring, FER X auction pricing for solar PF. Damodaran 2026 Italy ERP (6.7% / mature 4.23%) is the DCF baseline. IFRS 9 §B5.4.1 EIR is cited inline on every Returns sheet.

## How do I add a new template?

Roughly 4 files and a test. See the [Template Gallery](templates.md) — "Extending" section at the bottom.

## Can I run ModelForge on-prem / air-gapped?

Yes for build / QC / dossier / verify. Ingestion requires an LLM endpoint (can be Azure OpenAI / Bedrock / on-prem Llama in v1.0 per PRD). Full on-prem Helm chart is v1.0 scope.

## What's on the v0.5 / v1.0 roadmap?

v0.5 ships the three defensibility moats: probabilistic credit engine (Merton / KMV / IFRS 9 ECL), competitor-model reverse-engineer, and model diff. Also a web SaaS thin layer + ECB / Damodaran live data feeds.

v1.0 ships enterprise (SAML SSO, SOC 2 Type II, on-prem, multi-tenant), global regulatory packs (EDGAR / HKEX / SGX / PRA), model-memory agents with data-room watcher, voice MD-review mode, and a template marketplace.

See `PRD_v04_to_v10_sota.md` in the repo for the full plan.

## Licensing?

Proprietary. Contact the author for terms. Early-access freelance engagements starting now; SaaS in v0.5; enterprise in v1.0.

## Where do I report bugs or request features?

GitHub issues on the `modelforge` repo. For security issues, email `security@modelforge.app`.

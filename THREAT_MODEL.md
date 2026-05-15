# ModelForge — Formal Threat Model (STRIDE)

**Last updated**: 2026-05-15
**Owner**: Luka Stanisljevic (redacted@example.com)
**Companion**: [`SECURITY.md`](SECURITY.md) (vulnerability disclosure, supply-chain integrity, audit logging, compliance posture)

This document complements `SECURITY.md` with a STRIDE-style threat catalogue.
STRIDE = **S**poofing · **T**ampering · **R**epudiation · **I**nformation disclosure
· **D**enial of service · **E**levation of privilege.

---

## 1. System scope

ModelForge is a Python library + CLI + MCP server. Three deployment modes
are in scope today:

| Mode | Surface | Notes |
|---|---|---|
| **Local CLI** (`modelforge build/qc/audit-all`) | filesystem only | The primary mode. No network except optional Anthropic API for ingest + free data feeds (EDGAR, Yahoo, World Bank, FRED, ECB, GLEIF, OpenFIGI, Damodaran). |
| **MCP server** (`modelforge-mcp` stdio) | local IPC only | Same trust boundary as the calling MCP client (Claude Desktop, Claude Code, Cursor). |
| **PyPI distribution** (`modelforge-finance` wheel) | install pipeline | Build + publish supply chain. |

Out of scope today (Phase B+):
- Hosted multi-tenant SaaS
- HTTP API surface
- Browser UI

---

## 2. Trust boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│  USER's MACHINE                                                  │
│                                                                  │
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────┐      │
│  │ YAML spec  │ → │  ModelForge  │ → │ XLSX / DOCX / PPTX │      │
│  │ (trusted)  │   │  Python pkg  │   │  + audit DB         │      │
│  └────────────┘   └──────┬───────┘   └────────────────────┘      │
│                          │                                       │
│  ┌────────────┐          │           ┌────────────────────┐      │
│  │ PDF / XLSX │ ────────►│           │  ~/.modelforge/    │      │
│  │ data room  │  ingest  │           │   audit.db (SQLite)│      │
│  │ (UNTRUSTED)│          │           └────────────────────┘      │
│  └────────────┘          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┬───────────────┐
            ▼ Anthropic API│              ▼ Free feeds    ▼ MCP client
        (TLS, key in env)  │       (TLS, no auth needed) (stdio, local)
                           ▼
                    ┌──────────────┐
                    │ Anthropic    │
                    │ Claude API   │
                    │ (3rd party)  │
                    └──────────────┘
```

**Trusted**: YAML specs (analyst-authored), the Python interpreter, the user's
filesystem, the audit DB.

**Untrusted**: PDFs/XLSXs ingested from a data room; data fetched from free
public APIs; any input from network; the Anthropic API response stream.

---

## 3. STRIDE catalogue

### S — Spoofing identity / source

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| S-01 | Malicious upstream package on PyPI typo-squatting `modelforge-finance` (`modleforge`, `modeforge-finance`) | RCE on `pip install` | Document canonical names in README; future Sigstore signing on releases (this PRD); user verification of package source via PyPI trusted publishers. |
| S-02 | Forged `target.ticker` in spec spoofs another company's market cap reference | Misleading Trust Layer mcap deviation result | Trust Layer rule reports the ticker symbol it queried; user is responsible for ticker validity (same as any modelling input). Source IDs in `sources:` block remain authoritative. |
| S-03 | Compromised free-feed endpoint returns falsified market data (e.g., MITM on Yahoo) | Trust Layer mcap deviation false-clean | All free feed adapters use TLS. No certificate pinning today; for high-stakes runs prefer paid bulge-bracket adapter (Phase B). Documented in adapter docstrings. |

### T — Tampering with data / code

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| T-01 | Post-build XLSX modification (analyst alters number after sign-off) | Audit-trail divergence | Workbook hash recorded in audit DB at build time; reproducibility test (D2 next) regenerates from same spec → same hash. |
| T-02 | YAML spec edited after build to change source IDs | Sources sheet stale | Spec hash + source-IDs hash recorded in audit DB; lineage walk (D2) emits a verification report. |
| T-03 | Malicious YAML attempts code injection via `!!python/object` tags | RCE | `yaml.safe_load` everywhere; no `yaml.load`; pydantic schema rejects unknown types. |
| T-04 | PyPI artifact tampered between build and install | Wrong code on user machine | SHA-256 in PyPI metadata; SLSA L3 build provenance + Sigstore signing on releases (this PRD); `pip install --require-hashes` supported. |
| T-05 | Audit DB rows altered post-event | False clean audit trail | Append-only at application level; Phase-B adds hash chain + periodic anchoring (OriginStamp / OpenTimestamps). Documented as known-limit in SECURITY.md §4. |

### R — Repudiation (deniability)

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| R-01 | Analyst denies running a build that produced a specific model | No proof | Audit DB records OS user + host + PID + working directory + spec hash + output hash for every operation. |
| R-02 | "I never ingested that data room" denial | No traceable input chain | Ingest writes spec_source_path + spec_source_bytes hash to audit DB (T-04 & T-05 above). |
| R-03 | Reviewer denies seeing a workbook variant | No diff record | Phase-B (D6 collab): version diff between workbook builds. Today: filesystem timestamps + audit DB. |

### I — Information disclosure

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| I-01 | `ANTHROPIC_API_KEY` leaked in process env-var dump or logs | Anthropic billing fraud | Key read from env only; never logged; never written to spec/output/audit DB; install docs warn user. Rotate via Anthropic Console. |
| I-02 | Sensitive deal data in spec exposed to free public feeds (e.g., querying `ticker: TARGET-PRIVATE-NEWCO`) | Search-engine indexing of competitive intel | Free adapters do not POST spec content; only read public market data. `target.ticker` is opt-in per spec. |
| I-03 | Audit DB world-readable on shared filesystem | Inter-user information leak | DB stored in `~/.modelforge/audit.db` (user-private); install docs document chmod 600 recommendation. |
| I-04 | Workbook contains source-bound text (analyst notes from PDFs) which gets shared more widely than intended | Confidential text in a wider audience | Sources sheet shows publisher + URL but not raw page text by default; ingest output is reviewable before workbook redistribution. |
| I-05 | Anthropic ingest call sends entire deal PDF to a third party | Confidentiality breach if PDF is non-public | User opts in via `ingest`; Anthropic DPA covers data handling; documented in SECURITY.md §6 ("GDPR (with ingest)"). For ultra-sensitive deals: skip ingest, hand-author YAML. |

### D — Denial of service

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| D-01 | Pathological YAML triggers exponential memory in pydantic validation | OOM | Pydantic v2 caps recursion; spec sizes under 1MB in practice; large datasets (e.g., NPL portfolios) chunked at the model level. |
| D-02 | Free feed rate-limit exhaustion blocks legitimate use | Cannot run audit harness | Adapters back off (cache layer with TTL); harness uses `--sleep` flag (default 1.5s). Prefer paid adapter at scale (Phase B). |
| D-03 | Yahoo crumb expiry mid-run (24h cookie window) | Fundamentals fetch fails | Cached process-lifetime; refreshes on 401/403. Documented limit in `feeds/yahoo.py` docstring. |
| D-04 | Malicious data-room PDF crashes pdfplumber | Build pipeline fails | Sandboxed parsing recommended (Phase B: separate process); today: `try/except` around ingest, error → user. Trusted-source documentation in SECURITY.md §3. |

### E — Elevation of privilege

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| E-01 | XLSX template embeds `=HYPERLINK("file:///etc/passwd")` style formula | Local file read on Excel open | We do not write formulas referencing external commands; openpyxl does not auto-execute on write. User opening downloaded XLSXs in Excel is responsible for "Disable Macros" hygiene (no macros are emitted by ModelForge). |
| E-02 | MCP client invokes ModelForge tools with crafted args | Code path abuse | MCP server runs in user's permission context; tools do filesystem operations — same trust model as the user. No setuid/elevated paths. |
| E-03 | Dependency CVE introduces RCE in pdfplumber/openpyxl/pydantic | RCE on user machine | Dependabot enabled (Phase B target); `pip-audit` in CI advisory (this PRD); SECURITY.md §3 commits to advisory monitoring. |

---

## 4. Risk-rating summary

Likelihood × Impact (qualitative):

| ID | Likelihood | Impact | Inherent risk | Residual risk |
|---|---|---|---|---|
| S-01 (typo-squat) | Low | High (RCE) | Med-High | Low (PyPI canonical name + Sigstore) |
| S-03 (free-feed MITM) | Very low | Med | Low | Very low (TLS + paid alt for high-stakes) |
| T-04 (PyPI tamper) | Very low | High | Med | Very low (SLSA L3 + Sigstore once shipped) |
| T-05 (audit DB tamper) | Low | Med | Low-Med | Low (Phase-B hash chain) |
| I-01 (key leak) | Low | Med | Low-Med | Low (env-only handling) |
| I-05 (ingest exposure) | Med (user choice) | Med | Med | Low (opt-in + DPA) |
| D-04 (PDF crash) | Med | Low | Low-Med | Low (try/except + trusted-source guidance) |
| E-03 (dep CVE) | Med (always) | High | Med-High | Low (CI + Dependabot + advisory monitoring) |

All other threats: **Low** inherent, **Very low** residual.

---

## 5. Out-of-scope today (Phase B targets)

- Multi-tenant SaaS hosted at modelforge.* — when added, full re-threat-model required (auth, session mgmt, tenant isolation, OWASP API Top 10).
- HTTP API surface (today everything is local).
- WebSocket collab (D6 in PRD-v11).
- Bug bounty program (Phase B with capital).

---

## 6. Verification cadence

| Check | Frequency | Implementer |
|---|---|---|
| `pip-audit` against `requirements.txt` | every push (advisory CI) | `.github/workflows/security.yml` |
| Bandit static analysis | every push (advisory CI) | `.github/workflows/security.yml` |
| `safety` known-CVE scan | every push (advisory CI) | `.github/workflows/security.yml` |
| Manual STRIDE review | every minor release | Maintainer (Luka) |
| Threat model document refresh | every quarter or after major architecture change | Maintainer |

This document is **not** a substitute for an external pen-test. Pen-test is gated
on Phase-B capital per `SECURITY.md` §6.

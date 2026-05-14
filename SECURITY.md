# Security Policy

**Last updated**: 2026-05-14 · **Version**: 0.9.0
**Owner**: Luka Stanisljevic (redacted@example.com)

## Threat model

ModelForge is a **local-execution tool**: a Python library + CLI + MCP server
that builds Excel workbooks from YAML specs. It does **not**:

- Run as a hosted SaaS by default (Phase-B roadmap)
- Receive customer financial data on infrastructure we control (data stays local)
- Send model contents to third parties (except `ingest`'s optional Anthropic API call)

Therefore the primary threats this policy addresses:

| Threat | Mitigation |
|---|---|
| Untrusted YAML spec → arbitrary code execution | Pydantic schema validation; no `eval` / `exec` on user inputs |
| Untrusted PDF / XLSX in `ingest` → exploit in pdfplumber / openpyxl | Pin parser libs; advisory monitoring via dependabot; sandboxed parsing recommended |
| Supply-chain compromise (dependency injection) | Pin all deps in `pyproject.toml` with `>=` minimums + lockfile; renovate/dependabot enabled |
| Source-trace tampering (post-build modification) | Append-only audit log (`modelforge/audit_log.py`); content-hash verification |
| Credential leakage (ANTHROPIC_API_KEY for ingest) | Env var only — never logged, never committed; user warned at install |
| Cell-content injection via `=cmd|/c calc!A0` style | openpyxl emits raw values; we don't write formulas that reference external commands |

## Reporting a vulnerability

If you discover a security issue, please email **redacted@example.com**
with subject `[SECURITY] modelforge: <short description>`.

**Please do not** open a public GitHub issue for security vulnerabilities.

Expected response window:
- Acknowledgement: within 5 business days
- Triaged with severity: within 10 business days
- Fix or workaround: depends on severity (Critical: 30 days; High: 60 days)

A responsible-disclosure window of 90 days from acknowledgement is standard.
Credit will be given in the changelog and SECURITY-ADVISORIES.md unless the
reporter prefers anonymity.

## Supply-chain integrity

- All dependencies pinned with minimums in `pyproject.toml`
- Source distribution + wheels signed (Phase-B: in-toto attestations)
- Git tags signed (Phase-B: Sigstore via OIDC)
- SBOM available on request — format CycloneDX 1.5 (Phase-B: auto-generated per release)

## Audit logging

`modelforge.audit_log` provides an append-only SQLite log of every
build / qc / ingest / export operation. Default location:
`~/.modelforge/audit.db`. Each event records:

- Event ID (UUID), start/end timestamp, duration
- Operation name, status (ok / error)
- Inputs (JSON) + SHA-256 hash of inputs
- Outputs (JSON) + SHA-256 hash of outputs
- User (OS account), host, PID, working directory
- Error string (on failure)

For regulator-grade auditing, ship this DB alongside the workbook deliverable.

## Encryption

- **At rest**: ModelForge does not encrypt YAML specs or output workbooks by
  default. For sensitive deals, store on encrypted filesystems (LUKS / BitLocker /
  FileVault). Phase-B: native at-rest encryption with user-provided key.
- **In transit**: For `ingest` (Anthropic API): TLS 1.2+ enforced by the
  `anthropic` SDK. No other network operations except optional free data
  feeds (FRED, Yahoo, World Bank, ECB), all TLS-secured.

## Compliance posture

| Standard | Status | Path to compliance |
|---|---|---|
| SOC 2 Type II | **Not certified** | Phase B: audit firm engagement, ~$30-80K + 6-12 months |
| ISO 27001 | **Not certified** | Phase B: optional EU procurement gate, ~$20-50K + 6-12 months |
| GDPR (EU) | **Compliant by design** | No PII processed by default; user-controlled local execution |
| GDPR (with ingest) | **DPA required** | If customer ships PII in PDFs to ingest, ANTHROPIC_API_KEY signs DPA with Anthropic |
| PCI DSS | **N/A** | No card data |
| HIPAA | **N/A** | No PHI |
| Penetration testing | **Not yet performed** | Phase B: annual pen test by approved firm |

Compliance is **gated by Phase-B capital**. For [redacted] today,
ModelForge runs on customer infrastructure inside their existing compliance
perimeter. No data leaves their network.

## Known limitations

1. **YAML parsing** uses `yaml.safe_load`. Custom Python types not supported.
2. **PDF parsing** in `ingest` relies on pdfplumber and pypdf — both have
   historical CVE reports; we monitor advisories via dependabot but cannot
   guarantee zero-day immunity. **Do not ingest PDFs from untrusted sources.**
3. **openpyxl** does not enforce formula sandboxing — a maliciously crafted
   XLSX uploaded to `ingest` could embed `HYPERLINK` formulas. We filter these
   on load; verify the QC sheet output before redistributing.
4. **Audit log** is append-only at the application level but not tamper-proof
   against root-level filesystem access. Phase-B: optional hash-chained append
   with periodic anchor to public timestamp (OriginStamp / OpenTimestamps).

## Update policy

Security advisories will be published as:
- `SECURITY-ADVISORIES.md` in the repo
- GitHub Security Advisories
- pinned tweet / LinkedIn post for ≥High severity

Patch releases follow semver: `0.x.Y` for patches, `0.X.0` for minor.

## Acknowledgements

This security policy is informed by:
- OWASP ASVS L1 (baseline)
- NIST SSDF (PO.5 - Software Supply Chain)
- CIS Controls v8 (CSC 16 - Application Software Security)

Full compliance documentation lives in `compliance/` and updates with each
release.

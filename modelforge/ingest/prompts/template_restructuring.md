# Restructuring template — extractor guidance

Target spec class: `modelforge.spec.restructuring.RestructuringSpec`.

## A-id allocation

- `A-001 – A-049` — Enterprise value to be allocated (recoverable EV)
- `A-101 – A-149` — DIP facility terms (size, rate, super-priority status)
- `A-201 – A-299` — Claim classes (one block per class — see ClaimClass shape)
- `A-301 – A-349` — Plan recovery mechanics (cash, new equity, takeback debt)
- `A-401 – A-449` — Exit financing (revolver, term loan, exit equity)

## Absolute priority rule (US Chapter 11 / Italian L.155)

Recoveries flow strictly senior → junior:
1. Administrative + priority claims (paid in full, cash)
2. Secured claims (paid up to collateral value)
3. Unsecured claims (deficiency from secured + general unsecured)
4. Equity (old equity wiped unless out-of-the-money waterfall is overridden)

Cumulative class recovery cannot exceed 100% of allowed claim amount.

## Plan-of-reorganization conventions

- `enterprise_value_recoverable`: distinct from "going-concern EV" — this is what's
  available for distribution AFTER admin claims, DIP repayment, exit financing.
- `senior_secured_recovery_pct`: usually 80-100% par; fulcrum security typically 60-80%
- `unsecured_recovery_pct`: typically 5-40% par; lower for deeply distressed estates
- `time_to_emergence_months`: median 12-18 months for traditional Ch.11; pre-pack 1-3 months

## Section types to extract

- `target` (Target shape)
- `dip` (DIPFacility)
- `plan` (PlanRecovery)
- `claim_classes` (list of ClaimClass — handled as LLM-table)

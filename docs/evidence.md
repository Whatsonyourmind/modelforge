# Evidence-binding gate

`source_id: S-001` says a number came from a *document*. It does not say the
document states *that quantity*. The evidence-binding gate checks the binding:
for every numeric leaf, does the support given actually state this figure, at
this unit, as this kind of quantity?

It exists because of a real defect. The shipped Enfinity spec filed the €316M
*financing package* (€214M senior debt plus €101M VAT/PPA/decommissioning
facilities) as `total_capex_eur_m`, with `confidence: H` and a correct source
id. All fifteen existing gates (QC 8/8, Trust 3/3, Moat 4/4) passed it. The
evidence gate fails it with one line:

```
A-001  construction.total_capex_eur_m  316 eur_m  broken
       the rationale binds €316m to 'financing package' (financing_package),
       but the field is filed as capex
```

Tier 1 is **deterministic and uses no LLM**: number parsing, a hand-written
role lexicon, string matching and arithmetic. Every verdict can be re-derived
by reading the code.

## Running it

```bash
modelforge evidence check spec.yaml                       # offline checks
modelforge evidence check spec.yaml --dataroom ./dataroom # + locate quotes, cross-check documents
modelforge evidence check spec.yaml --strict --all --json evidence.json
```

`modelforge build` runs the gate first and **refuses to build** while any leaf
is `broken` or `contested`. It writes the full report next to the workbook as
`<stem>.evidence.json`. `build --dataroom DIR` and `build --evidence-strict`
pass straight through to the gate.

## Verdicts

| verdict | meaning | blocks |
|---|---|---|
| `bound` | the quote is in the cited document, states the value at the field's unit, and names the field's role | no |
| `derived` | the declared `expr` recomputes to the value, and its sourced inputs are bound | no |
| `assumption` | analyst judgment with an owner; no sourcing is claimed | no |
| `unverified` | a binding is claimed but could not be checked (no quote, no dataroom, document missing) | only with `--strict` |
| `contested` | another document states a conflicting figure, or the same figure as a different quantity | **yes** |
| `broken` | a deterministic check failed | **yes** |
| `overridden` | a blocking verdict accepted by a signed human override | no, but always reported |

## Declaring evidence in a spec

Any `Assumption` can carry an `evidence:` block.

```yaml
amount:
  { id: A-020, name: senior_amount, unit: eur_m, base: 214.0, source_id: S-006, ...,
    evidence: { kind: fact, source_id: S-006, page: 1,
                quote: "Facility amount: EUR 214,000,000." } }

availability_payment_eur_m_yr1:
  { id: A-010, name: revenue_yr1, unit: eur_m, base: 32.1, ...,
    evidence: { kind: derived,
                expr: "capacity_mw * yield_kwh_per_kwp * price_eur_per_mwh / 1e6",
                terms: { capacity_mw:       { value: 276,  source_id: S-001, quote: "..." },
                         yield_kwh_per_kwp: { value: 1550, source_id: S-003, quote: "..." },
                         price_eur_per_mwh: { value: 75,   source_id: S-004, quote: "..." } } } }

opex_pct_revenue:
  { id: A-012, unit: pct, base: 0.22, ...,
    evidence: { kind: benchmark, source_id: S-002, peer_set: "Italian utility-scale solar",
                quote: "... aggregate to approximately 22 percent of revenue" } }

total_capex_eur_m:
  { id: A-001, unit: eur_m, base: 316.0, confidence: L, ...,
    evidence: { kind: assumption, owner: Analyst, note: "capex not disclosed; proxy" } }
```

- **fact**: requires `quote` and a source. `page` is optional; when given, the
  quote must be on that page.
- **derived**: requires `expr`. Names resolve to `terms` or to other
  assumptions by `name`. Only `+ - * / **`, numbers and names are allowed.
  `eval` is never called.
- **benchmark**: requires `quote` and `peer_set`. The value may sit inside a
  quoted range ("150-200 bps").
- **assumption**: requires `owner`.
- **unverified**: an explicit "not yet supported".

A leaf with **no** `evidence:` block is read from what it already says. With a
`source_id`, it claims to be a sourced fact: the gate checks its rationale and
the source's `note` for a role conflict and for arithmetic, and with
`--dataroom` it searches the cited document for the value, suggesting a quote
when it finds one. Without a `source_id`, it is an assumption owned by
`meta.analyst`.

## The checks

| check | catches |
|---|---|
| `quote_present` | a quote that is not in the cited document (whitespace/unicode-normalised, case-insensitive), or is on a different page |
| `value_in_quote` | "cited page 8, number from nowhere" |
| `unit_consistent` | the digits are there but at a different scale or unit (`EUR 316 thousand` for 316 eur_m; 75 bps for 75%) |
| `role_quote` / `role_rationale` / `role_source_note` | the words next to the value name a different quantity: financing vs capex, equity vs enterprise value, gross vs net, committed vs drawn, GBV vs NBV, revenue vs GWP, margin vs base rate, … |
| `derived_recompute` | a declared derivation that does not recompute |
| `rationale_arithmetic` | arithmetic in a rationale that does not hold, or a derivation filed as a sourced fact |
| `cross_source` | another document stating the same figure as a different quantity, or a different figure for the same quantity |
| `locate` | a quote-less citation whose document states the value only as a different quantity |

The role lexicon (`modelforge/evidence/roles.py`) is versioned
(`LEXICON_VERSION`). Two roles only conflict inside the same confusable family;
a phrase the lexicon does not know is neutral, never a failure.

## Overrides

A blocked leaf ships only with a signed decision, recorded at the top level of
the spec:

```yaml
evidence_overrides:
  - { id: A-001, verdict: contested, signed_by: "L. Analyst", date: 2026-10-11,
      reason: "IM capex confirmed by the EPC contract; the press-release 316 is the financing package." }
```

The override must name the verdict it accepts. An override with no reason or
signer is rejected, and the build stops. Overrides that match nothing are
reported as unused. Every honoured override is printed and written into
`<stem>.evidence.json` with the original verdict.

## Limits (stated, not hidden)

- Only `Assumption` leaves are checked. Plain numeric fields with a sibling
  `*_source_id` (e.g. `target.revenue_last_fy_eur_m`) and templates whose
  specs use no `Assumption` (IPO, restructuring, portfolio review) are not
  covered yet.
- Only the `base` scenario value is checked, not `worst`/`best`.
- On specs that declare no evidence and supply no dataroom, the role check
  only engages when the rationale or source note mentions the value: 14 of
  661 leaves across the shipped examples. The gate's strength is in declared
  quotes checked against a dataroom.
- Tier 2 (an independent LLM adjudicator that may only *downgrade*) is not
  built. Tier 1 must never be an LLM.

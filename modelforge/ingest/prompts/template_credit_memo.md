# Credit Memo template — extractor guidance

Target spec class: `modelforge.spec.credit_memo.CreditMemoSpec`.
Extends Unitranche with stress scenarios, rating inputs, and narrative lists.

## A-id allocation

Follows Unitranche ranges (A-001 – A-089) plus:

- `A-090 – A-099` — stress scenarios (downside EBITDA, recovery %, LGD)
- `A-100 – A-109` — rating inputs (EBITDA coverage, leverage, sector risk)

## Narrative fields

Credit memo carries three plain-text lists:

- `credit_strengths` — 3-6 bullets
- `credit_weaknesses` — 3-6 bullets
- `mitigating_factors` — 3-6 bullets

Extract from the IM narrative / risk factors section.

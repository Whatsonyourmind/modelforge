"""Named ranges the deck exporter reads out of a built workbook.

The moat gate flags a defined name that no *formula* references, on the
principle that a declared driver the model ignores is a defect: an analyst
edits it and nothing moves. These names are the exception. They are defined so
``modelforge.deck.adapter`` can lift a headline figure straight out of the
workbook by name instead of hunting for a cell address, so they do have a
consumer — it just is not a formula.

Kept in a module of its own, with no heavy imports, so the gate can consult it
without pulling in python-pptx. ``tests/test_deck_named_facts.py`` asserts this
set matches the ``named_fact("…")`` call sites in the adapter, so the two
cannot drift apart silently.
"""

from __future__ import annotations

DECK_NAMED_FACTS: frozenset[str] = frozenset({
    "acquisition_price_eur_m",
    "dev_exit_cap_rate",
    "exit_cap_rate",
    "exit_year_input",
    "gp_promote_pct",
    "lp_capital_commitment_pct",
    "ltv_pct",
    "purchase_price_eur_m",
})

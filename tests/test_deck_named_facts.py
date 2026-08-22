"""The deck's named-fact allowlist must match its actual call sites.

``DECK_NAMED_FACTS`` tells the moat gate which defined names are exempt from
the orphan check because the deck exporter reads them. An allowlist that drifts
from reality is worse than none: a stale entry silently exempts a name that
really has become an orphan, which is exactly the "declared driver nothing
reads" defect the gate exists to catch.
"""

from __future__ import annotations

import re
from pathlib import Path

from modelforge.deck.named_facts import DECK_NAMED_FACTS

ADAPTER = Path(__file__).resolve().parents[1] / "modelforge" / "deck" / "adapter.py"


def test_allowlist_matches_adapter_call_sites():
    source = ADAPTER.read_text(encoding="utf-8")
    called = set(re.findall(r'named_fact\(\s*"([A-Za-z_][A-Za-z0-9_]*)"', source))
    assert called, "no named_fact(\"…\") call sites found — has the adapter moved?"

    missing = sorted(called - DECK_NAMED_FACTS)
    stale = sorted(DECK_NAMED_FACTS - called)
    assert not missing, (
        "names the deck reads but the allowlist omits (the moat gate will "
        f"report them as orphans): {missing}"
    )
    assert not stale, (
        "names on the allowlist the deck no longer reads — they are exempt "
        f"from the orphan gate for no reason: {stale}"
    )

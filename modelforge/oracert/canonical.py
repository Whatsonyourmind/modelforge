"""Cross-runtime canonical content hash — byte-identical to OraClaw's TS kernel.

OraClaw computes a certificate's ``contentHash`` as::

    sha256( JSON.stringify( canonicalize(payload) ) )

where ``canonicalize`` turns every finite number into ``Number.toFixed(12)`` (a
string), non-finite numbers into ``String(value)``, sorts object keys, and
preserves arrays; ``JSON.stringify`` then emits no whitespace. This module is
the exact Python port, so a standalone verifier can re-derive the OraClaw
content hash without the TS runtime.

The ONLY value class where naive Python diverges from JS is **negative zero**
(``(-0).toFixed(12)`` is ``"0.000000000000"`` in JS but ``"-0.000000000000"``
in Python); it is normalised here. A committed golden vector
(``tests/oracert``) locks the parity against drift.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _js_to_fixed_12(x: float) -> str:
    """ECMAScript ``Number.prototype.toFixed(12)``.

    Faithful in two places naive ``format(x, ".12f")`` diverges from JS:
      * ``|x| >= 1e21`` → toFixed delegates to ``ToString`` (exponential), which
        Python reproduces via ``repr`` over the same shortest-round-trip range;
      * negative zero → JS drops the sign.
    """
    if abs(x) >= 1e21:
        # JS ToString(x): shortest round-trip; exponential in this range, as in
        # Python's repr (both >= 1e21 emit "...e+NN").
        return repr(x)
    if x == 0.0:
        x = 0.0  # normalise -0.0 → 0.0
    return format(x, ".12f")


def canonicalize(value: Any) -> Any:
    """Mirror OraClaw's ``canonicalize`` (numbers→toFixed(12), sorted keys)."""
    if isinstance(value, bool):
        return value  # JS treats booleans as non-numbers (passthrough)
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f):
            return "NaN"
        if math.isinf(f):
            return "Infinity" if f > 0 else "-Infinity"
        return _js_to_fixed_12(f)
    if isinstance(value, list):
        return [canonicalize(v) for v in value]
    if isinstance(value, dict):
        return {k: canonicalize(value[k]) for k in sorted(value.keys())}
    return value  # str / None passthrough


def content_hash(payload: Any) -> str:
    """sha256-hex of the canonicalised payload, matching OraClaw byte-for-byte.

    ``separators=(",", ":")`` reproduces ``JSON.stringify`` (no whitespace);
    ``ensure_ascii=False`` matches JS emitting raw UTF-8; keys are already
    sorted by :func:`canonicalize`, so ``sort_keys`` stays off.
    """
    blob = json.dumps(
        canonicalize(payload), separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

"""Recompute derived values.

Two entry points:

* `evaluate(expr, names)` — a declared `evidence.expr`, evaluated by a tiny
  AST walker (numbers, names, + - * / **, parentheses). No `eval`.
* `rationale_arithmetic(text)` — arithmetic an analyst wrote into a rationale
  ("276 MW × 1,550 kWh/kWp/yr × €75/MWh = €32.1M/yr"). Used to notice that a
  value filed as a sourced fact is in fact a derivation, and to check the sum.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass

from modelforge.evidence.numbers import close, find_mentions

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow}


class ExprError(ValueError):
    pass


def evaluate(expr: str, names: dict[str, float]) -> float:
    """Evaluate `expr` over `names`. Raises ExprError on anything else."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ExprError(f"cannot parse expr {expr!r}: {e.msg}") from None

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ExprError(f"unknown name '{node.id}' in expr (define it in `terms` "
                                f"or reference an assumption by `name`)")
            return float(names[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        raise ExprError(f"unsupported syntax in expr {expr!r}: {type(node).__name__}")

    try:
        return ev(tree)
    except ZeroDivisionError:
        raise ExprError(f"division by zero in expr {expr!r}") from None


def expr_names(expr: str) -> set[str]:
    try:
        return {n.id for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.Name)}
    except SyntaxError:
        return set()


@dataclass(frozen=True)
class RationaleArithmetic:
    text: str            # the equation as found
    operands: tuple[float, ...]
    op: str              # "*" or "+"
    computed: float      # product / sum of the operands, as written
    stated: float        # right-hand side, as written (scale applied)
    consistent: bool     # computed == stated up to a power-of-1000 unit scale

    def scaled_to(self, target: float) -> float | None:
        """`computed`, rescaled by the power of 1000 that brings it closest to target."""
        if target == 0:
            return None
        best = None
        for k in range(-4, 5):
            v = self.computed * (1000.0 ** k)
            if best is None or abs(v - target) < abs(best - target):
                best = v
        return best


_EQ_SEGMENT = re.compile(r"([^=;.()\n]*?(?:\d[^=;()\n]*?)(?:×|\*|·|\sx\s|\+)[^=;()\n]*?)=\s*([^;()\n]*)")


def _same_up_to_1000s(a: float, b: float) -> bool:
    if a == 0 or b == 0:
        return a == b
    return any(close(a * (1000.0 ** k), b) for k in range(-4, 5))


def rationale_arithmetic(text: str) -> list[RationaleArithmetic]:
    """Purely multiplicative or purely additive chains `a op b op c = d`."""
    found = []
    for m in _EQ_SEGMENT.finditer(text):
        lhs, rhs = m.group(1), m.group(2)
        if "+" in lhs and re.search(r"×|\*|·|\sx\s", lhs):
            continue  # mixed chains are not parsed
        op = "+" if "+" in lhs else "*"
        parts = re.split(r"\+" if op == "+" else r"×|\*|·|\sx\s", lhs)
        operands = []
        for p in parts:
            ms = find_mentions(p)
            if not ms:
                operands = []
                break
            mm = ms[0]
            operands.append(mm.value * mm.scale)
        rhs_ms = find_mentions(rhs)
        if len(operands) < 2 or not rhs_ms:
            continue
        computed = 1.0
        if op == "*":
            for v in operands:
                computed *= v
        else:
            computed = sum(operands)
        stated = rhs_ms[0].value * rhs_ms[0].scale
        found.append(RationaleArithmetic(
            text=m.group(0).strip(), operands=tuple(operands), op=op,
            computed=computed, stated=stated,
            consistent=_same_up_to_1000s(computed, stated),
        ))
    return found

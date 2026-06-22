"""Run the moat gate against every example workbook and emit MOAT_SWEEP.md.

The four moat gates are the "fully-formulated live Excel" guarantee:

1. Core output sheets ≥90% formula density (no hidden hardcodes)
2. No magic-number literals in output formulas
3. ≤5 orphan named ranges (every defined assumption is actually used)
4. Third-party recalculation reconciles (workbook portable to any Excel)

This sweep gives an honest cross-template snapshot so D3 progress is
visible and the remaining gaps are unambiguous.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modelforge.moat.gate import MoatGate
from modelforge.templates import build_model

# Spec-class registry — explicit map keeps imports tidy
from modelforge.spec.credit_memo import CreditMemoSpec
from modelforge.spec.dcf import DCFSpec
from modelforge.spec.fairness import FairnessSpec
from modelforge.spec.ipo import IPOSpec
from modelforge.spec.merger import MergerSpec
from modelforge.spec.minibond import MinibondSpec
from modelforge.spec.npl import NPLSpec
from modelforge.spec.project_finance import ProjectFinanceSpec
from modelforge.spec.real_estate import RealEstateSpec
from modelforge.spec.restructuring import RestructuringSpec
from modelforge.spec.sponsor_lbo import SponsorLBOSpec
from modelforge.spec.structured_credit import StructuredCreditSpec
from modelforge.spec.three_statement import ThreeStatementSpec
from modelforge.spec.unitranche import UnitrancheSpec

REG = {
    "credit_memo": CreditMemoSpec,
    "dcf": DCFSpec,
    "fairness": FairnessSpec,
    "ipo": IPOSpec,
    "merger": MergerSpec,
    "minibond": MinibondSpec,
    "npl": NPLSpec,
    "project_finance": ProjectFinanceSpec,
    "real_estate": RealEstateSpec,
    "restructuring": RestructuringSpec,
    "sponsor_lbo": SponsorLBOSpec,
    "structured_credit": StructuredCreditSpec,
    "three_statement": ThreeStatementSpec,
    "unitranche": UnitrancheSpec,
}


def main() -> int:
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    g = MoatGate()

    rows: list[dict] = []
    for yaml_path in sorted(Path("examples").glob("*.yaml")):
        spec_dict = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        mt = spec_dict.get("model_type", "?")
        cls = REG.get(mt)
        if not cls:
            rows.append({"file": yaml_path.stem, "model_type": mt, "error": "no spec class"})
            continue
        try:
            spec = cls.model_validate(spec_dict)
            out_path = out_dir / f"{yaml_path.stem}.xlsx"
            build_model(spec, out_path)
            r = g.evaluate(out_path)
            gates = {gr.name: gr.passed for gr in r.gate_results}
            core_sheets = [
                m for m in r.sheet_metrics
                if m.sheet_class == "core_output" and m.numeric_cells >= 5
            ]
            avg_density = (
                sum(m.formula_ratio for m in core_sheets) / len(core_sheets)
                if core_sheets else 0.0
            )
            failing_density = [
                f"{m.name}: {m.formula_ratio:.0%}"
                for m in core_sheets if m.formula_ratio < 0.90
            ]
            rows.append({
                "file": yaml_path.stem,
                "model_type": mt,
                "all_pass": all(gates.values()),
                "gates": gates,
                "avg_core_density": avg_density,
                "orphans": r.orphan_named_ranges,
                "failing_density_sheets": failing_density,
            })
        except Exception as e:
            rows.append({
                "file": yaml_path.stem,
                "model_type": mt,
                "error": f"{type(e).__name__}: {e}",
            })

    pass_count = sum(1 for r in rows if r.get("all_pass"))
    total = len(rows)

    lines = [
        "# MOAT_SWEEP — moat-gate scoreboard across 14 templates",
        "",
        f"**Generated**: {date.today().isoformat()}  ",
        f"**Tool**: `scripts/moat_sweep.py`  ",
        f"**Pass rate**: **{pass_count}/{total}** templates pass all 4 moat gates",
        "",
        "## Per-template scoreboard",
        "",
        "| File | Template | All Pass | Density | Magic# | No Orphans | Recalc | Avg core density | Failing sheets | # orphans |",
        "|---|---|:-:|:-:|:-:|:-:|:-:|:-:|---|:-:|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(
                f"| {r['file']} | {r['model_type']} | ERR | — | — | — | — | — | "
                f"{r['error']} | — |"
            )
            continue
        gates = r["gates"]
        all_pass = "Y" if r["all_pass"] else "n"
        d = "Y" if gates.get("formula_density") else "n"
        m = "Y" if gates.get("reference_graph") else "n"
        o = "Y" if gates.get("no_orphan_inputs") else "n"
        rec = "Y" if gates.get("recalculation") else "n"
        avg = f"{r['avg_core_density']:.0%}" if r['avg_core_density'] else "—"
        fail_sheets = "; ".join(r["failing_density_sheets"]) or "—"
        n_orph = len(r["orphans"])
        lines.append(
            f"| {r['file']} | {r['model_type']} | {all_pass} | {d} | {m} | {o} | "
            f"{rec} | {avg} | {fail_sheets} | {n_orph} |"
        )

    lines += [
        "",
        "## Per-template gap details",
        "",
    ]
    for r in rows:
        if "error" in r or r.get("all_pass"):
            continue
        lines.append(f"### {r['file']} ({r['model_type']})")
        if r["failing_density_sheets"]:
            lines.append(f"- **Density gaps**: {', '.join(r['failing_density_sheets'])}")
        if r["orphans"]:
            ostr = ", ".join(f"`{o}`" for o in r["orphans"][:10])
            lines.append(
                f"- **Orphan named ranges** ({len(r['orphans'])}): "
                f"{ostr}{' ...' if len(r['orphans']) > 10 else ''}"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## How to use this report",
        "",
        "1. **Density gaps** mean a core output sheet has hardcoded numeric "
        "cells where the analyst expects formulas. Fix by replacing literals "
        "with formula references to named ranges.",
        "2. **Orphan named ranges** mean assumptions are defined in the spec "
        "but no formula uses them. Fix by either wiring the assumption into "
        "a formula or removing it from the spec.",
        "3. **Magic-number** failures mean a formula contains a numeric literal "
        "that's not 0/1/12/100/1000-class. Fix by extracting the literal to a "
        "named-range assumption.",
        "4. **Recalculation** failures mean the third-party `formulas` engine "
        "can't reproduce the workbook's cached values — usually a cross-sheet "
        "reference or named-range scope issue.",
    ]

    out = Path("MOAT_SWEEP.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(out.read_text())} chars)")
    print(f"\nPass: {pass_count}/{total}")
    for r in rows:
        if not r.get("all_pass") and "error" not in r:
            print(f"  {r['file']:35} {len(r['orphans'])} orphans, "
                  f"{len(r['failing_density_sheets'])} density gaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())

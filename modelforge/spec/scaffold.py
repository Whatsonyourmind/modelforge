"""Emit a starter YAML spec skeleton for a given model_type.

``modelforge scaffold <model_type>`` prints a ready-to-edit YAML spec so a
new user does not have to author one from a blank file. Rather than
hand-maintain 16 parallel skeletons (which would drift from the specs the
way the old list-templates descriptions did), the scaffold *reuses a
shipped example spec as the seed* — guaranteeing the emitted skeleton is a
genuinely valid spec that builds today. A banner header is prepended telling
the user these are illustrative placeholders to replace with real,
source-cited figures.

For model types that do not yet ship a full example (``ipo``,
``restructuring``), we honestly emit a minimal required-field skeleton
derived from the Pydantic model, clearly labelled as a stub rather than
faking a complete example.
"""

from __future__ import annotations

from pathlib import Path

# Directory of shipped example specs, resolved relative to the repo root
# (this file lives at modelforge/spec/scaffold.py → repo root is parents[2]).
_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"

# model_type -> the example file to seed the scaffold from. Where several
# examples exist we pick the smallest/most generic so the skeleton stays
# minimal. Keys MUST be a subset of templates.REGISTRY.
_SEED_EXAMPLE: dict[str, str] = {
    "unitranche": "unitranche_cdmo.yaml",
    "minibond": "minibond_logistics.yaml",
    "credit_memo": "credit_memo_cdmo.yaml",
    "project_finance": "project_finance_solar.yaml",
    "real_estate": "real_estate_pbsa.yaml",
    "npl": "npl_mixed_portfolio.yaml",
    "structured_credit": "structured_credit_pmi.yaml",
    "three_statement": "three_statement_cdmo.yaml",
    "dcf": "dcf_enel.yaml",
    "merger": "merger_tim_iliad.yaml",
    "fairness": "fairness_amplifon.yaml",
    "sponsor_lbo": "sponsor_lbo_techco.yaml",
    "hgb_carveout": "hgb_carveout_dach_chemicals.yaml",
    "portfolio_review": "portfolio_review_us_lower_mm.yaml",
    # ipo + restructuring ship no full example yet — handled by the
    # required-field stub fallback below.
}

_BANNER = (
    "# ─────────────────────────────────────────────────────────────────\n"
    "# ModelForge scaffold — model_type: {model_type}\n"
    "#\n"
    "# This is a STARTER skeleton seeded from a shipped example. Every\n"
    "# figure below is an ILLUSTRATIVE PLACEHOLDER: replace each value with\n"
    "# your deal's real numbers and point every `source_id` at a real entry\n"
    "# in the `sources:` block. Then validate + build:\n"
    "#\n"
    "#     modelforge validate my_spec.yaml\n"
    "#     modelforge build    my_spec.yaml\n"
    "# ─────────────────────────────────────────────────────────────────\n"
)


def _stub_skeleton(model_type: str, spec_cls: type) -> str:
    """Build a minimal required-field skeleton from a Pydantic spec class.

    Used only for model types that ship no full example. Emits each required
    top-level field as a commented placeholder so the user knows what to
    fill, without pretending to be a complete, build-ready example.
    """
    try:
        required = [
            name
            for name, field in spec_cls.model_fields.items()  # type: ignore[attr-defined]
            if field.is_required()
        ]
    except Exception:
        required = []

    lines = [
        _BANNER.format(model_type=model_type),
        "# NOTE: no full example ships for this template yet, so this is a",
        "# minimal required-field stub. Fill in each field below.",
        "",
        f"model_type: {model_type}",
        "",
    ]
    if required:
        lines.append("# Required fields (replace placeholder values):")
        for name in required:
            lines.append(f"# {name}: <FILL ME>")
    else:  # pragma: no cover - every spec has at least one required field
        lines.append("# (no required fields detected — see `modelforge schema "
                      f"{model_type}`)")
    lines.append("")
    return "\n".join(lines)


def scaffold_yaml(model_type: str, spec_cls: type | None = None) -> str:
    """Return a starter YAML spec for ``model_type`` as a string.

    Reuses a shipped example as the seed when one exists (prepending an
    instructional banner); otherwise falls back to a required-field stub
    derived from ``spec_cls``.

    Raises ``KeyError`` for an unknown ``model_type`` so the CLI can print a
    friendly "known types" message.
    """
    seed_name = _SEED_EXAMPLE.get(model_type)
    if seed_name is not None:
        seed_path = _EXAMPLES_DIR / seed_name
        if seed_path.exists():
            body = seed_path.read_text(encoding="utf-8")
            return _BANNER.format(model_type=model_type) + "\n" + body

    # No shipped example (ipo / restructuring) — emit an honest stub.
    if spec_cls is not None:
        return _stub_skeleton(model_type, spec_cls)

    raise KeyError(model_type)

"""Template registry.

Each template contributes a builder function. Dispatch by model_type.

``build_model`` also applies the post-build analytics layer (sensitivity
tornado) so every template ships with a SensitivityAnalysis sheet by
default. Callers that don't want it (e.g. unit tests on the bare
skeleton) can call the template builder directly or pass
``with_sensitivity=False``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from modelforge.templates import (
    unitranche, minibond, credit_memo, project_finance, real_estate, npl,
    structured_credit, three_statement, dcf, merger, fairness, sponsor_lbo,
    ipo, restructuring,
    hgb_carveout, portfolio_review,
    development_re,
    bank_fig,
    loan_tape_securitization,
)

REGISTRY: dict[str, Callable] = {
    "unitranche": unitranche.build,
    "minibond": minibond.build,
    "credit_memo": credit_memo.build,
    "project_finance": project_finance.build,
    "real_estate": real_estate.build,
    "npl": npl.build,
    "structured_credit": structured_credit.build,
    "three_statement": three_statement.build,
    "dcf": dcf.build,
    "merger": merger.build,
    "fairness": fairness.build,
    "sponsor_lbo": sponsor_lbo.build,
    "ipo": ipo.build,
    "restructuring": restructuring.build,
    # v0.10 foreign-market additions:
    "hgb_carveout": hgb_carveout.build,
    "portfolio_review": portfolio_review.build,
    # Ground-up development underwriting (phased capex, lease-up, promote):
    "development_re": development_re.build,
    # Bank / FIG: NII, RWA, CET1, leverage, MDA-gated capital return:
    "bank_fig": bank_fig.build,
    # Loan-tape cash securitization (CLO/RMBS): stratified tape → pool cashflow
    # → sequential-pay turbo waterfall + OC/IC + reserve → note WAL/IRR/rating:
    "loan_tape_securitization": loan_tape_securitization.build,
}

# v0.10 templates flagged as preview. CLI and MCP server can surface this.
PREVIEW_TEMPLATES: frozenset[str] = frozenset({"hgb_carveout", "portfolio_review"})


def build_model(
    spec,
    out_path,
    graph_db_path=None,
    with_sensitivity: bool = True,
    with_reproducibility: bool = True,
    with_manifest: bool = True,
    spec_source_bytes: bytes | None = None,
    spec_source_path: Path | str | None = None,
):
    """Dispatch to the right template builder based on spec.model_type.

    After the core template build, applies the sensitivity tornado,
    reproducibility, and manifest post-processors (each can be disabled).
    The manifest sidecar (``<workbook>.manifest.json``) is the audit-grade
    extension that records spec_sha256 + sources_sha256 + workbook_sha256
    + build_chain — verifiable via ``verify_manifest``.
    """
    mt = spec.model_type
    if mt not in REGISTRY:
        raise ValueError(
            f"Unknown model_type {mt!r}. Known: {list(REGISTRY)}"
        )
    xlsx_path, graph_path = REGISTRY[mt](spec, out_path, graph_db_path)

    if with_sensitivity:
        try:
            from modelforge.analytics.sensitivity import append_sensitivity_sheet
            from modelforge.analytics.monte_carlo import append_monte_carlo_sheet
            from modelforge.analytics.risk_sheet import append_risk_analysis_sheet
            append_sensitivity_sheet(xlsx_path, spec)
            # v0.8 US-233: 2D Data Tables (WACC × g, WACC × exit_x) for DCF.
            if mt == "dcf":
                from modelforge.analytics.sensitivity import append_dcf_2d_tables
                append_dcf_2d_tables(xlsx_path, spec)
            else:
                # v0.8.7 US-500: generic 2D Data Table block for every
                # non-DCF template (closes audit #83 universally).
                from modelforge.analytics.sensitivity import (
                    append_generic_2d_tables,
                )
                append_generic_2d_tables(xlsx_path, spec)
            # MC runs after sensitivity so it can reuse the primary_output
            # named range that sensitivity registers.
            append_monte_carlo_sheet(xlsx_path, spec)
            # Risk analysis only emits if spec.risk_analysis is set
            append_risk_analysis_sheet(xlsx_path, spec)
        except Exception:
            # Analytics are nice-to-haves; never block the build.
            pass

    if with_reproducibility:
        try:
            from modelforge.analytics.reproducibility import (
                append_reproducibility_block,
            )
            append_reproducibility_block(
                xlsx_path, spec,
                spec_source_bytes=spec_source_bytes,
                spec_source_path=spec_source_path,
            )
        except Exception:
            pass

    # v0.8.7 US-505: Macabacus AutoColor parity — must run LAST so it
    # colours every formula (including those written by sensitivity /
    # MC / risk / reproducibility post-processors).
    #
    # v1.1 US-555: immediately after AutoColor (same load/save), the
    # deterministic auto-styler closes the remaining styling gaps — numeric/
    # formula cells that still lack an explicit font colour or number_format.
    # It runs AFTER AutoColor so the cross-sheet green survives (those cells
    # already carry an explicit colour, so the styler never recolours them),
    # and BEFORE finalize_determinism + the manifest hash below, so the
    # styled bytes are exactly what gets timestamp-pinned and hashed. The
    # styler is clock/RNG-free, so a same-spec rebuild stays byte-identical.
    try:
        from openpyxl import load_workbook as _load
        from modelforge.builder.styles import (
            auto_color_xrefs as _autocolor,
            auto_style_gaps as _autostyle,
        )
        _wb = _load(xlsx_path, keep_links=True)
        _autocolor(_wb)
        _autostyle(_wb)
        _wb.save(xlsx_path)
    except Exception:
        pass

    # Reproducibility: this AutoColor save (and any save above) re-stamps
    # docProps/core.xml + zip mtimes with the wall clock. Re-pin them to the
    # deterministic instant LAST so two builds of the same spec are
    # byte-identical. (No-op-safe; honors SOURCE_DATE_EPOCH / wall-clock env.)
    if with_reproducibility:
        try:
            from modelforge.analytics.reproducibility import finalize_determinism
            finalize_determinism(
                xlsx_path, spec, spec_source_bytes=spec_source_bytes,
            )
        except Exception:
            pass

    # D2: write the per-build manifest sidecar (spec + sources + workbook
    # hashes + build chain) AFTER all post-processors have run, so the
    # workbook_sha256 reflects the FINAL bytes auditors will receive.
    if with_manifest:
        try:
            from modelforge.analytics.manifest import write_manifest
            write_manifest(
                xlsx_path, spec,
                spec_source_bytes=spec_source_bytes,
                spec_source_path=spec_source_path,
            )
        except Exception:
            # Manifest is auditing infrastructure; never block the build.
            pass

    return Path(xlsx_path), Path(graph_path)

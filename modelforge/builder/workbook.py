"""Top-level builder.

Orchestrates sheet emission in the correct order, wires cross-sheet
refs, saves the workbook, saves the linkage graph.

    spec (Pydantic) → Workbook (.xlsx) + LinkageGraph (SQLite)
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from modelforge.builder.sheets import (
    cover,
    sources,
    assumptions,
    operating,
    debt,
    covenants,
    returns as returns_sheet,
    qc,
)
from modelforge.builder.i18n import (
    apply_runtime_secondary_lang,
    reset_runtime_secondary_lang,
    SECONDARY_LANGS,
    FIRST_CUT_LANGS,
)
from modelforge.graph.schema import LinkageGraph
from modelforge.graph.store import GraphStore
from modelforge.spec.unitranche import UnitrancheSpec


SHEET_ORDER = [
    "Cover",
    "Sources",
    "Assumptions",
    "OperatingModel",
    "DebtSchedule",
    "Covenants",
    "Returns",
    "QC",
]


def build_workbook(
    spec: UnitrancheSpec,
    out_path: Path | str,
    graph_db_path: Path | str | None = None,
    secondary_lang: str = "it",
) -> tuple[Path, Path]:
    """Build a full ModelForge workbook from a spec.

    Args:
        spec: Pydantic spec describing the deal.
        out_path: Where to write the .xlsx.
        graph_db_path: Optional linkage-graph SQLite path (defaults next to xlsx).
        secondary_lang: Secondary language for the rendered workbook. One of
            "it" (default), "de", "es", "sv", "no", "da", "nl", or "en"
            (English-only). Languages in i18n.FIRST_CUT_LANGS are flagged as
            preview quality and emit a warning to the linkage graph.

    Returns (xlsx_path, graph_db_path).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if graph_db_path is None:
        graph_db_path = out_path.with_suffix(".graph.db")
    graph_db_path = Path(graph_db_path)

    # Apply requested secondary language (mutates global Label dict — see i18n.py).
    if secondary_lang != "it":
        if secondary_lang not in SECONDARY_LANGS and secondary_lang != "en":
            raise ValueError(
                f"Unknown secondary_lang '{secondary_lang}'. "
                f"Supported: {SECONDARY_LANGS} (or 'en' / 'it')."
            )
        apply_runtime_secondary_lang(secondary_lang)
        if secondary_lang in FIRST_CUT_LANGS:
            import warnings
            warnings.warn(
                f"secondary_lang='{secondary_lang}' is a v0.10 first-cut translation "
                f"and requires native-speaker review before production use. "
                f"See modelforge/builder/i18n.py header.",
                UserWarning,
                stacklevel=2,
            )

    # Initialise graph
    graph = LinkageGraph(model_id=spec.meta.project_code)

    # Initialise workbook
    wb = Workbook()
    # Remove default sheet
    default = wb.active
    wb.remove(default)

    wb.calculation.iterate = True
    wb.calculation.iterateCount = 100
    wb.calculation.iterateDelta = 0.001

    # Create all sheets up front in the right order
    sheet_objects = {name: wb.create_sheet(title=name) for name in SHEET_ORDER}

    # ─── Cover (must be first: creates scenario_index named range)
    cover.build(sheet_objects["Cover"], spec, graph)

    # ─── Sources
    source_rows = sources.build(sheet_objects["Sources"], spec, graph)

    # ─── Assumptions (creates all driver named ranges)
    driver_refs = assumptions.build(
        sheet_objects["Assumptions"], spec, graph, source_rows,
    )

    # ─── Operating Model
    operating_refs = operating.build(
        sheet_objects["OperatingModel"], spec, graph, driver_refs,
    )

    # ─── Debt Schedule (also patches Operating interest row)
    debt_refs = debt.build(
        sheet_objects["DebtSchedule"],
        spec,
        graph,
        driver_refs,
        operating_refs,
        operating_sheet_name="OperatingModel",
    )

    # ─── Covenants
    covenant_refs = covenants.build(
        sheet_objects["Covenants"],
        spec,
        operating_refs,
        debt_refs,
        operating_sheet_name="OperatingModel",
        debt_sheet_name="DebtSchedule",
    )

    # ─── Returns
    returns_sheet.build(
        sheet_objects["Returns"], spec, debt_refs, debt_sheet_name="DebtSchedule",
    )

    # ─── QC
    qc.build(
        sheet_objects["QC"],
        spec,
        operating_refs,
        debt_refs,
        covenant_refs,
        operating_sheet="OperatingModel",
        debt_sheet="DebtSchedule",
        covenants_sheet="Covenants",
    )

    # Save
    wb.save(out_path)

    # Persist graph
    store = GraphStore(graph_db_path)
    store.save(graph)

    # Restore default Italian secondary on exit (caller-friendly: next build
    # starts from a clean baseline).
    if secondary_lang != "it":
        reset_runtime_secondary_lang()

    return out_path, graph_db_path

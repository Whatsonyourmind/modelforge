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
) -> tuple[Path, Path]:
    """Build a full ModelForge workbook from a spec.

    Returns (xlsx_path, graph_db_path).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if graph_db_path is None:
        graph_db_path = out_path.with_suffix(".graph.db")
    graph_db_path = Path(graph_db_path)

    # Initialise graph
    graph = LinkageGraph(model_id=spec.meta.project_code)

    # Initialise workbook
    wb = Workbook()
    # Remove default sheet
    default = wb.active
    wb.remove(default)

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

    return out_path, graph_db_path

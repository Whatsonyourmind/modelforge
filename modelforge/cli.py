"""ModelForge CLI.

    modelforge build <spec.yaml>           → emit .xlsx + graph.db
    modelforge qc    <model.xlsx>          → run QC gate, print report
    modelforge sources <model.xlsx>        → list all sources used
    modelforge lineage <graph.db> <cell>   → walk back from cell to doc page
    modelforge stats <graph.db>            → graph node/edge counts
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from modelforge.builder.workbook import build_workbook
from modelforge.graph.store import GraphStore
from modelforge.qc import run_qc
from modelforge.spec.unitranche import UnitrancheSpec


console = Console()


@click.group()
def main() -> None:
    """ModelForge — bulge-tier Excel model factory."""


@main.command("build")
@click.argument("spec_path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Output .xlsx path. Defaults to output/<spec_stem>.xlsx.")
def build_cmd(spec_path: Path, out_path: Path | None) -> None:
    """Build an Excel workbook from a YAML spec."""
    with spec_path.open() as f:
        raw = yaml.safe_load(f)
    model_type = raw.get("model_type", "unitranche")
    if model_type != "unitranche":
        console.print(f"[red]Only 'unitranche' supported in v0.1 (got {model_type!r}).[/red]")
        sys.exit(2)

    spec = UnitrancheSpec.model_validate(raw)

    if out_path is None:
        out_path = Path("output") / f"{spec_path.stem}.xlsx"

    xlsx, graph = build_workbook(spec, out_path)
    console.print(f"[green]Built:[/green] {xlsx}")
    console.print(f"[green]Graph:[/green] {graph}")


@main.command("qc")
@click.argument("xlsx_path", type=click.Path(exists=True, path_type=Path))
def qc_cmd(xlsx_path: Path) -> None:
    """Run QC gate on a built workbook."""
    report = run_qc(xlsx_path)
    report.print()
    sys.exit(0 if report.all_pass else 1)


@main.command("sources")
@click.argument("xlsx_path", type=click.Path(exists=True, path_type=Path))
def sources_cmd(xlsx_path: Path) -> None:
    """List sources used in a workbook."""
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path)
    ws = wb["Sources"]
    tbl = Table(title=f"Sources in {xlsx_path.name}")
    tbl.add_column("ID")
    tbl.add_column("Document")
    tbl.add_column("Page")
    tbl.add_column("Publisher")
    tbl.add_column("Verified")
    tbl.add_column("URL", overflow="fold")
    for row in range(6, ws.max_row + 1):
        vid = ws.cell(row=row, column=1).value
        if not vid:
            continue
        tbl.add_row(
            str(vid),
            str(ws.cell(row=row, column=2).value or ""),
            str(ws.cell(row=row, column=3).value or ""),
            str(ws.cell(row=row, column=4).value or ""),
            "✔" if ws.cell(row=row, column=7).value == "✔" else "",
            str(ws.cell(row=row, column=6).value or ""),
        )
    console.print(tbl)


@main.command("lineage")
@click.argument("graph_db", type=click.Path(exists=True, path_type=Path))
@click.argument("cell_id")
def lineage_cmd(graph_db: Path, cell_id: str) -> None:
    """Walk the linkage graph back from a cell.

    Example: modelforge lineage model.graph.db "CELL:OperatingModel!D10"
    """
    store = GraphStore(graph_db)
    # Infer model_id from any stored row
    import sqlite3
    with sqlite3.connect(graph_db) as conn:
        row = conn.execute("SELECT DISTINCT model_id FROM nodes LIMIT 1").fetchone()
    if not row:
        console.print("[red]Graph DB empty.[/red]")
        sys.exit(2)
    model_id = row[0]
    hops = store.lineage(model_id, cell_id)
    tbl = Table(title=f"Lineage of {cell_id}")
    tbl.add_column("ID")
    tbl.add_column("Kind")
    tbl.add_column("Label")
    for h in hops:
        tbl.add_row(h["id"], h["kind"], h["label"])
    console.print(tbl)


@main.command("stats")
@click.argument("graph_db", type=click.Path(exists=True, path_type=Path))
def stats_cmd(graph_db: Path) -> None:
    """Print graph statistics."""
    store = GraphStore(graph_db)
    import sqlite3
    with sqlite3.connect(graph_db) as conn:
        models = [r[0] for r in conn.execute("SELECT DISTINCT model_id FROM nodes").fetchall()]
    for m in models:
        stats = store.stats(m)
        tbl = Table(title=f"Graph stats — {m}")
        tbl.add_column("Bucket")
        tbl.add_column("Count")
        for k, v in sorted(stats.items()):
            tbl.add_row(k, str(v))
        console.print(tbl)


if __name__ == "__main__":
    main()

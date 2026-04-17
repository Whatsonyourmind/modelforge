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

from modelforge.graph.store import GraphStore
from modelforge.qc import run_qc
from modelforge.spec.unitranche import UnitrancheSpec
from modelforge.templates import REGISTRY, build_model


console = Console()


@click.group()
def main() -> None:
    """ModelForge — bulge-tier Excel model factory."""


SPEC_CLASSES = {
    "unitranche": UnitrancheSpec,
}


def _load_spec_class(model_type: str):
    """Lazily import spec classes so missing deps in one template don't break CLI startup."""
    if model_type in SPEC_CLASSES:
        return SPEC_CLASSES[model_type]
    if model_type == "minibond":
        from modelforge.spec.minibond import MinibondSpec
        return MinibondSpec
    if model_type == "credit_memo":
        from modelforge.spec.credit_memo import CreditMemoSpec
        return CreditMemoSpec
    if model_type == "project_finance":
        from modelforge.spec.project_finance import ProjectFinanceSpec
        return ProjectFinanceSpec
    if model_type == "real_estate":
        from modelforge.spec.real_estate import RealEstateSpec
        return RealEstateSpec
    if model_type == "npl":
        from modelforge.spec.npl import NPLSpec
        return NPLSpec
    if model_type == "structured_credit":
        from modelforge.spec.structured_credit import StructuredCreditSpec
        return StructuredCreditSpec
    if model_type == "three_statement":
        from modelforge.spec.three_statement import ThreeStatementSpec
        return ThreeStatementSpec
    raise ValueError(
        f"Unknown model_type {model_type!r}. Known: unitranche, minibond, "
        "credit_memo, project_finance, real_estate, npl, structured_credit, three_statement"
    )


@main.command("build")
@click.argument("spec_path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Output .xlsx path. Defaults to output/<spec_stem>.xlsx.")
def build_cmd(spec_path: Path, out_path: Path | None) -> None:
    """Build an Excel workbook from a YAML spec."""
    spec_bytes = spec_path.read_bytes()
    raw = yaml.safe_load(spec_bytes)
    model_type = raw.get("model_type", "unitranche")

    try:
        SpecClass = _load_spec_class(model_type)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(2)

    spec = SpecClass.model_validate(raw)

    if out_path is None:
        out_path = Path("output") / f"{spec_path.stem}.xlsx"

    xlsx, graph = build_model(
        spec, out_path,
        spec_source_bytes=spec_bytes,
        spec_source_path=spec_path,
    )
    console.print(f"[green]Built:[/green] {xlsx}  [dim]({model_type})[/dim]")
    console.print(f"[green]Graph:[/green] {graph}")


@main.command("list-templates")
def list_templates_cmd() -> None:
    """List all available model templates."""
    from modelforge.templates import REGISTRY
    tbl = Table(title="ModelForge templates")
    tbl.add_column("model_type", style="bold")
    tbl.add_column("Description")
    tbl.add_column("Status")
    descriptions = {
        "unitranche": "Italian mid-market unitranche LBO (senior direct lending)",
        "minibond": "Italian minibond pricing + investor returns (Banca Finint territory)",
        "credit_memo": "Credit memo with covenant headroom + LGD + recovery analysis",
        "project_finance": "Infrastructure/RE project finance, DSCR-driven, construction + operating",
        "real_estate": "RE DCF with NOI build, exit cap, equity waterfall (pref + promote)",
        "npl": "NPL portfolio recovery waterfall (collection curves, IRR)",
        "structured_credit": "Securitization tranche waterfall (senior/mezz/junior)",
        "three_statement": "Classic 3-statement corporate model (P&L + BS + CFS)",
    }
    for name in [
        "unitranche", "minibond", "credit_memo", "project_finance",
        "real_estate", "npl", "structured_credit", "three_statement",
    ]:
        status = "[green]OK[/green]" if name in REGISTRY else "[yellow]planned[/yellow]"
        tbl.add_row(name, descriptions.get(name, ""), status)
    console.print(tbl)


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


@main.command("ingest")
@click.argument("dataroom_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-t", "--template", default="project_finance",
              help="Target template (default: project_finance).")
@click.option("-o", "--output", "output_yaml", type=click.Path(path_type=Path), default=None,
              help="Output YAML path. Defaults to output/<dir_name>.yaml.")
@click.option("--model", default="claude-opus-4-7",
              help="Anthropic model (default: claude-opus-4-7).")
@click.option("--backend", "backend_name", default="cli",
              type=click.Choice(["cli", "api"]),
              help="LLM backend: 'cli' (Claude Code, no API key) or 'api' (Anthropic SDK).")
@click.option("--max-docs", type=int, default=50,
              help="Cap docs scanned (default: 50).")
@click.option("--strict", is_flag=True,
              help="Fail on any Pydantic validation error (default: best-effort).")
@click.option("--dry-run", is_flag=True,
              help="Classify + report only; skip extraction.")
@click.option("--no-cache", is_flag=True,
              help="Disable Anthropic prompt caching (api backend only).")
@click.option("-v", "--verbose", is_flag=True,
              help="Print per-step progress.")
def ingest_cmd(
    dataroom_dir: Path, template: str, output_yaml: Path | None,
    model: str, backend_name: str, max_docs: int, strict: bool,
    dry_run: bool, no_cache: bool, verbose: bool,
) -> None:
    """Ingest a data room (PDFs/XLSX/CSV) and produce a ModelForge YAML spec.

    Default backend is 'cli' which uses your Claude Code subscription
    (no API key needed). Use '--backend api' with ANTHROPIC_API_KEY for
    the Anthropic SDK path with prompt caching.
    """
    from modelforge.ingest.pipeline import ingest
    if output_yaml is None:
        output_yaml = Path("output") / f"{dataroom_dir.name}.yaml"

    def log(msg: str) -> None:
        if verbose:
            console.print(f"[dim]{msg}[/dim]")

    console.print(f"[bold]Ingesting[/bold] {dataroom_dir} -> {output_yaml}")
    console.print(f"Template: {template}  Backend: {backend_name}  Model: {model}")
    try:
        result = ingest(
            dataroom_dir=dataroom_dir,
            template=template,
            output_yaml=output_yaml,
            max_docs=max_docs,
            model=model,
            use_cache=not no_cache,
            strict=strict,
            dry_run=dry_run,
            backend_name=backend_name,
            log=log,
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(2)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(2)

    status = "[green]PASS[/green]" if result.spec_valid else "[yellow]needs review[/yellow]"
    console.print(f"\nSpec validation: {status}")
    console.print(f"Cache hit rate:  {result.cache_hit_rate*100:.1f}%")
    console.print(f"Tokens:          {result.total_input_tokens:,} in / {result.total_output_tokens:,} out")
    console.print(f"Elapsed:         {result.elapsed_seconds:.1f}s")
    console.print(f"\n[green]YAML[/green]:   {result.yaml_path}")
    console.print(f"[green]Report[/green]: {result.report_path}")
    if not dry_run and result.spec_valid:
        console.print(f"\nNext: [cyan]modelforge build {result.yaml_path}[/cyan]")
    sys.exit(0 if result.spec_valid or dry_run else 1)


@main.command("verify")
@click.argument("xlsx_path", type=click.Path(exists=True, path_type=Path))
@click.option("--spec", "spec_path", type=click.Path(exists=True, path_type=Path),
              default=None, help="YAML spec to recompute hash from.")
def verify_cmd(xlsx_path: Path, spec_path: Path | None) -> None:
    """Read Reproducibility metadata and (optionally) verify spec hash.

    Without --spec, prints the stored metadata (hash, version, build
    timestamp). With --spec, recomputes the SHA-256 from the given YAML
    bytes and compares to the stored hash; exits 0 on match, 1 on
    mismatch.
    """
    from modelforge.analytics.reproducibility import (
        read_reproducibility,
        verify_spec_hash,
    )

    meta = read_reproducibility(xlsx_path)
    if not meta:
        console.print(f"[red]No Reproducibility metadata in {xlsx_path.name}. "
                      f"Rebuild with modelforge build.[/red]")
        sys.exit(2)

    tbl = Table(title=f"Reproducibility — {xlsx_path.name}")
    tbl.add_column("Field", style="bold")
    tbl.add_column("Value", overflow="fold")
    for k, v in meta.items():
        tbl.add_row(k, v)
    console.print(tbl)

    if spec_path is None:
        sys.exit(0)

    spec_bytes = spec_path.read_bytes()
    match, stored, recomputed = verify_spec_hash(xlsx_path, spec_bytes)
    if match:
        console.print(f"\n[green]PASS[/green] spec hash matches: {stored}")
        sys.exit(0)
    console.print(
        f"\n[red]FAIL[/red] spec hash mismatch.\n"
        f"  stored:     {stored}\n"
        f"  recomputed: {recomputed}"
    )
    sys.exit(1)


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

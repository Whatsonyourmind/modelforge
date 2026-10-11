"""Console rendering for the evidence-binding gate."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from modelforge.evidence.gate import GateResult, Verdict

_STYLE = {
    Verdict.BOUND: "green", Verdict.DERIVED: "green", Verdict.ASSUMPTION: "cyan",
    Verdict.UNVERIFIED: "yellow", Verdict.CONTESTED: "red", Verdict.BROKEN: "bold red",
    Verdict.OVERRIDDEN: "magenta",
}
_ORDER = [Verdict.BROKEN, Verdict.CONTESTED, Verdict.OVERRIDDEN, Verdict.UNVERIFIED,
          Verdict.ASSUMPTION, Verdict.DERIVED, Verdict.BOUND]


def summary_line(result: GateResult) -> str:
    c = result.counts()
    parts = [f"{c[v.value]} {v.value}" for v in _ORDER if c[v.value]]
    mode = "strict" if result.strict else "default"
    return f"{len(result.leaves)} leaves: " + " · ".join(parts) + f"  [{mode}]"


def render(result: GateResult, console: Console, show_all: bool = False) -> None:
    status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
    console.print(f"[bold]Evidence:[/bold] {status}  {summary_line(result)}")
    if result.dataroom:
        console.print(f"  dataroom: {result.dataroom} ({len(result.documents)} documents)")
    else:
        console.print("  [dim]no dataroom: quotes are checked for value/unit/role but not "
                      "located in their documents[/dim]")

    shown = [lf for lf in result.leaves
             if show_all or lf.verdict in result.blocking_verdicts or lf.verdict == Verdict.OVERRIDDEN]
    shown.sort(key=lambda lf: _ORDER.index(lf.verdict))
    if shown:
        t = Table(show_header=True, header_style="bold", expand=False)
        t.add_column("id")
        t.add_column("field")
        t.add_column("value", justify="right")
        t.add_column("verdict")
        t.add_column("why")
        for lf in shown:
            why = lf.reasons[0] if lf.reasons else ""
            if lf.override:
                why = (f"OVERRIDE by {lf.override['signed_by']} ({lf.override['date']}): "
                       f"{lf.override['reason']}  — was {lf.original_verdict.value}: {why}")
            elif len(lf.reasons) > 1:
                why += f"  (+{len(lf.reasons) - 1} more)"
            t.add_row(lf.id, lf.path, f"{lf.value:g} {lf.unit}",
                      f"[{_STYLE[lf.verdict]}]{lf.verdict.value}[/{_STYLE[lf.verdict]}]", why)
        console.print(t)
    if not show_all:
        hidden = len(result.leaves) - len(shown)
        if hidden:
            console.print(f"  [dim]{hidden} non-blocking leaves hidden (use --all)[/dim]")
    for u in result.unused_overrides:
        console.print(f"  [yellow]unused override[/yellow] {u['id']} ({u['verdict']}): {u['why_unused']}")
    if not result.passed:
        console.print("  [red]Blocked.[/red] Fix the binding, or record a signed override under "
                      "`evidence_overrides:` (id, verdict, reason, signed_by, date).")

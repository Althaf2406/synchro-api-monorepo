"""
hackathon_core_engine/dashboard_cli.py
Rich Terminal Live Telemetry Viewer for SynchroAPI Autonomous Cross-Repo Orchestration.
Designed for the 3-Minute Meta Global AI Developer Hackathon Video Demo.
"""

from __future__ import annotations

from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


console = Console(width=140, force_terminal=True)


def render_synchro_banner(upstream_repo: str, pr_number: int) -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]SYNCHRO-API: AUTONOMOUS CROSS-REPO CI/CD ORCHESTRATOR[/bold cyan]\n"
            f"[white]Upstream Trigger:[/white] [bold yellow]{upstream_repo} (PR #{pr_number})[/bold yellow]\n"
            f"[white]Reasoning & Critic:[/white] [bold green]Meta Muse Spark Open[/bold green] (Baseten 2M TPM)\n"
            f"[white]Surgical Refactor:[/white] [bold magenta]Meta Muse Code[/bold magenta] (Fireworks AI Speculative Decoding)\n"
            f"[white]Verification Engine:[/white] [bold blue]Hybrid Tree-sitter GraphRAG + Ephemeral Modal.Sandbox[/bold blue]",
            border_style="bright_cyan",
            title="[bold white]Meta Global AI Developer Hackathon[/bold white]",
        )
    )


def render_breaking_changes_table(breaking_changes: List[Dict[str, Any]]) -> None:
    table = Table(
        title="[bold red]1. Deterministic OpenAPI Breaking Changes (oasdiff)[/bold red]",
        show_header=True,
        header_style="bold white on dark_red",
    )
    table.add_column("Rule ID", style="cyan", no_wrap=True)
    table.add_column("Endpoint", style="yellow")
    table.add_column("Schema.Field", style="magenta")
    table.add_column("Change Type", style="bold red")
    table.add_column("Contract Diff Details", style="white")

    for bc in breaking_changes:
        table.add_row(
            str(bc.get("rule_id") or bc.get("id")),
            f"{bc.get('http_method', bc.get('operation', 'POST'))} {bc.get('endpoint_path', bc.get('path', '/v2/charges'))}",
            f"{bc.get('schema_model', '')}.{bc.get('field_name', bc.get('source_field', ''))}",
            str(bc.get("change_type", "")),
            str(bc.get("description") or bc.get("text", "")),
        )
    console.print(table)


def render_blast_radius_tree(blast_radius: Dict[str, Dict[str, Any]]) -> None:
    root = Tree("[bold cyan]2. Hybrid Tree-sitter GraphRAG Multi-Hop Blast Radius Subgraph[/bold cyan]")
    for repo_id, bundle in blast_radius.items():
        repo_branch = root.add(f"[bold yellow]Downstream Repo:[/bold yellow] {repo_id}")
        order_branch = repo_branch.add("[bold green]Topological Execution Order (DTO -> Function -> Test)[/bold green]")
        for idx, node_id in enumerate(bundle.get("topological_order", []), start=1):
            order_branch.add(f"[white]{idx}.[/white] [cyan]{node_id}[/cyan]")
    console.print(root)


def render_downstream_execution_results(results: List[Dict[str, Any]]) -> None:
    table = Table(
        title="[bold green]3. Autonomous Sandbox Self-Healing Loop & PR Telemetry[/bold green]",
        show_header=True,
        header_style="bold black on bright_green",
    )
    table.add_column("Downstream Repo", style="bold yellow")
    table.add_column("Iterations", justify="center", style="cyan")
    table.add_column("Mypy & Pytest", justify="center")
    table.add_column("Critic Purity Score", justify="center", style="magenta")
    table.add_column("Status", style="bold green")
    table.add_column("Automated Pull Request", style="underline blue")

    for res in results:
        hist = res.get("iteration_history", [])
        last_iter = hist[-1] if hist else {}
        passed_str = (
            "[bold green]PASS (exit=0)[/bold green]"
            if last_iter.get("sandbox_exit_code") == 0
            else "[bold red]FAIL[/bold red]"
        )
        purity = f"{last_iter.get('semantic_purity_score', 0.0):.2f}"
        table.add_row(
            res["target_repo"],
            str(res["iterations_used"]),
            passed_str,
            purity,
            res["status"],
            res["pull_request_url"],
        )
    console.print(table)

    # Tampilkan detail Self-Healing jika ada iterasi > 1
    for res in results:
        hist = res.get("iteration_history", [])
        if len(hist) > 1:
            console.print(
                Panel(
                    "\n".join(
                        [
                            f"[bold yellow]Iteration {h['iteration']}:[/bold yellow] "
                            f"exit_code={h['sandbox_exit_code']} | mypy={h['mypy_passed']} | pytest={h['pytest_passed']} | "
                            f"critic_approved={h['critic_approved']}\n"
                            f"   [dim]Feedback:[/dim] {h['diagnostic_feedback']}"
                            for h in hist
                        ]
                    ),
                    title=f"[bold magenta]Self-Healing Diagnostic Trace: {res['target_repo']}[/bold magenta]",
                    border_style="magenta",
                )
            )

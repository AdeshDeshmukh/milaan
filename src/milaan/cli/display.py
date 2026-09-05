"""Rich terminal formatting and tables for Milaan reconciliation CLI."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_banner() -> None:
    """Print the Milaan branded startup banner."""
    banner_text = (
        "[bold cyan]Milaan (मिलान)[/bold cyan] — [bold green]Three-Way Settlement Reconciliation Agent[/bold green]\n"
        "[dim]Razorpay Payments ↔ Settlements ↔ Bank Statements ↔ Merchant Order Ledger[/dim]\n"
        "[yellow]Deterministic Matching Tiers · Bounded LLM Residue · Human-Approved Actions[/yellow]"
    )
    console.print(Panel(banner_text, border_style="cyan"))


def print_tier_breakdown_table(tier_counts: dict[str, int], total_records: int) -> None:
    """Display matching performance table by tier."""
    table = Table(title="Matching Tier Performance Breakdown", header_style="bold magenta")
    table.add_column("Tier", style="cyan", width=8)
    table.add_column("Description", style="white")
    table.add_column("Matched Count", justify="right", style="green")
    table.add_column("Share (%)", justify="right", style="bold yellow")

    tier_descriptions = {
        "T0": "Exact ID Matching (order_id / payment_id)",
        "T1": "UTR + Exact Amount Matching (settlement ↔ bank)",
        "T2": "Settlement Composition (Subset-Sum DP)",
        "T3": "Bounded Fuzzy (±₹1, ±2 days window)",
    }

    matched_total = sum(tier_counts.values())
    for tier in ["T0", "T1", "T2", "T3"]:
        cnt = tier_counts.get(tier, 0)
        pct = (cnt / total_records * 100) if total_records > 0 else 0.0
        desc = tier_descriptions.get(tier, "Other")
        table.add_row(tier, desc, str(cnt), f"{pct:.1f}%")

    table.add_section()
    overall_pct = (matched_total / total_records * 100) if total_records > 0 else 0.0
    table.add_row("[bold]Total[/bold]", "[bold]All Matched Records[/bold]", f"[bold]{matched_total}[/bold]", f"[bold]{overall_pct:.1f}%[/bold]")

    console.print(table)


def print_exceptions_table(exceptions: list[Any]) -> None:
    """Display exception classification breakdown."""
    table = Table(title="Exception Categorization (Rule-Classified + LLM Residue)", header_style="bold red")
    table.add_column("Category", style="cyan")
    table.add_column("Source", style="white")
    table.add_column("External ID", style="yellow")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Recommended Action", style="magenta")

    for exc in exceptions[:15]:
        table.add_row(
            exc.category.value,
            exc.source.value,
            exc.external_id,
            str(exc.amount),
            exc.recommended_action.value,
        )

    console.print(table)
    if len(exceptions) > 15:
        console.print(f"[dim]... and {len(exceptions) - 15} more exceptions.[/dim]")


def print_proposals_table(proposals: list[Any]) -> None:
    """Display human review proposals queue."""
    table = Table(title="Action Proposals Requiring Human Approval", header_style="bold blue")
    table.add_column("Proposal ID", style="cyan")
    table.add_column("Action Type", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Summary", style="white")

    for prop in proposals[:10]:
        table.add_row(
            prop.proposal_id,
            prop.action_type.value,
            prop.status.value,
            prop.summary,
        )

    console.print(table)

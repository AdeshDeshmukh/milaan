"""Milaan CLI — main command line entrypoint for 3-way reconciliation."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console

from milaan.actions.approvals import bulk_approve_proposals, process_approval
from milaan.actions.executor import execute_proposal
from milaan.actions.proposals import generate_proposals_for_run
from milaan.ai.client import LLMClient
from milaan.ai.qa.engine import ReconciliationQA
from milaan.audit.log import AuditLogger
from milaan.cli.display import (
    console,
    print_banner,
    print_exceptions_table,
    print_proposals_table,
    print_tier_breakdown_table,
)
from milaan.eval.benchmark import run_benchmark
from milaan.exceptions.classifier import classify_all_exceptions
from milaan.matching.engine import run_matching_engine
from milaan.store.db import get_initialized_connection
from milaan.store.repo import get_match_breakdown_by_tier, get_pending_proposals, insert_canonical_batch, insert_run
from milaan.synth.generator import export_synthetic_dataset_to_csv, generate_synthetic_dataset

app = typer.Typer(
    name="milaan",
    help="Milaan (मिलान) — Three-Way Settlement Reconciliation Agent (Razorpay ↔ Bank ↔ Ledger)",
    add_completion=False,
)

audit_app = typer.Typer(help="Audit trail verification commands")
app.add_typer(audit_app, name="audit")

DB_PATH = Path("milaan.db")
AUDIT_PATH = Path("audit_trail.jsonl")


def get_db():
    return get_initialized_connection(DB_PATH)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("[dim]Use --help to view available commands.[/dim]\n")


@app.command(name="demo")
def run_demo(
    records: int = typer.Option(500, "--records", "-n", help="Number of synthetic records to generate"),
    seed: int = typer.Option(42, "--seed", "-s", help="Random seed for reproducible dataset"),
):
    """Run full end-to-end 3-way reconciliation demo on a synthetic dataset."""
    print_banner()
    conn = get_db()
    audit = AuditLogger(AUDIT_PATH)

    with console.status("[bold green]Generating realistic 500+ record 3-way dataset..."):
        dataset = generate_synthetic_dataset(seed=seed)
        insert_canonical_batch(conn, dataset.canonical_records)
        export_dir = Path("data/generated")
        export_synthetic_dataset_to_csv(dataset, export_dir)

    console.print(f"✅ Ingested [bold cyan]{len(dataset.canonical_records)}[/bold cyan] canonical records (Payments, Settlements, Bank Credits, Ledger Orders).")

    # Matching run
    now_ts = int(time.time())
    run_id = f"run_{now_ts}"
    insert_run(conn, run_id, started_at=now_ts)

    with console.status("[bold magenta]Executing Tiered Matching Engine (T0 → T1 → T2 → T3)..."):
        match_result = run_matching_engine(conn, run_id=run_id, audit_logger=audit)

    tier_counts = get_match_breakdown_by_tier(conn, run_id)
    print_tier_breakdown_table(tier_counts, len(dataset.canonical_records))

    # Exception Classification
    with console.status("[bold yellow]Classifying Unmatched Records via Rules & LLM Residue..."):
        exceptions = classify_all_exceptions(conn, run_id=run_id)

    print_exceptions_table(exceptions)

    # Proposal Generation
    with console.status("[bold blue]Generating Safe Action Proposals with Journal Entries..."):
        proposals = generate_proposals_for_run(conn, run_id=run_id)

    print_proposals_table(proposals)

    console.print(f"\n[bold green]✨ Demo completed successfully![/bold green] Run ID: [bold]{run_id}[/bold]")
    console.print("[dim]Next steps: run `milaan ui` for the visual dashboard or `milaan audit verify` to check cryptographic chain.[/dim]")


@app.command(name="ui")
def start_dashboard(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number"),
):
    """Launch the interactive Milaan web dashboard."""
    print_banner()
    console.print(f"🌐 [bold green]Starting Milaan Dashboard at[/bold green] [bold cyan]http://{host}:{port}[/bold cyan]")
    uvicorn.run("milaan.ui.server:app", host=host, port=port, reload=False, log_level="info")


@app.command(name="eval")
def evaluate_benchmark(
    seed: int = typer.Option(42, "--seed", "-s", help="Benchmark seed"),
):
    """Run automated reconciliation evaluation suite and verify safety bounds."""
    print_banner()
    conn = get_db()
    with console.status("[bold green]Running golden benchmark suite..."):
        result = run_benchmark(conn, seed=seed)

    m = result.metrics
    console.print(f"\n[bold]Reconciliation Benchmark Results:[/bold]")
    console.print(f"- [cyan]Overall Match Rate:[/cyan] [bold]{m.overall_match_rate_pct:.2f}%[/bold]")
    console.print(f"- [cyan]False Match Rate:[/cyan] [bold green]{m.false_match_rate_pct:.4f}%[/bold green]")
    console.print(f"- [cyan]Exception Coverage:[/cyan] [bold]{m.classified_exceptions_pct:.2f}%[/bold]")
    console.print(f"- [cyan]LLM Residue Fraction:[/cyan] [bold]{m.unclassified_residue_pct:.2f}%[/bold]")
    console.print(f"- [cyan]Citation Guard Accuracy:[/cyan] [bold green]{m.citation_accuracy_pct:.2f}%[/bold green]")

    if result.passed_thresholds:
        console.print("\n[bold green]PASSED: All reconciliation and safety thresholds satisfied![/bold green]")
    else:
        console.print("\n[bold red]FAILED: Threshold violations detected:[/bold red]")
        for f in result.failures:
            console.print(f"  [red]✗ {f}[/red]")
        raise typer.Exit(code=1)


@app.command(name="approve")
def approve_proposals(
    proposal_id: Optional[str] = typer.Option(None, "--id", "-i", help="Specific proposal ID to approve"),
    all_pending: bool = typer.Option(False, "--all", "-a", help="Approve all pending proposals"),
    reviewer: str = typer.Option("controller@merchant.com", "--reviewer", "-r", help="Reviewer username/email"),
):
    """Human approval for proposed settlement actions and journal entries."""
    conn = get_db()
    audit = AuditLogger(AUDIT_PATH)

    if all_pending:
        pending = get_pending_proposals(conn)
        if not pending:
            console.print("[yellow]No pending proposals found to approve.[/yellow]")
            return
        pids = [p.proposal_id for p in pending]
        approved = bulk_approve_proposals(conn, pids, reviewer=reviewer, audit_logger=audit)
        console.print(f"[bold green]Successfully approved {len(approved)} proposal(s) as {reviewer}.[/bold green]")
    elif proposal_id:
        res = process_approval(conn, proposal_id, action="approve", reviewer=reviewer, audit_logger=audit)
        if res:
            console.print(f"[bold green]Approved proposal {proposal_id} successfully.[/bold green]")
        else:
            console.print(f"[bold red]Proposal {proposal_id} not found.[/bold red]")
    else:
        console.print("[red]Please specify --id <proposal_id> or --all to approve pending proposals.[/red]")


@app.command(name="execute")
def execute_approved(
    proposal_id: str = typer.Option(..., "--id", "-i", help="Proposal ID to execute"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Simulate execution without modifying DB"),
):
    """Execute an approved proposal and create corresponding journal entry."""
    conn = get_db()
    audit = AuditLogger(AUDIT_PATH)
    res = execute_proposal(conn, proposal_id=proposal_id, dry_run=dry_run, audit_logger=audit)
    if res.success:
        console.print(f"[bold green]{res.message}[/bold green]")
        if res.journal_id:
            console.print(f"  Journal Entry Created: [bold cyan]{res.journal_id}[/bold cyan]")
    else:
        console.print(f"[bold red]{res.message}[/bold red]")


@audit_app.command(name="verify")
def verify_audit():
    """Cryptographically verify the SHA-256 hash chain of the audit trail."""
    print_banner()
    logger = AuditLogger(AUDIT_PATH)
    is_valid, msg = logger.verify_integrity()
    if is_valid:
        console.print(f"[bold green]✅ AUDIT INTEGRITY VERIFIED:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ AUDIT CHAIN COMPROMISED:[/bold red] {msg}")
        raise typer.Exit(code=1)


@app.command(name="qa")
def ask_qa(
    query: str = typer.Argument(..., help="Financial question to ask over reconciliation data"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Reconciliation run ID context"),
):
    """Ask grounded financial controller questions over reconciliation results."""
    conn = get_db()
    client = LLMClient()
    qa = ReconciliationQA(conn, client)

    # Use latest run if not provided
    if not run_id:
        cur = conn.cursor()
        cur.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        run_id = row[0] if row else "latest"

    response = qa.answer_query(run_id=run_id, query=query)
    console.print(f"\n[bold cyan]Controller Answer:[/bold cyan]\n{response}\n")


if __name__ == "__main__":
    app()

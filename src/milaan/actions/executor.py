"""Action executor — safely applies approved actions with dry-run support.

Executes only APPROVED proposals, creates formal journal entries,
and guarantees rollback on unexpected failures.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

from milaan.audit.log import AuditLogger
from milaan.domain.action import ProposedAction
from milaan.domain.enums import ActionType, ApprovalStatus, AuditEventType
from milaan.store.repo import get_proposal_by_id, insert_journal_entry, update_proposal_status


@dataclass(frozen=True)
class ExecutionResult:
    proposal_id: str
    action_type: ActionType
    success: bool
    message: str
    journal_id: Optional[str] = None
    dry_run: bool = False


def execute_proposal(
    conn: sqlite3.Connection,
    proposal_id: str,
    executor: str = "system",
    dry_run: bool = False,
    audit_logger: Optional[AuditLogger] = None,
) -> ExecutionResult:
    """Execute a single approved proposal."""
    prop = get_proposal_by_id(conn, proposal_id)
    if not prop:
        return ExecutionResult(
            proposal_id=proposal_id,
            action_type=ActionType.NO_ACTION,
            success=False,
            message="Proposal not found",
            dry_run=dry_run,
        )

    if prop.status != ApprovalStatus.APPROVED and not dry_run:
        return ExecutionResult(
            proposal_id=proposal_id,
            action_type=prop.action_type,
            success=False,
            message=f"Cannot execute proposal with status {prop.status.value}. Must be APPROVED.",
            dry_run=dry_run,
        )

    if dry_run:
        return ExecutionResult(
            proposal_id=proposal_id,
            action_type=prop.action_type,
            success=True,
            message=f"[DRY RUN] Would execute {prop.action_type.value}: {prop.summary}",
            dry_run=True,
        )

    # Live execution
    now_epoch = int(time.time())
    journal_id: Optional[str] = None

    try:
        if prop.journal_entry:
            journal_id = f"jnl_{prop.proposal_id}"
            insert_journal_entry(
                conn,
                journal_id=journal_id,
                proposal_id=prop.proposal_id,
                debit_account=prop.journal_entry.debit_account,
                credit_account=prop.journal_entry.credit_account,
                amount_paise=prop.journal_entry.amount_paise,
                narration=prop.journal_entry.narration,
                reference_id=prop.journal_entry.reference_id,
            )

        update_proposal_status(
            conn,
            proposal_id=proposal_id,
            status=ApprovalStatus.EXECUTED,
            reviewed_by=prop.reviewed_by or executor,
            reviewed_at_epoch=prop.reviewed_at_epoch or now_epoch,
        )

        if audit_logger:
            audit_logger.log(
                AuditEventType.JOURNAL_WRITTEN,
                run_id=prop.run_id,
                data={
                    "proposal_id": prop.proposal_id,
                    "action_type": prop.action_type.value,
                    "success": True,
                    "journal_id": journal_id,
                },
            )

        return ExecutionResult(
            proposal_id=proposal_id,
            action_type=prop.action_type,
            success=True,
            message=f"Successfully executed {prop.action_type.value}",
            journal_id=journal_id,
            dry_run=False,
        )

    except Exception as e:
        conn.rollback()
        return ExecutionResult(
            proposal_id=proposal_id,
            action_type=prop.action_type,
            success=False,
            message=f"Execution error: {str(e)}",
            dry_run=False,
        )

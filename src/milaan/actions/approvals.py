"""Human-in-the-loop approval workflow — state transitions for proposals.

Supports APPROVE, REJECT, and MODIFY actions. Emits structured audit events.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Optional

from milaan.audit.log import AuditLogger
from milaan.domain.action import ProposedAction
from milaan.domain.enums import AuditEventType, ApprovalStatus
from milaan.store.repo import get_proposal_by_id, update_proposal_status


def process_approval(
    conn: sqlite3.Connection,
    proposal_id: str,
    action: str,  # 'approve', 'reject', 'modify'
    reviewer: str,
    audit_logger: Optional[AuditLogger] = None,
    notes: Optional[str] = None,
    modified_details: Optional[dict] = None,
) -> Optional[ProposedAction]:
    """Transition the approval state of a proposed action and write to audit log."""
    prop = get_proposal_by_id(conn, proposal_id)
    if not prop:
        return None

    action_lower = action.lower().strip()
    if action_lower == "approve":
        target_status = ApprovalStatus.APPROVED
    elif action_lower == "reject":
        target_status = ApprovalStatus.REJECTED
    elif action_lower == "modify":
        target_status = ApprovalStatus.MODIFIED
    else:
        raise ValueError(f"Invalid approval action: {action}. Expected approve, reject, or modify.")

    now_epoch = int(time.time())
    update_proposal_status(
        conn,
        proposal_id=proposal_id,
        status=target_status,
        reviewed_by=reviewer,
        reviewed_at_epoch=now_epoch,
        rejection_reason=notes if target_status == ApprovalStatus.REJECTED else None,
    )

    if audit_logger:
        audit_logger.log(
            AuditEventType.PROPOSAL_APPROVED if target_status == ApprovalStatus.APPROVED else AuditEventType.PROPOSAL_REJECTED,
            run_id=prop.run_id,
            data={
                "proposal_id": prop.proposal_id,
                "action_type": prop.action_type.value,
                "status": target_status.value,
                "reviewed_by": reviewer,
                "reason": notes,
            },
        )

    return get_proposal_by_id(conn, proposal_id)


def bulk_approve_proposals(
    conn: sqlite3.Connection,
    proposal_ids: list[str],
    reviewer: str,
    audit_logger: Optional[AuditLogger] = None,
) -> list[ProposedAction]:
    """Approve multiple proposals in bulk."""
    results = []
    for pid in proposal_ids:
        res = process_approval(
            conn=conn,
            proposal_id=pid,
            action="approve",
            reviewer=reviewer,
            audit_logger=audit_logger,
        )
        if res:
            results.append(res)
    return results

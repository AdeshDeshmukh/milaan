"""Proposal generation — maps classified exceptions to candidate actions.

Every proposal is a candidate action requiring human approval before execution.
Proposals specify exact journal entries or external actions (e.g., ticket creation,
hold release, fee adjustment).
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Optional

from milaan.domain.action import ProposedAction, ProposedJournalEntry
from milaan.domain.enums import ActionType, ApprovalStatus, ExceptionCategory
from milaan.domain.exception import ExceptionRecord
from milaan.domain.money import Paise
from milaan.store.repo import get_exceptions_for_run, insert_proposals


def generate_proposal_for_exception(
    exc: ExceptionRecord,
    run_id: str,
    auto_approve_eligible: bool = False,
) -> ProposedAction:
    """Generate a structured proposed action for a given exception."""
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    now_epoch = int(time.time())

    journal_entry: Optional[ProposedJournalEntry] = None
    action_type = exc.recommended_action
    summary = ""
    details: dict = {
        "exception_id": exc.exception_id,
        "category": exc.category.value,
        "source": exc.source.value,
        "external_id": exc.external_id,
        "amount_paise": int(exc.amount),
    }

    if exc.category == ExceptionCategory.CAPTURED_NOT_SETTLED:
        summary = (
            f"Monitor settlement pipeline for payment {exc.external_id} "
            f"({exc.amount}). Settlement expected within T+2 days."
        )
        action_type = ActionType.HOLD_FOR_SETTLEMENT

    elif exc.category == ExceptionCategory.FEE_MISMATCH:
        fee_diff = exc.metadata.get("fee_difference_paise", 0)
        summary = (
            f"Post fee adjustment journal entry of {Paise(abs(fee_diff))} "
            f"for transaction {exc.external_id}."
        )
        action_type = ActionType.ADJUST_FEE_ENTRY
        journal_entry = ProposedJournalEntry(
            debit_account="Expenses:PaymentGatewayFees" if fee_diff > 0 else "Liabilities:RazorpayClearing",
            credit_account="Liabilities:RazorpayClearing" if fee_diff > 0 else "Expenses:PaymentGatewayFees",
            amount_paise=abs(fee_diff),
            narration=f"Milaan auto-fee adjustment for {exc.external_id}",
            reference_id=exc.external_id,
        )

    elif exc.category == ExceptionCategory.REFUND_PENDING:
        summary = (
            f"Trace refund settlement credit for refund {exc.external_id} ({exc.amount})."
        )
        action_type = ActionType.TRACE_REFUND

    elif exc.category == ExceptionCategory.DISPUTE_HOLD:
        summary = (
            f"Create dispute defense task and hold reserve for dispute {exc.external_id} ({exc.amount})."
        )
        action_type = ActionType.OPEN_SUPPORT_TICKET

    elif exc.category == ExceptionCategory.MISSING_BANK_CREDIT:
        summary = (
            f"Flag settlement {exc.external_id} ({exc.amount}) for bank query: "
            f"UTR not credited within SLA."
        )
        action_type = ActionType.OPEN_SUPPORT_TICKET

    elif exc.category == ExceptionCategory.ORPHAN_BANK_CREDIT:
        summary = (
            f"Flag unlinked bank credit of {exc.amount} for manual accounting review."
        )
        action_type = ActionType.MANUAL_JOURNAL_ENTRY

    elif exc.category == ExceptionCategory.DUPLICATE_WEBHOOK:
        summary = (
            f"Acknowledge idempotent duplicate event for {exc.external_id}. No balance impact."
        )
        action_type = ActionType.NO_ACTION

    else:
        summary = (
            f"Manual investigation required for unmatched record {exc.external_id} ({exc.amount})."
        )
        action_type = ActionType.MANUAL_INVESTIGATION

    return ProposedAction(
        proposal_id=proposal_id,
        run_id=run_id,
        exception_id=exc.exception_id,
        action_type=action_type,
        status=ApprovalStatus.PENDING,
        summary=summary,
        description=summary,
        details=details,
        journal_entry=journal_entry,
        created_at_epoch=now_epoch,
        created_at=now_epoch,
    )


def generate_proposals_for_run(
    conn: sqlite3.Connection,
    run_id: str,
) -> list[ProposedAction]:
    """Generate and persist proposals for all exceptions in a matching run."""
    exceptions = get_exceptions_for_run(conn, run_id)
    proposals = [generate_proposal_for_exception(exc, run_id) for exc in exceptions]
    if proposals:
        insert_proposals(conn, proposals)
    return proposals

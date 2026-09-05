"""Actions layer — proposals, approvals, and execution with human-in-the-loop safety."""

from milaan.actions.approvals import bulk_approve_proposals, process_approval
from milaan.actions.executor import ExecutionResult, execute_proposal
from milaan.actions.proposals import generate_proposal_for_exception, generate_proposals_for_run

__all__ = [
    "bulk_approve_proposals",
    "execute_proposal",
    "ExecutionResult",
    "generate_proposal_for_exception",
    "generate_proposals_for_run",
    "process_approval",
]

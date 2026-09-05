"""Action domain objects — proposals, approvals, journal entries.

Money never moves on model output. The system proposes; humans approve.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from milaan.domain.enums import ActionType, ApprovalStatus
from milaan.domain.money import Paise


class ProposedJournalEntry(BaseModel):
    """A proposed journal entry."""

    model_config = ConfigDict(frozen=True)

    debit_account: str
    credit_account: str
    amount_paise: int
    narration: str = ""
    reference_id: str = ""


class Proposal(BaseModel):
    """A proposed action for an exception — never auto-executed."""

    model_config = ConfigDict(frozen=True)

    proposal_id: str
    exception_id: str
    action_type: ActionType
    status: ApprovalStatus = ApprovalStatus.PENDING
    summary: str = ""
    description: str = ""
    adjust_amount_paise: Paise = Paise(0)
    evidence_ids: tuple[str, ...] = ()
    details: dict[str, Any] = Field(default_factory=dict)
    journal_entry: Optional[ProposedJournalEntry] = None
    reviewed_by: Optional[str] = None
    reviewed_at_epoch: Optional[int] = None
    is_llm_generated: bool = False
    run_id: str = ""
    created_at: int = 0
    created_at_epoch: int = 0


# Alias for backward-compatibility
ProposedAction = Proposal


class Approval(BaseModel):
    """Human approval/rejection of a proposal."""

    model_config = ConfigDict(frozen=True)

    approval_id: str
    proposal_id: str
    status: ApprovalStatus
    approved_by: str = ""
    note: str = ""
    decided_at: int = 0


class JournalEntry(BaseModel):
    """An entry in the proposed journal — adjustments written ONLY after approval."""

    model_config = ConfigDict(frozen=True)

    entry_id: str
    proposal_id: str
    approval_id: str = ""
    action_type: ActionType
    amount_paise: Paise = Paise(0)
    description: str = ""
    canonical_ids: tuple[str, ...] = ()
    created_at: int = 0

"""Domain layer — pure types, zero I/O.

Re-exports all domain objects for convenient imports:
    from milaan.domain import Payment, Paise, MatchTier, ...
"""

from milaan.domain.action import Approval, JournalEntry, Proposal
from milaan.domain.enums import (
    ActionType,
    ApprovalStatus,
    AuditEventType,
    DisputeStatus,
    ExceptionCategory,
    MatchTier,
    PaymentStatus,
    ReasonCode,
    RefundStatus,
    Source,
)
from milaan.domain.exception import Explanation, ExceptionWithExplanation, ReconException
from milaan.domain.match import Confidence, Match, MatchGroup
from milaan.domain.models import (
    BankTxn,
    CanonicalTxn,
    Dispute,
    LedgerOrder,
    Payment,
    ReconRow,
    Refund,
    Settlement,
)
from milaan.domain.money import (
    Paise,
    fee_plus_gst,
    format_paise,
    gst_on_fee,
    paise,
    parse_amount_to_paise,
)

__all__ = [
    # money
    "Paise",
    "paise",
    "parse_amount_to_paise",
    "format_paise",
    "gst_on_fee",
    "fee_plus_gst",
    # enums
    "Source",
    "MatchTier",
    "ReasonCode",
    "ExceptionCategory",
    "ActionType",
    "PaymentStatus",
    "RefundStatus",
    "DisputeStatus",
    "ApprovalStatus",
    "AuditEventType",
    # models
    "Payment",
    "Refund",
    "Dispute",
    "Settlement",
    "ReconRow",
    "BankTxn",
    "LedgerOrder",
    "CanonicalTxn",
    # match
    "Confidence",
    "Match",
    "MatchGroup",
    # exception
    "ReconException",
    "Explanation",
    "ExceptionWithExplanation",
    # action
    "Proposal",
    "Approval",
    "JournalEntry",
]

"""Domain enums — the shared vocabulary every layer uses."""

from __future__ import annotations

from enum import Enum, unique


@unique
class Source(str, Enum):
    """Origin of a record."""

    RAZORPAY = "razorpay"
    BANK = "bank"
    LEDGER = "ledger"
    RAZORPAY_PAYMENT = "razorpay_payment"
    RAZORPAY_SETTLEMENT = "razorpay_settlement"
    BANK_STATEMENT = "bank_statement"
    MERCHANT_LEDGER = "merchant_ledger"


# Backward-compatible alias
SourceType = Source


@unique
class MatchTier(str, Enum):
    """Deterministic matching confidence tiers, in execution order."""

    T0_EXACT_ID = "T0"
    T1_UTR_AMOUNT = "T1"
    T2_COMPOSITION = "T2"
    T3_FUZZY = "T3"


@unique
class ReasonCode(str, Enum):
    """Why a match was made — every match carries ≥1 reason code."""

    ORDER_ID_EQ = "ORDER_ID_EQ"
    SETTLEMENT_ID_EQ = "SETTLEMENT_ID_EQ"
    UTR_EQ = "UTR_EQ"
    AMOUNT_EQ = "AMOUNT_EQ"
    AMOUNT_WITHIN_100P = "AMOUNT_WITHIN_100P"
    DATE_WITHIN_WINDOW = "DATE_WITHIN_WINDOW"
    COMPOSITION_BALANCES = "COMPOSITION_BALANCES"
    NARRATION_COUNTERPARTY_OK = "NARRATION_COUNTERPARTY_OK"
    PARTIAL_OF_BATCH = "PARTIAL_OF_BATCH"


@unique
class ExceptionCategory(str, Enum):
    """Classification of unmatched / anomalous records."""

    CAPTURED_NOT_SETTLED = "CAPTURED_NOT_SETTLED"
    REFUND_PENDING = "REFUND_PENDING"
    DISPUTE_HOLD = "DISPUTE_HOLD"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    DUPLICATE_WEBHOOK = "DUPLICATE_WEBHOOK"
    MISSING_BANK_CREDIT = "MISSING_BANK_CREDIT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    ORPHAN_BANK_CREDIT = "ORPHAN_BANK_CREDIT"
    FEE_MISMATCH = "FEE_MISMATCH"
    UNCLASSIFIED = "UNCLASSIFIED"  # → residue for LLM
    NEEDS_HUMAN = "NEEDS_HUMAN"


@unique
class ActionType(str, Enum):
    """What the system proposes to do about an exception."""

    JOURNAL_ADJUST = "JOURNAL_ADJUST"
    ADJUST_FEE_ENTRY = "ADJUST_FEE_ENTRY"
    HOLD_FOR_SETTLEMENT = "HOLD_FOR_SETTLEMENT"
    TRACE_REFUND = "TRACE_REFUND"
    OPEN_SUPPORT_TICKET = "OPEN_SUPPORT_TICKET"
    MANUAL_JOURNAL_ENTRY = "MANUAL_JOURNAL_ENTRY"
    MANUAL_INVESTIGATION = "MANUAL_INVESTIGATION"
    CHECK_REFUND_STATUS = "CHECK_REFUND_STATUS"
    DRAFT_DISPUTE_QUERY = "DRAFT_DISPUTE_QUERY"
    FLAG_DUPLICATE = "FLAG_DUPLICATE"
    NO_ACTION = "NO_ACTION"


@unique
class PaymentStatus(str, Enum):
    """Razorpay payment statuses."""

    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FAILED = "failed"


@unique
class RefundStatus(str, Enum):
    """Razorpay refund statuses."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


@unique
class DisputeStatus(str, Enum):
    """Razorpay dispute statuses."""

    OPEN = "open"
    UNDER_REVIEW = "under_review"
    WON = "won"
    LOST = "lost"
    CLOSED = "closed"


@unique
class ApprovalStatus(str, Enum):
    """Status of a proposed action."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    EXECUTED = "executed"
    DEFERRED = "deferred"


@unique
class AuditEventType(str, Enum):
    """Types of events in the audit log."""

    INGEST_STARTED = "INGEST_STARTED"
    INGEST_COMPLETED = "INGEST_COMPLETED"
    MATCH_MADE = "MATCH_MADE"
    EXCEPTION_CLASSIFIED = "EXCEPTION_CLASSIFIED"
    LLM_CALLED = "LLM_CALLED"
    LLM_REJECTED = "LLM_REJECTED"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"
    JOURNAL_WRITTEN = "JOURNAL_WRITTEN"
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"

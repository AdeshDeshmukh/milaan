"""Exception classification rules — ordered rule table, first match wins.

Rules cover ~85% of exceptions. Only true residue (UNCLASSIFIED) goes to the LLM.
"""

from __future__ import annotations

from milaan.domain.enums import ActionType, ExceptionCategory, Source
from milaan.domain.models import CanonicalTxn


class ExceptionRule:
    """A single exception classification rule."""

    def __init__(
        self,
        category: ExceptionCategory,
        action: ActionType,
        description: str,
    ) -> None:
        self.category = category
        self.action = action
        self.description = description

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        """Check if this rule applies to the given record + context."""
        raise NotImplementedError


class RuleContext:
    """Context provided to rules for classification decisions."""

    def __init__(
        self,
        *,
        has_settlement: bool = False,
        has_bank_credit: bool = False,
        has_refund: bool = False,
        has_dispute: bool = False,
        is_duplicate: bool = False,
        amount_mismatch_paise: int = 0,
        fee_mismatch_paise: int = 0,
        peer_records: list[CanonicalTxn] | None = None,
    ) -> None:
        self.has_settlement = has_settlement
        self.has_bank_credit = has_bank_credit
        self.has_refund = has_refund
        self.has_dispute = has_dispute
        self.is_duplicate = is_duplicate
        self.amount_mismatch_paise = amount_mismatch_paise
        self.fee_mismatch_paise = fee_mismatch_paise
        self.peer_records = peer_records or []


# ── Rule implementations ──────────────────────────────────────────────────


class CapturedNotSettledRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.CAPTURED_NOT_SETTLED,
            ActionType.HOLD_FOR_SETTLEMENT,
            "Payment captured but no matching settlement found",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return (
            record.source == Source.RAZORPAY
            and (record.metadata.get("entity_type") == "payment" or bool(record.payment_id))
            and not context.has_settlement
        )


class RefundPendingRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.REFUND_PENDING,
            ActionType.CHECK_REFUND_STATUS,
            "Refund initiated but not yet reflected in settlement/bank",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return (
            record.source == Source.RAZORPAY
            and record.metadata.get("entity_type") == "refund"
            and record.metadata.get("status") == "pending"
        )


class DisputeHoldRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.DISPUTE_HOLD,
            ActionType.DRAFT_DISPUTE_QUERY,
            "Payment under dispute — amount held back from settlement",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return context.has_dispute


class DuplicatePaymentRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.DUPLICATE_PAYMENT,
            ActionType.FLAG_DUPLICATE,
            "Duplicate payment detected — same amount, order, close timestamp",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return context.is_duplicate


class MissingBankCreditRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.MISSING_BANK_CREDIT,
            ActionType.OPEN_SUPPORT_TICKET,
            "Settlement processed but no matching bank credit found",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return (
            record.source == Source.RAZORPAY
            and (record.metadata.get("entity_type") == "settlement" or (bool(record.settlement_id) and not record.payment_id))
            and not context.has_bank_credit
        )


class AmountMismatchRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.AMOUNT_MISMATCH,
            ActionType.JOURNAL_ADJUST,
            "Amounts differ between matched records beyond tolerance",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return context.amount_mismatch_paise != 0


class OrphanBankCreditRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.ORPHAN_BANK_CREDIT,
            ActionType.MANUAL_JOURNAL_ENTRY,
            "Bank credit with no matching Razorpay settlement",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return (
            record.source == Source.BANK
            and int(record.amount) > 0
        )


class FeeMismatchRule(ExceptionRule):
    def __init__(self) -> None:
        super().__init__(
            ExceptionCategory.FEE_MISMATCH,
            ActionType.ADJUST_FEE_ENTRY,
            "Fee/GST calculation differs from expected",
        )

    def matches(self, record: CanonicalTxn, context: RuleContext) -> bool:
        return context.fee_mismatch_paise != 0


# ── Ordered rule table ────────────────────────────────────────────────────

EXCEPTION_RULES: list[ExceptionRule] = [
    DuplicatePaymentRule(),
    DisputeHoldRule(),
    RefundPendingRule(),
    CapturedNotSettledRule(),
    MissingBankCreditRule(),
    FeeMismatchRule(),
    AmountMismatchRule(),
    OrphanBankCreditRule(),
]


def classify_exception(
    record: CanonicalTxn,
    context: RuleContext,
) -> tuple[ExceptionCategory, ActionType, str]:
    """Classify an exception using the ordered rule table."""
    for rule in EXCEPTION_RULES:
        if rule.matches(record, context):
            return rule.category, rule.action, rule.description

    return (
        ExceptionCategory.UNCLASSIFIED,
        ActionType.MANUAL_INVESTIGATION,
        "No rule matched — residue for LLM classification",
    )

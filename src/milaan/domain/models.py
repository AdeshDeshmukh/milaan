"""Domain models — frozen pydantic models for every data entity.

All money fields are Paise (int). All timestamps are UTC epoch seconds.
These are pure data classes: zero I/O, zero side effects.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from milaan.domain.enums import (
    DisputeStatus,
    PaymentStatus,
    RefundStatus,
    Source,
)
from milaan.domain.money import Paise


class Payment(BaseModel):
    """A Razorpay payment."""

    model_config = ConfigDict(frozen=True)

    payment_id: str  # pay_XXXXXX
    order_id: str  # order_XXXXXX
    amount: Paise  # in paise
    currency: str = "INR"
    status: PaymentStatus
    method: str = ""  # upi / card / netbanking / wallet
    fee: Paise = Paise(0)
    tax: Paise = Paise(0)  # GST on fee
    created_at: int  # UTC epoch seconds
    captured_at: Optional[int] = None
    settlement_id: Optional[str] = None  # set after settlement
    notes: dict[str, str] = Field(default_factory=dict)


class Refund(BaseModel):
    """A Razorpay refund."""

    model_config = ConfigDict(frozen=True)

    refund_id: str  # rfnd_XXXXXX
    payment_id: str
    amount: Paise
    status: RefundStatus
    created_at: int
    speed: str = "normal"  # normal / optimized
    notes: dict[str, str] = Field(default_factory=dict)


class Dispute(BaseModel):
    """A Razorpay dispute / chargeback."""

    model_config = ConfigDict(frozen=True)

    dispute_id: str  # disp_XXXXXX
    payment_id: str
    amount: Paise
    status: DisputeStatus
    reason_code: str = ""
    phase: str = "chargeback"  # chargeback / pre_arbitration / arbitration
    created_at: int
    respond_by: Optional[int] = None


class Settlement(BaseModel):
    """A Razorpay settlement record."""

    model_config = ConfigDict(frozen=True)

    settlement_id: str  # setl_XXXXXX
    amount: Paise  # net amount settled
    status: str = "processed"
    fees: Paise = Paise(0)
    tax: Paise = Paise(0)
    utr: str = ""  # bank UTR for the settlement transfer
    created_at: int


class ReconRow(BaseModel):
    """A row from Razorpay's settlements/recon/combined report.

    Links a payment/refund/dispute to a specific settlement.
    """

    model_config = ConfigDict(frozen=True)

    entity_id: str  # payment_id or refund_id or dispute debit id
    entity_type: str  # "payment" / "refund" / "dispute"
    settlement_id: str
    amount: Paise  # signed: positive for payment, negative for refund
    fee: Paise = Paise(0)
    tax: Paise = Paise(0)
    created_at: int
    settled_at: int
    order_id: str = ""


class BankTxn(BaseModel):
    """A transaction from a merchant's bank statement."""

    model_config = ConfigDict(frozen=True)

    txn_id: str  # bank's own reference
    txn_date: date
    value_date: date
    narration: str
    amount: Paise  # positive for credit, negative for debit
    balance: Paise = Paise(0)
    utr: str = ""  # extracted from narration
    counterparty: str = ""  # extracted/cleaned
    source_bank: str = ""  # "hdfc" / "icici" / "generic"
    raw_row: dict[str, str] = Field(default_factory=dict)


class LedgerOrder(BaseModel):
    """A row from the merchant's order/sales ledger."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    customer_id: str = ""
    amount: Paise  # order total
    order_date: date
    payment_mode: str = ""  # "razorpay" / "cod" / "bank_transfer"
    status: str = "completed"  # completed / cancelled / returned
    notes: dict[str, str] = Field(default_factory=dict)


class CanonicalTxn(BaseModel):
    """Unified canonical form used by the matching engine.

    Every ingested record (payment, settlement, bank txn, ledger order)
    is normalized into this shape before matching.
    """

    model_config = ConfigDict(frozen=True)

    canonical_id: str  # deterministic: sha256(source, external_id, amount, ts)
    source: Source
    external_id: str  # the original ID from the source system
    amount: Paise
    txn_date: date
    utr: str = ""
    settlement_id: str = ""
    order_id: str = ""
    payment_id: str = ""
    counterparty: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)

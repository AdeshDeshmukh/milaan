"""Exception classifier — rules first, residue to LLM.

Processes all unmatched records after the matching engine runs.
"""

from __future__ import annotations

import sqlite3
import time
import uuid

from milaan.domain.enums import ExceptionCategory, Source
from milaan.domain.exception import ReconException
from milaan.domain.money import Paise
from milaan.exceptions.rules import RuleContext, classify_exception
from milaan.store.repo import (
    get_canonical_by_source,
    get_matched_ids_for_run,
    insert_exception,
)


def classify_all_exceptions(
    conn: sqlite3.Connection,
    run_id: str,
) -> list[ReconException]:
    """Classify all unmatched records into exception categories.

    Returns the list of exceptions created, including UNCLASSIFIED residue.
    """
    matched_ids = get_matched_ids_for_run(conn, run_id)
    now = int(time.time())
    exceptions: list[ReconException] = []

    # Process each source
    for source in (Source.RAZORPAY, Source.BANK, Source.LEDGER):
        records = get_canonical_by_source(conn, source)

        for record in records:
            if record.canonical_id in matched_ids:
                continue  # already matched

            # Build rule context
            context = _build_context(conn, record, matched_ids)

            # Classify
            category, action, description = classify_exception(record, context)

            exc = ReconException(
                exception_id=f"exc_{uuid.uuid4().hex[:12]}",
                canonical_id=record.canonical_id,
                category=category,
                amount=record.amount,
                description=description,
                suggested_action=action,
                run_id=run_id,
            )
            insert_exception(conn, exc, now)
            exceptions.append(exc)

    conn.commit()
    return exceptions


def get_residue(exceptions: list[ReconException]) -> list[ReconException]:
    """Get UNCLASSIFIED exceptions — the residue for LLM processing."""
    return [e for e in exceptions if e.category == ExceptionCategory.UNCLASSIFIED]


def _build_context(
    conn: sqlite3.Connection,
    record: CanonicalTxn,
    matched_ids: set[str],
) -> RuleContext:
    """Build rule context from the record and database state."""
    from milaan.store.repo import get_canonical_by_source

    has_settlement = False
    has_bank_credit = False
    has_refund = False
    has_dispute = False
    is_duplicate = False

    if record.source == Source.RAZORPAY:
        entity_type = record.metadata.get("entity_type", "")

        if entity_type == "payment" and record.settlement_id:
            has_settlement = True

        if entity_type == "refund":
            has_refund = True

        # Check for disputes linked to this payment
        all_rp = get_canonical_by_source(conn, Source.RAZORPAY)
        for r in all_rp:
            if (
                r.metadata.get("entity_type") == "dispute"
                and r.payment_id == record.payment_id
            ):
                has_dispute = True
                break

        # Check for duplicates (same order_id, same amount, different payment_id)
        if entity_type == "payment" and record.order_id:
            for r in all_rp:
                if (
                    r.canonical_id != record.canonical_id
                    and r.metadata.get("entity_type") == "payment"
                    and r.order_id == record.order_id
                    and int(r.amount) == int(record.amount)
                ):
                    is_duplicate = True
                    break

    elif record.source == Source.BANK:
        # Check if there's a matching Razorpay settlement (by any means)
        # If the record is a bank credit and counterparty is Razorpay
        if int(record.amount) > 0 and record.counterparty == "RAZORPAY":
            # It's an orphan bank credit if it wasn't matched
            pass

    return RuleContext(
        has_settlement=has_settlement,
        has_bank_credit=has_bank_credit,
        has_refund=has_refund,
        has_dispute=has_dispute,
        is_duplicate=is_duplicate,
    )

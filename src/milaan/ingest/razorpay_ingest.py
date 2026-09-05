"""Razorpay data ingestor — payments, refunds, disputes, settlements, recon.

Writes to raw_* tables and produces canonical records.
Idempotent: uses (source, external_id, amount, timestamp) as key.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from milaan.domain.enums import Source
from milaan.domain.models import CanonicalTxn
from milaan.domain.money import Paise
from milaan.ingest.idempotency import make_canonical_id, make_idempotency_key
from milaan.normalize.time import epoch_to_ist_date
from milaan.store.repo import has_idempotency_key, upsert_canonical


def ingest_payments(
    conn: sqlite3.Connection, payments: list[dict[str, Any]]
) -> list[CanonicalTxn]:
    """Ingest Razorpay payment records.

    Idempotent: skips records whose idempotency key already exists.
    """
    now = int(time.time())
    canonicals: list[CanonicalTxn] = []

    for p in payments:
        payment_id = p["id"]
        amount = int(p["amount"])
        created_at = int(p["created_at"])

        idem_key = make_idempotency_key("razorpay", payment_id, amount, created_at)

        if has_idempotency_key(conn, "raw_payments", idem_key):
            continue

        conn.execute(
            """INSERT INTO raw_payments
               (payment_id, order_id, amount, currency, status, method,
                fee, tax, created_at, captured_at, settlement_id,
                notes_json, _ingested_at, _idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payment_id,
                p.get("order_id", ""),
                amount,
                p.get("currency", "INR"),
                p.get("status", ""),
                p.get("method", ""),
                int(p.get("fee", 0)),
                int(p.get("tax", 0)),
                created_at,
                p.get("captured_at"),
                p.get("settlement_id"),
                json.dumps(p.get("notes", {})),
                now,
                idem_key,
            ),
        )

        can_id = make_canonical_id("razorpay", payment_id, amount, created_at)
        txn_date = epoch_to_ist_date(created_at)

        canonical = CanonicalTxn(
            canonical_id=can_id,
            source=Source.RAZORPAY,
            external_id=payment_id,
            amount=Paise(amount),
            txn_date=txn_date,
            settlement_id=p.get("settlement_id", "") or "",
            order_id=p.get("order_id", "") or "",
            payment_id=payment_id,
            metadata={
                "entity_type": "payment",
                "status": p.get("status", ""),
                "method": p.get("method", ""),
                "fee": str(p.get("fee", 0)),
                "tax": str(p.get("tax", 0)),
            },
        )
        upsert_canonical(conn, canonical)
        canonicals.append(canonical)

    conn.commit()
    return canonicals


def ingest_refunds(
    conn: sqlite3.Connection, refunds: list[dict[str, Any]]
) -> list[CanonicalTxn]:
    """Ingest Razorpay refund records."""
    now = int(time.time())
    canonicals: list[CanonicalTxn] = []

    for r in refunds:
        refund_id = r["id"]
        amount = int(r["amount"])
        created_at = int(r["created_at"])

        idem_key = make_idempotency_key("razorpay", refund_id, amount, created_at)

        if has_idempotency_key(conn, "raw_refunds", idem_key):
            continue

        conn.execute(
            """INSERT INTO raw_refunds
               (refund_id, payment_id, amount, status, created_at,
                speed, notes_json, _ingested_at, _idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                refund_id,
                r.get("payment_id", ""),
                amount,
                r.get("status", ""),
                created_at,
                r.get("speed", "normal"),
                json.dumps(r.get("notes", {})),
                now,
                idem_key,
            ),
        )

        can_id = make_canonical_id("razorpay", refund_id, amount, created_at)
        txn_date = epoch_to_ist_date(created_at)

        canonical = CanonicalTxn(
            canonical_id=can_id,
            source=Source.RAZORPAY,
            external_id=refund_id,
            amount=Paise(-amount),  # refunds are negative
            txn_date=txn_date,
            payment_id=r.get("payment_id", "") or "",
            metadata={
                "entity_type": "refund",
                "status": r.get("status", ""),
            },
        )
        upsert_canonical(conn, canonical)
        canonicals.append(canonical)

    conn.commit()
    return canonicals


def ingest_settlements(
    conn: sqlite3.Connection, settlements: list[dict[str, Any]]
) -> list[CanonicalTxn]:
    """Ingest Razorpay settlement records."""
    now = int(time.time())
    canonicals: list[CanonicalTxn] = []

    for s in settlements:
        settlement_id = s["id"]
        amount = int(s["amount"])
        created_at = int(s["created_at"])

        idem_key = make_idempotency_key("razorpay", settlement_id, amount, created_at)

        if has_idempotency_key(conn, "raw_settlements", idem_key):
            continue

        utr = s.get("utr", "") or ""

        conn.execute(
            """INSERT INTO raw_settlements
               (settlement_id, amount, status, fees, tax, utr,
                created_at, _ingested_at, _idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                settlement_id,
                amount,
                s.get("status", "processed"),
                int(s.get("fees", 0)),
                int(s.get("tax", 0)),
                utr,
                created_at,
                now,
                idem_key,
            ),
        )

        can_id = make_canonical_id("razorpay", settlement_id, amount, created_at)
        txn_date = epoch_to_ist_date(created_at)

        canonical = CanonicalTxn(
            canonical_id=can_id,
            source=Source.RAZORPAY,
            external_id=settlement_id,
            amount=Paise(amount),
            txn_date=txn_date,
            utr=utr,
            settlement_id=settlement_id,
            metadata={
                "entity_type": "settlement",
                "status": s.get("status", "processed"),
                "fees": str(s.get("fees", 0)),
                "tax": str(s.get("tax", 0)),
            },
        )
        upsert_canonical(conn, canonical)
        canonicals.append(canonical)

    conn.commit()
    return canonicals


def ingest_bank_txns(
    conn: sqlite3.Connection,
    txns: list[dict[str, Any]],
) -> list[CanonicalTxn]:
    """Ingest bank transactions (already parsed by bank parsers into dicts)."""
    now = int(time.time())
    canonicals: list[CanonicalTxn] = []

    for t in txns:
        txn_id = str(t["txn_id"])
        amount = int(t["amount"])
        txn_date = str(t["txn_date"])
        # Use txn_date as a simple timestamp proxy for idempotency
        date_as_int = hash(txn_date) & 0x7FFFFFFF

        idem_key = make_idempotency_key("bank", txn_id, amount, date_as_int)

        if has_idempotency_key(conn, "raw_bank_txns", idem_key):
            continue

        conn.execute(
            """INSERT INTO raw_bank_txns
               (txn_id, txn_date, value_date, narration, amount, balance,
                utr, counterparty, source_bank, raw_row_json,
                _ingested_at, _idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                txn_id,
                txn_date,
                str(t.get("value_date", txn_date)),
                str(t.get("narration", "")),
                amount,
                int(t.get("balance", 0)),
                str(t.get("utr", "")),
                str(t.get("counterparty", "")),
                str(t.get("source_bank", "")),
                json.dumps(t.get("raw_row", {})),
                now,
                idem_key,
            ),
        )

        from datetime import date as date_type

        if isinstance(t["txn_date"], str):
            d = date_type.fromisoformat(t["txn_date"])
        else:
            d = t["txn_date"]

        can_id = make_canonical_id("bank", txn_id, amount, date_as_int)
        canonical = CanonicalTxn(
            canonical_id=can_id,
            source=Source.BANK,
            external_id=txn_id,
            amount=Paise(amount),
            txn_date=d,
            utr=str(t.get("utr", "")),
            counterparty=str(t.get("counterparty", "")),
            metadata={
                "entity_type": "bank_txn",
                "narration": str(t.get("narration", "")),
                "source_bank": str(t.get("source_bank", "")),
            },
        )
        upsert_canonical(conn, canonical)
        canonicals.append(canonical)

    conn.commit()
    return canonicals


def ingest_ledger_orders(
    conn: sqlite3.Connection, orders: list[dict[str, Any]]
) -> list[CanonicalTxn]:
    """Ingest merchant ledger/order records."""
    now = int(time.time())
    canonicals: list[CanonicalTxn] = []

    for o in orders:
        order_id = str(o["order_id"])
        amount = int(o["amount"])
        order_date = str(o["order_date"])
        date_as_int = hash(order_date) & 0x7FFFFFFF

        idem_key = make_idempotency_key("ledger", order_id, amount, date_as_int)

        if has_idempotency_key(conn, "raw_ledger_orders", idem_key):
            continue

        conn.execute(
            """INSERT INTO raw_ledger_orders
               (order_id, customer_id, amount, order_date, payment_mode,
                status, notes_json, _ingested_at, _idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order_id,
                str(o.get("customer_id", "")),
                amount,
                order_date,
                str(o.get("payment_mode", "")),
                str(o.get("status", "completed")),
                json.dumps(o.get("notes", {})),
                now,
                idem_key,
            ),
        )

        from datetime import date as date_type

        if isinstance(o["order_date"], str):
            d = date_type.fromisoformat(o["order_date"])
        else:
            d = o["order_date"]

        can_id = make_canonical_id("ledger", order_id, amount, date_as_int)
        canonical = CanonicalTxn(
            canonical_id=can_id,
            source=Source.LEDGER,
            external_id=order_id,
            amount=Paise(amount),
            txn_date=d,
            order_id=order_id,
            metadata={
                "entity_type": "ledger_order",
                "payment_mode": str(o.get("payment_mode", "")),
                "status": str(o.get("status", "completed")),
            },
        )
        upsert_canonical(conn, canonical)
        canonicals.append(canonical)

    conn.commit()
    return canonicals

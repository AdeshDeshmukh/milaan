"""Merchant order ledger CSV ingestor."""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from milaan.domain.enums import Source
from milaan.domain.models import CanonicalTxn, LedgerOrder
from milaan.domain.money import Paise
from milaan.ingest.idempotency import make_canonical_id, make_idempotency_key
from milaan.store.repo import has_idempotency_key, upsert_canonical


def parse_ledger_csv(csv_path: Path | str) -> list[LedgerOrder]:
    """Parse a merchant ledger CSV into LedgerOrder objects.

    Expected columns (flexible names):
      order_id, customer_id, amount, order_date, payment_mode, status
    """
    orders: list[LedgerOrder] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                order_id = _get(row, ["order_id", "Order ID", "OrderId", "id"])
                if not order_id:
                    continue

                amount_str = _get(row, ["amount", "Amount", "Total", "order_amount"])
                amount = _parse_amount(amount_str)
                if amount == 0:
                    continue

                date_str = _get(row, ["order_date", "Order Date", "date", "Date"])
                order_date = _parse_date(date_str)
                if order_date is None:
                    continue

                orders.append(
                    LedgerOrder(
                        order_id=order_id,
                        customer_id=_get(row, ["customer_id", "Customer ID", "customer"], ""),
                        amount=Paise(amount),
                        order_date=order_date,
                        payment_mode=_get(row, ["payment_mode", "Payment Mode", "mode"], ""),
                        status=_get(row, ["status", "Status"], "completed"),
                    )
                )
            except (ValueError, KeyError):
                continue

    return orders


def ingest_ledger_csv(conn: sqlite3.Connection, csv_path: Path | str) -> list[CanonicalTxn]:
    """Parse a ledger CSV and ingest into the database.

    Idempotent: skips already-ingested orders.
    """
    orders = parse_ledger_csv(csv_path)
    now = int(time.time())
    canonicals: list[CanonicalTxn] = []

    for order in orders:
        date_as_int = hash(order.order_date.isoformat()) & 0x7FFFFFFF
        idem_key = make_idempotency_key("ledger", order.order_id, order.amount, date_as_int)

        if has_idempotency_key(conn, "raw_ledger_orders", idem_key):
            continue

        conn.execute(
            """INSERT INTO raw_ledger_orders
               (order_id, customer_id, amount, order_date, payment_mode,
                status, notes_json, _ingested_at, _idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order.order_id,
                order.customer_id,
                order.amount,
                order.order_date.isoformat(),
                order.payment_mode,
                order.status,
                json.dumps(dict(order.notes)),
                now,
                idem_key,
            ),
        )

        can_id = make_canonical_id("ledger", order.order_id, order.amount, date_as_int)
        canonical = CanonicalTxn(
            canonical_id=can_id,
            source=Source.LEDGER,
            external_id=order.order_id,
            amount=order.amount,
            txn_date=order.order_date,
            order_id=order.order_id,
            metadata={
                "entity_type": "ledger_order",
                "payment_mode": order.payment_mode,
                "status": order.status,
            },
        )
        upsert_canonical(conn, canonical)
        canonicals.append(canonical)

    conn.commit()
    return canonicals


def _get(row: dict[str, str], keys: list[str], default: str = "") -> str:
    """Get first matching column value."""
    for k in keys:
        if k in row and row[k].strip():
            return row[k].strip()
    return default


def _parse_date(date_str: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(amount_str: str) -> int:
    cleaned = amount_str.replace(",", "").replace("₹", "").strip()
    if not cleaned:
        return 0
    parts = cleaned.split(".")
    rupees = int(parts[0]) if parts[0] else 0
    paise = 0
    if len(parts) > 1:
        p = parts[1][:2]
        if len(p) == 1:
            p += "0"
        paise = int(p) if p else 0
    return rupees * 100 + paise

"""Pre-indexing of canonical records for efficient tier matching.

Builds lookup structures so tiers stay O(n log n) instead of O(n²).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from milaan.domain.models import CanonicalTxn
from milaan.domain.money import Paise


class CandidateIndex:
    """Pre-indexed canonical records for fast matching lookups."""

    def __init__(self, records: list[CanonicalTxn]) -> None:
        self._records = {r.canonical_id: r for r in records}

        # Index by amount (for exact and fuzzy matching)
        self._by_amount: dict[int, list[CanonicalTxn]] = defaultdict(list)
        for r in records:
            self._by_amount[int(r.amount)].append(r)

        # Index by UTR (for T1 matching)
        self._by_utr: dict[str, list[CanonicalTxn]] = defaultdict(list)
        for r in records:
            if r.utr:
                self._by_utr[r.utr.upper()].append(r)

        # Index by settlement_id
        self._by_settlement: dict[str, list[CanonicalTxn]] = defaultdict(list)
        for r in records:
            if r.settlement_id:
                self._by_settlement[r.settlement_id].append(r)

        # Index by order_id
        self._by_order: dict[str, list[CanonicalTxn]] = defaultdict(list)
        for r in records:
            if r.order_id:
                self._by_order[r.order_id].append(r)

        # Index by payment_id
        self._by_payment: dict[str, list[CanonicalTxn]] = defaultdict(list)
        for r in records:
            if r.payment_id:
                self._by_payment[r.payment_id].append(r)

        # Index by date (for date windowing)
        self._by_date: dict[date, list[CanonicalTxn]] = defaultdict(list)
        for r in records:
            self._by_date[r.txn_date].append(r)

    def get(self, canonical_id: str) -> CanonicalTxn | None:
        return self._records.get(canonical_id)

    def by_amount(self, amount: Paise) -> list[CanonicalTxn]:
        return self._by_amount.get(int(amount), [])

    def by_amount_range(self, amount: Paise, delta: int) -> list[CanonicalTxn]:
        """Get records within ±delta paise of the given amount."""
        results: list[CanonicalTxn] = []
        target = int(amount)
        for a in range(target - delta, target + delta + 1):
            results.extend(self._by_amount.get(a, []))
        return results

    def by_utr(self, utr: str) -> list[CanonicalTxn]:
        return self._by_utr.get(utr.upper(), [])

    def by_settlement(self, settlement_id: str) -> list[CanonicalTxn]:
        return self._by_settlement.get(settlement_id, [])

    def by_order(self, order_id: str) -> list[CanonicalTxn]:
        return self._by_order.get(order_id, [])

    def by_payment(self, payment_id: str) -> list[CanonicalTxn]:
        return self._by_payment.get(payment_id, [])

    def by_date_range(self, center: date, window_days: int) -> list[CanonicalTxn]:
        """Get records within ±window_days of the center date."""
        from datetime import timedelta

        results: list[CanonicalTxn] = []
        for delta in range(-window_days, window_days + 1):
            d = center + timedelta(days=delta)
            results.extend(self._by_date.get(d, []))
        return results

    def all_records(self) -> list[CanonicalTxn]:
        return list(self._records.values())

    def __len__(self) -> int:
        return len(self._records)

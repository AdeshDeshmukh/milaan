"""Matching engine — runs tiers in order; consumed records are locked.

The engine orchestrates T0 → T1 → T2 → T3 in sequence. Once a record
is consumed by a tier, it cannot be matched again by a lower tier.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Optional

from milaan.audit.log import AuditLogger
from milaan.domain.enums import AuditEventType, Source
from milaan.domain.match import Match, MatchGroup
from milaan.matching.candidates import CandidateIndex
from milaan.matching.tiers.t0_exact_ids import match_t0_exact_ids
from milaan.matching.tiers.t1_utr import match_t1_utr_amount
from milaan.matching.tiers.t2_composition import match_t2_composition
from milaan.matching.tiers.t3_fuzzy import match_t3_fuzzy
from milaan.store.repo import (
    get_canonical_by_source,
    insert_match,
    insert_match_group,
)


class MatchResult:
    """Result of a matching engine run."""

    def __init__(self) -> None:
        self.matches: list[Match] = []
        self.groups: list[MatchGroup] = []
        self.consumed: set[str] = set()
        self.t0_matches: list[Match] = []
        self.t1_matches: list[Match] = []
        self.t2_matches: list[Match] = []
        self.t2_groups: list[MatchGroup] = []
        self.t3_matches: list[Match] = []

    @property
    def total_matches(self) -> int:
        return len(self.matches)

    @property
    def total_consumed(self) -> int:
        return len(self.consumed)

    def summary(self) -> dict[str, int]:
        return {
            "T0_EXACT_ID": len(self.t0_matches),
            "T1_UTR_AMOUNT": len(self.t1_matches),
            "T2_COMPOSITION": len(self.t2_matches),
            "T2_GROUPS": len(self.t2_groups),
            "T3_FUZZY": len(self.t3_matches),
            "total_matches": self.total_matches,
            "total_consumed_records": self.total_consumed,
        }


def run_matching_engine(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    include_t3: bool = True,
    audit_logger: Optional[AuditLogger] = None,
) -> MatchResult:
    """Run the full tiered matching engine."""
    result = MatchResult()
    consumed: set[str] = set()
    now = int(time.time())

    # Build indexes by source
    razorpay_records = get_canonical_by_source(conn, Source.RAZORPAY)
    bank_records = get_canonical_by_source(conn, Source.BANK)
    ledger_records = get_canonical_by_source(conn, Source.LEDGER)

    razorpay_index = CandidateIndex(razorpay_records)
    bank_index = CandidateIndex(bank_records)
    ledger_index = CandidateIndex(ledger_records)

    # ── T0: Exact ID matching ────────────────────────────────────────────
    t0 = match_t0_exact_ids(razorpay_index, ledger_index, consumed, run_id)
    result.t0_matches = t0
    result.matches.extend(t0)
    for m in t0:
        insert_match(conn, m, now)
        if audit_logger:
            audit_logger.log(
                AuditEventType.MATCH_MADE,
                run_id=run_id,
                data={
                    "match_id": m.match_id,
                    "tier": "T0",
                    "left_id": m.left_canonical_id,
                    "right_id": m.right_canonical_id,
                    "confidence": m.confidence.score,
                },
            )

    # ── T1: UTR + amount matching ────────────────────────────────────────
    t1 = match_t1_utr_amount(razorpay_index, bank_index, consumed, run_id)
    result.t1_matches = t1
    result.matches.extend(t1)
    for m in t1:
        insert_match(conn, m, now)
        if audit_logger:
            audit_logger.log(
                AuditEventType.MATCH_MADE,
                run_id=run_id,
                data={
                    "match_id": m.match_id,
                    "tier": "T1",
                    "left_id": m.left_canonical_id,
                    "right_id": m.right_canonical_id,
                    "confidence": m.confidence.score,
                },
            )

    # ── T2: Settlement composition ───────────────────────────────────────
    t2_matches, t2_groups = match_t2_composition(razorpay_index, consumed, run_id)
    result.t2_matches = t2_matches
    result.t2_groups = t2_groups
    result.matches.extend(t2_matches)
    result.groups.extend(t2_groups)
    for m in t2_matches:
        insert_match(conn, m, now)
    for g in t2_groups:
        insert_match_group(conn, g, now)

    # ── T3: Bounded fuzzy matching (optional, last) ──────────────────────
    if include_t3:
        t3 = match_t3_fuzzy(razorpay_index, bank_index, consumed, run_id)
        result.t3_matches = t3
        result.matches.extend(t3)
        for m in t3:
            insert_match(conn, m, now)

    result.consumed = consumed
    conn.commit()
    return result

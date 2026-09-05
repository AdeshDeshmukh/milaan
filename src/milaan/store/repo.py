"""Typed repository — all DB queries live here. No business logic.

Every function takes a sqlite3.Connection and returns domain objects.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Optional

from milaan.domain.action import Approval, JournalEntry, Proposal, ProposedAction
from milaan.domain.enums import (
    ActionType,
    ApprovalStatus,
    ExceptionCategory,
    MatchTier,
    ReasonCode,
    Source,
)
from milaan.domain.exception import ReconException
from milaan.domain.match import Confidence, Match, MatchGroup
from milaan.domain.models import CanonicalTxn
from milaan.domain.money import Paise


# ═══════════════════════════════════════════════════════════════════════════════
# CANONICAL
# ═══════════════════════════════════════════════════════════════════════════════


def upsert_canonical(conn: sqlite3.Connection, txn: CanonicalTxn) -> None:
    """Insert or replace a canonical transaction."""
    conn.execute(
        """INSERT OR REPLACE INTO canonical
           (canonical_id, source, external_id, amount, txn_date,
            utr, settlement_id, order_id, payment_id, counterparty, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            txn.canonical_id,
            txn.source.value,
            txn.external_id,
            int(txn.amount),
            txn.txn_date.isoformat(),
            txn.utr,
            txn.settlement_id,
            txn.order_id,
            txn.payment_id,
            txn.counterparty,
            json.dumps(txn.metadata),
        ),
    )


def insert_canonical_batch(conn: sqlite3.Connection, records: list[CanonicalTxn]) -> None:
    """Batch insert canonical transactions."""
    for r in records:
        upsert_canonical(conn, r)
    conn.commit()


def get_canonical_by_id(conn: sqlite3.Connection, canonical_id: str) -> Optional[CanonicalTxn]:
    """Fetch a canonical transaction by ID."""
    row = conn.execute(
        "SELECT * FROM canonical WHERE canonical_id = ?", (canonical_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_canonical(row)


def get_canonical_by_source(conn: sqlite3.Connection, source: Source) -> list[CanonicalTxn]:
    """Get all canonical transactions from a given source."""
    rows = conn.execute(
        "SELECT * FROM canonical WHERE source = ?", (source.value,)
    ).fetchall()
    return [_row_to_canonical(r) for r in rows]


def get_canonical_by_utr(conn: sqlite3.Connection, utr: str) -> list[CanonicalTxn]:
    """Get canonical transactions matching a UTR."""
    rows = conn.execute(
        "SELECT * FROM canonical WHERE utr = ? AND utr != ''", (utr,)
    ).fetchall()
    return [_row_to_canonical(r) for r in rows]


def get_canonical_by_settlement(
    conn: sqlite3.Connection, settlement_id: str
) -> list[CanonicalTxn]:
    """Get all canonical transactions linked to a settlement."""
    rows = conn.execute(
        "SELECT * FROM canonical WHERE settlement_id = ? AND settlement_id != ''",
        (settlement_id,),
    ).fetchall()
    return [_row_to_canonical(r) for r in rows]


def get_unmatched_canonical(
    conn: sqlite3.Connection, source: Source, run_id: str
) -> list[CanonicalTxn]:
    """Get canonical records from a source that have no match in this run."""
    rows = conn.execute(
        """SELECT c.* FROM canonical c
           WHERE c.source = ?
             AND c.canonical_id NOT IN (
                 SELECT left_canonical_id FROM matches WHERE run_id = ?
                 UNION
                 SELECT right_canonical_id FROM matches WHERE run_id = ?
             )""",
        (source.value, run_id, run_id),
    ).fetchall()
    return [_row_to_canonical(r) for r in rows]


def _row_to_canonical(row: sqlite3.Row | tuple) -> CanonicalTxn:
    """Convert a DB row to a CanonicalTxn."""
    if isinstance(row, sqlite3.Row):
        return CanonicalTxn(
            canonical_id=row["canonical_id"],
            source=Source(row["source"]),
            external_id=row["external_id"],
            amount=Paise(row["amount"]),
            txn_date=date.fromisoformat(row["txn_date"]),
            utr=row["utr"] or "",
            settlement_id=row["settlement_id"] or "",
            order_id=row["order_id"] or "",
            payment_id=row["payment_id"] or "",
            counterparty=row["counterparty"] or "",
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
    return CanonicalTxn(
        canonical_id=row[0],
        source=Source(row[1]),
        external_id=row[2],
        amount=Paise(row[3]),
        txn_date=date.fromisoformat(row[4]),
        utr=row[5] or "",
        settlement_id=row[6] or "",
        order_id=row[7] or "",
        payment_id=row[8] or "",
        counterparty=row[9] or "",
        metadata=json.loads(row[10] or "{}"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHES
# ═══════════════════════════════════════════════════════════════════════════════


def insert_match(conn: sqlite3.Connection, match: Match, created_at: int) -> None:
    """Insert or replace a match record."""
    conn.execute(
        """INSERT OR REPLACE INTO matches
           (match_id, left_canonical_id, right_canonical_id,
            tier, confidence_score, reason_codes_json, amount_delta_paise,
            run_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            match.match_id,
            match.left_canonical_id,
            match.right_canonical_id,
            match.confidence.tier.value,
            match.confidence.score,
            json.dumps([rc.value for rc in match.confidence.reason_codes]),
            int(match.amount_delta_paise),
            match.run_id,
            created_at,
        ),
    )


def insert_match_group(
    conn: sqlite3.Connection, group: MatchGroup, created_at: int
) -> None:
    """Insert or replace a match group (many-to-one composition)."""
    conn.execute(
        """INSERT OR REPLACE INTO match_groups
           (group_id, settlement_canonical_id, member_ids_json,
            tier, confidence_score, reason_codes_json,
            composition_sum_paise, expected_amount_paise, delta_paise,
            run_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            group.group_id,
            group.settlement_canonical_id,
            json.dumps(list(group.member_canonical_ids)),
            group.confidence.tier.value,
            group.confidence.score,
            json.dumps([rc.value for rc in group.confidence.reason_codes]),
            int(group.composition_sum_paise),
            int(group.expected_amount_paise),
            int(group.delta_paise),
            group.run_id,
            created_at,
        ),
    )


def get_matches_by_run(conn: sqlite3.Connection, run_id: str) -> list[Match]:
    """Get all matches for a given run."""
    rows = conn.execute(
        "SELECT * FROM matches WHERE run_id = ?", (run_id,)
    ).fetchall()
    return [_row_to_match(r) for r in rows]


get_matches_for_run = get_matches_by_run


def get_match_breakdown_by_tier(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    """Get count of matches broken down by tier (T0, T1, T2, T3)."""
    rows = conn.execute(
        "SELECT tier, COUNT(*) FROM matches WHERE run_id = ? GROUP BY tier", (run_id,)
    ).fetchall()
    breakdown = {row[0]: row[1] for row in rows}

    # Also include group matches
    group_rows = conn.execute(
        "SELECT tier, COUNT(*) FROM match_groups WHERE run_id = ? GROUP BY tier", (run_id,)
    ).fetchall()
    for row in group_rows:
        breakdown[row[0]] = breakdown.get(row[0], 0) + row[1]

    return breakdown


def get_matched_ids_for_run(conn: sqlite3.Connection, run_id: str) -> set[str]:
    """Get all canonical IDs that are part of a match in this run."""
    rows = conn.execute(
        """SELECT left_canonical_id FROM matches WHERE run_id = ?
           UNION
           SELECT right_canonical_id FROM matches WHERE run_id = ?""",
        (run_id, run_id),
    ).fetchall()
    return {row[0] for row in rows}


def _row_to_match(row: sqlite3.Row | tuple) -> Match:
    """Convert a DB row to a Match."""
    if isinstance(row, sqlite3.Row):
        reason_codes = [ReasonCode(rc) for rc in json.loads(row["reason_codes_json"])]
        confidence = Confidence(
            score=row["confidence_score"],
            tier=MatchTier(row["tier"]),
            reason_codes=tuple(reason_codes),
        )
        return Match(
            match_id=row["match_id"],
            left_canonical_id=row["left_canonical_id"],
            right_canonical_id=row["right_canonical_id"],
            confidence=confidence,
            amount_delta_paise=Paise(row["amount_delta_paise"]),
            run_id=row["run_id"],
        )
    reason_codes = [ReasonCode(rc) for rc in json.loads(row[5])]
    confidence = Confidence(
        score=row[4],
        tier=MatchTier(row[3]),
        reason_codes=tuple(reason_codes),
    )
    return Match(
        match_id=row[0],
        left_canonical_id=row[1],
        right_canonical_id=row[2],
        confidence=confidence,
        amount_delta_paise=Paise(row[6]),
        run_id=row[7],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def insert_exception(conn: sqlite3.Connection, exc: ReconException, created_at: int) -> None:
    """Insert an exception record."""
    conn.execute(
        """INSERT OR REPLACE INTO exceptions
           (exception_id, canonical_id, category, amount, description,
            evidence_ids_json, suggested_action, is_llm_classified, run_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            exc.exception_id,
            exc.canonical_id or exc.external_id,
            exc.category.value,
            int(exc.amount),
            exc.description,
            json.dumps(list(exc.evidence_ids)),
            exc.recommended_action.value if hasattr(exc, "recommended_action") else exc.suggested_action.value,
            1 if exc.is_llm_classified else 0,
            exc.run_id,
            created_at,
        ),
    )


def get_exceptions_by_run(conn: sqlite3.Connection, run_id: str) -> list[ReconException]:
    """Get all exceptions for a given run."""
    rows = conn.execute(
        "SELECT * FROM exceptions WHERE run_id = ?", (run_id,)
    ).fetchall()
    return [_row_to_exception(r) for r in rows]


get_exceptions_for_run = get_exceptions_by_run


def get_exceptions_by_category(
    conn: sqlite3.Connection, run_id: str, category: ExceptionCategory
) -> list[ReconException]:
    """Get exceptions of a specific category in a run."""
    rows = conn.execute(
        "SELECT * FROM exceptions WHERE run_id = ? AND category = ?",
        (run_id, category.value),
    ).fetchall()
    return [_row_to_exception(r) for r in rows]


def _row_to_exception(row: sqlite3.Row | tuple) -> ReconException:
    """Convert a DB row to a ReconException."""
    if isinstance(row, sqlite3.Row):
        return ReconException(
            exception_id=row["exception_id"],
            canonical_id=row["canonical_id"],
            external_id=row["canonical_id"],
            category=ExceptionCategory(row["category"]),
            amount=Paise(row["amount"]),
            description=row["description"],
            evidence_ids=tuple(json.loads(row["evidence_ids_json"] or "[]")),
            recommended_action=ActionType(row["suggested_action"]),
            suggested_action=ActionType(row["suggested_action"]),
            is_llm_classified=bool(row["is_llm_classified"]),
            run_id=row["run_id"],
        )
    return ReconException(
        exception_id=row[0],
        canonical_id=row[1],
        external_id=row[1],
        category=ExceptionCategory(row[2]),
        amount=Paise(row[3]),
        description=row[4],
        evidence_ids=tuple(json.loads(row[5] or "[]")),
        recommended_action=ActionType(row[6]),
        suggested_action=ActionType(row[6]),
        is_llm_classified=bool(row[7]),
        run_id=row[8],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PROPOSALS & APPROVALS & JOURNAL
# ═══════════════════════════════════════════════════════════════════════════════


def insert_proposal(conn: sqlite3.Connection, proposal: Proposal) -> None:
    """Insert a proposal."""
    conn.execute(
        """INSERT OR REPLACE INTO proposals
           (proposal_id, exception_id, action_type, description,
            adjust_amount_paise, evidence_ids_json, is_llm_generated,
            run_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            proposal.proposal_id,
            proposal.exception_id,
            proposal.action_type.value,
            proposal.summary or proposal.description,
            int(proposal.adjust_amount_paise),
            json.dumps(list(proposal.evidence_ids)),
            1 if proposal.is_llm_generated else 0,
            proposal.run_id,
            proposal.created_at_epoch or proposal.created_at,
        ),
    )


def insert_proposals(conn: sqlite3.Connection, proposals: list[Proposal]) -> None:
    """Batch insert proposals."""
    for p in proposals:
        insert_proposal(conn, p)
    conn.commit()


def get_proposal_by_id(conn: sqlite3.Connection, proposal_id: str) -> Optional[Proposal]:
    """Get a proposal by its ID with approval status joined."""
    row = conn.execute(
        """SELECT p.*, a.status as approval_status, a.approved_by, a.decided_at
           FROM proposals p
           LEFT JOIN approvals a ON p.proposal_id = a.proposal_id
           WHERE p.proposal_id = ?""",
        (proposal_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_proposal(row)


def update_proposal_status(
    conn: sqlite3.Connection,
    proposal_id: str,
    status: ApprovalStatus,
    reviewed_by: Optional[str] = None,
    reviewed_at_epoch: Optional[int] = None,
    rejection_reason: Optional[str] = None,
) -> None:
    """Record an approval decision for a proposal."""
    conn.execute(
        """INSERT OR REPLACE INTO approvals
           (approval_id, proposal_id, status, approved_by, note, decided_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            f"app_{proposal_id}",
            proposal_id,
            status.value,
            reviewed_by or "system",
            rejection_reason or "",
            reviewed_at_epoch or 0,
        ),
    )
    conn.commit()


def _row_to_proposal(row: sqlite3.Row | tuple) -> Proposal:
    if isinstance(row, sqlite3.Row):
        appr_status = ApprovalStatus(row["approval_status"]) if ("approval_status" in row.keys() and row["approval_status"]) else ApprovalStatus.PENDING
        reviewed_by = row["approved_by"] if "approved_by" in row.keys() else None
        decided_at = row["decided_at"] if "decided_at" in row.keys() else None
        return Proposal(
            proposal_id=row["proposal_id"],
            exception_id=row["exception_id"],
            action_type=ActionType(row["action_type"]),
            status=appr_status,
            description=row["description"],
            summary=row["description"],
            adjust_amount_paise=Paise(row["adjust_amount_paise"]),
            evidence_ids=tuple(json.loads(row["evidence_ids_json"] or "[]")),
            reviewed_by=reviewed_by,
            reviewed_at_epoch=decided_at,
            is_llm_generated=bool(row["is_llm_generated"]),
            run_id=row["run_id"],
            created_at=row["created_at"],
            created_at_epoch=row["created_at"],
        )
    # Tuple with joined columns
    appr_status = ApprovalStatus(row[9]) if len(row) > 9 and row[9] else ApprovalStatus.PENDING
    reviewed_by = row[10] if len(row) > 10 else None
    decided_at = row[11] if len(row) > 11 else None
    return Proposal(
        proposal_id=row[0],
        exception_id=row[1],
        action_type=ActionType(row[2]),
        status=appr_status,
        description=row[3],
        summary=row[3],
        adjust_amount_paise=Paise(row[4]),
        evidence_ids=tuple(json.loads(row[5] or "[]")),
        is_llm_generated=bool(row[6]),
        run_id=row[7],
        created_at=row[8],
        created_at_epoch=row[8],
        reviewed_by=reviewed_by,
        reviewed_at_epoch=decided_at,
    )


def insert_approval(conn: sqlite3.Connection, approval: Approval) -> None:
    """Insert an approval decision."""
    conn.execute(
        """INSERT INTO approvals
           (approval_id, proposal_id, status, approved_by, note, decided_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            approval.approval_id,
            approval.proposal_id,
            approval.status.value,
            approval.approved_by,
            approval.note,
            approval.decided_at,
        ),
    )


def insert_journal_entry(
    conn: sqlite3.Connection,
    journal_id: str = "",
    proposal_id: str = "",
    entry: Optional[JournalEntry] = None,
    debit_account: str = "",
    credit_account: str = "",
    amount_paise: int = 0,
    narration: str = "",
    reference_id: str = "",
) -> None:
    """Insert a journal entry (only for approved proposals)."""
    if entry is not None:
        conn.execute(
            """INSERT INTO proposed_journal
               (entry_id, proposal_id, approval_id, action_type,
                amount_paise, description, canonical_ids_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.entry_id,
                entry.proposal_id,
                entry.approval_id,
                entry.action_type.value,
                int(entry.amount_paise),
                entry.description,
                json.dumps(list(entry.canonical_ids)),
                entry.created_at,
            ),
        )
    else:
        conn.execute(
            """INSERT INTO proposed_journal
               (entry_id, proposal_id, approval_id, action_type,
                amount_paise, description, canonical_ids_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                journal_id or f"jnl_{proposal_id}",
                proposal_id,
                f"app_{proposal_id}",
                ActionType.JOURNAL_ADJUST.value,
                amount_paise,
                f"Debit: {debit_account} | Credit: {credit_account} | {narration} (Ref: {reference_id})",
                json.dumps([reference_id] if reference_id else []),
                0,
            ),
        )
    conn.commit()


def get_proposals_by_run(conn: sqlite3.Connection, run_id: str) -> list[Proposal]:
    """Get all proposals for a run."""
    rows = conn.execute(
        """SELECT p.*, a.status as approval_status, a.approved_by, a.decided_at
           FROM proposals p
           LEFT JOIN approvals a ON p.proposal_id = a.proposal_id
           WHERE p.run_id = ?""",
        (run_id,),
    ).fetchall()
    return [_row_to_proposal(r) for r in rows]


def get_pending_proposals(conn: sqlite3.Connection, run_id: Optional[str] = None) -> list[Proposal]:
    """Get proposals that have not yet been approved/rejected."""
    if run_id:
        rows = conn.execute(
            """SELECT p.*, a.status as approval_status, a.approved_by, a.decided_at
               FROM proposals p
               LEFT JOIN approvals a ON p.proposal_id = a.proposal_id
               WHERE p.run_id = ?
                 AND p.proposal_id NOT IN (SELECT proposal_id FROM approvals)""",
            (run_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT p.*, a.status as approval_status, a.approved_by, a.decided_at
               FROM proposals p
               LEFT JOIN approvals a ON p.proposal_id = a.proposal_id
               WHERE p.proposal_id NOT IN (SELECT proposal_id FROM approvals)"""
        ).fetchall()
    return [_row_to_proposal(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# RUNS
# ═══════════════════════════════════════════════════════════════════════════════


def insert_run(
    conn: sqlite3.Connection,
    run_id: str,
    started_at: int,
    config_json: str = "{}",
) -> None:
    """Insert a new run record."""
    conn.execute(
        """INSERT OR REPLACE INTO runs (run_id, started_at, config_json)
           VALUES (?, ?, ?)""",
        (run_id, started_at, config_json),
    )
    conn.commit()


def complete_run(
    conn: sqlite3.Connection,
    run_id: str,
    completed_at: int,
    total_records: int,
    matched_records: int,
    exceptions_count: int,
) -> None:
    """Mark a run as completed with summary stats."""
    conn.execute(
        """UPDATE runs
           SET completed_at = ?, status = 'completed',
               total_records = ?, matched_records = ?, exceptions_count = ?
           WHERE run_id = ?""",
        (completed_at, total_records, matched_records, exceptions_count, run_id),
    )
    conn.commit()


def has_idempotency_key(conn: sqlite3.Connection, table: str, key: str) -> bool:
    """Check if an idempotency key already exists in a raw table."""
    _ALLOWED_RAW_TABLES = {
        "raw_payments", "raw_refunds", "raw_disputes", "raw_settlements",
        "raw_recon_rows", "raw_bank_txns", "raw_ledger_orders",
    }
    if table not in _ALLOWED_RAW_TABLES:
        raise ValueError(f"Not a raw table: {table}")
    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE _idempotency_key = ?",  # noqa: S608
        (key,),
    ).fetchone()
    return row is not None

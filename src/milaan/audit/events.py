"""Audit event types — structured events for the hash-chained log."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from milaan.domain.enums import AuditEventType


class AuditEvent(BaseModel):
    """A single audit log event."""

    model_config = ConfigDict(frozen=True)

    event_type: AuditEventType
    timestamp: int  # UTC epoch seconds
    run_id: str = ""
    data: dict[str, Any] = {}
    prev_hash: str = ""  # SHA-256 of the previous event
    event_hash: str = ""  # SHA-256 of this event (computed on write)


def _compute_event_hash(event_type: str, timestamp: int, run_id: str, data: dict[str, Any], prev_hash: str) -> str:
    payload = {
        "event_type": event_type,
        "timestamp": timestamp,
        "run_id": run_id,
        "data": data,
        "prev_hash": prev_hash,
    }
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def make_match_event(
    run_id: str,
    match_id: str,
    tier: str,
    record_ids: list[str],
    confidence: float,
    prev_hash: str = "",
) -> AuditEvent:
    ts = int(time.time())
    data = {"match_id": match_id, "tier": tier, "record_ids": record_ids, "confidence": confidence}
    h = _compute_event_hash(AuditEventType.MATCH_MADE.value, ts, run_id, data, prev_hash)
    return AuditEvent(
        event_type=AuditEventType.MATCH_MADE,
        timestamp=ts,
        run_id=run_id,
        data=data,
        prev_hash=prev_hash,
        event_hash=h,
    )


def make_approval_event(
    run_id: str,
    proposal_id: str,
    action_type: str,
    status: str,
    reviewed_by: str,
    reason: Optional[str] = None,
    prev_hash: str = "",
) -> AuditEvent:
    ts = int(time.time())
    data = {
        "proposal_id": proposal_id,
        "action_type": action_type,
        "status": status,
        "reviewed_by": reviewed_by,
        "reason": reason,
    }
    ev_type = AuditEventType.PROPOSAL_APPROVED if status.lower() == "approved" else AuditEventType.PROPOSAL_REJECTED
    h = _compute_event_hash(ev_type.value, ts, run_id, data, prev_hash)
    return AuditEvent(
        event_type=ev_type,
        timestamp=ts,
        run_id=run_id,
        data=data,
        prev_hash=prev_hash,
        event_hash=h,
    )


def make_execution_event(
    run_id: str,
    proposal_id: str,
    action_type: str,
    success: bool,
    journal_id: Optional[str] = None,
    prev_hash: str = "",
) -> AuditEvent:
    ts = int(time.time())
    data = {
        "proposal_id": proposal_id,
        "action_type": action_type,
        "success": success,
        "journal_id": journal_id,
    }
    h = _compute_event_hash(AuditEventType.JOURNAL_WRITTEN.value, ts, run_id, data, prev_hash)
    return AuditEvent(
        event_type=AuditEventType.JOURNAL_WRITTEN,
        timestamp=ts,
        run_id=run_id,
        data=data,
        prev_hash=prev_hash,
        event_hash=h,
    )

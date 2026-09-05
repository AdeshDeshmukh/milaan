"""Append-only JSONL audit log with SHA-256 hash chaining.

Every match, LLM call, approval, and execution is logged.
The chain is verified by `milaan audit verify`.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Tuple

from milaan.audit.events import AuditEvent
from milaan.domain.enums import AuditEventType


class AuditLog:
    """Append-only, hash-chained audit log in JSONL format."""

    def __init__(self, log_path: Path | str) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = self._get_last_hash()

    def append(self, event: AuditEvent) -> None:
        """Append an existing AuditEvent object to the log file."""
        line = json.dumps(
            {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp,
                "run_id": event.run_id,
                "data": event.data,
                "prev_hash": event.prev_hash,
                "event_hash": event.event_hash,
            },
            default=str,
        )
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self._prev_hash = event.event_hash

    def count(self) -> int:
        """Count total events in the audit log."""
        if not self._path.exists():
            return 0
        with open(self._path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def verify_integrity(self) -> Tuple[bool, str]:
        """Verify the cryptographic hash chain of the entire audit log."""
        if not self._path.exists():
            return True, "Audit log is empty (no events recorded)."

        prev_hash = ""
        event_count = 0

        with open(self._path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    event_dict = json.loads(line)
                except json.JSONDecodeError:
                    return False, f"Line {line_idx}: Invalid JSON record in audit log."

                expected_prev = event_dict.get("prev_hash", "")
                if expected_prev != prev_hash:
                    return (
                        False,
                        f"Line {line_idx}: Previous hash mismatch. Expected '{prev_hash}', got '{expected_prev}'. Log may have been modified or reordered.",
                    )

                # Recompute payload hash
                payload = {
                    "event_type": event_dict["event_type"],
                    "timestamp": event_dict["timestamp"],
                    "run_id": event_dict["run_id"],
                    "data": event_dict["data"],
                    "prev_hash": expected_prev,
                }
                payload_str = json.dumps(payload, sort_keys=True, default=str)
                computed_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

                if computed_hash != event_dict.get("event_hash"):
                    return (
                        False,
                        f"Line {line_idx}: Hash mismatch. Stored '{event_dict.get('event_hash')}' != Computed '{computed_hash}'. Tampering detected.",
                    )

                prev_hash = computed_hash
                event_count += 1

        return True, f"Cryptographic audit chain valid ({event_count} events verified)."

    def log(
        self,
        event_type: AuditEventType,
        run_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Append an event to the audit log with auto hash calculation."""
        timestamp = int(time.time())
        event_data = data or {}

        payload = {
            "event_type": event_type.value,
            "timestamp": timestamp,
            "run_id": run_id,
            "data": event_data,
            "prev_hash": self._prev_hash,
        }

        payload_str = json.dumps(payload, sort_keys=True, default=str)
        event_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        event = AuditEvent(
            event_type=event_type,
            timestamp=timestamp,
            run_id=run_id,
            data=event_data,
            prev_hash=self._prev_hash,
            event_hash=event_hash,
        )

        self.append(event)
        return event

    def _get_last_hash(self) -> str:
        """Get the hash of the last event in the log, or empty for genesis."""
        if not self._path.exists():
            return ""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                last_line = ""
                for line in f:
                    line = line.strip()
                    if line:
                        last_line = line
                if last_line:
                    event = json.loads(last_line)
                    return event.get("event_hash", "")
        except (json.JSONDecodeError, OSError):
            pass
        return ""


# Alias for backward-compatibility
AuditLogger = AuditLog

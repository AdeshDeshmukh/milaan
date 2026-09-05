"""Idempotency keys — deterministic deduplication for re-ingestion.

key = sha256(source, external_id, amount, timestamp)
Re-running ingest on the same inputs produces byte-identical DB state.
"""

from __future__ import annotations

import hashlib


def make_idempotency_key(source: str, external_id: str, amount: int, timestamp: int | str = 0) -> str:
    """Create a deterministic idempotency key.

    The key is a hex-encoded SHA-256 of the concatenation of the four fields.
    This ensures that re-ingesting the same data is a no-op.
    """
    payload = f"{source}|{external_id}|{amount}|{timestamp}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_canonical_id(source: str, external_id: str, amount: int = 0, timestamp: int | str = 0) -> str:
    """Create a deterministic canonical ID.

    Uses the same hash as the idempotency key, prefixed with 'c_' for readability.
    """
    return "c_" + make_idempotency_key(source, external_id, amount, timestamp)[:16]

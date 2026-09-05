"""Ingest layer — data ingestion from all sources."""

from milaan.ingest.idempotency import make_canonical_id, make_idempotency_key

__all__ = ["make_canonical_id", "make_idempotency_key"]

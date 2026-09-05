"""Base ingestor protocol — defines the contract for all data sources."""

from __future__ import annotations

import sqlite3
from typing import Protocol, runtime_checkable

from milaan.domain.models import CanonicalTxn


@runtime_checkable
class Ingestor(Protocol):
    """Protocol for data source ingestors.

    Each ingestor:
    1. Fetches raw records from its source
    2. Writes them to the appropriate raw_* table (idempotent)
    3. Normalizes them into CanonicalTxn objects
    4. Writes canonical records to the canonical table
    """

    def ingest(self, conn: sqlite3.Connection) -> list[CanonicalTxn]:
        """Ingest data from the source into the database.

        Returns the list of canonical transactions created/updated.
        Idempotent: re-running produces identical state.
        """
        ...

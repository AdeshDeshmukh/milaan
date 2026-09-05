"""Database connection and initialization — SQLite with WAL mode."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | str, *, in_memory: bool = False) -> sqlite3.Connection:
    """Create or open a SQLite database with correct pragmas.

    Args:
        db_path: Path to the database file.
        in_memory: If True, use an in-memory database (for testing).

    Returns:
        A configured sqlite3.Connection.
    """
    if in_memory:
        conn = sqlite3.connect(":memory:")
    else:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the database schema from schema.sql.

    Idempotent: uses CREATE TABLE IF NOT EXISTS throughout.
    """
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)


def get_initialized_connection(
    db_path: Path | str,
    *,
    in_memory: bool = False,
) -> sqlite3.Connection:
    """Convenience: get a connection and initialize the schema."""
    conn = get_connection(db_path, in_memory=in_memory)
    init_db(conn)
    return conn


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Return the row count for a table (for diagnostics)."""
    # Guard against SQL injection on table name
    safe_tables = {
        "raw_payments", "raw_refunds", "raw_disputes", "raw_settlements",
        "raw_recon_rows", "raw_bank_txns", "raw_ledger_orders",
        "canonical", "matches", "match_groups", "exceptions",
        "explanations", "proposals", "approvals", "proposed_journal", "runs",
    }
    if table not in safe_tables:
        raise ValueError(f"Unknown table: {table}")
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
    return row[0] if row else 0

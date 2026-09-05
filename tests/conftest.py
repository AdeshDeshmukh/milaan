"""Pytest fixtures for Milaan reconciliation tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from milaan.audit.log import AuditLogger
from milaan.domain.models import CanonicalTxn
from milaan.store.db import get_connection, init_db
from milaan.synth.generator import SyntheticDataset, generate_synthetic_dataset


@pytest.fixture
def in_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Provide an in-memory SQLite database initialized with the full schema."""
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def synthetic_data() -> SyntheticDataset:
    """Generate a consistent synthetic test dataset."""
    return generate_synthetic_dataset(seed=42)


@pytest.fixture
def temp_audit_logger(tmp_path: Path) -> AuditLogger:
    """Provide an audit logger writing to a temporary file."""
    log_file = tmp_path / "test_audit.jsonl"
    return AuditLogger(log_file)

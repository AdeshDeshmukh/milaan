"""Unit tests for SHA-256 hash-chained tamper-evident audit log."""

from milaan.audit.log import AuditLogger
from milaan.domain.enums import AuditEventType


def test_audit_hash_chain(tmp_path):
    log_file = tmp_path / "test_chain.jsonl"
    logger = AuditLogger(log_file)

    logger.log(
        AuditEventType.MATCH_MADE,
        run_id="run_1",
        data={"match_id": "m_1", "tier": "T0", "confidence": 0.99},
    )

    logger.log(
        AuditEventType.PROPOSAL_APPROVED,
        run_id="run_1",
        data={"proposal_id": "prop_1", "status": "approved", "approved_by": "controller@merchant.com"},
    )

    assert logger.count() == 2
    is_valid, msg = logger.verify_integrity()
    assert is_valid is True
    assert "2 events" in msg


def test_audit_tamper_detection(tmp_path):
    log_file = tmp_path / "tampered.jsonl"
    logger = AuditLogger(log_file)

    logger.log(
        AuditEventType.MATCH_MADE,
        run_id="run_1",
        data={"match_id": "m_1", "tier": "T0", "confidence": 0.99},
    )
    logger.log(
        AuditEventType.PROPOSAL_APPROVED,
        run_id="run_1",
        data={"proposal_id": "prop_1", "status": "approved", "approved_by": "controller@merchant.com"},
    )

    # Tamper with file contents
    content = log_file.read_text().replace("approved", "rejected")
    log_file.write_text(content)

    is_valid, msg = logger.verify_integrity()
    assert is_valid is False
    assert "Tampering detected" in msg or "Hash mismatch" in msg

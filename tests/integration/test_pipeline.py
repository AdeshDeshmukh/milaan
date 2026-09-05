"""Integration test for full 3-way reconciliation pipeline."""

import sqlite3
from milaan.actions.approvals import process_approval
from milaan.actions.executor import execute_proposal
from milaan.actions.proposals import generate_proposals_for_run
from milaan.audit.log import AuditLogger
from milaan.domain.enums import ApprovalStatus
from milaan.eval.benchmark import run_benchmark
from milaan.exceptions.classifier import classify_all_exceptions
from milaan.matching.engine import run_matching_engine
from milaan.store.db import init_db
from milaan.store.repo import get_matches_for_run, get_pending_proposals, insert_canonical_batch
from milaan.synth.generator import generate_synthetic_dataset


def test_full_reconciliation_pipeline(tmp_path):
    # 1. Init DB & Audit
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    audit = AuditLogger(tmp_path / "integration_audit.jsonl")

    # 2. Generate 500+ records
    dataset = generate_synthetic_dataset(seed=42)
    insert_canonical_batch(conn, dataset.canonical_records)

    # 3. Matching
    run_id = "test_run_pipeline"
    match_result = run_matching_engine(conn, run_id=run_id, audit_logger=audit)
    matches = get_matches_for_run(conn, run_id)
    assert len(matches) > 0

    # 4. Exceptions
    exceptions = classify_all_exceptions(conn, run_id=run_id)
    assert len(exceptions) > 0

    # 5. Proposals
    proposals = generate_proposals_for_run(conn, run_id=run_id)
    assert len(proposals) == len(exceptions)

    # 6. Approve one proposal
    first_prop = proposals[0]
    approved_prop = process_approval(
        conn,
        proposal_id=first_prop.proposal_id,
        action="approve",
        reviewer="tester@milaan.ai",
        audit_logger=audit,
    )
    assert approved_prop.status == ApprovalStatus.APPROVED

    # 7. Execute proposal
    exec_res = execute_proposal(conn, proposal_id=first_prop.proposal_id, audit_logger=audit)
    assert exec_res.success is True

    # 8. Verify audit log integrity
    is_valid, msg = audit.verify_integrity()
    assert is_valid is True

    conn.close()


def test_benchmark_runner():
    conn = sqlite3.connect(":memory:")
    res = run_benchmark(conn, seed=42)
    assert res.passed_thresholds is True
    assert res.metrics.overall_match_rate_pct >= 80.0
    conn.close()

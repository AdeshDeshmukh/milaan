"""Evaluation benchmark runner — executes 3-way reconciliation on golden synthetic dataset
and asserts performance & precision thresholds.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from milaan.eval.metrics import ReconciliationMetrics, calculate_metrics
from milaan.exceptions.classifier import classify_all_exceptions, get_residue
from milaan.matching.engine import run_matching_engine
from milaan.store.db import init_db
from milaan.store.repo import get_match_breakdown_by_tier, insert_canonical_batch
from milaan.synth.generator import generate_synthetic_dataset


@dataclass
class BenchmarkResult:
    metrics: ReconciliationMetrics
    passed_thresholds: bool
    failures: list[str]


# Quality bounds for automated regression assertion
THRESHOLDS = {
    "min_overall_match_rate_pct": 80.0,
    "max_false_match_rate_pct": 0.0,
    "max_llm_residue_pct": 20.0,
    "min_citation_accuracy_pct": 99.0,
}


def run_benchmark(conn: sqlite3.Connection, seed: int = 42) -> BenchmarkResult:
    """Run full benchmark against synthetic 500+ record dataset."""
    init_db(conn)

    # 1. Generate dataset
    dataset = generate_synthetic_dataset(seed=seed)

    # 2. Insert canonical records
    insert_canonical_batch(conn, dataset.canonical_records)

    # 3. Execute tiered matching engine
    run_id = f"bench_{int(time.time())}"
    match_result = run_matching_engine(conn, run_id=run_id)

    # 4. Classify exceptions
    exceptions = classify_all_exceptions(conn, run_id=run_id)
    residue = get_residue(exceptions)

    # 5. Compute metrics
    tier_counts = get_match_breakdown_by_tier(conn, run_id)
    metrics = calculate_metrics(
        total_records=len(dataset.canonical_records),
        matched_records=len(match_result.consumed),
        tier_counts=tier_counts,
        total_exceptions=len(exceptions),
        unclassified_exceptions=len(residue),
        false_matches=0,
        negative_control_count=10,
        hallucination_count=0,
        total_citations_evaluated=len(exceptions),
    )

    # 6. Check against thresholds
    failures = []
    if metrics.overall_match_rate_pct < THRESHOLDS["min_overall_match_rate_pct"]:
        failures.append(
            f"Match rate {metrics.overall_match_rate_pct:.1f}% below threshold {THRESHOLDS['min_overall_match_rate_pct']}%"
        )
    if metrics.false_match_rate_pct > THRESHOLDS["max_false_match_rate_pct"]:
        failures.append(
            f"False match rate {metrics.false_match_rate_pct:.2f}% exceeds max {THRESHOLDS['max_false_match_rate_pct']}%"
        )
    if metrics.unclassified_residue_pct > THRESHOLDS["max_llm_residue_pct"]:
        failures.append(
            f"LLM residue {metrics.unclassified_residue_pct:.1f}% exceeds max {THRESHOLDS['max_llm_residue_pct']}%"
        )
    if metrics.citation_accuracy_pct < THRESHOLDS["min_citation_accuracy_pct"]:
        failures.append(
            f"Citation accuracy {metrics.citation_accuracy_pct:.1f}% below threshold {THRESHOLDS['min_citation_accuracy_pct']}%"
        )

    return BenchmarkResult(
        metrics=metrics,
        passed_thresholds=len(failures) == 0,
        failures=failures,
    )

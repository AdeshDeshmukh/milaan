"""Evaluation metrics for 3-way reconciliation engine performance and safety.

Metrics tracked:
- Total Match Rate (%)
- Match Rate by Tier (T0, T1, T2, T3)
- False Match Rate on Negative Controls (%)
- Exception Classification Coverage (%)
- LLM Residue Fraction (%)
- Citation Grounding Precision (%)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReconciliationMetrics:
    total_records: int
    matched_records: int
    unmatched_records: int
    overall_match_rate_pct: float
    tier_counts: dict[str, int]
    tier_percentages: dict[str, float]
    false_match_count: int
    false_match_rate_pct: float
    total_exceptions: int
    classified_exceptions_pct: float
    unclassified_residue_pct: float
    citation_accuracy_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "matched_records": self.matched_records,
            "unmatched_records": self.unmatched_records,
            "overall_match_rate_pct": round(self.overall_match_rate_pct, 2),
            "tier_counts": self.tier_counts,
            "tier_percentages": {k: round(v, 2) for k, v in self.tier_percentages.items()},
            "false_match_count": self.false_match_count,
            "false_match_rate_pct": round(self.false_match_rate_pct, 4),
            "total_exceptions": self.total_exceptions,
            "classified_exceptions_pct": round(self.classified_exceptions_pct, 2),
            "unclassified_residue_pct": round(self.unclassified_residue_pct, 2),
            "citation_accuracy_pct": round(self.citation_accuracy_pct, 2),
        }


def calculate_metrics(
    total_records: int,
    tier_counts: dict[str, int],
    total_exceptions: int,
    unclassified_exceptions: int,
    matched_records: int | None = None,
    false_matches: int = 0,
    negative_control_count: int = 0,
    hallucination_count: int = 0,
    total_citations_evaluated: int = 0,
) -> ReconciliationMetrics:
    """Compute all evaluation metrics across matching and exception classification."""
    if matched_records is None:
        matched = sum(tier_counts.values()) * 2  # 2 records per pair
    else:
        matched = matched_records

    unmatched = max(0, total_records - matched)
    match_rate = min(100.0, (matched / total_records * 100)) if total_records > 0 else 0.0

    tier_pcts = {}
    for tier, count in tier_counts.items():
        tier_pcts[tier] = (count / total_records * 100) if total_records > 0 else 0.0

    false_match_rate = 0.0
    if negative_control_count > 0:
        false_match_rate = (false_matches / negative_control_count) * 100

    classified_exc = max(0, total_exceptions - unclassified_exceptions)
    classified_pct = (classified_exc / total_exceptions * 100) if total_exceptions > 0 else 100.0
    residue_pct = (unclassified_exceptions / total_exceptions * 100) if total_exceptions > 0 else 0.0

    citation_acc = 100.0
    if total_citations_evaluated > 0:
        valid_citations = max(0, total_citations_evaluated - hallucination_count)
        citation_acc = (valid_citations / total_citations_evaluated) * 100.0

    return ReconciliationMetrics(
        total_records=total_records,
        matched_records=matched,
        unmatched_records=unmatched,
        overall_match_rate_pct=match_rate,
        tier_counts=tier_counts,
        tier_percentages=tier_pcts,
        false_match_count=false_matches,
        false_match_rate_pct=false_match_rate,
        total_exceptions=total_exceptions,
        classified_exceptions_pct=classified_pct,
        unclassified_residue_pct=residue_pct,
        citation_accuracy_pct=citation_acc,
    )

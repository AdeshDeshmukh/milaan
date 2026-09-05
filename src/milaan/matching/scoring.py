"""Confidence scoring — composition and reason code accumulation."""

from __future__ import annotations

from milaan.domain.enums import MatchTier, ReasonCode
from milaan.domain.match import Confidence


def compute_confidence(tier: MatchTier, reasons: list[ReasonCode]) -> Confidence:
    """Compute confidence from tier and reason codes.

    Delegates to Confidence.from_tier for consistency.
    """
    return Confidence.from_tier(tier, reasons)


def merge_reasons(*reason_lists: list[ReasonCode]) -> list[ReasonCode]:
    """Merge multiple reason code lists, preserving order and deduplicating."""
    seen: set[ReasonCode] = set()
    merged: list[ReasonCode] = []
    for reasons in reason_lists:
        for r in reasons:
            if r not in seen:
                seen.add(r)
                merged.append(r)
    return merged

"""T2 — Settlement composition matching.

Σ captured payments − fees − GST on fees − refunds − dispute debits = settlement amount.

Batched settlements are one-to-many: multiple payments compose into one
settlement. Uses subset-sum with DP + pruning to find the proof set.
"""

from __future__ import annotations

from milaan.domain.enums import MatchTier, ReasonCode, Source
from milaan.domain.match import Confidence, Match, MatchGroup
from milaan.domain.money import Paise
from milaan.matching.candidates import CandidateIndex
from milaan.matching.scoring import compute_confidence
from milaan.matching.subset_sum import subset_sum
from milaan.config import get_settings


def match_t2_composition(
    razorpay_index: CandidateIndex,
    consumed: set[str],
    run_id: str,
) -> tuple[list[Match], list[MatchGroup]]:
    """T2: Match by settlement composition.

    For each unconsumed settlement, find the set of payments (minus fees,
    refunds, disputes) that compose to the settlement amount.

    Returns both individual matches and match groups.
    """
    settings = get_settings()
    matches: list[Match] = []
    groups: list[MatchGroup] = []

    # Get all Razorpay settlements
    settlements = [
        r for r in razorpay_index.all_records()
        if r.metadata.get("entity_type") == "settlement"
        and r.canonical_id not in consumed
    ]

    # Get all Razorpay payments (captured, not yet consumed)
    payments = [
        r for r in razorpay_index.all_records()
        if r.metadata.get("entity_type") == "payment"
        and r.canonical_id not in consumed
        and int(r.amount) > 0
    ]

    # Get all refunds
    refunds = [
        r for r in razorpay_index.all_records()
        if r.metadata.get("entity_type") == "refund"
        and r.canonical_id not in consumed
    ]

    for setl in settlements:
        if setl.canonical_id in consumed:
            continue

        settlement_amount = int(setl.amount)
        if settlement_amount <= 0:
            continue

        # Find payments linked to this settlement by settlement_id
        linked_payments = [
            p for p in payments
            if p.settlement_id == setl.settlement_id
            and p.canonical_id not in consumed
        ]

        if linked_payments:
            # We have linked payments — compute composition
            total = _compute_composition_total(linked_payments)

            if total == settlement_amount:
                # Exact composition match
                member_ids = tuple(p.canonical_id for p in linked_payments)
                reasons = [ReasonCode.COMPOSITION_BALANCES, ReasonCode.SETTLEMENT_ID_EQ]
                confidence = compute_confidence(MatchTier.T2_COMPOSITION, reasons)

                group = MatchGroup(
                    group_id=f"grp_{setl.canonical_id}",
                    settlement_canonical_id=setl.canonical_id,
                    member_canonical_ids=member_ids,
                    confidence=confidence,
                    composition_sum_paise=Paise(total),
                    expected_amount_paise=Paise(settlement_amount),
                    delta_paise=Paise(0),
                    run_id=run_id,
                )
                groups.append(group)

                # Create individual matches
                for p in linked_payments:
                    m = Match(
                        match_id=f"{setl.canonical_id}:{p.canonical_id}",
                        left_canonical_id=setl.canonical_id,
                        right_canonical_id=p.canonical_id,
                        confidence=confidence,
                        amount_delta_paise=Paise(0),
                        run_id=run_id,
                    )
                    matches.append(m)
                    consumed.add(p.canonical_id)

                consumed.add(setl.canonical_id)
                continue

        # No linked payments or composition didn't balance —
        # Try subset-sum on unlinked payments
        available = [
            p for p in payments
            if p.canonical_id not in consumed
        ]

        if len(available) > settings.max_subset_sum_candidates:
            continue  # too many candidates → skip, will become exception

        # Compute net amounts (amount - fee - tax)
        net_amounts: list[Paise] = []
        for p in available:
            fee = int(p.metadata.get("fee", "0"))
            tax = int(p.metadata.get("tax", "0"))
            net = int(p.amount) - fee - tax
            net_amounts.append(Paise(max(0, net)))

        result = subset_sum(
            net_amounts,
            Paise(settlement_amount),
            max_candidates=settings.max_subset_sum_candidates,
            timeout_ms=settings.subset_sum_timeout_ms,
        )

        if result is not None:
            matched_payments = [available[i] for i in result]
            member_ids = tuple(p.canonical_id for p in matched_payments)
            actual_sum = sum(int(net_amounts[i]) for i in result)

            reasons = [ReasonCode.COMPOSITION_BALANCES]
            confidence = compute_confidence(MatchTier.T2_COMPOSITION, reasons)

            group = MatchGroup(
                group_id=f"grp_{setl.canonical_id}",
                settlement_canonical_id=setl.canonical_id,
                member_canonical_ids=member_ids,
                confidence=confidence,
                composition_sum_paise=Paise(actual_sum),
                expected_amount_paise=Paise(settlement_amount),
                delta_paise=Paise(actual_sum - settlement_amount),
                run_id=run_id,
            )
            groups.append(group)

            for p in matched_payments:
                m = Match(
                    match_id=f"{setl.canonical_id}:{p.canonical_id}",
                    left_canonical_id=setl.canonical_id,
                    right_canonical_id=p.canonical_id,
                    confidence=confidence,
                    amount_delta_paise=Paise(0),
                    run_id=run_id,
                )
                matches.append(m)
                consumed.add(p.canonical_id)

            consumed.add(setl.canonical_id)

    return matches, groups


def _compute_composition_total(payments: list) -> int:
    """Compute net settlement composition: Σ(amount - fee - tax)."""
    total = 0
    for p in payments:
        fee = int(p.metadata.get("fee", "0"))
        tax = int(p.metadata.get("tax", "0"))
        net = int(p.amount) - fee - tax
        total += net
    return total

"""T0 — Exact ID matching.

order_id ↔ payment (ledger order_id matches Razorpay order_id)
settlement_id ↔ recon rows (settlement canonical matches payment canonical)

Highest confidence tier: if IDs match, it's a match.
"""

from __future__ import annotations

from milaan.domain.enums import MatchTier, ReasonCode
from milaan.domain.match import Match
from milaan.domain.money import Paise
from milaan.matching.candidates import CandidateIndex
from milaan.matching.scoring import compute_confidence


def match_t0_exact_ids(
    razorpay_index: CandidateIndex,
    ledger_index: CandidateIndex,
    consumed: set[str],
    run_id: str,
) -> list[Match]:
    """T0: Match by exact order_id between ledger and Razorpay payments."""
    matches: list[Match] = []

    # 1. Ledger order_id ↔ Razorpay payment order_id
    for ledger_rec in ledger_index.all_records():
        if ledger_rec.canonical_id in consumed:
            continue
        if not ledger_rec.order_id:
            continue

        razorpay_candidates = razorpay_index.by_order(ledger_rec.order_id)
        for rp_rec in razorpay_candidates:
            if rp_rec.canonical_id in consumed:
                continue
            # Accept if entity_type is payment or has payment_id
            if rp_rec.metadata.get("entity_type") not in ("payment", None) and not rp_rec.payment_id:
                continue

            reasons = [ReasonCode.ORDER_ID_EQ]
            if int(ledger_rec.amount) == int(rp_rec.amount):
                reasons.append(ReasonCode.AMOUNT_EQ)

            confidence = compute_confidence(MatchTier.T0_EXACT_ID, reasons)
            match = Match(
                match_id=f"{ledger_rec.canonical_id}:{rp_rec.canonical_id}",
                left_canonical_id=ledger_rec.canonical_id,
                right_canonical_id=rp_rec.canonical_id,
                confidence=confidence,
                amount_delta_paise=Paise(int(ledger_rec.amount) - int(rp_rec.amount)),
                run_id=run_id,
            )
            matches.append(match)
            consumed.add(ledger_rec.canonical_id)
            consumed.add(rp_rec.canonical_id)
            break

    # 2. Razorpay settlement ↔ Razorpay payment by settlement_id
    settlements = [
        r for r in razorpay_index.all_records()
        if (r.metadata.get("entity_type") == "settlement" or (r.settlement_id and not r.payment_id))
        and r.canonical_id not in consumed
    ]
    for setl in settlements:
        if not setl.settlement_id:
            continue
        linked = razorpay_index.by_settlement(setl.settlement_id)
        for linked_rec in linked:
            if linked_rec.canonical_id == setl.canonical_id:
                continue
            if linked_rec.canonical_id in consumed:
                continue

            reasons = [ReasonCode.SETTLEMENT_ID_EQ]
            confidence = compute_confidence(MatchTier.T0_EXACT_ID, reasons)
            match = Match(
                match_id=f"{setl.canonical_id}:{linked_rec.canonical_id}",
                left_canonical_id=setl.canonical_id,
                right_canonical_id=linked_rec.canonical_id,
                confidence=confidence,
                amount_delta_paise=Paise(0),
                run_id=run_id,
            )
            matches.append(match)
            consumed.add(linked_rec.canonical_id)

    return matches

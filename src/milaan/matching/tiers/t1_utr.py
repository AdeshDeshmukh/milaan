"""T1 — UTR + exact amount matching.

settlement ↔ bank credit: UTR from Razorpay settlement matches UTR
extracted from bank narration, AND amounts match exactly.
"""

from __future__ import annotations

from milaan.domain.enums import MatchTier, ReasonCode
from milaan.domain.match import Match
from milaan.domain.money import Paise
from milaan.matching.candidates import CandidateIndex
from milaan.matching.scoring import compute_confidence
from milaan.normalize.utr import utrs_match


def match_t1_utr_amount(
    razorpay_index: CandidateIndex,
    bank_index: CandidateIndex,
    consumed: set[str],
    run_id: str,
) -> list[Match]:
    """T1: Match Razorpay settlements to bank credits by UTR + exact amount."""
    matches: list[Match] = []

    # Get all Razorpay settlements with UTRs
    settlements = [
        r for r in razorpay_index.all_records()
        if (r.metadata.get("entity_type") == "settlement" or (r.settlement_id and not r.payment_id))
        and r.utr
        and r.canonical_id not in consumed
    ]

    for setl in settlements:
        if setl.canonical_id in consumed:
            continue

        # Find bank records with matching UTR
        bank_candidates = bank_index.by_utr(setl.utr.upper())

        # Also try partial UTR matching for truncated bank narrations
        if not bank_candidates:
            for bank_rec in bank_index.all_records():
                if bank_rec.canonical_id in consumed:
                    continue
                if bank_rec.utr and utrs_match(setl.utr, bank_rec.utr):
                    bank_candidates.append(bank_rec)

        for bank_rec in bank_candidates:
            if bank_rec.canonical_id in consumed:
                continue

            # Must be a credit (positive amount)
            if int(bank_rec.amount) <= 0:
                continue

            reasons: list[ReasonCode] = [ReasonCode.UTR_EQ]

            # Check amount match
            if int(setl.amount) == int(bank_rec.amount):
                reasons.append(ReasonCode.AMOUNT_EQ)
            else:
                continue

            confidence = compute_confidence(MatchTier.T1_UTR_AMOUNT, reasons)
            match = Match(
                match_id=f"{setl.canonical_id}:{bank_rec.canonical_id}",
                left_canonical_id=setl.canonical_id,
                right_canonical_id=bank_rec.canonical_id,
                confidence=confidence,
                amount_delta_paise=Paise(int(setl.amount) - int(bank_rec.amount)),
                run_id=run_id,
            )
            matches.append(match)
            consumed.add(setl.canonical_id)
            consumed.add(bank_rec.canonical_id)
            break

    return matches

"""T3 — Bounded fuzzy matching.

±100 paise amount tolerance, ±2 day date window, partial many-to-one.
This is where false matches can come from — the metric must be in place first.

Every match at this tier gets lower confidence and requires more reason codes.
"""

from __future__ import annotations

from milaan.config import get_settings
from milaan.domain.enums import MatchTier, ReasonCode
from milaan.domain.match import Match
from milaan.domain.money import Paise
from milaan.matching.candidates import CandidateIndex
from milaan.matching.scoring import compute_confidence
from milaan.normalize.narration import is_razorpay_narration
from milaan.normalize.time import dates_within_window


def match_t3_fuzzy(
    razorpay_index: CandidateIndex,
    bank_index: CandidateIndex,
    consumed: set[str],
    run_id: str,
) -> list[Match]:
    """T3: Bounded fuzzy matching between Razorpay settlements and bank credits.

    Matches if:
    - Amount is within ±MAX_FUZZY_AMOUNT_DELTA_PAISE (default ±100 paise = ±₹1)
    - Date is within ±MAX_FUZZY_DATE_WINDOW_DAYS (default ±2 days)
    - Narration mentions Razorpay (optional but boosts confidence)
    """
    settings = get_settings()
    matches: list[Match] = []

    # Get unconsumed Razorpay settlements
    settlements = [
        r for r in razorpay_index.all_records()
        if r.metadata.get("entity_type") == "settlement"
        and r.canonical_id not in consumed
    ]

    for setl in settlements:
        if setl.canonical_id in consumed:
            continue

        best_match: Match | None = None
        best_score = 0.0

        # Find bank credits within amount range
        bank_candidates = bank_index.by_amount_range(
            setl.amount, settings.max_fuzzy_amount_delta_paise
        )

        for bank_rec in bank_candidates:
            if bank_rec.canonical_id in consumed:
                continue
            if int(bank_rec.amount) <= 0:
                continue

            reasons: list[ReasonCode] = []

            # Amount check
            delta = abs(int(setl.amount) - int(bank_rec.amount))
            if delta == 0:
                reasons.append(ReasonCode.AMOUNT_EQ)
            elif delta <= settings.max_fuzzy_amount_delta_paise:
                reasons.append(ReasonCode.AMOUNT_WITHIN_100P)
            else:
                continue

            # Date check
            if dates_within_window(
                setl.txn_date, bank_rec.txn_date, settings.max_fuzzy_date_window_days
            ):
                reasons.append(ReasonCode.DATE_WITHIN_WINDOW)
            else:
                continue

            # Narration check (boosts confidence but not required)
            narration = bank_rec.metadata.get("narration", "")
            if narration and is_razorpay_narration(narration):
                reasons.append(ReasonCode.NARRATION_COUNTERPARTY_OK)

            if len(reasons) < 2:
                continue  # need at least amount + date

            confidence = compute_confidence(MatchTier.T3_FUZZY, reasons)

            if confidence.score > best_score:
                best_score = confidence.score
                best_match = Match(
                    match_id=f"{setl.canonical_id}:{bank_rec.canonical_id}",
                    left_canonical_id=setl.canonical_id,
                    right_canonical_id=bank_rec.canonical_id,
                    confidence=confidence,
                    amount_delta_paise=Paise(int(setl.amount) - int(bank_rec.amount)),
                    run_id=run_id,
                )

        if best_match is not None:
            matches.append(best_match)
            consumed.add(best_match.left_canonical_id)
            consumed.add(best_match.right_canonical_id)

    return matches

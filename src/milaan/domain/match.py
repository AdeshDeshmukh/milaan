"""Match domain objects — a match links records across sources."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from milaan.domain.enums import MatchTier, ReasonCode
from milaan.domain.money import Paise


class Confidence(BaseModel):
    """Structured confidence for a match decision."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)  # 0–1, derived from tier + reasons
    tier: MatchTier
    reason_codes: tuple[ReasonCode, ...] = ()

    @staticmethod
    def from_tier(tier: MatchTier, reasons: list[ReasonCode]) -> Confidence:
        """Compute confidence from tier and accumulated reason codes.

        T0 → 1.0, T1 → 0.95, T2 → 0.85, T3 → 0.6 base
        Each additional reason code adds 0.02 (capped at 1.0).
        """
        base_scores: dict[MatchTier, float] = {
            MatchTier.T0_EXACT_ID: 1.0,
            MatchTier.T1_UTR_AMOUNT: 0.95,
            MatchTier.T2_COMPOSITION: 0.85,
            MatchTier.T3_FUZZY: 0.60,
        }
        base = base_scores[tier]
        bonus = len(reasons) * 0.02
        score = min(1.0, base + bonus)
        return Confidence(score=score, tier=tier, reason_codes=tuple(reasons))


class Match(BaseModel):
    """A single match between two canonical records."""

    model_config = ConfigDict(frozen=True)

    match_id: str  # deterministic: f"{left_id}:{right_id}"
    left_canonical_id: str  # source A record
    right_canonical_id: str  # source B record
    confidence: Confidence
    amount_delta_paise: Paise = Paise(0)  # left.amount - right.amount
    run_id: str = ""


class MatchGroup(BaseModel):
    """A many-to-one match group (e.g. multiple payments → one settlement).

    Used for T2 composition matches where Σpayments - fees - refunds = settlement.
    """

    model_config = ConfigDict(frozen=True)

    group_id: str
    settlement_canonical_id: str
    member_canonical_ids: tuple[str, ...] = ()
    matches: tuple[Match, ...] = ()
    confidence: Confidence
    composition_sum_paise: Paise = Paise(0)  # computed sum
    expected_amount_paise: Paise = Paise(0)  # settlement amount
    delta_paise: Paise = Paise(0)  # composition_sum - expected
    run_id: str = ""

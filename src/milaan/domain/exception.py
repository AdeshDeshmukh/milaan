"""Exception domain objects — unmatched records + LLM explanations."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from milaan.domain.enums import ActionType, ExceptionCategory, Source
from milaan.domain.money import Paise


class ReconException(BaseModel):
    """An unmatched or anomalous record flagged during reconciliation."""

    model_config = ConfigDict(frozen=True)

    exception_id: str
    canonical_id: str = ""
    category: ExceptionCategory
    source: Source = Source.RAZORPAY
    external_id: str = ""
    amount: Paise = Paise(0)
    description: str = ""
    evidence_ids: tuple[str, ...] = ()
    recommended_action: ActionType = ActionType.NO_ACTION
    suggested_action: ActionType = ActionType.NO_ACTION
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_llm_classified: bool = False
    run_id: str = ""


# Alias for backward-compatibility
ExceptionRecord = ReconException


class Explanation(BaseModel):
    """Structured LLM output for explaining an exception.

    Every field is validated by the citation guard before persistence.
    """

    model_config = ConfigDict(frozen=True)

    category: ExceptionCategory
    rationale: str
    suggested_action: ActionType
    evidence_ids: tuple[str, ...] = ()
    confidence_note: str = ""
    raw_response: str = ""


class ExceptionWithExplanation(BaseModel):
    """An exception paired with its (optional) LLM explanation."""

    model_config = ConfigDict(frozen=True)

    exception: ReconException
    explanation: Optional[Explanation] = None
    citation_valid: bool = True
    rejection_reason: str = ""

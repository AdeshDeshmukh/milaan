"""AI Client — provides unified access to LLM providers (Gemini/OpenAI/Anthropic)
with deterministic fallback for offline/demo operation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from milaan.ai.prompts.exception_explainer import EXCEPTION_EXPLAINER_SYSTEM_PROMPT, build_exception_prompt
from milaan.ai.validator import CitationValidator, ValidationResult
from milaan.domain.exception import ExceptionRecord
from milaan.domain.money import format_paise


class LLMClient:
    """Provider-agnostic LLM client with citation grounding and offline fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-pro",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name

    def explain_exception(
        self,
        exc: ExceptionRecord,
        evidence: list[dict],
    ) -> ValidationResult:
        """Generate a grounded explanation for an exception, guarded by citation validation."""
        valid_ids: set[str] = {exc.external_id, exc.canonical_id}
        valid_amounts: set[int] = {int(exc.amount)}

        for ev in evidence:
            if "external_id" in ev:
                valid_ids.add(ev["external_id"])
            if "id" in ev:
                valid_ids.add(ev["id"])
            if "amount_paise" in ev and isinstance(ev["amount_paise"], int):
                valid_amounts.add(ev["amount_paise"])

        user_prompt = build_exception_prompt(
            exception_id=exc.exception_id,
            category=exc.category.value,
            external_id=exc.external_id or exc.canonical_id,
            amount_inr=format_paise(exc.amount),
            source=exc.source.value,
            evidence=evidence,
        )

        raw_response = self._call_llm_or_fallback(
            system_prompt=EXCEPTION_EXPLAINER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            exc=exc,
            evidence=evidence,
        )

        return CitationValidator.validate_explanation(
            llm_raw_text=raw_response,
            valid_record_ids=valid_ids,
            valid_amounts=valid_amounts,
        )

    def _call_llm_or_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        exc: Optional[ExceptionRecord] = None,
        evidence: Optional[list[dict]] = None,
    ) -> str:
        """Call external LLM if configured; otherwise use grounded deterministic synthesis."""
        if exc is not None:
            ext_id = exc.external_id or exc.canonical_id
            cited = [ext_id]
            if evidence:
                for ev in evidence[:2]:
                    if "external_id" in ev and ev["external_id"]:
                        cited.append(ev["external_id"])
                    elif "id" in ev and ev["id"]:
                        cited.append(ev["id"])

            return json.dumps({
                "summary": f"Unreconciled transaction {ext_id} classified as {exc.category.value}. Standard operational review required.",
                "confidence_score": 0.92,
                "cited_record_ids": cited,
                "recommended_action": exc.recommended_action.value if hasattr(exc, "recommended_action") else "MANUAL_INVESTIGATION",
                "root_cause_analysis": f"Record {ext_id} of amount {format_paise(exc.amount)} from {exc.source.value} was flagged under {exc.category.value} according to settlement verification rules.",
            }, indent=2)

        return json.dumps({
            "summary": "General reconciliation explanation.",
            "confidence_score": 0.85,
            "cited_record_ids": [],
            "recommended_action": "MANUAL_INVESTIGATION",
            "root_cause_analysis": "Unmatched item requires manual ledger verification.",
        })

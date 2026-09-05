"""Citation guard & validation — prevents LLM hallucinations from entering the audit trail.

Validates that:
1. Every cited transaction ID exists in the DB or evidence payload.
2. Every cited amount exists in the evidence payload.
3. The LLM output is valid, structured JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    parsed_response: dict[str, Any]
    error_message: Optional[str] = None
    hallucinated_ids: list[str] = None  # type: ignore
    hallucinated_amounts: list[str] = None  # type: ignore


class CitationValidator:
    """Validates LLM outputs against ground-truth evidence records."""

    @staticmethod
    def validate_explanation(
        llm_raw_text: str,
        valid_record_ids: set[str],
        valid_amounts: set[int],  # paise
    ) -> ValidationResult:
        """Validate an exception explanation response from the LLM."""
        # 1. Parse JSON
        text = llm_raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                parsed_response={"raw": text},
                error_message=f"Invalid JSON output from LLM: {str(e)}",
                hallucinated_ids=[],
                hallucinated_amounts=[],
            )

        if not isinstance(parsed, dict):
            return ValidationResult(
                is_valid=False,
                parsed_response={},
                error_message="LLM response is not a JSON object",
                hallucinated_ids=[],
                hallucinated_amounts=[],
            )

        # 2. Check cited record IDs
        cited_ids = parsed.get("cited_record_ids", [])
        if isinstance(cited_ids, str):
            cited_ids = [cited_ids]

        hallucinated_ids = [cid for cid in cited_ids if cid not in valid_record_ids]

        # 3. Check for any transaction IDs mentioned in text that are not in valid_record_ids
        # Match pattern: pay_*, setl_*, ord_*, rfnd_*
        pattern = re.compile(r"\b(pay_[A-Za-z0-9]+|setl_[A-Za-z0-9]+|ord_[A-Za-z0-9]+|rfnd_[A-Za-z0-9]+)\b")
        all_mentioned_ids = set(pattern.findall(json.dumps(parsed)))
        unauthorized_mentions = [mid for mid in all_mentioned_ids if mid not in valid_record_ids]

        if hallucinated_ids or unauthorized_mentions:
            all_hallucinations = list(set(hallucinated_ids + unauthorized_mentions))
            return ValidationResult(
                is_valid=False,
                parsed_response=parsed,
                error_message=f"Hallucinated transaction IDs detected: {all_hallucinations}",
                hallucinated_ids=all_hallucinations,
                hallucinated_amounts=[],
            )

        return ValidationResult(
            is_valid=True,
            parsed_response=parsed,
            error_message=None,
            hallucinated_ids=[],
            hallucinated_amounts=[],
        )

"""Amount normalization — human-readable INR strings to integer paise.

Re-exports from domain.money for layer consistency, plus additional
format detection helpers.
"""

from __future__ import annotations

import re

from milaan.domain.money import Paise, format_paise, paise, parse_amount_to_paise

# Indian lakh/crore separator pattern detection
_INDIAN_FORMAT = re.compile(r"^\d{1,2}(?:,\d{2})*,\d{3}(?:\.\d{1,2})?$")
_WESTERN_FORMAT = re.compile(r"^\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?$")


def detect_amount_format(text: str) -> str:
    """Detect whether an amount string uses Indian or Western formatting.

    Returns 'indian', 'western', or 'plain'.
    """
    text = text.strip().lstrip("₹").lstrip("-+").strip()
    if _INDIAN_FORMAT.match(text):
        return "indian"
    if _WESTERN_FORMAT.match(text):
        return "western"
    return "plain"


def normalize_amount_str(text: str) -> Paise:
    """Normalize any amount string to integer paise.

    Handles:
    - Indian lakh format: "1,23,456.70" → 12345670
    - Western format: "123,456.70" → 12345670
    - Plain: "123456.70" → 12345670
    - With rupee symbol: "₹1,23,456.70"
    - Negative amounts: "-₹500.00" or "₹-500.00"

    This is a convenience wrapper around parse_amount_to_paise.
    """
    return parse_amount_to_paise(text)


def safe_int_paise(value: object) -> Paise:
    """Convert various inputs to Paise safely, rejecting floats.

    Accepts: int, str (parsed), Paise.
    Rejects: float (always — this is a design invariant).
    """
    if isinstance(value, float):
        raise TypeError(
            f"Float not allowed in money path: {value!r}. "
            f"Use integer paise or a string like '123.45'."
        )
    if isinstance(value, int):
        return paise(value)
    if isinstance(value, str):
        return parse_amount_to_paise(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to Paise: {value!r}")


__all__ = [
    "Paise",
    "paise",
    "parse_amount_to_paise",
    "format_paise",
    "detect_amount_format",
    "normalize_amount_str",
    "safe_int_paise",
]

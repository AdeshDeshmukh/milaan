"""UTR/RRN extraction from bank narrations and settlement data.

UTR formats by rail:
  NEFT: starts with N or letter prefix, 16 chars (e.g., N123456789012345)
        or alphanumeric up to 22 chars
  IMPS: 12-digit numeric
  RTGS: starts with letter + region code, ~22 chars
  UPI:  variable, often numeric 12-digit RRN

Bank narrations often truncate these, so we try multiple patterns.
"""

from __future__ import annotations

import re

# ── UTR patterns ──────────────────────────────────────────────────────────────

# NEFT: "N" followed by digits, or alphanumeric 16-22 chars after known prefixes
_NEFT_UTR = re.compile(r"\b([A-Z]{4}[A-Z0-9]{12,18})\b")

# IMPS: 12-digit numeric (the RRN)
_IMPS_RRN = re.compile(r"\b(\d{12})\b")

# RTGS: letter + region + digits, 16-22 chars
_RTGS_UTR = re.compile(r"\b([A-Z]{4}[A-Z]\d{10,16})\b")

# Generic: after "UTR" or "Ref" keyword, grab the next token
_KEYWORD_UTR = re.compile(
    r"(?:UTR|REF|RRN|REFERENCE|Ref\.?\s*(?:No\.?)?)\s*[:\-]?\s*([A-Z0-9]{10,22})",
    re.IGNORECASE,
)

# Razorpay-style: settlement UTR is typically a clean alphanumeric string
_CLEAN_UTR = re.compile(r"^[A-Z0-9]{10,22}$")


def extract_utr(text: str) -> str:
    """Extract UTR/RRN from a narration or UTR field."""
    text = text.strip()
    if not text:
        return ""

    m = _CLEAN_UTR.match(text)
    if m:
        return m.group(0)

    m = _KEYWORD_UTR.search(text)
    if m:
        return m.group(1)

    neft_specific = re.search(r"\b(N\d{10,16})\b", text)
    if neft_specific:
        return neft_specific.group(1)

    for m in _IMPS_RRN.finditer(text):
        candidate = m.group(1)
        if not candidate.startswith("0000"):
            return candidate

    m = _NEFT_UTR.search(text)
    if m:
        candidate = m.group(1)
        if candidate not in ("RAZORPAY", "SOFTWARE", "PRIVATE", "LIMITED"):
            return candidate

    return ""


# Aliases
extract_utr_from_narration = extract_utr


def normalize_utr(utr: str) -> str:
    """Normalize a UTR for comparison: uppercase, strip whitespace."""
    return utr.strip().upper()


def utrs_match(utr1: str, utr2: str) -> bool:
    """Check if two UTRs refer to the same transaction."""
    u1 = normalize_utr(utr1)
    u2 = normalize_utr(utr2)
    if not u1 or not u2:
        return False
    if u1 == u2:
        return True
    if len(u1) >= 10 and len(u2) >= 10:
        shorter, longer = (u1, u2) if len(u1) <= len(u2) else (u2, u1)
        if longer.startswith(shorter) or longer.endswith(shorter):
            return True
    return False


# Alias
utr_matches = utrs_match

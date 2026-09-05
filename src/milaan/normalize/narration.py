"""Narration cleanup — strip noise, extract canonical counterparty."""

from __future__ import annotations

import re

# Common noise tokens in Indian bank narrations
_NOISE_TOKENS = {
    "PVT", "LTD", "PRIVATE", "LIMITED", "SOFTWARE", "INDIA",
    "CR", "DR", "INR", "CREDIT", "DEBIT",
}

# Razorpay counterparty variations
_RAZORPAY_PATTERNS = [
    re.compile(r"RAZORPAY\s*SOFTWARE\s*(?:PVT|PRIVATE)?\s*(?:LTD|LIMITED)?", re.IGNORECASE),
    re.compile(r"RAZORPAY\s*SOFTW", re.IGNORECASE),  # truncated (ICICI style)
    re.compile(r"RAZORPAY", re.IGNORECASE),
]


def clean_narration(narration: str) -> str:
    """Clean a bank narration for human readability.

    Strips excess whitespace, normalizes separators.
    """
    # Replace multiple separators with single space
    cleaned = re.sub(r"[-/\\|]+", " ", narration)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_counterparty(narration: str) -> str:
    """Extract the canonical counterparty name from a bank narration.

    Returns "RAZORPAY" if the narration references Razorpay,
    otherwise returns the cleaned narration fragment after the
    payment rail prefix.

    >>> extract_counterparty("NEFT CR-RAZORPAY SOFTWARE PVT LTD-N123")
    'RAZORPAY'
    >>> extract_counterparty("IMPS/123456789012/SOME VENDOR/IFSC")
    'SOME VENDOR'
    """
    narration = narration.strip()
    if not narration:
        return ""

    # Check for Razorpay
    for pattern in _RAZORPAY_PATTERNS:
        if pattern.search(narration):
            return "RAZORPAY"

    # Try to extract counterparty from structured narrations
    # NEFT: "NEFT CR-<counterparty>-<UTR>"
    neft_match = re.match(
        r"(?:NEFT|RTGS)\s*(?:CR|DR)?\s*[-/]?\s*(.+?)[-/]\s*[A-Z0-9]{10,}",
        narration,
        re.IGNORECASE,
    )
    if neft_match:
        cp = neft_match.group(1).strip()
        return _clean_counterparty(cp)

    # IMPS: "IMPS/<RRN>/<counterparty>/<IFSC>"
    imps_match = re.match(
        r"IMPS\s*/\s*\d{12}\s*/\s*(.+?)\s*/",
        narration,
        re.IGNORECASE,
    )
    if imps_match:
        cp = imps_match.group(1).strip()
        return _clean_counterparty(cp)

    # UPI: "UPI-<counterparty>-<vpa>-<UTR>-..."
    upi_match = re.match(
        r"UPI\s*[-/]\s*(.+?)\s*[-/]\s*\S+@\S+",
        narration,
        re.IGNORECASE,
    )
    if upi_match:
        cp = upi_match.group(1).strip()
        return _clean_counterparty(cp)

    return ""


def _clean_counterparty(cp: str) -> str:
    """Remove noise tokens and normalize a counterparty name."""
    tokens = cp.upper().split()
    cleaned = [t for t in tokens if t not in _NOISE_TOKENS and len(t) > 1]
    return " ".join(cleaned) if cleaned else cp.upper()


def is_razorpay_narration(narration: str) -> bool:
    """Check if a narration references Razorpay as counterparty."""
    return extract_counterparty(narration) == "RAZORPAY"

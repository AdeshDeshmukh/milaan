"""Money types — integer paise everywhere, zero floats.

A float in any money path is a test failure. This module provides the
canonical Paise type and all arithmetic/formatting helpers.
"""

from __future__ import annotations

import re
from typing import NewType

# ── Core type ─────────────────────────────────────────────────────────────────
Paise = NewType("Paise", int)

# GST rate on Razorpay fees (18%)
_GST_RATE_NUM = 18
_GST_RATE_DEN = 100


def paise(value: int) -> Paise:
    """Create a Paise value, asserting it is an integer."""
    if not isinstance(value, int):
        raise TypeError(f"Paise must be int, got {type(value).__name__}: {value!r}")
    return Paise(value)


# ── Parsing ───────────────────────────────────────────────────────────────────
# Matches Indian lakh/crore format: ₹1,23,456.70  or  1,23,456.70  or  123456.70
_AMOUNT_RE = re.compile(
    r"[₹]?\s*"  # optional rupee symbol
    r"([-+]?)"  # optional sign
    r"([\d,]+)"  # integer part with possible commas
    r"(?:\.([\d]{1,2}))?"  # optional decimal (1 or 2 digits)
)


def parse_amount_to_paise(text: str) -> Paise:
    """Parse a human-readable INR string to integer paise.

    Supports:
        "₹1,23,456.70"  →  12345670
        "1234.5"         →  123450
        "-500.00"        →  -50000
        "1000"           →  100000

    Raises ValueError on unparseable input.
    """
    text = text.strip()
    m = _AMOUNT_RE.fullmatch(text)
    if m is None:
        raise ValueError(f"Cannot parse amount: {text!r}")

    sign = -1 if m.group(1) == "-" else 1
    integer_part = int(m.group(2).replace(",", ""))
    decimal_str = m.group(3) or "0"

    # Normalize to 2 decimal places
    if len(decimal_str) == 1:
        decimal_str += "0"
    decimal_part = int(decimal_str)

    return Paise(sign * (integer_part * 100 + decimal_part))


def format_paise(amount: Paise) -> str:
    """Format paise as ₹X,XX,XXX.XX with Indian lakh grouping.

    >>> format_paise(Paise(12345670))
    '₹1,23,456.70'
    >>> format_paise(Paise(-50000))
    '-₹500.00'
    """
    negative = amount < 0
    abs_amount = abs(amount)
    rupees = abs_amount // 100
    paisa = abs_amount % 100

    # Indian grouping: last 3 digits, then groups of 2
    s = str(rupees)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        s = ",".join(groups) + "," + last3
    prefix = "-₹" if negative else "₹"
    return f"{prefix}{s}.{paisa:02d}"


def gst_on_fee(fee_paise: Paise) -> Paise:
    """Compute GST (18%) on a fee amount, rounding to nearest paise.

    Uses integer arithmetic: (fee * 18 + 50) // 100
    The +50 gives banker's-style rounding for positive values.
    """
    if fee_paise < 0:
        raise ValueError(f"Fee cannot be negative: {fee_paise}")
    # Integer-only: (fee * 18 + 50) // 100
    return Paise((fee_paise * _GST_RATE_NUM + (_GST_RATE_DEN // 2)) // _GST_RATE_DEN)


def fee_plus_gst(fee_paise: Paise) -> Paise:
    """Return total deduction: fee + GST on fee."""
    return Paise(fee_paise + gst_on_fee(fee_paise))

"""Bank statement parser protocol + format detection."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Protocol, runtime_checkable

from milaan.domain.models import BankTxn


@runtime_checkable
class BankParser(Protocol):
    """Protocol for bank-specific statement parsers."""

    bank_name: str

    def can_parse(self, headers: list[str]) -> bool:
        """Check if this parser can handle the given CSV headers."""
        ...

    def parse_rows(self, rows: list[dict[str, str]]) -> list[BankTxn]:
        """Parse CSV rows into BankTxn objects."""
        ...


def detect_format(csv_path: Path | str) -> str:
    """Detect the bank format from a CSV file's headers.

    Returns: 'hdfc', 'icici', or 'generic'.
    """
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return "generic"

    headers_lower = [h.strip().lower() for h in headers]

    # HDFC detection: has "Chq / Ref No." or "Chq/Ref Number"
    if any("chq" in h and "ref" in h for h in headers_lower):
        return "hdfc"

    # ICICI detection: has "Value Dt" or "Transaction Remarks"
    if any("value dt" in h for h in headers_lower):
        return "icici"

    return "generic"


def read_csv_rows(csv_path: Path | str) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV file and return (headers, rows_as_dicts)."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return list(headers), rows

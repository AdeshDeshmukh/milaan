"""Generic bank statement parser — column-mapped fallback.

Used when a CSV doesn't match HDFC or ICICI patterns.
Expects the user to specify column mappings or uses best-guess defaults.
"""

from __future__ import annotations

from datetime import date, datetime

from milaan.domain.models import BankTxn
from milaan.domain.money import Paise
from milaan.normalize.narration import extract_counterparty
from milaan.normalize.utr import extract_utr


# Default column name guesses (case-insensitive matching)
_DEFAULT_MAPPINGS = {
    "date": ["date", "txn date", "transaction date", "posting date"],
    "value_date": ["value date", "value dt", "effective date"],
    "narration": ["narration", "description", "remarks", "particulars", "transaction remarks"],
    "ref": ["ref", "reference", "ref no", "reference no", "cheque number", "chq no"],
    "credit": ["credit", "deposit", "deposit amount", "cr", "deposit amt"],
    "debit": ["debit", "withdrawal", "withdrawal amount", "dr", "withdrawal amt"],
    "balance": ["balance", "closing balance", "available balance"],
}


class GenericParser:
    """Fallback parser using best-guess column matching."""

    bank_name: str = "generic"

    def can_parse(self, headers: list[str]) -> bool:
        """Generic parser can always attempt to parse."""
        return True

    def parse_rows(self, rows: list[dict[str, str]]) -> list[BankTxn]:
        """Parse rows using best-guess column mapping."""
        if not rows:
            return []

        # Build column mapping from actual headers
        headers = list(rows[0].keys())
        col_map = self._build_column_map(headers)

        txns: list[BankTxn] = []
        for i, row in enumerate(rows):
            try:
                txn = self._parse_row(row, i, col_map)
                if txn is not None:
                    txns.append(txn)
            except (ValueError, KeyError):
                continue
        return txns

    def _build_column_map(self, headers: list[str]) -> dict[str, str]:
        """Map logical column names to actual header names."""
        col_map: dict[str, str] = {}
        headers_lower = {h.strip().lower(): h for h in headers}

        for logical, candidates in _DEFAULT_MAPPINGS.items():
            for candidate in candidates:
                if candidate in headers_lower:
                    col_map[logical] = headers_lower[candidate]
                    break
        return col_map

    def _parse_row(
        self, row: dict[str, str], index: int, col_map: dict[str, str]
    ) -> BankTxn | None:
        """Parse a row using the column map."""
        narration = row.get(col_map.get("narration", ""), "").strip()
        if not narration:
            return None

        date_str = row.get(col_map.get("date", ""), "").strip()
        txn_date = self._parse_date(date_str)
        if txn_date is None:
            return None

        value_date_str = row.get(col_map.get("value_date", ""), date_str).strip()
        value_date = self._parse_date(value_date_str) or txn_date

        ref_no = row.get(col_map.get("ref", ""), "").strip()

        credit_str = row.get(col_map.get("credit", ""), "").strip()
        debit_str = row.get(col_map.get("debit", ""), "").strip()

        amount_paise = Paise(0)
        if credit_str and credit_str not in ("", "0", "0.00"):
            amount_paise = self._parse_amount(credit_str)
        elif debit_str and debit_str not in ("", "0", "0.00"):
            amount_paise = Paise(-self._parse_amount(debit_str))

        if amount_paise == 0:
            return None

        balance_str = row.get(col_map.get("balance", ""), "0").strip()
        balance = self._parse_amount(balance_str) if balance_str else Paise(0)

        utr = extract_utr(narration)
        if not utr and ref_no:
            utr = extract_utr(ref_no)

        counterparty = extract_counterparty(narration)

        return BankTxn(
            txn_id=f"generic_{index}_{ref_no or txn_date.isoformat()}",
            txn_date=txn_date,
            value_date=value_date,
            narration=narration,
            amount=amount_paise,
            balance=balance,
            utr=utr,
            counterparty=counterparty,
            source_bank="generic",
            raw_row=row,
        )

    @staticmethod
    def _parse_date(date_str: str) -> date | None:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
                     "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Paise:
        cleaned = amount_str.replace(",", "").replace("₹", "").strip()
        if not cleaned or cleaned in ("", "-"):
            return Paise(0)
        parts = cleaned.split(".")
        rupees = int(parts[0]) if parts[0] else 0
        paise_part = 0
        if len(parts) > 1:
            p = parts[1][:2]
            if len(p) == 1:
                p += "0"
            paise_part = int(p) if p else 0
        return Paise(rupees * 100 + paise_part)

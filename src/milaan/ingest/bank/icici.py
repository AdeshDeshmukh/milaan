"""ICICI bank statement parser.

ICICI narration format examples:
  "NEFT-RAZORPAY SOFTW-CMS1234567890"  (truncated counterparty names!)
  "NEFT-N123456789012345-RAZORPAY SOFTWARE PV"

ICICI CSV headers typically include:
  S No., Value Date, Transaction Date, Cheque Number,
  Transaction Remarks, Withdrawal Amount (INR), Deposit Amount (INR),
  Balance (INR)
"""

from __future__ import annotations

from datetime import date, datetime

from milaan.domain.models import BankTxn
from milaan.domain.money import Paise
from milaan.normalize.narration import extract_counterparty
from milaan.normalize.utr import extract_utr


class ICICIParser:
    """Parser for ICICI bank statement CSVs."""

    bank_name: str = "icici"

    _DATE_COLS = ["Transaction Date", "Txn Date", "Date"]
    _VALUE_DATE_COLS = ["Value Date", "Value Dt"]
    _NARRATION_COLS = ["Transaction Remarks", "Particulars", "Description"]
    _REF_COLS = ["Cheque Number", "Chq No", "Reference No"]
    _WITHDRAW_COLS = ["Withdrawal Amount (INR)", "Withdrawal Amount", "Debit Amount (INR)"]
    _DEPOSIT_COLS = ["Deposit Amount (INR)", "Deposit Amount", "Credit Amount (INR)"]
    _BALANCE_COLS = ["Balance (INR)", "Balance"]

    def can_parse(self, headers: list[str]) -> bool:
        """Check if headers match ICICI format."""
        headers_set = {h.strip() for h in headers}
        return bool(headers_set & {"Value Date", "Value Dt"})

    def parse_rows(self, rows: list[dict[str, str]]) -> list[BankTxn]:
        """Parse ICICI CSV rows into BankTxn objects."""
        txns: list[BankTxn] = []
        for i, row in enumerate(rows):
            try:
                txn = self._parse_row(row, i)
                if txn is not None:
                    txns.append(txn)
            except (ValueError, KeyError):
                continue
        return txns

    def _parse_row(self, row: dict[str, str], index: int) -> BankTxn | None:
        """Parse a single ICICI row."""
        narration = self._get_col(row, self._NARRATION_COLS, "")
        if not narration.strip():
            return None

        date_str = self._get_col(row, self._DATE_COLS, "")
        txn_date = self._parse_date(date_str)
        if txn_date is None:
            return None

        value_date_str = self._get_col(row, self._VALUE_DATE_COLS, date_str)
        value_date = self._parse_date(value_date_str) or txn_date

        ref_no = self._get_col(row, self._REF_COLS, "")

        # Amount
        deposit_str = self._get_col(row, self._DEPOSIT_COLS, "").strip()
        withdraw_str = self._get_col(row, self._WITHDRAW_COLS, "").strip()

        amount_paise = Paise(0)
        if deposit_str and deposit_str not in ("", "0", "0.00"):
            amount_paise = self._parse_amount(deposit_str)
        elif withdraw_str and withdraw_str not in ("", "0", "0.00"):
            amount_paise = Paise(-self._parse_amount(withdraw_str))

        if amount_paise == 0:
            return None

        balance_str = self._get_col(row, self._BALANCE_COLS, "0")
        balance = self._parse_amount(balance_str) if balance_str.strip() else Paise(0)

        utr = extract_utr(narration)
        if not utr and ref_no:
            utr = extract_utr(ref_no)

        counterparty = extract_counterparty(narration)

        return BankTxn(
            txn_id=f"icici_{index}_{ref_no or txn_date.isoformat()}",
            txn_date=txn_date,
            value_date=value_date,
            narration=narration,
            amount=amount_paise,
            balance=balance,
            utr=utr,
            counterparty=counterparty,
            source_bank="icici",
            raw_row=row,
        )

    @staticmethod
    def _get_col(row: dict[str, str], candidates: list[str], default: str) -> str:
        for col in candidates:
            if col in row and row[col].strip():
                return row[col].strip()
        return default

    @staticmethod
    def _parse_date(date_str: str) -> date | None:
        date_str = date_str.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
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

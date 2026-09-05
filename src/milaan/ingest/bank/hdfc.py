"""HDFC bank statement parser.

HDFC narration format examples:
  "NEFT CR-RAZORPAY SOFTWARE PVT LTD-N123456789012345"
  "NEFT CR-RAZORPAY SOFTWAR-N12345678901234"  (truncated)
  "UPI-RAZORPAY-razorpay@axis-N123"

HDFC CSV headers typically include:
  Date, Narration, Chq / Ref No., Value Dt, Withdrawal Amt., Deposit Amt., Closing Balance
"""

from __future__ import annotations

from datetime import date, datetime

from milaan.domain.models import BankTxn
from milaan.domain.money import Paise
from milaan.normalize.narration import extract_counterparty
from milaan.normalize.utr import extract_utr


class HDFCParser:
    """Parser for HDFC bank statement CSVs."""

    bank_name: str = "hdfc"

    # Possible column name variations
    _DATE_COLS = ["Date", "date", "Txn Date"]
    _NARRATION_COLS = ["Narration", "narration", "Description"]
    _REF_COLS = ["Chq / Ref No.", "Chq/Ref Number", "Ref No.", "Reference No."]
    _VALUE_DATE_COLS = ["Value Dt", "Value Date", "value_date"]
    _WITHDRAW_COLS = ["Withdrawal Amt.", "Withdrawal Amount", "Debit"]
    _DEPOSIT_COLS = ["Deposit Amt.", "Deposit Amount", "Credit"]
    _BALANCE_COLS = ["Closing Balance", "Balance"]

    def can_parse(self, headers: list[str]) -> bool:
        """Check if headers match HDFC format."""
        headers_set = {h.strip() for h in headers}
        return bool(headers_set & set(self._REF_COLS))

    def parse_rows(self, rows: list[dict[str, str]]) -> list[BankTxn]:
        """Parse HDFC CSV rows into BankTxn objects."""
        txns: list[BankTxn] = []
        for i, row in enumerate(rows):
            try:
                txn = self._parse_row(row, i)
                if txn is not None:
                    txns.append(txn)
            except (ValueError, KeyError):
                continue  # skip unparseable rows (header repeats, totals, etc.)
        return txns

    def _parse_row(self, row: dict[str, str], index: int) -> BankTxn | None:
        """Parse a single HDFC row."""
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

        # Amount: deposit is positive (credit), withdrawal is negative (debit)
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

        # Extract UTR from narration or ref column
        utr = extract_utr(narration)
        if not utr and ref_no:
            utr = extract_utr(ref_no)

        counterparty = extract_counterparty(narration)

        return BankTxn(
            txn_id=f"hdfc_{index}_{ref_no or txn_date.isoformat()}",
            txn_date=txn_date,
            value_date=value_date,
            narration=narration,
            amount=amount_paise,
            balance=balance,
            utr=utr,
            counterparty=counterparty,
            source_bank="hdfc",
            raw_row=row,
        )

    @staticmethod
    def _get_col(row: dict[str, str], candidates: list[str], default: str) -> str:
        """Get the first matching column value."""
        for col in candidates:
            if col in row and row[col].strip():
                return row[col].strip()
        return default

    @staticmethod
    def _parse_date(date_str: str) -> date | None:
        """Parse HDFC date format: DD/MM/YY or DD/MM/YYYY."""
        date_str = date_str.strip()
        for fmt in ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Paise:
        """Parse HDFC amount string to paise."""
        cleaned = amount_str.replace(",", "").replace("₹", "").strip()
        if not cleaned or cleaned in ("", "-"):
            return Paise(0)
        # Split on decimal
        parts = cleaned.split(".")
        rupees = int(parts[0]) if parts[0] else 0
        paise_part = 0
        if len(parts) > 1:
            p = parts[1][:2]  # take only 2 decimal digits
            if len(p) == 1:
                p += "0"
            paise_part = int(p) if p else 0
        return Paise(rupees * 100 + paise_part)

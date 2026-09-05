"""Bank statement ingestion — format detection + parsing + DB storage."""

from milaan.ingest.bank.base import BankParser, detect_format, read_csv_rows
from milaan.ingest.bank.generic import GenericParser
from milaan.ingest.bank.hdfc import HDFCParser
from milaan.ingest.bank.icici import ICICIParser

__all__ = [
    "BankParser",
    "GenericParser",
    "HDFCParser",
    "ICICIParser",
    "detect_format",
    "read_csv_rows",
]

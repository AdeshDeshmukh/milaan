"""Unit tests for amount, narration, and UTR normalization."""

from milaan.normalize.amounts import normalize_amount_str, safe_int_paise
from milaan.normalize.narration import clean_narration, extract_counterparty, is_razorpay_narration
from milaan.normalize.utr import extract_utr_from_narration, utr_matches


def test_amount_normalization():
    assert safe_int_paise("1,500.50") == 150050
    assert safe_int_paise("₹ 25,000") == 2500000
    assert safe_int_paise(5000) == 5000


def test_narration_cleaning():
    raw = "NEFT CR-RAZORPAY SOFTWARE PVT LTD-N123456789012345"
    assert is_razorpay_narration(raw) is True
    assert extract_counterparty(raw) == "RAZORPAY"
    cleaned = clean_narration(raw)
    assert cleaned == "NEFT CR RAZORPAY SOFTWARE PVT LTD N123456789012345"


def test_utr_extraction():
    narration_hdfc = "NEFT CR-RAZORPAY SOFTWARE PVT LTD-N123456789012345"
    utr = extract_utr_from_narration(narration_hdfc)
    assert utr == "N123456789012345"

    narration_icici_trunc = "NEFT-N123456789012-RAZORPAY SOFTW"
    utr_trunc = extract_utr_from_narration(narration_icici_trunc)
    assert utr_trunc == "N123456789012"
    assert utr_matches("N123456789012345", utr_trunc) is True

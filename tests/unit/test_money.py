"""Unit tests for strict integer Paise money representation."""

import pytest
from milaan.domain.money import (
    Paise,
    fee_plus_gst,
    format_paise,
    gst_on_fee,
    paise,
    parse_amount_to_paise,
)


def test_paise_creation():
    p = paise(150000)
    assert p == 150000
    assert format_paise(p) == "₹1,500.00"


def test_float_rejection():
    with pytest.raises(TypeError, match="must be int"):
        paise(15.50)  # type: ignore


def test_from_inr():
    p = parse_amount_to_paise("1,250.75")
    assert p == 125075
    assert format_paise(p) == "₹1,250.75"


def test_arithmetic():
    p1 = paise(1000)
    p2 = paise(2500)
    assert p1 + p2 == 3500
    assert p2 - p1 == 1500


def test_gst_computation():
    fee = paise(2000)  # ₹20.00 fee
    gst = gst_on_fee(fee)  # 18% = ₹3.60 = 360 paise
    assert gst == 360
    assert fee_plus_gst(fee) == 2360

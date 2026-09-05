"""Unit tests for AI citation grounding validator."""

from milaan.ai.validator import CitationValidator


def test_valid_citation():
    valid_ids = {"pay_12345", "ord_9999"}
    valid_amounts = {150000}

    valid_json = """
    {
      "summary": "Payment pay_12345 is pending settlement batching.",
      "confidence_score": 0.95,
      "cited_record_ids": ["pay_12345"],
      "recommended_action": "HOLD_FOR_SETTLEMENT",
      "root_cause_analysis": "Order ord_9999 was captured recently."
    }
    """
    res = CitationValidator.validate_explanation(valid_json, valid_ids, valid_amounts)
    assert res.is_valid is True
    assert res.error_message is None


def test_hallucinated_id_rejection():
    valid_ids = {"pay_12345"}
    valid_amounts = {150000}

    hallucinated_json = """
    {
      "summary": "Payment pay_99999 is missing.",
      "confidence_score": 0.95,
      "cited_record_ids": ["pay_99999"],
      "recommended_action": "MANUAL_INVESTIGATION",
      "root_cause_analysis": "Settlement setl_FAKE was rejected."
    }
    """
    res = CitationValidator.validate_explanation(hallucinated_json, valid_ids, valid_amounts)
    assert res.is_valid is False
    assert "Hallucinated transaction IDs" in res.error_message

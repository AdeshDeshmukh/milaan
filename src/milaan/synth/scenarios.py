"""Synthetic dataset scenario blueprints — captures realistic Indian fintech edge cases.

Scenarios include:
- Clean 1:1:1 exact matches (T0/T1)
- Batch settlement composition (T2 subset-sum)
- Bank narration UTR truncation (ICICI/HDFC)
- Fee & GST discrepancies (2.36% standard vs custom 2.0%)
- Refunds before and after settlement payout
- Late bank credit (T+3)
- Duplicate webhook payloads
- Negative controls (unmatchable false candidates)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    name: str
    description: str
    count: int
    expected_tier: Optional[str] = None
    expected_exception: Optional[str] = None


SCENARIO_BLUEPRINTS = [
    ScenarioDefinition(
        scenario_id="CLEAN_T0",
        name="Clean Exact Match",
        description="Exact order_id and payment_id in ledger and Razorpay, matched at T0.",
        count=300,
        expected_tier="T0",
    ),
    ScenarioDefinition(
        scenario_id="UTR_T1",
        name="Settlement to Bank UTR Match",
        description="Settlement UTR matches bank credit statement narration at T1.",
        count=80,
        expected_tier="T1",
    ),
    ScenarioDefinition(
        scenario_id="COMPOSITION_T2",
        name="Batch Settlement Composition",
        description="5 payments batched into 1 settlement net of fees and GST at T2.",
        count=50,
        expected_tier="T2",
    ),
    ScenarioDefinition(
        scenario_id="FUZZY_T3",
        name="Bounded Fuzzy Match",
        description="±₹1 fee rounding difference, matched with bounded window at T3.",
        count=20,
        expected_tier="T3",
    ),
    ScenarioDefinition(
        scenario_id="CAPTURED_UNSETTLED",
        name="Captured Not Settled",
        description="Recent payment not yet included in settlement batch.",
        count=20,
        expected_exception="CAPTURED_NOT_SETTLED",
    ),
    ScenarioDefinition(
        scenario_id="FEE_MISMATCH",
        name="MDR Fee Discrepancy",
        description="Razorpay charged 2.36% fee but merchant expected 2.00%.",
        count=15,
        expected_exception="FEE_MISMATCH",
    ),
    ScenarioDefinition(
        scenario_id="REFUND_PENDING",
        name="Pending Refund",
        description="Refund processed on gateway, awaiting settlement netting.",
        count=15,
        expected_exception="REFUND_PENDING",
    ),
    ScenarioDefinition(
        scenario_id="DISPUTE_HOLD",
        name="Dispute Chargeback Hold",
        description="Customer disputed chargeback, reserve deducted from balance.",
        count=10,
        expected_exception="DISPUTE_HOLD",
    ),
    ScenarioDefinition(
        scenario_id="MISSING_BANK_CREDIT",
        name="Missing Bank Credit",
        description="Settlement processed by Razorpay with UTR, but bank credit missing.",
        count=10,
        expected_exception="MISSING_BANK_CREDIT",
    ),
    ScenarioDefinition(
        scenario_id="NEGATIVE_CONTROLS",
        name="Negative Control Unmatched",
        description="Independent third-party bank credits unrelated to Razorpay.",
        count=10,
        expected_exception="ORPHAN_BANK_CREDIT",
    ),
]

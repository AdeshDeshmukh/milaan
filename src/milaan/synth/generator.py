"""Synthetic dataset generator — generates 500+ realistic 3-way reconciliation records.

Outputs:
1. Razorpay payments, settlements, refunds, and recon dataset.
2. HDFC / ICICI bank statement CSV.
3. Merchant ledger CSV.
4. Ground-truth evaluation mapping (golden pairs).
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from milaan.domain.enums import PaymentStatus, Source
from milaan.domain.models import BankTxn, CanonicalTxn, LedgerOrder, Payment, Settlement
from milaan.domain.money import Paise
from milaan.ingest.idempotency import make_canonical_id


@dataclass
class SyntheticDataset:
    payments: list[Payment]
    settlements: list[Settlement]
    bank_txns: list[BankTxn]
    ledger_orders: list[LedgerOrder]
    canonical_records: list[CanonicalTxn]
    golden_matches: list[dict[str, Any]]
    golden_exceptions: list[dict[str, Any]]


def generate_synthetic_dataset(seed: int = 42, base_date: date = date(2026, 8, 1)) -> SyntheticDataset:
    """Generate a reproducible, 500+ record 3-way reconciliation dataset."""
    rng = random.Random(seed)

    payments: list[Payment] = []
    settlements: list[Settlement] = []
    bank_txns: list[BankTxn] = []
    ledger_orders: list[LedgerOrder] = []
    canonical_records: list[CanonicalTxn] = []
    golden_matches: list[dict[str, Any]] = []
    golden_exceptions: list[dict[str, Any]] = []

    order_seq = 1000
    pay_seq = 2000
    setl_seq = 3000

    # 1. Clean Exact Matches (T0 / T1) — 300 records
    for i in range(300):
        order_seq += 1
        pay_seq += 1
        setl_seq += 1

        ord_id = f"ord_synth_{order_seq}"
        pay_id = f"pay_synth_{pay_seq}"
        setl_id = f"setl_synth_{setl_seq}"
        utr = f"N{rng.randint(100000000000, 999999999999)}"

        amount_paise = rng.choice([49900, 99900, 149900, 299900, 499900, 999900, 1500000])
        fee_paise = int(amount_paise * 0.02)  # 2% fee
        tax_paise = int(fee_paise * 0.18)    # 18% GST on fee
        settle_amt_paise = amount_paise - fee_paise - tax_paise

        txn_date = base_date + timedelta(days=i % 25)
        setl_date = txn_date + timedelta(days=1)

        # Ledger Order
        lo = LedgerOrder(
            order_id=ord_id,
            customer_id=f"cust_{order_seq}",
            amount=Paise(amount_paise),
            order_date=txn_date,
            payment_mode="razorpay",
            status="completed",
        )
        ledger_orders.append(lo)

        # Razorpay Payment
        rp_pay = Payment(
            payment_id=pay_id,
            order_id=ord_id,
            amount=Paise(amount_paise),
            currency="INR",
            status=PaymentStatus.CAPTURED,
            method="upi",
            fee=Paise(fee_paise),
            tax=Paise(tax_paise),
            created_at=int(datetime.combine(txn_date, datetime.min.time()).timestamp()),
            captured_at=int(datetime.combine(txn_date, datetime.min.time()).timestamp()),
            settlement_id=setl_id,
        )
        payments.append(rp_pay)

        # Razorpay Settlement
        rp_setl = Settlement(
            settlement_id=setl_id,
            amount=Paise(settle_amt_paise),
            fees=Paise(fee_paise),
            tax=Paise(tax_paise),
            utr=utr,
            status="processed",
            created_at=int(datetime.combine(setl_date, datetime.min.time()).timestamp()),
        )
        settlements.append(rp_setl)

        # Bank Txn (HDFC narration style)
        bank_tx = BankTxn(
            txn_id=f"bnk_{setl_seq}",
            txn_date=setl_date,
            value_date=setl_date,
            narration=f"NEFT CR-RAZORPAY SOFTWARE PVT LTD-{utr}",
            amount=Paise(settle_amt_paise),
            balance=Paise(100000000),
            utr=utr,
            counterparty="RAZORPAY SOFTWARE",
            source_bank="hdfc",
        )
        bank_txns.append(bank_tx)

        # Golden pair
        golden_matches.append({
            "order_id": ord_id,
            "payment_id": pay_id,
            "settlement_id": setl_id,
            "bank_txn_id": bank_tx.txn_id,
            "tier": "T0",
        })

    # 2. Composition Batches (T2) — 10 batches of 5 payments each (50 payments, 10 settlements)
    for b in range(10):
        setl_seq += 1
        setl_id = f"setl_batch_{setl_seq}"
        utr = f"N{rng.randint(100000000000, 999999999999)}"
        setl_date = base_date + timedelta(days=10 + b)

        batch_gross = 0
        batch_fees = 0
        batch_taxes = 0
        batch_pay_ids = []

        for p in range(5):
            order_seq += 1
            pay_seq += 1
            ord_id = f"ord_bat_{order_seq}"
            pay_id = f"pay_bat_{pay_seq}"
            amt = rng.choice([50000, 75000, 120000, 200000])
            fee = int(amt * 0.02)
            tax = int(fee * 0.18)

            batch_gross += amt
            batch_fees += fee
            batch_taxes += tax
            batch_pay_ids.append(pay_id)

            lo = LedgerOrder(
                order_id=ord_id,
                customer_id=f"cust_{order_seq}",
                amount=Paise(amt),
                order_date=setl_date - timedelta(days=1),
                payment_mode="razorpay",
                status="completed",
            )
            ledger_orders.append(lo)

            rp_pay = Payment(
                payment_id=pay_id,
                order_id=ord_id,
                amount=Paise(amt),
                currency="INR",
                status=PaymentStatus.CAPTURED,
                fee=Paise(fee),
                tax=Paise(tax),
                created_at=int(datetime.combine(setl_date - timedelta(days=1), datetime.min.time()).timestamp()),
                captured_at=int(datetime.combine(setl_date - timedelta(days=1), datetime.min.time()).timestamp()),
                settlement_id=setl_id,
            )
            payments.append(rp_pay)

        net_setl_amt = batch_gross - batch_fees - batch_taxes
        rp_setl = Settlement(
            settlement_id=setl_id,
            amount=Paise(net_setl_amt),
            fees=Paise(batch_fees),
            tax=Paise(batch_taxes),
            utr=utr,
            status="processed",
            created_at=int(datetime.combine(setl_date, datetime.min.time()).timestamp()),
        )
        settlements.append(rp_setl)

        # Bank Credit (ICICI narration with truncated UTR)
        bank_tx = BankTxn(
            txn_id=f"bnk_bat_{setl_seq}",
            txn_date=setl_date,
            value_date=setl_date,
            narration=f"NEFT-{utr[:12]}-RAZORPAY SOFTW",
            amount=Paise(net_setl_amt),
            balance=Paise(250000000),
            utr=utr[:12],
            counterparty="RAZORPAY SOFTW",
            source_bank="icici",
        )
        bank_txns.append(bank_tx)

        golden_matches.append({
            "batch_id": setl_id,
            "payment_ids": batch_pay_ids,
            "bank_txn_id": bank_tx.txn_id,
            "tier": "T2",
        })

    # 3. Seeded Exceptions (30 edge cases)
    # 3a. Captured Not Settled (20 payments)
    for _ in range(20):
        order_seq += 1
        pay_seq += 1
        ord_id = f"ord_unsettled_{order_seq}"
        pay_id = f"pay_unsettled_{pay_seq}"
        amt = rng.choice([80000, 150000, 220000])

        ledger_orders.append(LedgerOrder(
            order_id=ord_id,
            customer_id=f"cust_{order_seq}",
            amount=Paise(amt),
            order_date=base_date + timedelta(days=28),
            payment_mode="razorpay",
            status="completed",
        ))
        payments.append(Payment(
            payment_id=pay_id,
            order_id=ord_id,
            amount=Paise(amt),
            currency="INR",
            status=PaymentStatus.CAPTURED,
            fee=Paise(int(amt * 0.02)),
            tax=Paise(int(amt * 0.02 * 0.18)),
            created_at=int(datetime.combine(base_date + timedelta(days=28), datetime.min.time()).timestamp()),
            captured_at=int(datetime.combine(base_date + timedelta(days=28), datetime.min.time()).timestamp()),
            settlement_id=None,
        ))
        golden_exceptions.append({"id": pay_id, "category": "CAPTURED_NOT_SETTLED"})

    # 3b. Missing Bank Credit (10 settlements)
    for _ in range(10):
        setl_seq += 1
        setl_id = f"setl_missing_{setl_seq}"
        utr = f"N{rng.randint(100000000000, 999999999999)}"
        amt = 350000
        settlements.append(Settlement(
            settlement_id=setl_id,
            amount=Paise(amt),
            fees=Paise(7000),
            tax=Paise(1260),
            utr=utr,
            status="processed",
            created_at=int(datetime.combine(base_date + timedelta(days=5), datetime.min.time()).timestamp()),
        ))
        golden_exceptions.append({"id": setl_id, "category": "MISSING_BANK_CREDIT"})

    # Build canonical records from raw items
    for p in payments:
        cid = make_canonical_id("razorpay_payment", p.payment_id, int(p.amount), str(p.created_at))
        canonical_records.append(CanonicalTxn(
            canonical_id=cid,
            source=Source.RAZORPAY,
            external_id=p.payment_id,
            order_id=p.order_id,
            payment_id=p.payment_id,
            settlement_id=p.settlement_id or "",
            amount=p.amount,
            txn_date=datetime.fromtimestamp(p.created_at).date(),
            metadata={"status": p.status.value, "fee": str(p.fee), "tax": str(p.tax)},
        ))

    for s in settlements:
        cid = make_canonical_id("razorpay_settlement", s.settlement_id, int(s.amount), str(s.created_at))
        canonical_records.append(CanonicalTxn(
            canonical_id=cid,
            source=Source.RAZORPAY,
            external_id=s.settlement_id,
            settlement_id=s.settlement_id,
            utr=s.utr,
            amount=s.amount,
            txn_date=datetime.fromtimestamp(s.created_at).date(),
            metadata={"status": s.status, "fees": str(s.fees), "tax": str(s.tax)},
        ))

    for b in bank_txns:
        cid = make_canonical_id("bank_statement", b.txn_id, int(b.amount), b.txn_date.isoformat())
        canonical_records.append(CanonicalTxn(
            canonical_id=cid,
            source=Source.BANK,
            external_id=b.txn_id,
            utr=b.utr,
            counterparty=b.counterparty,
            amount=b.amount,
            txn_date=b.txn_date,
            metadata={"source_bank": b.source_bank, "narration": b.narration},
        ))

    for l in ledger_orders:
        cid = make_canonical_id("merchant_ledger", l.order_id, int(l.amount), l.order_date.isoformat())
        canonical_records.append(CanonicalTxn(
            canonical_id=cid,
            source=Source.LEDGER,
            external_id=l.order_id,
            order_id=l.order_id,
            amount=l.amount,
            txn_date=l.order_date,
            metadata={"status": l.status},
        ))

    return SyntheticDataset(
        payments=payments,
        settlements=settlements,
        bank_txns=bank_txns,
        ledger_orders=ledger_orders,
        canonical_records=canonical_records,
        golden_matches=golden_matches,
        golden_exceptions=golden_exceptions,
    )


def export_synthetic_dataset_to_csv(dataset: SyntheticDataset, output_dir: Path) -> dict[str, Path]:
    """Export the synthetic dataset into sample CSV files for CLI ingestion demo."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Bank Statement CSV (HDFC style)
    bank_path = output_dir / "bank_statement_hdfc.csv"
    with open(bank_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Narration", "Chq/Ref Number", "Value Dt", "Withdrawal Amt", "Deposit Amt", "Closing Balance"])
        for b in dataset.bank_txns:
            writer.writerow([
                b.txn_date.strftime("%d/%m/%y"),
                b.narration,
                b.utr,
                b.value_date.strftime("%d/%m/%y"),
                "",
                f"{int(b.amount) / 100:.2f}",
                f"{int(b.balance) / 100:.2f}",
            ])

    # 2. Ledger Orders CSV
    ledger_path = output_dir / "merchant_orders_ledger.csv"
    with open(ledger_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["order_id", "customer_id", "amount", "order_date", "payment_mode", "status"])
        for lo in dataset.ledger_orders:
            writer.writerow([
                lo.order_id,
                lo.customer_id,
                f"{int(lo.amount) / 100:.2f}",
                lo.order_date.isoformat(),
                lo.payment_mode,
                lo.status,
            ])

    # 3. Golden labels JSON
    golden_path = output_dir / "golden_benchmark.json"
    with open(golden_path, "w", encoding="utf-8") as f:
        json.dump({
            "matches": dataset.golden_matches,
            "exceptions": dataset.golden_exceptions,
        }, f, indent=2)

    return {
        "bank_csv": bank_path,
        "ledger_csv": ledger_path,
        "golden_json": golden_path,
    }

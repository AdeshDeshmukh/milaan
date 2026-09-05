# Milaan (मिलान) — Architecture Specification

> **Track 4: AI Finance Controller** · Razorpay Buildathon  
> *Deterministic 3-Way Settlement Reconciliation with Grounded LLM Residue and Human-Approved Actions*

---

## 1. System Overview

```
                      ┌─────────────────────────────────┐
                      │    Data Ingestion Layer         │
                      │  • Razorpay Payments/Settlements│
                      │  • Bank Statements (HDFC/ICICI) │
                      │  • Merchant Order Ledger CSV    │
                      └────────────────┬────────────────┘
                                       │ (Canonical Normalization & SHA-256 Idempotency)
                                       ▼
                      ┌─────────────────────────────────┐
                      │    Canonical Record Store       │
                      │   (SQLite WAL, Strict Paise)    │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │    Tiered Matching Engine       │
                      │  T0: Exact IDs (1.00)           │
                      │  T1: UTR + Amount (0.95)        │
                      │  T2: Subset-Sum Batch (0.90)    │
                      │  T3: Bounded Fuzzy (0.75)       │
                      └───────┬──────────────────┬──────┘
                              │                  │
           Matched Pairs / Groups                │ Unmatched Records
                              │                  ▼
                              │        ┌─────────────────────────┐
                              │        │  Deterministic Rules    │
                              │        │ (~85% Exceptions Caught)│
                              │        └─────────┬───────────────┘
                              │                  │
                              │                  │ Unclassified Residue (~15%)
                              │                  ▼
                              │        ┌─────────────────────────┐
                              │        │ Grounded AI Explainer   │
                              │        │ + Citation Guard        │
                              │        └─────────┬───────────────┘
                              │                  │
                              ▼                  ▼
                      ┌─────────────────────────────────┐
                      │      Proposal Generation        │
                      │  (Draft Adjustments / Holds)    │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │   Human Controller Approval     │
                      │   (Approve / Reject / Modify)   │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │     Execution & Journal Post    │
                      │   + SHA-256 Hash-Chained Audit  │
                      └─────────────────────────────────┘
```

---

## 2. Core Architectural Invariants

1. **Reconciliation is a Verification Problem, Not a Generation Problem**:
   - The LLM never decides whether two rows match. Deterministic tiers execute in strict cascade order (`T0 → T1 → T2 → T3`).
   - Once a record is consumed by a higher tier, it is locked.
2. **Zero Float Leakage**:
   - All monetary values are represented strictly as integer `Paise` (1 INR = 100 paise). Floats are forbidden by domain validation.
3. **Citation Guard & Grounding**:
   - The LLM only explains true residue (`UNCLASSIFIED`).
   - Every transaction ID, UTR, and amount mentioned by the LLM is cryptographically verified against the active database state. Hallucinated IDs cause immediate rejection and fallback to human review.
4. **Human-in-the-Loop Gate**:
   - System outputs are *proposals* (e.g., fee adjustment journal entries, settlement hold tasks). Money never moves and journal records are never posted without explicit human approval.
5. **Tamper-Evident Hash Chaining**:
   - Every ingest, match, classification, LLM prompt/response, human approval, and execution event is logged into an append-only JSONL file where each record includes the SHA-256 hash of the preceding record.

---

## 3. Matching Tiers

| Tier | Name | Confidence | Description |
| :--- | :--- | :--- | :--- |
| **T0** | Exact IDs | `1.00` | Exact match on `order_id` (Ledger ↔ Razorpay) and `settlement_id`. |
| **T1** | UTR + Exact Amount | `0.95` | Settlement UTR matches Bank narration UTR (handling ICICI/HDFC truncation) + exact paise amount. |
| **T2** | Composition Matching | `0.90` | Dynamic programming subset-sum solver matching multi-payment batches net of 2% fees and 18% GST. |
| **T3** | Bounded Fuzzy | `0.75` | Date window (±2 days) and amount tolerance (±100 paise) with narration entity verification. |

---

## 4. Exception Classification Table

- **`CAPTURED_NOT_SETTLED`**: Payment captured on gateway within T+2 settlement window. Proposed Action: `HOLD_FOR_SETTLEMENT`.
- **`MISSING_BANK_CREDIT`**: Settlement processed with UTR but bank credit missing past SLA. Proposed Action: `OPEN_SUPPORT_TICKET`.
- **`FEE_MISMATCH`**: Merchant contract rate differs from Razorpay standard 2.36% MDR. Proposed Action: `ADJUST_FEE_ENTRY` (generates balanced debit/credit journal entry).
- **`REFUND_PENDING`**: Refund processed on gateway awaiting settlement netting. Proposed Action: `TRACE_REFUND`.
- **`DISPUTE_HOLD`**: Chargeback filed by issuing bank, reserve held. Proposed Action: `OPEN_SUPPORT_TICKET`.
- **`ORPHAN_BANK_CREDIT`**: Bank credit from external sources without settlement link. Proposed Action: `MANUAL_JOURNAL_ENTRY`.
- **`UNCLASSIFIED`**: True residue sent to grounded LLM with strict citation guard.

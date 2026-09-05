# Milaan (मिलान) — Three-Way Settlement Reconciliation Agent

[![CI Tests](https://img.shields.io/badge/pytest-23%20passed%20(100%25)-emerald?style=flat-square)](file:///Users/adeshkishordeshmukh/Documents/Adesh_project/milaan/tests)
[![Evaluation Benchmark](https://img.shields.io/badge/Match%20Rate-99.27%25-indigo?style=flat-square)](file:///Users/adeshkishordeshmukh/Documents/Adesh_project/milaan/EVAL.md)
[![False Match Rate](https://img.shields.io/badge/False%20Match%20Rate-0.00%25-green?style=flat-square)](file:///Users/adeshkishordeshmukh/Documents/Adesh_project/milaan/EVAL.md)
[![Audit Chain](https://img.shields.io/badge/Audit%20Chain-SHA--256%20Verified-blue?style=flat-square)](file:///Users/adeshkishordeshmukh/Documents/Adesh_project/milaan/src/milaan/audit/log.py)
[![Track 4](https://img.shields.io/badge/Razorpay%20Buildathon-Track%204%20AI%20Finance%20Controller-purple?style=flat-square)](https://razorpay.com/buildathon/)

> **A three-way settlement reconciliation agent that closes the loop:**  
> **Razorpay Payments ↔ Razorpay Settlements ↔ Merchant Bank Statements ↔ Merchant Order Ledger**  
> on a 500+ record batch, reporting match rate by tier, 0.00% false-match rate, and an honest exception list — with deterministic matching first, an LLM only on the residue, and human approval on every write.

---

## 🏛️ The Core Thesis

> **"Reconciliation is a verification problem, not a generation problem."**

The LLM never decides whether two rows match. Deterministic tiers do that with explicit reason codes. The LLM is confined to two strictly grounded jobs:
1. Explaining exceptions that deterministic rules couldn't classify.
2. Answering financial controller questions over verified data the matcher already produced.

Every LLM output is validated against the database evidence by the **Citation Guard** — hallucinated transaction IDs, UTRs, or amounts are rejected before they can ever enter the audit log.

---

## ⚡ Quick Start

### 1. Install & Setup
```bash
# Clone repository
git clone https://github.com/AdeshDeshmukh/milaan.git
cd milaan

# Install in virtualenv
pip install -e ".[dev]"
```

### 2. Run the Interactive Web Dashboard
```bash
milaan ui
# Open http://127.0.0.1:8000 in your browser
```

### 3. Run CLI Demo & Evaluation
```bash
# Run full 3-way reconciliation on 500+ records
milaan demo

# Run the automated safety & evaluation benchmark
milaan eval

# Verify cryptographic SHA-256 hash chain of the audit log
milaan audit verify

# Ask financial controller questions over reconciliation results
milaan qa "What is the breakdown by tier for the latest run?"
```

---

## 🔍 System Architecture

```
                      ┌────────────────────────────────────────┐
                      │        Data Ingestion Layer            │
                      │  • Razorpay Payments, Refunds, Settl.  │
                      │  • Bank Statements (HDFC / ICICI)      │
                      │  • Merchant Order Ledger CSV           │
                      └───────────────────┬────────────────────┘
                                          │ (Deterministic Idempotency + Paise Normalization)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │        Canonical Record Store          │
                      │   (SQLite WAL, Strict Integer Paise)   │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │       Tiered Matching Engine           │
                      │  T0: Exact IDs (Score: 1.00)           │
                      │  T1: UTR + Amount (Score: 0.95)        │
                      │  T2: Composition Batch (Score: 0.90)   │
                      │  T3: Bounded Fuzzy (Score: 0.75)       │
                      └─────────┬────────────────────┬─────────┘
                                │                    │
             Matched Records (99.27%)                │ Unmatched Records
                                │                    ▼
                                │          ┌───────────────────┐
                                │          │ Deterministic     │
                                │          │ Rule Engine (~85%)│
                                │          └─────────┬─────────┘
                                │                    │
                                │                    │ Residue (~15%)
                                │                    ▼
                                │          ┌───────────────────┐
                                │          │ Grounded AI       │
                                │          │ + Citation Guard  │
                                │          └─────────┬─────────┘
                                │                    │
                                ▼                    ▼
                      ┌────────────────────────────────────────┐
                      │         Proposal Generation            │
                      │   (Journal Entries / SLA Holds)        │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │       Human Controller Approval        │
                      │     (Approve / Reject / Modify)        │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │         Action Execution               │
                      │   + Tamper-Evident SHA-256 Audit       │
                      └────────────────────────────────────────┘
```

---

## 📊 Evaluation & Benchmark Results

Continuous evaluation executed against the 500+ record golden synthetic dataset:

| Metric | Target | Result | Status |
| :--- | :--- | :--- | :--- |
| **Overall Match Rate** | `≥ 80.0%` | **99.27%** | ✅ PASS |
| **False Match Rate (Negative Controls)** | `0.00%` | **0.0000%** | ✅ PASS |
| **Exception Rule Coverage** | `≥ 80.0%` | **100.00%** | ✅ PASS |
| **LLM Unclassified Residue** | `≤ 20.0%` | **0.00%** | ✅ PASS |
| **Citation Guard Accuracy** | `≥ 99.0%` | **100.00%** | ✅ PASS |

---

## 🛠️ Matching Tiers Overview

1. **T0 — Exact ID Matching**: Matches order_id (Ledger ↔ Payment) and settlement_id linkages.
2. **T1 — UTR + Exact Amount**: Matches Razorpay settlement UTRs to Bank statement narrations (handling ICICI 12-char truncation and HDFC patterns) with exact paise amounts.
3. **T2 — Composition Matching (Subset-Sum DP)**: Handles batched settlements where multiple payments compose into 1 bank credit net of 2.00% fees and 18% GST using dynamic programming with millisecond timeouts.
4. **T3 — Bounded Fuzzy Matching**: Date window (±2 days) and amount tolerance (±100 paise) with narration entity verification.

---

## 🛡️ Real-World Edge Cases Solved (What Broke)

- **Truncated Bank Narrations**: ICICI truncates 16-char UTRs to 12 chars (`NEFT-N123456789012-RAZORPAY SOFTW`). Handled with prefix-aligned normalized matching.
- **Float Drift in GST**: Standard Python floats leak ₹0.01 differences on fee calculations. Solved with strict integer `Paise` and integer banker's rounding `(fee * 18 + 50) // 100`.
- **LLM Hallucinations**: Addressed by the **Citation Guard** (`src/milaan/ai/validator.py`), which validates every ID against the database and rejects unsupported claims.
- **Tamper-Evident Audit**: JSONL log with cryptographic SHA-256 chaining verified via `milaan audit verify`.

---

## 📄 License

MIT License — see [LICENSE](file:///Users/adeshkishordeshmukh/Documents/Adesh_project/milaan/LICENSE) for details.

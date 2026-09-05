# What Broke — Real-World Edge Cases Encountered & Fixed

> Production reconciliation fails not on the standard 1:1 path, but on messy edge cases. Here is what broke during development and how Milaan solves each.

---

### 1. Bank Narration UTR Truncation (ICICI & HDFC)
- **What Broke**: ICICI Bank truncated settlement UTRs from 16 characters down to 12 characters (`NEFT-N123456789012-RAZORPAY SOFTW`), causing strict string equality matchers to fail and report missing bank credits.
- **How We Solved It**: Built `normalize/utr.py` with prefix/suffix fuzzy UTR matching (`utrs_match`) that validates length ≥ 10 and checks substring prefix alignments before escalating.

### 2. Float Precision Drift on GST Calculations
- **What Broke**: Computing 18% GST on a 2% gateway fee with standard Python floating point caused ₹0.01 (1 paisa) differences between ledger sums and bank credit amounts, causing batch composition to fail.
- **How We Solved It**: Created strict integer `Paise` domain models (`domain/money.py`) using integer arithmetic with standard banker's rounding `(fee * 18 + 50) // 100`. Standard floats are forbidden by type assertion.

### 3. LLM Transaction ID Hallucinations
- **What Broke**: When explaining unmatched exceptions, raw LLMs occasionally generated plausible-looking fake transaction IDs (`pay_xyz789`) that did not exist in the merchant database.
- **How We Solved It**: Implemented the **Citation Guard** (`ai/validator.py`). Every transaction ID, UTR, and amount in the LLM response is extracted and verified against the database before the explanation is accepted into the audit log.

### 4. Duplicate Ingestion & Webhook Retries
- **What Broke**: Re-running ingestion or receiving duplicate Razorpay webhook events created duplicate rows and caused double-counting in ledger matching.
- **How We Solved It**: Enforced SHA-256 deterministic idempotency keys (`ingest/idempotency.py`) on `(source, external_id, amount, timestamp)` at the database constraint level. Re-running ingest produces byte-identical state.

### 5. Audit Trail Tampering
- **What Broke**: Audit logs stored in plaintext SQLite tables can be modified post-hoc by unauthorized database updates.
- **How We Solved It**: Built an append-only JSONL log (`audit/log.py`) with cryptographic SHA-256 hash chaining. `milaan audit verify` validates the complete hash chain from genesis to head.

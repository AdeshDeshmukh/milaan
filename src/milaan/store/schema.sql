-- Milaan schema — append-only, nothing mutates source tables.
-- All money columns are INTEGER (paise). A float is a schema violation.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ═══════════════════════════════════════════════════════════════════════
-- RAW TABLES — exact copies from each source, never mutated after insert
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS raw_payments (
    payment_id    TEXT PRIMARY KEY,
    order_id      TEXT NOT NULL,
    amount        INTEGER NOT NULL,  -- paise
    currency      TEXT NOT NULL DEFAULT 'INR',
    status        TEXT NOT NULL,
    method        TEXT NOT NULL DEFAULT '',
    fee           INTEGER NOT NULL DEFAULT 0,
    tax           INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL,  -- UTC epoch
    captured_at   INTEGER,
    settlement_id TEXT,
    notes_json    TEXT NOT NULL DEFAULT '{}',
    _ingested_at  INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raw_refunds (
    refund_id     TEXT PRIMARY KEY,
    payment_id    TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    status        TEXT NOT NULL,
    created_at    INTEGER NOT NULL,
    speed         TEXT NOT NULL DEFAULT 'normal',
    notes_json    TEXT NOT NULL DEFAULT '{}',
    _ingested_at  INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raw_disputes (
    dispute_id    TEXT PRIMARY KEY,
    payment_id    TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    status        TEXT NOT NULL,
    reason_code   TEXT NOT NULL DEFAULT '',
    phase         TEXT NOT NULL DEFAULT 'chargeback',
    created_at    INTEGER NOT NULL,
    respond_by    INTEGER,
    _ingested_at  INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raw_settlements (
    settlement_id TEXT PRIMARY KEY,
    amount        INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'processed',
    fees          INTEGER NOT NULL DEFAULT 0,
    tax           INTEGER NOT NULL DEFAULT 0,
    utr           TEXT NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL,
    _ingested_at  INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raw_recon_rows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    settlement_id   TEXT NOT NULL,
    amount          INTEGER NOT NULL,
    fee             INTEGER NOT NULL DEFAULT 0,
    tax             INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL,
    settled_at      INTEGER NOT NULL,
    order_id        TEXT NOT NULL DEFAULT '',
    _ingested_at    INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raw_bank_txns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id        TEXT NOT NULL,
    txn_date      TEXT NOT NULL,  -- ISO date
    value_date    TEXT NOT NULL,
    narration     TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    balance       INTEGER NOT NULL DEFAULT 0,
    utr           TEXT NOT NULL DEFAULT '',
    counterparty  TEXT NOT NULL DEFAULT '',
    source_bank   TEXT NOT NULL DEFAULT '',
    raw_row_json  TEXT NOT NULL DEFAULT '{}',
    _ingested_at  INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raw_ledger_orders (
    order_id      TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL DEFAULT '',
    amount        INTEGER NOT NULL,
    order_date    TEXT NOT NULL,  -- ISO date
    payment_mode  TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'completed',
    notes_json    TEXT NOT NULL DEFAULT '{}',
    _ingested_at  INTEGER NOT NULL,
    _idempotency_key TEXT NOT NULL UNIQUE
);

-- ═══════════════════════════════════════════════════════════════════════
-- CANONICAL TABLE — unified form for matching
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS canonical (
    canonical_id    TEXT PRIMARY KEY,
    source          TEXT NOT NULL,  -- 'razorpay' / 'bank' / 'ledger'
    external_id     TEXT NOT NULL,
    amount          INTEGER NOT NULL,
    txn_date        TEXT NOT NULL,  -- ISO date
    utr             TEXT NOT NULL DEFAULT '',
    settlement_id   TEXT NOT NULL DEFAULT '',
    order_id        TEXT NOT NULL DEFAULT '',
    payment_id      TEXT NOT NULL DEFAULT '',
    counterparty    TEXT NOT NULL DEFAULT '',
    metadata_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_canonical_source ON canonical(source);
CREATE INDEX IF NOT EXISTS idx_canonical_amount ON canonical(amount);
CREATE INDEX IF NOT EXISTS idx_canonical_utr ON canonical(utr) WHERE utr != '';
CREATE INDEX IF NOT EXISTS idx_canonical_settlement ON canonical(settlement_id) WHERE settlement_id != '';
CREATE INDEX IF NOT EXISTS idx_canonical_order ON canonical(order_id) WHERE order_id != '';
CREATE INDEX IF NOT EXISTS idx_canonical_payment ON canonical(payment_id) WHERE payment_id != '';
CREATE INDEX IF NOT EXISTS idx_canonical_date ON canonical(txn_date);

-- ═══════════════════════════════════════════════════════════════════════
-- MATCHES — every match carries tier + confidence + reason codes
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS matches (
    match_id            TEXT PRIMARY KEY,
    left_canonical_id   TEXT NOT NULL REFERENCES canonical(canonical_id),
    right_canonical_id  TEXT NOT NULL REFERENCES canonical(canonical_id),
    tier                TEXT NOT NULL,
    confidence_score    REAL NOT NULL,
    reason_codes_json   TEXT NOT NULL DEFAULT '[]',
    amount_delta_paise  INTEGER NOT NULL DEFAULT 0,
    run_id              TEXT NOT NULL,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_run ON matches(run_id);
CREATE INDEX IF NOT EXISTS idx_matches_left ON matches(left_canonical_id);
CREATE INDEX IF NOT EXISTS idx_matches_right ON matches(right_canonical_id);

-- ═══════════════════════════════════════════════════════════════════════
-- MATCH GROUPS — many-to-one (composition matches)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS match_groups (
    group_id                TEXT PRIMARY KEY,
    settlement_canonical_id TEXT NOT NULL REFERENCES canonical(canonical_id),
    member_ids_json         TEXT NOT NULL DEFAULT '[]',
    tier                    TEXT NOT NULL,
    confidence_score        REAL NOT NULL,
    reason_codes_json       TEXT NOT NULL DEFAULT '[]',
    composition_sum_paise   INTEGER NOT NULL DEFAULT 0,
    expected_amount_paise   INTEGER NOT NULL DEFAULT 0,
    delta_paise             INTEGER NOT NULL DEFAULT 0,
    run_id                  TEXT NOT NULL,
    created_at              INTEGER NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- EXCEPTIONS — unmatched/anomalous records
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS exceptions (
    exception_id        TEXT PRIMARY KEY,
    canonical_id        TEXT NOT NULL REFERENCES canonical(canonical_id),
    category            TEXT NOT NULL,
    amount              INTEGER NOT NULL DEFAULT 0,
    description         TEXT NOT NULL DEFAULT '',
    evidence_ids_json   TEXT NOT NULL DEFAULT '[]',
    suggested_action    TEXT NOT NULL DEFAULT 'NO_ACTION',
    is_llm_classified   INTEGER NOT NULL DEFAULT 0,
    run_id              TEXT NOT NULL,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exceptions_run ON exceptions(run_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_category ON exceptions(category);

-- ═══════════════════════════════════════════════════════════════════════
-- LLM EXPLANATIONS
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS explanations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    exception_id        TEXT NOT NULL REFERENCES exceptions(exception_id),
    category            TEXT NOT NULL,
    rationale           TEXT NOT NULL,
    suggested_action    TEXT NOT NULL,
    evidence_ids_json   TEXT NOT NULL DEFAULT '[]',
    confidence_note     TEXT NOT NULL DEFAULT '',
    raw_response        TEXT NOT NULL DEFAULT '',
    citation_valid      INTEGER NOT NULL DEFAULT 1,
    rejection_reason    TEXT NOT NULL DEFAULT '',
    created_at          INTEGER NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- PROPOSALS — proposed actions (never auto-executed)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id         TEXT PRIMARY KEY,
    exception_id        TEXT NOT NULL REFERENCES exceptions(exception_id),
    action_type         TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    adjust_amount_paise INTEGER NOT NULL DEFAULT 0,
    evidence_ids_json   TEXT NOT NULL DEFAULT '[]',
    is_llm_generated    INTEGER NOT NULL DEFAULT 0,
    run_id              TEXT NOT NULL,
    created_at          INTEGER NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- APPROVALS — human decisions
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS approvals (
    approval_id   TEXT PRIMARY KEY,
    proposal_id   TEXT NOT NULL REFERENCES proposals(proposal_id),
    status        TEXT NOT NULL,  -- approved / rejected / deferred
    approved_by   TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    decided_at    INTEGER NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- PROPOSED JOURNAL — adjustments ONLY after approval (never source of truth)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS proposed_journal (
    entry_id      TEXT PRIMARY KEY,
    proposal_id   TEXT NOT NULL REFERENCES proposals(proposal_id),
    approval_id   TEXT NOT NULL REFERENCES approvals(approval_id),
    action_type   TEXT NOT NULL,
    amount_paise  INTEGER NOT NULL DEFAULT 0,
    description   TEXT NOT NULL DEFAULT '',
    canonical_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at    INTEGER NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- RUNS — metadata for each reconciliation run
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    started_at      INTEGER NOT NULL,
    completed_at    INTEGER,
    status          TEXT NOT NULL DEFAULT 'running',
    config_json     TEXT NOT NULL DEFAULT '{}',
    total_records   INTEGER NOT NULL DEFAULT 0,
    matched_records INTEGER NOT NULL DEFAULT 0,
    exceptions_count INTEGER NOT NULL DEFAULT 0,
    notes           TEXT NOT NULL DEFAULT ''
);

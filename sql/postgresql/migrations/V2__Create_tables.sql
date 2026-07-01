---------------------------------------------------------
-- 1. ACCOUNTS
---------------------------------------------------------
CREATE TABLE operation.accounts (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'USER_WALLET', 'SYSTEM_FEES', 'SUSPENSE'
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

---------------------------------------------------------
-- 2. IDEMPOTENCY_KEYS
---------------------------------------------------------
CREATE TABLE operation.idempotency_keys (
    key_value VARCHAR(255),
    status VARCHAR(50) NOT NULL, -- 'PROCESSING', 'COMPLETED'
    response_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (key_value)
);

---------------------------------------------------------
-- 3. TRANSACTIONS
---------------------------------------------------------
CREATE TABLE operation.transactions (
    id UUID,
    idempotency_key VARCHAR(255),
    description TEXT,
    status VARCHAR(50) NOT NULL, -- 'PENDING', 'SETTLED', 'FAILED'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE operation.transactions_2024 PARTITION OF operation.transactions FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');
CREATE TABLE operation.transactions_2025 PARTITION OF operation.transactions FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');
CREATE TABLE operation.transactions_2026 PARTITION OF operation.transactions FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');


---------------------------------------------------------
-- 4. LEDGER_LINES
---------------------------------------------------------
CREATE TABLE operation.ledger_lines (
    id UUID,
    transaction_id UUID NOT NULL,
    account_id UUID NOT NULL,
    amount NUMERIC(19, 4) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE operation.ledger_lines_2024 PARTITION OF operation.ledger_lines FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');
CREATE TABLE operation.ledger_lines_2025 PARTITION OF operation.ledger_lines FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');
CREATE TABLE operation.ledger_lines_2026 PARTITION OF operation.ledger_lines FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
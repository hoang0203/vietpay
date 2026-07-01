CREATE TABLE reporting.ledger_lines
(
    id UUID,
    transaction_id UUID,
    account_id UUID,
    amount Decimal(19, 4),
    currency FixedString(3),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, transaction_id)
SETTINGS index_granularity = 8192;

CREATE TABLE reporting.transactions_settled
(
    id UUID,
    status String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(created_at)
ORDER BY (id)
SETTINGS index_granularity = 8192;
erDiagram
    ACCOUNTS {
        uuid id PK
        varchar name
        varchar type
        char currency
        timestamptz created_at
    }

    IDEMPOTENCY_KEYS {
        varchar key_value PK
        varchar status
        jsonb response_payload
        timestamptz created_at PK
        timestamptz expires_at
    }

    TRANSACTIONS {
        uuid id PK
        varchar idempotency_key
        text description
        varchar status
        timestamptz created_at PK
    }

    LEDGER_LINES {
        uuid id PK
        uuid transaction_id
        uuid account_id
        numeric amount
        char currency
        timestamptz created_at PK
    }

    %% the relationships
    IDEMPOTENCY_KEYS ||--|o TRANSACTIONS : "(1:1)"
    TRANSACTIONS ||--|{ LEDGER_LINES : "(1:N)"
    ACCOUNTS ||--|{ LEDGER_LINES : "(1:N)"
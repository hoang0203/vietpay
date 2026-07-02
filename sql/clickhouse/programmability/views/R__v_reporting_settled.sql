CREATE OR REPLACE VIEW v_reporting_settled AS
SELECT 
    ll.transaction_id,
    ll.account_id,
    ll.amount,
    ll.currency,
    ll.created_at AS ledger_created_at,
    t.status
FROM ledger_lines AS ll
INNER JOIN transactions_settled AS t 
    ON ll.transaction_id = t.id;
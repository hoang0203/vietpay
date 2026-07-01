-- support reporting query to find settled transactions in a specific time range
CREATE INDEX idx_transactions_status_created 
ON transactions (status, created_at);

-- support reporting query
CREATE INDEX idx_ledger_lines_join_report 
ON ledger_lines (transaction_id, created_at) 
INCLUDE (account_id, amount, currency);

-- support to find balance of an account at a specific time
CREATE INDEX idx_ledger_lines_account_balance 
ON ledger_lines (account_id, created_at) 
INCLUDE (amount);
-- Revert the application code first to stop writing to this column, then run:
ALTER TABLE operation.transactions 
DROP COLUMN IF EXISTS settlement_batch_id;
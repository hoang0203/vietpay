-- Add a CHECK constraint as NOT VALID. 
ALTER TABLE operation.transactions 
ADD CONSTRAINT chk_settlement_batch_id_not_null 
CHECK (settlement_batch_id IS NOT NULL) NOT VALID;

-- Validate the constraint concurrently.
ALTER TABLE operation.transactions 
VALIDATE CONSTRAINT chk_settlement_batch_id_not_null;

-- Explicitly promote the column to NOT NULL.
ALTER TABLE operation.transactions 
ALTER COLUMN settlement_batch_id SET NOT NULL;

-- Clean up the helper CHECK constraint
ALTER TABLE operation.transactions 
DROP CONSTRAINT chk_settlement_batch_id_not_null;
-- 1. Remove the NOT NULL catalog flag
ALTER TABLE operation.transactions 
ALTER COLUMN settlement_batch_id DROP NOT NULL;

-- 2. Remove the CHECK constraint if the migration failed mid-way
ALTER TABLE operation.transactions 
DROP CONSTRAINT IF EXISTS chk_settlement_batch_id_not_null;
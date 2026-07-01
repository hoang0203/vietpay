-- Add a new nullable column
ALTER TABLE operation.transactions 
ADD COLUMN IF NOT EXISTS settlement_batch_id UUID NULL;

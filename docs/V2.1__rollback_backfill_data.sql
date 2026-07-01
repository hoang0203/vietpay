-- Warning: This is a heavy operation. Usually, stopping the script is sufficient.
UPDATE operation.transactions 
SET settlement_batch_id = NULL 
WHERE settlement_batch_id = '00000000-0000-0000-0000-000000000000'::uuid;
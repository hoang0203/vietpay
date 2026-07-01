-- Backfill the new column with a default value
DO $$
DECLARE
    partition_name TEXT;
    partitions TEXT[] := ARRAY['transactions_2024', 'transactions_2025', 'transactions_2026'];
    rows_updated INT;
    batch_size INT := 20000;
BEGIN
    FOREACH partition_name IN ARRAY partitions LOOP
        RAISE NOTICE 'Starting backfill for partition: %', partition_name;
        LOOP
            -- Execute chunked update on the specific partition
            EXECUTE format('
                UPDATE operation.%I 
                SET settlement_batch_id = ''00000000-0000-0000-0000-000000000000''::uuid
                WHERE id IN (
                    SELECT id FROM operation.%I 
                    WHERE settlement_batch_id IS NULL 
                    LIMIT %L
                );', partition_name, partition_name, batch_size);

            GET DIAGNOSTICS rows_updated = ROW_COUNT;
            
            -- Commit the current batch to free locks and allow vacuuming
            COMMIT; 
            
            EXIT WHEN rows_updated = 0;
            
            -- Sleep briefly (100ms) to allow replica catch-up and prevent CPU spikes
            PERFORM pg_sleep(0.1); 
        END LOOP;
    END LOOP;
END $$;

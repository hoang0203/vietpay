DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN 
        SELECT proname, 
               oidvectortypes(proargtypes) as argtypes
        FROM pg_proc
        JOIN pg_namespace ON pg_proc.pronamespace = pg_namespace.oid
        WHERE pg_namespace.nspname = 'operation'  -- Change to your schema
          AND proname = 'sp_fast_track_transfer'   -- Change to your procedure name
    LOOP
        EXECUTE format('DROP PROCEDURE IF EXISTS operation.%I(%s)', 
                       rec.proname, rec.argtypes);
        RAISE NOTICE 'Dropped: % (%)', rec.proname, rec.argtypes;
    END LOOP;
END $$;

CREATE OR REPLACE PROCEDURE operation.sp_fast_track_transfer(
    p_tx_id UUID,
    p_idemp_key VARCHAR,
    p_amount NUMERIC,
    p_source_id UUID,
    p_dest_id UUID,
    p_desc TEXT
)
LANGUAGE plpgsql AS $$
DECLARE
    v_current_balance NUMERIC;
BEGIN

    PERFORM id FROM operation.accounts 
    WHERE id IN (p_source_id, p_dest_id) 
    ORDER BY id FOR UPDATE;

    SELECT COALESCE(SUM(amount), 0) INTO v_current_balance 
    FROM operation.ledger_lines WHERE account_id = p_source_id;
    
    IF p_source_id != '99999999-9999-9999-9999-999999999999'::uuid THEN
        SELECT COALESCE(SUM(amount), 0) INTO v_current_balance 
        FROM operation.ledger_lines WHERE account_id = p_source_id;
        
        IF v_current_balance < p_amount THEN
            RAISE EXCEPTION 'Insufficient balance.';
        END IF;
    END IF;

    INSERT INTO operation.idempotency_keys (key_value, status, expires_at)
    VALUES (p_idemp_key, 'COMPLETED', NOW() + INTERVAL '1 hour');

    INSERT INTO operation.transactions (id, idempotency_key, description, status)
    VALUES (p_tx_id, p_idemp_key, p_desc, 'SETTLED');

    INSERT INTO operation.ledger_lines (id, transaction_id, account_id, amount, currency)
    VALUES (gen_random_uuid(), p_tx_id, p_source_id, -p_amount, 'VND'),
           (gen_random_uuid(), p_tx_id, p_dest_id, p_amount, 'VND');

EXCEPTION 
    WHEN OTHERS THEN
        RAISE EXCEPTION 'sp_fast_track_transfer failed: %', SQLERRM;
END;
$$;
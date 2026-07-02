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
          AND proname = 'sp_fail_transaction'   -- Change to your procedure name
    LOOP
        EXECUTE format('DROP PROCEDURE IF EXISTS operation.%I(%s)', 
                       rec.proname, rec.argtypes);
        RAISE NOTICE 'Dropped: % (%)', rec.proname, rec.argtypes;
    END LOOP;
END $$;

CREATE OR REPLACE PROCEDURE operation.sp_fail_transaction(
    p_idemp_key VARCHAR,
    p_tx_id UUID
)
LANGUAGE plpgsql AS $$
DECLARE
    v_status VARCHAR;
    v_suspense_id UUID;
    v_source_id UUID;
    v_amount NUMERIC;
BEGIN

    SELECT status INTO v_status FROM operation.transactions WHERE id = p_tx_id FOR UPDATE;
    IF v_status != 'PENDING' THEN
        RAISE EXCEPTION 'Transaction % is not PENDING', p_tx_id;
    END IF;

    SELECT account_id, amount INTO v_suspense_id, v_amount
    FROM operation.ledger_lines WHERE transaction_id = p_tx_id AND amount > 0 LIMIT 1;

    SELECT account_id INTO v_source_id
    FROM operation.ledger_lines WHERE transaction_id = p_tx_id AND amount < 0 LIMIT 1;

    PERFORM id FROM operation.accounts 
    WHERE id IN (v_suspense_id, v_source_id) 
    ORDER BY id FOR UPDATE;

    UPDATE operation.transactions SET status = 'FAILED' WHERE id = p_tx_id;

    INSERT INTO operation.ledger_lines (id, transaction_id, account_id, amount, currency)
    VALUES (gen_random_uuid(), p_tx_id, v_suspense_id, -v_amount, 'VND'),
           (gen_random_uuid(), p_tx_id, v_source_id, v_amount, 'VND');

    UPDATE operation.idempotency_keys SET status = 'FAILED' WHERE key_value = p_idemp_key;
EXCEPTION 
    WHEN OTHERS THEN
        RAISE EXCEPTION 'sp_fail_transaction failed: %', SQLERRM;
END;
$$;
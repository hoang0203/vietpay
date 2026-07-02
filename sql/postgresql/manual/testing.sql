INSERT INTO operation.accounts (id, name, type, currency) 
VALUES 
    -- System / Gateway Account (Allowed to have a negative balance)
    ('99999999-9999-9999-9999-999999999999', 'System Gateway', 'SYSTEM_GATEWAY', 'VND'),
    
    -- User Wallets
    ('11111111-1111-1111-1111-111111111111', 'User A Wallet', 'USER_WALLET', 'VND'),
    ('22222222-2222-2222-2222-222222222222', 'User B Wallet', 'USER_WALLET', 'VND'),
    
    -- Suspense Account (Temporary holding for PENDING transactions)
    ('33333333-3333-3333-3333-333333333333', 'Main Suspense', 'SUSPENSE', 'VND')
ON CONFLICT (id) DO NOTHING;

-- firt deposit after create account
CALL operation.sp_fast_track_transfer(
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 
    'DEPOSIT_FAST_001',                     -- Idempotency key
    500000,                                 -- Amount
    '99999999-9999-9999-9999-999999999999', -- System account
    '11111111-1111-1111-1111-111111111111', -- User account
    'Deposit 500,000 VND to user account'
);

-- CASE 1
CALL operation.sp_init_pending_transaction(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 
    'IDEMP_TEST_001',                       -- Idempotency key
    200000,                                 -- amount
    '11111111-1111-1111-1111-111111111111', 
    '33333333-3333-3333-3333-333333333333', 
    'electricity bill payment'
);


CALL operation.sp_settle_transaction(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', -- Transaction ID
    'IDEMP_TEST_001',                       -- Idempotency key
    '22222222-2222-2222-2222-222222222222'  -- Destination Account
);

-- CASE 2
CALL operation.sp_init_pending_transaction(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', -- Transaction ID
    'IDEMP_TEST_002', 
    300000, 
    '11111111-1111-1111-1111-111111111111', 
    '33333333-3333-3333-3333-333333333333', 
    'ticket booking'
);


CALL operation.sp_fail_transaction(
    'IDEMP_TEST_002', 
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb' -- Transaction ID
);

CALL operation.sp_fast_track_transfer(
    'dddddddd-dddd-dddd-dddd-dddddddddddd', 
    'IDEMP_TEST_004', 
    999000000, -- Amount is greater than the balance of the source account
    '11111111-1111-1111-1111-111111111111', 
    '22222222-2222-2222-2222-222222222222', 
    'must fail due to insufficient balance'
);
-- use for streaming data
DROP PUBLICATION IF EXISTS dbz_publication;

CREATE PUBLICATION dbz_publication 
FOR TABLE operation.ledger_lines, operation.transactions 
WITH (publish_via_partition_root = true);
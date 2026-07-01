# Enterprise Database Architect — Fintech
## 1) Relational core model
Based on the provided context, I have designed the database with four primary tables:

**-accounts:** Stores account metadata and balances.<br>
**-idempotency_keys:** Stores idempotency keys and their lifespan to prevent duplicate processing.<br>
**-transactions:** Records the overall status and intent of a payment or transfer.<br>
**-ledger_lines:** Contains the double-entry cash flow records for each transaction.<br>

For more information use this [link](sql/postgresql/manual/V2__Create_tables.sql)

For ER you can use this [link](docs/ER_mermaid.js) or copy the code and paste to https://mermaid.ai/live 

**How the ledger always balances**<br>
In a double-entry ledger, a transaction must involve two or more accounts, and the total sum of amounts for these accounts must always equal exactly zero.

I have categorized banking transactions into two types:

**1.Internal Transfers:** Moving funds between two accounts within the same bank.<br>
**2.Complex/External Transfers:** Involving external banks, QR code payments, biometric authentication, or third-party services.

For the first type, 2 accounts can transfer money to each other, and no need middle account. But for the second type, they need a middle account, I call it "SUSPENSE" (system account). The first account will deposit money to the "SUSPENSE". Then after the businness action was done, the "SUSPENSE" will release the money to the second account.

So all inserts to transactions and ledger_lines happen within a single ACID Database Transaction (BEGIN; ... COMMIT;) and a database trigger explicitly checks that SUM(amount) = 0 for the given transaction_id before executing the COMMIT.

### Example Scenarios:
### Case 1: Simple internal transfer

**- Step 1:** Generate a new idempotency key in the idempotency_keys table.<br>
**- Step 2:** Insert a new record into the transactions table with a SETTLED status.<br>
**- Step 3:** Insert two new records into the ledger_lines table (one negative, one positive). If a transfer fee applies, a third line is added for the SYSTEM_FEES account.

### Case 2: Complex transfer (e.g., booking a ride, external deposit)

**- Step 1:** Generate a new idempotency key.<br>
**- Step 2:** Insert a new record into the transactions table with a PENDING status.<br>
**- Step 3:** Insert two records into ledger_lines: a negative amount for the sender's account and a positive amount for the SUSPENSE account (locking the funds).<br>
**- Step 4:** After the required business action is completed (e.g., OTP verified, driver finishes the ride), the funds are released. We insert at least two more records into ledger_lines: negative for the SUSPENSE account and positive for the receiver.<br>
**- Step 5:** Update the status in the transactions table to SETTLED.<br>

**Handling Failed Transactions:**<br>
If a transaction fails during a complex transfer, the system inserts two new records into ledger_lines to reverse the hold (negative for SUSPENSE, positive for the sender) and updates the transaction status to FAILED.

**How a duplicate request cannot post twice**<br>
We require a unique idempotency key for incoming requests. If the key already exists, the database rejects the insert, and the application returns the cached status of the original request.

**Indexing strategy**<br>
For more information use this [link](sql/postgresql/manual/V3__Create_partition_index.sql)

for the 2 first indexes, I will use it for the reporting query.
For the last index, It will help me to get balance of an account at a specific time

## 2) Query & performance
As you can see, I use different design with yours. So that I will anwser this question in 2 case.

1.Follow your design:
I will create an index that contains the status and created_at columns and also includes the wallet_id, currency, amount columns. I also use partition by year. If we have any rule that only use recent time, I will split the partition by month in current year, and year for old year. And If we go to next year, I will merge 12-month partitions into 1 year partition, and split new year into 12 month partitions

With above plan, the query will use the index scan only instead of sequential scan or Bitmap Heap Scan. That make system read a lot of blocks. Then with the year partition, it can help to prune other blocks that do not match the conditions. However, this plan will cost more space in disk and ram, because this plan will create a copy of the table and it also create additional burden when we insert or update the status column.

2.My new design
I combine the partition and index too (the reporting query). So mostly the explaination is same as the above case. However, In my design, we need a joining step. And that may cause a performance issue.

So to overcome it, I scrutinize our context and realize some issues:
- The transactions table is used for operation and reporting activities in parallel. That make it slow
- Because of double-entry ledger pattern, when we update the status from "PENDING" to "SETTLED", it would change not only the table, but also the index table dramatically
- Duplicated status value

So that, I recommend we decouple reporting and opration activities, using clickhouse for the reporting.
So this is my design:

you can see [hear](docs/new_design_mermaid.js) or copy the code and paste to https://mermaid.ai/live

## 3) Zero-downtime migration
To change the structure of a table, I follow 2 rules:
1. No delete column
2. Always add new column at the end

With 2 rules, I can avoid crashing the application and if you want to revert instantly, you can drop this column easily.
To make the scripts idempotent, I use flyway rule. I will create a table name "pyflyway_schema_history" to follow the version of the database. And I also use prefix "V__" for the versioned script and "R__" for the repeatable script.

Step for addition column:
- step 1: add nullable column [migrate](docs/V1__add_new_column.sql) | [rollback](docs/V1.1__rollback_add_new_column.sql)
- step 2: start dual-write window
- step 3: backfill data [migrate](docs/V2__backfill_data.sql) | [rollback](docs/V2.1__rollback_backfill_data.sql)
- step 4: promote constraint [migrate](docs/V3__promote_constraint.sql) | [rollback](docs/V3.1__rollback_promote_constraint.sql)

## 4) Polyglot modelling
**- MongoDB:** For example, we got 2 more than weather apis, they are json data but different structure. We've got specific data but maybe we want use more data in the json in the future. So we decide to keep the json data in JSONB column to easily explore in the future.
So we may get 2 problems:
1.The Oversized-Attribute Storage Technique: It mean if the json value is more than 2kb in size, the postgresql will write the data to another table. Then make the table bigger and slow the performance
2.GIN Index: If you use GIN Index to boost up the query, it may cause the performance issue in the future. 

**- Neo4j:** for example, we want to detect a Fraud-Ring, if you use postgresql to figure out which account or device or IP that involves to the fraud, you must be use a lot of joinning and recursive CTE. If it has too many accounts, devices or/and IP, your postgresql may be overheaded. So that why a graph DB is suitable for this case.

In this case, the graph DB has 2 things:

Nodes: (:User), (:Device), (:Card), (:IPAddress)

Relationships: [:LOGGED_IN_FROM], [:USED_CARD], [:TRANSFERRED_TO]

**Cypher query 1**: detect sharing IP
```
MATCH (u:User)-[r:LOGGED_IN_FROM]->(d:Device)
WHERE r.timestamp >= datetime().truncoToWeek()
WITH d, count(DISTINCT u) as user_count, collect(u.user_id) as users
WHERE user_count > 3
RETURN d.device_id, user_count, users
ORDER BY user_count DESC;
```

**Cypher query 2**: detect suspicious accounts that shared card or device with fraud account
```
MATCH (bad_user:User {is_fraud: true})-[:LOGGED_IN_FROM|USED_CARD*1..2]-(shared_entity)-[:LOGGED_IN_FROM|USED_CARD*1..2]-(suspect_user:User {is_fraud: false})
RETURN DISTINCT suspect_user.user_id, suspect_user.email, shared_entity.id
LIMIT 50;
```
## 5) Observability

|Category|Metric to Track|SLO (Target Commitment)|Alerts & Thresholds|Reason & Business Impact|
| :--- | :--- | :--- | :--- | :--- |
|Latency|p50, p95, p99 Query Duration:Measured separately for Read/Write queries.|p99 Write < 50ms <br> p99 Read < 10ms|Warning: p99 Write > 100ms for 5 mins. Critical: > 250ms for 3 mins.|Slow DB responses cause upstream API timeouts. This is usually caused by disk I/O bottlenecks or write-penalties on indexes as tables grow.|
|Throughput|TPS (Transactions Per Second): <br> Rate of Commit vs. Rollback.|> 99.9% commit success rate.|Critical: TPS drops by > 50% compared to the normal baseline for > 2 minutes.|A sudden drop in TPS (rather than a spike) is a major red flag. It indicates the app cannot reach the DB, connection pools are exhausted, or the system is deadlocked.|
|Replication Lag|Replication Delay: <br> Byte/Time gap between Primary and Replicas.|p99 Lag < 50ms|Warning: Lag > 500ms for 3 mins. <br> Critical: Lag > 5s for 1 min.|If read-replicas fall behind, balance checks might return outdated (pre-deduction) data, potentially allowing users to overspend past their actual balance.|
|Lock Contention|Active Waiting Queries: <br> Queries blocked waiting for a lock.|0 queries waiting > 500ms for row-level locks on accounts or transactions.|Critical: > 10 queries in active state with wait_event_type = 'Lock' for > 2 seconds.|Because you use SELECT FOR UPDATE, one slow transaction (e.g., a delayed webhook) holds the lock and causes a massive domino-effect queue behind it.|
|Settlement Lag|Pending Queue Age: <br> Time transactions spend in the PENDING state.|- 99% internal transfers settle < 1s. <br> - 99% external gateways settle < 5 mins.|Warning: > 50 transactions stuck as PENDING for > 15 mins. <br> Critical: Sum of SUSPENSE account balance does not equal total PENDING transaction amounts.|Measures business health. The DB infra might be green, but if background workers crash, funds are "frozen." Imbalances indicate severe double-entry ledger violations.|
|Capacity|Disk Space, Connection Pool, TXID Age: <br> Core infrastructure limits.|- Disk < 75% <br> - Connections < 80% <br> - TXID Age < 1 Billion|Warning: datfrozenxid > 1.2 Billion (Wraparound risk). <br> Critical: Active Connections > 90% for > 2 mins.|Prevents complete outages. Maxed connections drop API calls instantly. Maxed TXIDs force PostgreSQL to shut down completely to prevent data corruption.|
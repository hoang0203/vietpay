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

For the 2 first indexes, I will use it for the reporting query.
For the last index, It will help me to get balance of an account at a specific time

## 2) Query & performance
As you can see, I use different design with yours. So that I will anwser this question in 2 case.

**1.Follow your design:**<br>
To optimize the provided reporting query within PostgreSQL, I would implement:

**- Covering Indexes:** I created an index on (status, created_at) and included wallet_id, currency, amount using the INCLUDE clause. This allows for an Index-Only Scan, preventing costly heap lookups.<br>
**- Tiered Partitioning:** I use a hybrid partitioning strategy: monthly partitions for the current year to handle hot data and yearly partitions for historical data. This facilitates partition pruning and improves maintenance efficiency (e.g., easier data archiving/dropping).<br>
**- Trade-off:** This increases disk I/O during writes due to index maintenance and storage overhead, but it is necessary for maintaining low-latency reporting.<br>

**2.My new design**<br>
Given the "double-entry" nature of our ledger and the high frequency of status updates, I recommend decoupling reporting from operational traffic to prevent resource contention.

My proposal is to use ClickHouse as an OLAP engine.

**- Mechanism:** I will use Debezium CDC to capture changes from the PostgreSQL Write-Ahead Log (WAL), stream them through Apache Kafka, and ingest them into ClickHouse using PySpark or the ClickHouse Kafka engine.<br>

**- Benefit:** This offloads the reporting query to a column-oriented database specifically designed for analytical workloads, ensuring that heavy aggregations do not affect the throughput of the primary payment gateway.<br>

So that, I recommend we decouple reporting and opration activities, using clickhouse for the reporting.
So this is my design:

you can see [hear](docs/new_design_mermaid.js) or copy the code and paste to https://mermaid.ai/live

## 3) Zero-downtime migration
To minimize downtime, I adhere to a strict two-phase schema evolution strategy:
1. No delete column
2. Always add new column at the end

With 2 rules, I can avoid crashing the application and if you want to revert instantly, you can drop this column easily.
I utilize Flyway to manage migration versioning, ensuring idempotency and deterministic state transitions. I will create a table name "pyflyway_schema_history" to follow the version of the database. And I also use prefix "V__" for the versioned script and "R__" for the repeatable script.

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

## 6) Design write-up (ADR)

**1. Data Modelling** <br>
**- Double-Entry Integrity:** We reject the "simple balance update" pattern. Every value movement is recorded as an immutable ledger_line. We maintain a strict invariant: $\sum_{entry \in Transaction} amount = 0$.<br>
**- Idempotency as a First-Class Citizen:** Every request must be keyed by an idempotency_key enforced at the database constraint level. This prevents race conditions and duplicate processing, which is non-negotiable in financial services.<br>
**- Design-Led Schema:** Our schema is normalized to 3NF to prevent anomalies. We utilize PostgreSQL’s PARTITION BY RANGE to manage the lifecycle of 50M+ rows, ensuring high-performance query execution via partition pruning.<br>
**2. Consistency vs. Availability Trade-offs**<br>
**- Operational Layer (Strong Consistency):** The core transactions and ledger are optimized for ACID compliance. We use SELECT FOR UPDATE to lock balance rows during atomic operations, ensuring that the system never allows an overdraft or race condition during high-concurrency periods.<br>
**- Reporting Layer (Eventual Consistency):** To protect the OLTP performance, we decouple reporting via Change Data Capture (CDC). Reporting queries are routed to an OLAP engine (ClickHouse), accepting sub-second latency in exchange for massive scalability and complex analytical throughput.<br>
**3. Evolutionary Data Contracts (The "Safe-Migration" Doctrine)**<br>
We treat our database schema as a public API. To support zero-downtime evolution:<br>
**- Expand-Contract Migration:** No destructive operations (e.g., DROP COLUMN) are permitted. Changes follow the cycle: Add (NULL) $\rightarrow$ Backfill $\rightarrow$ Constraint (NOT VALID) $\rightarrow$ Validate $\rightarrow$ Set NOT NULL.<br>
**- Consumer Protection:** We utilize a Schema Registry and contract testing (Pact). Downstream microservices must be validated against schema snapshots before any deployment that alters the transactions table.<br>
**- Idempotent DDL:** Every migration script is idempotent (using IF NOT EXISTS or standard Flyway versioning), ensuring that partial failures in CI/CD pipelines do not leave the database in an inconsistent state.
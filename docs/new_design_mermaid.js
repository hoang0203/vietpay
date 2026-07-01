flowchart TD
    %% Define layer format
    classDef client fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px;
    classDef cache fill:#fce4ec,stroke:#e91e63,stroke-width:2px;
    classDef db fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px;
    classDef stream fill:#fff3e0,stroke:#ff9800,stroke-width:2px;
    classDef olap fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;

    subgraph AppLayer [Application layer]
        REQ([API Request]):::client
        REDIS[(Redis Cache)]:::cache
    end

    subgraph OLTPLayer [Operation layer]
        PG[(PostgreSQL)]:::db
    end

    subgraph StreamingLayer [Streaming layer]
        DBZ(Debezium CDC):::stream
        KAFKA{{Apache Kafka}}:::stream
        SPARK(PySpark):::stream
    end

    subgraph OLAPLayer [Reporting layer]
        CH[(ClickHouse)]:::olap
    end

    %% Data flow
    REQ -->|1. Check Idempotency / Cache| REDIS
    REDIS -->|2. Process to DB| PG
    PG -.->|3. Read WAL| DBZ
    DBZ -->|4. Produce Events| KAFKA
    KAFKA -->|5. Consume & Transform| SPARK
    SPARK -->|6. Batch/Stream Insert| CH
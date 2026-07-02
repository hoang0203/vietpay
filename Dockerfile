# 1. Explicitly pin to bookworm to guarantee OpenJDK 17 availability
FROM python:3.11-slim-bookworm

# 2. Cài đặt Java, curl, và bổ sung procps (lệnh ps cho Spark), ca-certificates, wget (để tải file)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    procps \
    ca-certificates \
    wget \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /app

# 3. Cài đặt Python dependencies (PySpark sẽ được cài đặt qua file này)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Tải sẵn các thư viện JAR của Kafka và ClickHouse thẳng vào thư mục jars của PySpark
RUN wget -q https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar -P /usr/local/lib/python3.11/site-packages/pyspark/jars/ && \
    wget -q https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar -P /usr/local/lib/python3.11/site-packages/pyspark/jars/ && \
    wget -q https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.0/spark-token-provider-kafka-0-10_2.12-3.5.0.jar -P /usr/local/lib/python3.11/site-packages/pyspark/jars/ && \
    wget -q https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar -P /usr/local/lib/python3.11/site-packages/pyspark/jars/ && \
    wget -q https://repo1.maven.org/maven2/com/clickhouse/spark/clickhouse-spark-runtime-3.5_2.12/0.10.0/clickhouse-spark-runtime-3.5_2.12-0.10.0.jar -P /usr/local/lib/python3.11/site-packages/pyspark/jars/

ENTRYPOINT ["./entrypoint.sh"]
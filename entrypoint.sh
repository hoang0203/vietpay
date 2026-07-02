#!/bin/bash

echo "⏳ Waiting for Debezium Connect to be fully ready..."
# Loop until Debezium endpoint responds with a 200 status code
until curl -s -o /dev/null -w "%{http_code}" http://debezium:8083/connectors | grep -q "200"; do
  sleep 3
done

echo "🚀 Debezium is up! Registering the PostgreSQL connector..."
python register_connector.py

echo "🛠️ Ensuring Kafka topic exists before Spark starts..."
python create_topic.py

echo "📧 Starting Email Worker Service in the background..."
python -u streaming_ledger.py > /dev/stdout 2>&1 &

echo "📊 Starting PySpark Streaming Application..."
python -u streaming_transactions.py > /dev/stdout 2>&1
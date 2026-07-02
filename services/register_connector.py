import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv("DEBEZIUM_API_URL", "http://debezium:8083/connectors")
connector_name = "double-ledger-connector"

url = f"{base_url.rstrip('/')}/{connector_name}/config"

payload = {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": os.getenv("POSTGRES_USERNAME"),
    "database.password": os.getenv("POSTGRES_PASSWORD"),
    "database.dbname": os.getenv("POSTGRES_DB_NAME"),
    "topic.prefix": "pgstream",
    "table.include.list": "operation.ledger_lines,operation.transactions",
    "decimal.handling.mode": "string",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_slot",
    "publication.name": "dbz_publication",
    "publication.autocreate.mode": "disabled",
    "snapshot.mode": "initial" 
}

req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode('utf-8'), 
    headers={'Content-Type': 'application/json'},
    method='PUT'
)

try:
    response = urllib.request.urlopen(req)
    print(f"✅ Connector '{connector_name}' successfully configured!")
    print(response.read().decode('utf-8'))
except Exception as e:
    print(f"❌ Error configuring Connector: {e}")
    
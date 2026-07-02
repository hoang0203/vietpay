from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import time

KAFKA_SERVER = "kafka:29092" 
TOPICS = [
    "pgstream.operation.ledger_lines",
    "pgstream.operation.transactions"
]

print(f"⏳ Connecting to Kafka at {KAFKA_SERVER}...")

# Retry loop 
connected = False
while not connected:
    try:
        admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_SERVER, client_id='init_script')
        connected = True
    except Exception:
        print("Kafka not ready yet, retrying in 3 seconds...")
        time.sleep(3)

print("🚀 Kafka is up! Attempting to create topics...")

for topic_name in TOPICS:
    try:
        
        topic = NewTopic(name=topic_name, num_partitions=3, replication_factor=1)
        admin_client.create_topics(new_topics=[topic], validate_only=False)
        print(f"✅ Topic '{topic_name}' created successfully!")
    except TopicAlreadyExistsError:
        print(f"👍 Topic '{topic_name}' already exists.")
    except Exception as e:
        print(f"⚠️ Could not create topic {topic_name}: {e}")

admin_client.close()

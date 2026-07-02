import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp
from pyspark.sql.types import StructType, StringType
from dotenv import load_dotenv

load_dotenv()
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVER", "kafka:29092")

os.environ['PYSPARK_SUBMIT_ARGS'] = 'pyspark-shell'

def write_to_clickhouse(batch_df, batch_id):
    batch_df.write \
            .format("console") \
            .option("truncate", "false") \
            .mode("append") \
            .save()
    batch_df.write \
        .format("clickhouse") \
        .mode("append") \
        .option("host", "clickhouse") \
        .option("port", "8123") \
        .option("database", "vietpay") \
        .option("user", os.getenv("CLICKHOUSE_USER")) \
        .option("password", os.getenv("CLICKHOUSE_PASSWORD")) \
        .option("table", "ledger_lines") \
        .save()
        
spark = SparkSession.builder \
    .appName("PostgresCDC_Streaming_To_ClickHouse") \
    .config("spark.sql.session.timeZone", "UTC") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")


ledger_schema = StructType() \
    .add("id", StringType()) \
    .add("transaction_id", StringType()) \
    .add("account_id", StringType()) \
    .add("amount", StringType()) \
    .add("currency", StringType()) \
    .add("created_at", StringType())

kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_SERVER) \
    .option("subscribe", "pgstream.operation.ledger_lines") \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .load()

# Parse JSON from Debezium
debezium_schema = StructType().add("payload", StructType().add("after", ledger_schema))

final_df = kafka_df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), debezium_schema).alias("data")) \
    .select("data.payload.after.*") \
    .withColumn("amount", col("amount").cast("decimal(19,4)")) \
    .withColumn("created_at", to_timestamp(col("created_at")))

query = final_df.writeStream \
    .foreachBatch(write_to_clickhouse) \
    .option("checkpointLocation", "/tmp/checkpoints/ledger_lines/") \
    .start()

query.awaitTermination()

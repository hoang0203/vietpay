import os
import sys

from dotenv import load_dotenv

from tools.py_flyway_postgresql import PyFlyway as PostgresFlyway 
from tools.py_flyway_clickhouse import PyFlyway as ClickhouseFlyway 

load_dotenv(override=True)

SERVER_NAME = f"localhost"
# PostgreSQL Configs
PORT_POSTGRESQL = 5432
DB_USER_POSTGRESQL = os.getenv("POSTGRES_USERNAME")
DB_PASSWORD_POSTGRESQL = os.getenv("POSTGRES_PASSWORD")
DB_NAME_POSTGRESQL = os.getenv("POSTGRES_DB_NAME")

# ClickHouse Configs
PORT_CLICKHOUSE = 9002 
DB_USER_CLICKHOUSE = os.getenv("CLICKHOUSE_USER")
DB_PASSWORD_CLICKHOUSE = os.getenv("CLICKHOUSE_PASSWORD")
DB_NAME_CLICKHOUSE = os.getenv("CLICKHOUSE_DB")

def run_custom_flyway(action, db_type, db_name):
    print(f"\n🚀 [{action.upper()}] Database: {db_name} ({db_type.upper()})...")
    
    
    if db_type == "postgresql":
        folders = [
            "sql/postgresql/migrations",
            "sql/postgresql/programmability/functions",
            "sql/postgresql/programmability/views",
            "sql/postgresql/programmability/procedures"
        ]
        tool = PostgresFlyway(SERVER_NAME, db_name, DB_USER_POSTGRESQL, DB_PASSWORD_POSTGRESQL, PORT_POSTGRESQL)
        
    elif db_type == "clickhouse":
        folders = [
            "sql/clickhouse/migrations",
            "sql/clickhouse/programmability/views"
        ]
        tool = ClickhouseFlyway(SERVER_NAME, db_name, DB_USER_CLICKHOUSE, DB_PASSWORD_CLICKHOUSE, PORT_CLICKHOUSE)
        
    else:
        print(f"❌ Unsupported database type: {db_type}")
        return False

    try:
        if action == "migrate":
            tool.migrate(folders)
            print(f"✅ Successed: {db_name}")
        elif action == "clean":
            tool.clean()
            print(f"✅ Cleaned: {db_name}")
            
        tool.close()
        return True
    except Exception as e:
        print(f"❌ Failed: {db_name}")
        print(str(e))
        if 'tool' in locals():
            try:
                tool.close()
            except:
                pass
        return False

def start_promotion_flow():
    # PostgreSQL Migration
    print("-" * 40)
    print("STEP 1: POSTGRESQL MIGRATION")
    if not run_custom_flyway("migrate", "postgresql", DB_NAME_POSTGRESQL):
        print("\n🚨 PostgreSQL migration failed! Halting the process.")
        sys.exit(1)
        
    # ClickHouse Migration
    print("-" * 40)
    print("STEP 2: CLICKHOUSE MIGRATION")
    if not run_custom_flyway("migrate", "clickhouse", DB_NAME_CLICKHOUSE):
        print("\n🚨 ClickHouse migration failed! Halting the process.")
        sys.exit(1)

    print("\n🎉 Finished all migrations successfully.")
    sys.exit(0)

if __name__ == "__main__":
    start_promotion_flow()
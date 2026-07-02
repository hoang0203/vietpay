import os
import re
import hashlib
import time
from clickhouse_driver import Client
from clickhouse_driver.errors import Error as ClickHouseError

class PyFlyway:
    def __init__(self, host, database, username, password, port=9002):
        # 1. Establish ClickHouse connection (Native TCP Port defaults to 9000)
        print(f"Connecting to ClickHouse -> HOST={host} DB={database}")
        self.client = Client(
            host=host,
            database=database,
            user=username,
            password=password,
            port=port
        )
        self.history_table = "pyflyway_schema_history"
        self._ensure_history_table()

    def _ensure_history_table(self):
        """Create the history table using ClickHouse MergeTree engine"""
        # Note: ClickHouse uses specific types (String, DateTime, UInt8 for boolean)
        # and requires an ENGINE definition.
        sql_script = f"""
        CREATE TABLE IF NOT EXISTS {self.history_table} (
            version String,
            description String,
            script String,
            checksum String,
            installed_on DateTime DEFAULT now(),
            execution_time_ms UInt32,
            success UInt8
        ) ENGINE = MergeTree()
        ORDER BY script;
        """
        self.client.execute(sql_script)

    def _calculate_checksum(self, file_path):
        """Calculate MD5 hash of file content"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_applied_migrations(self):
        """Get list of successfully executed files"""
        result = self.client.execute(f"SELECT script, checksum FROM {self.history_table} WHERE success = 1")
        return {row[0]: row[1] for row in result}

    def _execute_and_log(self, file_path, file_name, checksum, version, description, action="INSERT"):
        """Executes the ClickHouse script and logs the result."""
        if action == "INSERT":
            print(f"  -> 🚀 Applying: {file_name}...")
            
        start_time = time.time()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. Execute the actual SQL script
            if content.strip():
                # ClickHouse execute doesn't natively handle multiple statements separated by ';' well
                # if they are complex DDL. It's best to split them or ensure single-statement files.
                statements = [s.strip() for s in content.split(';') if s.strip()]
                for stmt in statements:
                    self.client.execute(stmt)
                
            exec_time = int((time.time() - start_time) * 1000)
            
            # 2. Log SUCCESS
            if action == "INSERT":
                query = f"""
                    INSERT INTO {self.history_table} 
                    (version, description, script, checksum, execution_time_ms, success)
                    VALUES 
                """
                # clickhouse_driver uses sequence of dictionaries or tuples for inserts
                self.client.execute(query, [{
                    'version': version or '', 
                    'description': description, 
                    'script': file_name, 
                    'checksum': checksum, 
                    'execution_time_ms': exec_time, 
                    'success': 1
                }])
            elif action == "UPDATE":
                # ClickHouse UPDATE is an asynchronous mutation. We use mutations_sync to wait for it.
                query = f"""
                    ALTER TABLE {self.history_table} 
                    UPDATE checksum = %(checksum)s, execution_time_ms = %(exec_time)s, installed_on = now(), success = 1
                    WHERE script = %(script)s
                    SETTINGS mutations_sync = 2
                """
                self.client.execute(query, {'checksum': checksum, 'exec_time': exec_time, 'script': file_name})
                
        except ClickHouseError as e:
            # 🚨 1. ERROR OCCURRED: No Rollback in ClickHouse!
            exec_time = int((time.time() - start_time) * 1000)
            print(f"  -> ❌ Failed: {file_name}. No rollback available in ClickHouse. Manual cleanup may be required.")
            
            # 🚨 2. Log the FAILURE
            try:
                if action == "INSERT":
                    fail_query = f"INSERT INTO {self.history_table} (version, description, script, checksum, execution_time_ms, success) VALUES"
                    self.client.execute(fail_query, [{
                        'version': version or '', 'description': description, 'script': file_name, 
                        'checksum': checksum, 'execution_time_ms': exec_time, 'success': 0
                    }])
                elif action == "UPDATE":
                    fail_query = f"""
                        ALTER TABLE {self.history_table} 
                        UPDATE checksum = %(checksum)s, execution_time_ms = %(exec_time)s, installed_on = now(), success = 0
                        WHERE script = %(script)s
                        SETTINGS mutations_sync = 2
                    """
                    self.client.execute(fail_query, {'checksum': checksum, 'exec_time': exec_time, 'script': file_name})
            except Exception as log_error:
                print(f"     ⚠️ Could not log failure to history table: {log_error}")

            raise Exception(f"❌ SQL Error in {file_name}:\n{e}")
        
    def migrate(self, folder_paths):
        """Execute SQL files (Supports Versioned 'V' and Repeatable 'R')"""
        applied_migrations = self._get_applied_migrations()
        versioned_scripts = []
        repeatable_scripts = []
        
        # SCAN AND FILTER
        for folder in folder_paths:
            if not os.path.exists(folder):
                continue
            for file in os.listdir(folder):
                if not file.endswith(".sql"):
                    continue 
                
                file_path = os.path.join(folder, file)
                
                v_match = re.match(r"^V([\d\.]+)__(.+)\.sql$", file)
                r_match = re.match(r"^R__(.+)\.sql$", file)

                if v_match:
                    version = v_match.group(1)
                    description = v_match.group(2).replace("_", " ")
                    version_tuple = tuple(map(int, version.split('.')))
                    versioned_scripts.append((version_tuple, file_path, file, version, description))
                elif r_match:
                    description = r_match.group(1).replace("_", " ")
                    repeatable_scripts.append((file_path, file, description))

        # SORT
        versioned_scripts.sort(key=lambda x: x[0])  
        repeatable_scripts.sort(key=lambda x: x[1]) 
        
        # EXECUTE VERSIONED
        for _, file_path, file_name, version, description in versioned_scripts:
            current_checksum = self._calculate_checksum(file_path)

            if file_name in applied_migrations:
                if applied_migrations[file_name] != current_checksum:
                    raise Exception(f"🚨 CHECK_SUM_ERROR: Versioned file '{file_name}' was changed. Create a new version!")
                continue

            self._execute_and_log(file_path, file_name, current_checksum, version, description, "INSERT")

        # EXECUTE REPEATABLE
        for file_path, file_name, description in repeatable_scripts:
            current_checksum = self._calculate_checksum(file_path)

            if file_name in applied_migrations:
                if applied_migrations[file_name] == current_checksum:
                    continue 
                else:
                    print(f"  -> 🔄 Repeatable script changed. Re-applying: {file_name}...")
                    self._execute_and_log(file_path, file_name, current_checksum, None, description, "UPDATE")
            else:
                self._execute_and_log(file_path, file_name, current_checksum, None, description, "INSERT")

    def clean(self):
        """Drops all tables/views by dropping and recreating the database (ClickHouse way)"""
        print("  -> 🧹 Cleaning ClickHouse database...")
        try:
            # Note: Proceed with extreme caution. 
            # In ClickHouse, schemas are equivalent to databases.
            db_name = self.client.connection.database
            
            # Switch to default to safely drop the target database
            self.client.execute("USE default")
            self.client.execute(f"DROP DATABASE IF EXISTS {db_name} SYNC")
            self.client.execute(f"CREATE DATABASE {db_name}")
            self.client.execute(f"USE {db_name}")
            
            print("  -> 🧹 Clean completed.")
        except ClickHouseError as e:
            raise Exception(f"❌ Error while cleaning DB:\n{e}")

    def close(self):
        self.client.disconnect()
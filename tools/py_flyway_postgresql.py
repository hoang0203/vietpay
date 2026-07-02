import os
import re
import hashlib
import time

import psycopg2
from psycopg2 import sql

class PyFlyway:
    def __init__(self, host, database, username, password, port=5432):
        # 1. Establish PostgreSQL connection using psycopg2
        print(f"Connecting to PostgreSQL -> HOST={host} DB={database}")
        self.conn = psycopg2.connect(
            host=host,
            database=database,
            user=username,
            password=password,
            port=port
        )
        # Turn off autocommit so we can safely rollback failed migrations
        self.conn.autocommit = False 
        self.cursor = self.conn.cursor()
        self.history_table = "pyflyway_schema_history"
        self._ensure_history_table()

    def _ensure_history_table(self):
        """Create the history table if it does not exist (PostgreSQL syntax)"""
        sql_script = f"""
        CREATE TABLE IF NOT EXISTS {self.history_table} (
            installed_rank SERIAL PRIMARY KEY,
            version VARCHAR(50),
            description VARCHAR(200),
            script VARCHAR(1000) NOT NULL,
            checksum VARCHAR(32) NOT NULL,
            installed_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            execution_time_ms INT,
            success BOOLEAN NOT NULL
        );
        """
        self.cursor.execute(sql_script)
        self.conn.commit()

    def _calculate_checksum(self, file_path):
        """Calculate MD5 hash of file content"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_applied_migrations(self):
        """Get list of successfully executed files"""
        self.cursor.execute(f"SELECT script, checksum FROM {self.history_table} WHERE success = true")
        # psycopg2 returns tuples by default, so we use row[0] and row[1]
        return {row[0]: row[1] for row in self.cursor.fetchall()}

    def _execute_and_log(self, file_path, file_name, checksum, version, description, action="INSERT"):
        """Executes the PostgreSQL script with strict transaction and failure logging."""
        if action == "INSERT":
            print(f"  -> 🚀 Applying: {file_name}...")
            
        start_time = time.time()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. Execute the actual SQL script
            if content.strip():
                self.cursor.execute(content)
                
            exec_time = int((time.time() - start_time) * 1000)
            
            # 2. If it succeeds, log the SUCCESS in the history table
            if action == "INSERT":
                query = f"""
                    INSERT INTO {self.history_table} 
                    (version, description, script, checksum, execution_time_ms, success)
                    VALUES (%s, %s, %s, %s, %s, true)
                """
                self.cursor.execute(query, (version, description, file_name, checksum, exec_time))
            elif action == "UPDATE":
                query = f"""
                    UPDATE {self.history_table} 
                    SET checksum = %s, execution_time_ms = %s, installed_on = CURRENT_TIMESTAMP, success = true
                    WHERE script = %s
                """
                self.cursor.execute(query, (checksum, exec_time, file_name))
                
            # 3. Commit BOTH the schema changes and the history log together
            self.conn.commit()
            
        except Exception as e:
            # 🚨 1. ERROR OCCURRED: Rollback the broken database changes immediately!
            self.conn.rollback()
            
            exec_time = int((time.time() - start_time) * 1000)
            print(f"  -> ❌ Failed: {file_name}. Rolling back and logging failure...")
            
            # 🚨 2. Log the FAILURE in the history table (requires a fresh transaction)
            try:
                if action == "INSERT":
                    fail_query = f"""
                        INSERT INTO {self.history_table} 
                        (version, description, script, checksum, execution_time_ms, success)
                        VALUES (%s, %s, %s, %s, %s, false)
                    """
                    self.cursor.execute(fail_query, (version, description, file_name, checksum, exec_time))
                elif action == "UPDATE":
                    fail_query = f"""
                        UPDATE {self.history_table} 
                        SET checksum = %s, execution_time_ms = %s, installed_on = CURRENT_TIMESTAMP, success = false
                        WHERE script = %s
                    """
                    self.cursor.execute(fail_query, (checksum, exec_time, file_name))
                    
                self.conn.commit() # Commit the failure log
            except Exception as log_error:
                self.conn.rollback()
                print(f"     ⚠️ Could not log failure to history table: {log_error}")

            # 🚨 3. Halt the Python execution so you can fix the SQL file
            raise Exception(f"❌ SQL Error in {file_name}:\n{e}")
        
    def migrate(self, folder_paths):
        """Execute SQL files (Supports Versioned 'V' and Repeatable 'R')"""
        applied_migrations = self._get_applied_migrations()
        versioned_scripts = []
        repeatable_scripts = []
        
        # 1. SCAN AND FILTER FILES
        for folder in folder_paths:
            if not os.path.exists(folder):
                continue
            for file in os.listdir(folder):
                if not file.endswith(".sql"):
                    continue 
                
                file_path = os.path.join(folder, file)
                
                # Regex classification
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

        # 2. SORT
        versioned_scripts.sort(key=lambda x: x[0])  
        repeatable_scripts.sort(key=lambda x: x[1]) 
        
        # 3. EXECUTE VERSIONED MIGRATIONS
        for _, file_path, file_name, version, description in versioned_scripts:
            current_checksum = self._calculate_checksum(file_path)

            if file_name in applied_migrations:
                if applied_migrations[file_name] != current_checksum:
                    raise Exception(f"🚨 CHECK_SUM_ERROR: Versioned file '{file_name}' was changed after execution. Create a new version (V...) instead of altering the old file!")
                continue

            self._execute_and_log(file_path, file_name, current_checksum, version, description, "INSERT")

        # 4. EXECUTE REPEATABLE MIGRATIONS
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
        """Drops all objects in the Database by cascading schemas"""
        print("  -> 🧹 Cleaning database objects...")
        try:
            # In PostgreSQL, the safest and cleanest way to drop all tables, views, 
            # and functions is to drop the schemas with CASCADE, then recreate them.
            self.cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast') 
                AND schema_name NOT LIKE 'pg_temp_%' 
                AND schema_name NOT LIKE 'pg_toast_temp_%';
            """)
            
            schemas = self.cursor.fetchall()
            for schema in schemas:
                schema_name = schema[0]
                # Drop all objects inside the schema
                self.cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")
                # Recreate the empty schema
                self.cursor.execute(f"CREATE SCHEMA {schema_name};")
            
            self.conn.commit()
            print("  -> 🧹 Clean completed.")
        except psycopg2.Error as e:
            self.conn.rollback()
            raise Exception(f"❌ Error while cleaning DB:\n{e}")

    def close(self):
        self.cursor.close()
        self.conn.close()
        
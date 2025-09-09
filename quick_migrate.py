#!/usr/bin/env python3
"""
Quick Database Migration Script
Automatically creates a fresh database and runs migrations without user input.
"""

import os
import subprocess
from sqlalchemy import create_engine, text

# Database configuration
MYSQL_USER = os.getenv("MYSQL_USER", "response_collector_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "morashark")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
DB_NAME = "stress_management"

def main():
    print("🚀 Quick Database Migration Starting...")
    print("=" * 50)
    
    try:
        # Step 1: Create fresh database
        print("1️⃣ Creating fresh database...")
        connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}"
        engine = create_engine(connection_string, echo=False)
        
        with engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{DB_NAME}`"))
            conn.execute(text(f"CREATE DATABASE `{DB_NAME}`"))
            conn.commit()
        engine.dispose()
        print(f"✅ Fresh database '{DB_NAME}' created successfully")
        
        # Step 2: Run migration
        print("2️⃣ Running fresh schema migration...")
        env = os.environ.copy()
        env["MYSQL_DB"] = DB_NAME
        
        alembic_path = os.path.join(os.path.dirname(__file__), "venv", "bin", "alembic")
        result = subprocess.run(
            [alembic_path, "upgrade", "fresh_schema_001"],
            cwd=".",
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Migration completed successfully!")
            print("🎉 Database is ready!")
            print(f"💡 Set MYSQL_DB={DB_NAME} to use the new database")
            print("🚀 Your server is now ready to start!")
        else:
            print("❌ Migration failed:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main() 
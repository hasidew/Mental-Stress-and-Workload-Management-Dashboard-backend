#!/usr/bin/env python3
"""
Script to migrate to a fresh database by resetting migration history
and running all migrations from scratch.
"""

import os
import sys
import subprocess
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Database configuration
MYSQL_USER = os.getenv("MYSQL_USER", "response_collector_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "morashark")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")

def create_fresh_database(db_name):
    """Create a fresh database, dropping existing one if it exists."""
    # Connect to MySQL server (without specifying database)
    connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}"
    
    try:
        engine = create_engine(connection_string, echo=False)
        with engine.connect() as conn:
            # Drop database if it exists and create a fresh one
            conn.execute(text(f"DROP DATABASE IF EXISTS `{db_name}`"))
            conn.execute(text(f"CREATE DATABASE `{db_name}`"))
            conn.commit()
            print(f"✅ Fresh database '{db_name}' created successfully")
        engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

def reset_migration_history(db_name):
    """Reset the migration history by dropping and recreating alembic_version table."""
    connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{db_name}"
    
    try:
        engine = create_engine(connection_string, echo=False)
        with engine.connect() as conn:
            # Drop alembic_version table if it exists
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
            print("✅ Migration history reset")
        engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Error resetting migration history: {e}")
        return False

def run_migrations(db_name):
    """Run fresh schema migration."""
    try:
        # Check if fresh_schema_001 migration exists
        migration_file = os.path.join(os.path.dirname(__file__), "alembic", "versions", "fresh_schema_001.py")
        if not os.path.exists(migration_file):
            print("❌ fresh_schema_001.py migration file not found!")
            print("Please ensure the fresh schema migration exists.")
            return False
        
        # Set the database environment variable
        env = os.environ.copy()
        env["MYSQL_DB"] = db_name
        
        # Run alembic upgrade to our fresh schema migration
        alembic_path = os.path.join(os.path.dirname(__file__), "venv", "bin", "alembic")
        result = subprocess.run(
            [alembic_path, "upgrade", "fresh_schema_001"],
            cwd=".",
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Fresh schema migration completed successfully")
            print("Migration output:")
            print(result.stdout)
        else:
            print("❌ Migration failed")
            print("Error output:")
            print(result.stderr)
            return False
            
        return True
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        return False

def main():
    print("🔄 Database Migration to Fresh Database")
    print("=" * 50)
    
    # Get database name from user or use default
    default_db = "stress_management"
    db_name = input(f"Enter new database name (default: {default_db}): ").strip()
    if not db_name:
        db_name = default_db
    
    print(f"\n📋 Target database: {db_name}")
    print(f"📋 Host: {MYSQL_HOST}:{MYSQL_PORT}")
    print(f"📋 User: {MYSQL_USER}")
    
    # Confirm before proceeding
    confirm = input("\n⚠️  This will create a fresh database and run the clean schema migration. Continue? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Migration cancelled")
        return
    
    print("\n🚀 Starting migration process...")
    
    # Step 1: Create fresh database
    print("\n1️⃣ Creating fresh database...")
    if not create_fresh_database(db_name):
        print("❌ Failed to create database. Exiting.")
        return
    
    # Step 2: Reset migration history
    print("\n2️⃣ Resetting migration history...")
    if not reset_migration_history(db_name):
        print("❌ Failed to reset migration history. Exiting.")
        return
    
    # Step 3: Run all migrations
    print("\n3️⃣ Running all migrations...")
    if not run_migrations(db_name):
        print("❌ Failed to run migrations. Exiting.")
        return
    
    print("\n🎉 Migration completed successfully!")
    print(f"📊 Fresh database '{db_name}' is ready with all tables and data structures.")
    
    # Update environment variable for future use
    print(f"\n💡 To use the new database, set MYSQL_DB={db_name}")
    print("   Or update your .env file or environment variables.")
    print("\n🚀 Your server is now ready to start!")

if __name__ == "__main__":
    main() 
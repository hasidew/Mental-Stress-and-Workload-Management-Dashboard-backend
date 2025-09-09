#!/bin/bash

# Quick Database Setup Script
# This script sets up a fresh database in one command

set -e

echo "🚀 Quick Database Setup Starting..."
echo "=================================="

# Database configuration
DB_USER=${MYSQL_USER:-"response_collector_user"}
DB_PASS=${MYSQL_PASSWORD:-"morashark"}
DB_HOST=${MYSQL_HOST:-"localhost"}
DB_PORT=${MYSQL_PORT:-"3306"}
DB_NAME="stress_management"

# Step 1: Create fresh database
echo "1️⃣ Creating fresh database..."
mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" -e "DROP DATABASE IF EXISTS \`$DB_NAME\`; CREATE DATABASE \`$DB_NAME\`;"
echo "✅ Fresh database '$DB_NAME' created successfully"

# Step 2: Run migration
echo "2️⃣ Running fresh schema migration..."
export MYSQL_DB="$DB_NAME"
source venv/bin/activate
alembic upgrade fresh_schema_001

echo "✅ Migration completed successfully!"
echo "🎉 Database is ready!"
echo "💡 Set MYSQL_DB=$DB_NAME to use the new database"
echo "🚀 Your server is now ready to start!" 
#!/bin/bash

# Database Migration Reset Script
# This script creates a fresh database and runs all migrations from scratch

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database configuration
DB_USER=${MYSQL_USER:-"response_collector_user"}
DB_PASS=${MYSQL_PASSWORD:-"morashark"}
DB_HOST=${MYSQL_HOST:-"localhost"}
DB_PORT=${MYSQL_PORT:-"3306"}
DB_NAME=${MYSQL_DB:-"stress_management_fresh"}

echo -e "${BLUE}🔄 Database Migration Reset Script${NC}"
echo "=========================================="
echo -e "${YELLOW}Target Database:${NC} $DB_NAME"
echo -e "${YELLOW}Host:${NC} $DB_HOST:$DB_PORT"
echo -e "${YELLOW}User:${NC} $DB_USER"
echo ""

# Confirm before proceeding
read -p "⚠️  This will create a new database and run ALL migrations from scratch. Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Migration cancelled${NC}"
    exit 1
fi

echo -e "\n${BLUE}🚀 Starting migration process...${NC}"

# Step 1: Create fresh database
echo -e "\n${BLUE}1️⃣ Creating fresh database...${NC}"
mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`;"
echo -e "${GREEN}✅ Database '$DB_NAME' created successfully${NC}"

# Step 2: Reset migration history
echo -e "\n${BLUE}2️⃣ Resetting migration history...${NC}"
mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "DROP TABLE IF EXISTS alembic_version;"
echo -e "${GREEN}✅ Migration history reset${NC}"

# Step 3: Run all migrations
echo -e "\n${BLUE}3️⃣ Running all migrations...${NC}"
export MYSQL_DB="$DB_NAME"
alembic upgrade head

echo -e "\n${GREEN}🎉 Migration completed successfully!${NC}"
echo -e "${GREEN}📊 New database '$DB_NAME' is ready with all tables and data structures.${NC}"
echo ""
echo -e "${YELLOW}💡 To use the new database, set:${NC}"
echo -e "   export MYSQL_DB=$DB_NAME"
echo -e "   Or update your .env file or environment variables." 
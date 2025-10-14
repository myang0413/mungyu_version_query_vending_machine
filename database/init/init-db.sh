#!/bin/bash
set -e

# 데이터베이스 복원
echo "Restoring database from /docker-entrypoint-initdb.d/dvdrental.tar..."
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" /docker-entrypoint-initdb.d/dvdrental.tar

# pgvector 확장 활성화
echo "Creating pgvector extension..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "DVD Rental database and pgvector extension created successfully."
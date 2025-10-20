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

# 벡터 임베딩 테이블 생성
echo "Creating vector embedding tables..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Film 벡터 임베딩 테이블 (영화 제목 + 설명)
    CREATE TABLE IF NOT EXISTS film_embeddings (
        film_id INTEGER PRIMARY KEY REFERENCES film(film_id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        embedding vector(1536)
    );
    CREATE INDEX IF NOT EXISTS film_embeddings_idx ON film_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

    -- Actor 벡터 임베딩 테이블 (배우 이름 + 출연 영화)
    CREATE TABLE IF NOT EXISTS actor_embeddings (
        actor_id INTEGER PRIMARY KEY REFERENCES actor(actor_id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        embedding vector(1536)
    );
    CREATE INDEX IF NOT EXISTS actor_embeddings_idx ON actor_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

    -- Customer 벡터 임베딩 테이블 (고객 정보)
    CREATE TABLE IF NOT EXISTS customer_embeddings (
        customer_id INTEGER PRIMARY KEY REFERENCES customer(customer_id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        embedding vector(1536)
    );
    CREATE INDEX IF NOT EXISTS customer_embeddings_idx ON customer_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

    -- Category 벡터 임베딩 테이블 (카테고리 + 영화 목록)
    CREATE TABLE IF NOT EXISTS category_embeddings (
        category_id INTEGER PRIMARY KEY REFERENCES category(category_id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        embedding vector(1536)
    );
    CREATE INDEX IF NOT EXISTS category_embeddings_idx ON category_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

    -- 통합 검색을 위한 전체 데이터 벡터 테이블
    CREATE TABLE IF NOT EXISTS unified_embeddings (
        id SERIAL PRIMARY KEY,
        source_table VARCHAR(50) NOT NULL,
        source_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding vector(1536),
        metadata JSONB
    );
    CREATE INDEX IF NOT EXISTS unified_embeddings_idx ON unified_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    CREATE INDEX IF NOT EXISTS unified_embeddings_source_idx ON unified_embeddings(source_table, source_id);
EOSQL

echo "DVD Rental database, pgvector extension, and vector tables created successfully."
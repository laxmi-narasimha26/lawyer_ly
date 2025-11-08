-- Advanced Legal KB RAG schema aligned with 2020 chunk pipeline outputs
\set ON_ERROR_STOP on

-- Enable required extensions (idempotent – safe if run twice)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Ensure updated_at auto-maintenance helper exists
CREATE OR REPLACE FUNCTION set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------------

-- Supreme Court judgment chunks (2020 cohort)
CREATE TABLE IF NOT EXISTS judgment_chunks (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type = 'judgment_window'),
    "order" INTEGER NOT NULL,
    text TEXT NOT NULL,
    tokens INTEGER NOT NULL CHECK (tokens BETWEEN 80 AND 800),
    overlap_tokens INTEGER NOT NULL CHECK (overlap_tokens BETWEEN 0 AND 80),
    case_title TEXT,
    decision_date DATE,
    bench JSONB NOT NULL DEFAULT '[]'::jsonb,
    citation_strings JSONB NOT NULL DEFAULT '[]'::jsonb,
    para_range TEXT,
    source_path TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, "order"),
    UNIQUE (sha256)
);

DROP TRIGGER IF EXISTS trg_judgment_chunks_updated_at ON judgment_chunks;
CREATE TRIGGER trg_judgment_chunks_updated_at
BEFORE UPDATE ON judgment_chunks
FOR EACH ROW
EXECUTE FUNCTION set_current_timestamp_updated_at();

-- Statute chunks (BNS 2023)
CREATE TABLE IF NOT EXISTS statute_chunks (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type = 'statute_unit'),
    "order" NUMERIC(10,2) NOT NULL,
    act TEXT NOT NULL,
    year INTEGER NOT NULL,
    section_no TEXT NOT NULL,
    unit_type TEXT NOT NULL CHECK (unit_type IN ('Section', 'Sub-section', 'Illustration', 'Explanation', 'Proviso')),
    title TEXT,
    text TEXT NOT NULL,
    tokens INTEGER NOT NULL CHECK (tokens BETWEEN 1 AND 800),
    effective_from DATE NOT NULL,
    effective_to DATE,
    source_path TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, "order"),
    UNIQUE (sha256)
);

DROP TRIGGER IF EXISTS trg_statute_chunks_updated_at ON statute_chunks;
CREATE TRIGGER trg_statute_chunks_updated_at
BEFORE UPDATE ON statute_chunks
FOR EACH ROW
EXECUTE FUNCTION set_current_timestamp_updated_at();

-- Metadata table to track ingestion runs
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_type TEXT NOT NULL CHECK (run_type IN ('judgment', 'statute')),
    source_path TEXT NOT NULL,
    chunks_emitted INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    message TEXT
);

-- ---------------------------------------------------------------------------
-- Indexes and search helpers
-- ---------------------------------------------------------------------------

-- Vector search indexes (HNSW)
CREATE INDEX IF NOT EXISTS ix_judgment_chunks_embedding
    ON judgment_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX IF NOT EXISTS ix_statute_chunks_embedding
    ON statute_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Text search helpers
CREATE INDEX IF NOT EXISTS ix_judgment_chunks_tsv
    ON judgment_chunks USING gin (to_tsvector('english', text));

CREATE INDEX IF NOT EXISTS ix_statute_chunks_tsv
    ON statute_chunks USING gin (to_tsvector('english', text));

-- Common lookup indexes
CREATE INDEX IF NOT EXISTS ix_judgment_chunks_doc_order
    ON judgment_chunks (doc_id, "order");

CREATE INDEX IF NOT EXISTS ix_statute_chunks_doc_order
    ON statute_chunks (doc_id, "order");

-- Hash lookup for dedupe checks
CREATE INDEX IF NOT EXISTS ix_judgment_chunks_sha256
    ON judgment_chunks (sha256);

CREATE INDEX IF NOT EXISTS ix_statute_chunks_sha256
    ON statute_chunks (sha256);

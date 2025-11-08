-- Token-aware Legal Knowledge Base Schema
-- Updated for text-embedding-3-small (1536 dimensions) and token-aware chunking

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Legal documents table (parent documents)
CREATE TABLE legal_documents (
    id VARCHAR(200) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('judgment', 'statute', 'bns', 'constitution')),
    source_file VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Document chunks table (token-aware chunks with embeddings)
CREATE TABLE document_chunks (
    id VARCHAR(200) PRIMARY KEY,
    document_id VARCHAR(200) NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL, -- text-embedding-3-small dimensions
    metadata JSONB DEFAULT '{}', -- Contains token_count, char_count, paragraph_numbers, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Legal citations table
CREATE TABLE legal_citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id VARCHAR(200) NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    citation_text VARCHAR(200) NOT NULL,
    citation_type VARCHAR(50) NOT NULL, -- 'case', 'statute', 'neutral'
    target_document_id VARCHAR(200), -- If we have the referenced document
    created_at TIMESTAMP DEFAULT NOW()
);

-- Legal synonyms for query expansion
CREATE TABLE legal_synonyms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    term VARCHAR(100) NOT NULL,
    synonyms JSONB NOT NULL,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Query cache for performance
CREATE TABLE query_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_hash VARCHAR(64) NOT NULL UNIQUE,
    query_text TEXT NOT NULL,
    query_embedding vector(1536),
    results JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

-- System metrics
CREATE TABLE system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- HNSW indexes for vector similarity search
CREATE INDEX document_chunks_embedding_idx ON document_chunks 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 200);

-- Additional indexes
CREATE INDEX document_chunks_document_id_idx ON document_chunks (document_id);
CREATE INDEX legal_documents_type_idx ON legal_documents (document_type);
CREATE INDEX legal_citations_chunk_id_idx ON legal_citations (chunk_id);
CREATE INDEX legal_citations_type_idx ON legal_citations (citation_type);

-- Full-text search indexes for BM25
CREATE INDEX document_chunks_content_idx ON document_chunks USING gin(to_tsvector('english', content));
CREATE INDEX legal_documents_title_idx ON legal_documents USING gin(to_tsvector('english', title));

-- Query cache indexes
CREATE INDEX query_cache_hash_idx ON query_cache (query_hash);
CREATE INDEX query_cache_expires_idx ON query_cache (expires_at);

-- System metrics indexes
CREATE INDEX system_metrics_name_time_idx ON system_metrics (metric_name, recorded_at);

-- Insert legal synonyms for query expansion
INSERT INTO legal_synonyms (term, synonyms, category) VALUES
('FIR', '["First Information Report", "police complaint", "initial report", "complaint", "cognizance"]', 'procedural'),
('cognizable', '["arrestable", "police powers", "without warrant", "cognisable", "suo moto"]', 'procedural'),
('non-bailable', '["custody", "no bail", "detention", "non bailable", "remand"]', 'procedural'),
('remand', '["custody", "detention", "judicial custody", "police custody", "interim custody"]', 'procedural'),
('SLP', '["Special Leave Petition", "Supreme Court appeal", "special leave", "leave to appeal"]', 'procedural'),
('anticipatory', '["pre-arrest", "advance bail", "protection from arrest", "anticipatory bail", "interim protection"]', 'procedural'),
('locus', '["standing", "legal capacity", "right to sue", "locus standi", "maintainability"]', 'judicial'),
('obiter', '["obiter dicta", "judicial observation", "non-binding", "passing remark", "incidental observation"]', 'judicial'),
('ratio', '["ratio decidendi", "binding principle", "legal principle", "holding", "precedent"]', 'judicial'),
('per incuriam', '["through lack of care", "oversight", "error", "inadvertent", "without due consideration"]', 'judicial'),
('robbery', '["dacoity", "theft with violence", "forcible taking", "extortion", "criminal force"]', 'criminal'),
('theft', '["stealing", "dishonest taking", "larceny", "misappropriation", "criminal breach of trust"]', 'criminal'),
('cheating', '["fraud", "deception", "dishonest inducement", "fraudulent representation", "criminal breach of trust"]', 'criminal'),
('bail', '["release", "surety", "bond", "interim bail", "regular bail", "statutory bail"]', 'procedural'),
('appeal', '["revision", "writ", "petition", "application", "review"]', 'procedural'),
('quash', '["set aside", "annul", "cancel", "declare void", "strike down"]', 'judicial'),
('conviction', '["finding of guilt", "criminal liability", "sentence", "punishment"]', 'criminal'),
('acquittal', '["discharge", "exoneration", "not guilty", "benefit of doubt"]', 'criminal');

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_legal_documents_updated_at BEFORE UPDATE ON legal_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_chunks_updated_at BEFORE UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create function for vector similarity search
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(1536),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 50,
    document_type_filter VARCHAR DEFAULT NULL
)
RETURNS TABLE(
    chunk_id VARCHAR,
    document_id VARCHAR,
    similarity_score FLOAT,
    content TEXT,
    document_title VARCHAR,
    document_type VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id as chunk_id,
        c.document_id,
        1 - (c.embedding <=> query_embedding) as similarity_score,
        c.content,
        d.title as document_title,
        d.document_type
    FROM document_chunks c
    JOIN legal_documents d ON c.document_id = d.id
    WHERE 
        (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
        AND (document_type_filter IS NULL OR d.document_type = document_type_filter)
    ORDER BY c.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Create function for cleaning expired cache entries
CREATE OR REPLACE FUNCTION clean_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM query_cache WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE legal_documents IS 'Parent documents (judgments, statutes, etc.)';
COMMENT ON TABLE document_chunks IS 'Token-aware chunks with embeddings for semantic search';
COMMENT ON TABLE legal_citations IS 'Citations extracted from document chunks';
COMMENT ON TABLE legal_synonyms IS 'Legal terminology synonyms for query expansion';
COMMENT ON TABLE query_cache IS 'Cache for query embeddings and results';
COMMENT ON TABLE system_metrics IS 'System performance and usage metrics';
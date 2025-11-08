-- Migration script to add temporal validity fields to legal_kb database
-- This adds support for as-on date reasoning and temporal filtering

-- Add temporal fields to legal_documents metadata
-- We'll store these in the metadata JSONB field for flexibility

-- Add helper function to extract temporal metadata
CREATE OR REPLACE FUNCTION get_effective_from(doc legal_documents)
RETURNS DATE AS $
BEGIN
    RETURN (doc.metadata->>'effective_from')::DATE;
END;
$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION get_effective_to(doc legal_documents)
RETURNS DATE AS $
BEGIN
    RETURN (doc.metadata->>'effective_to')::DATE;
END;
$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION get_decision_date(doc legal_documents)
RETURNS DATE AS $
BEGIN
    RETURN (doc.metadata->>'decision_date')::DATE;
END;
$ LANGUAGE plpgsql IMMUTABLE;

-- Create index on temporal metadata for efficient filtering
CREATE INDEX IF NOT EXISTS legal_documents_effective_from_idx 
ON legal_documents ((metadata->>'effective_from'));

CREATE INDEX IF NOT EXISTS legal_documents_effective_to_idx 
ON legal_documents ((metadata->>'effective_to'));

CREATE INDEX IF NOT EXISTS legal_documents_decision_date_idx 
ON legal_documents ((metadata->>'decision_date'));

-- Create BNS to IPC/CrPC mapping table
CREATE TABLE IF NOT EXISTS legacy_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bns_section VARCHAR(50) NOT NULL,
    legacy_section VARCHAR(50) NOT NULL,
    legacy_act VARCHAR(10) NOT NULL CHECK (legacy_act IN ('IPC', 'CrPC')),
    description VARCHAR(500) NOT NULL,
    effective_from DATE NOT NULL DEFAULT '2024-07-01',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(bns_section, legacy_act),
    UNIQUE(legacy_section, legacy_act)
);

-- Insert key BNS to IPC mappings
INSERT INTO legacy_mappings (bns_section, legacy_section, legacy_act, description, notes) VALUES
('BNS:2023:Sec:147', 'IPC:1860:Sec:392', 'IPC', 'Robbery', 'BNS Section 147 replaces IPC Section 392'),
('BNS:2023:Sec:303', 'IPC:1860:Sec:378', 'IPC', 'Theft', 'BNS Section 303 replaces IPC Section 378'),
('BNS:2023:Sec:318', 'IPC:1860:Sec:420', 'IPC', 'Cheating', 'BNS Section 318 replaces IPC Section 420'),
('BNS:2023:Sec:103', 'IPC:1860:Sec:302', 'IPC', 'Murder', 'BNS Section 103 replaces IPC Section 302'),
('BNS:2023:Sec:101', 'IPC:1860:Sec:300', 'IPC', 'Murder (definition)', 'BNS Section 101 replaces IPC Section 300'),
('BNS:2023:Sec:115', 'IPC:1860:Sec:304', 'IPC', 'Culpable homicide not amounting to murder', 'BNS Section 115 replaces IPC Section 304'),
('BNS:2023:Sec:64', 'IPC:1860:Sec:354', 'IPC', 'Assault or criminal force to woman with intent to outrage her modesty', 'BNS Section 64 replaces IPC Section 354'),
('BNS:2023:Sec:70', 'IPC:1860:Sec:376', 'IPC', 'Rape', 'BNS Section 70 replaces IPC Section 376'),
('BNS:2023:Sec:111', 'IPC:1860:Sec:307', 'IPC', 'Attempt to murder', 'BNS Section 111 replaces IPC Section 307'),
('BNS:2023:Sec:140', 'IPC:1860:Sec:379', 'IPC', 'Theft in dwelling house', 'BNS Section 140 replaces IPC Section 379'),
('BNS:2023:Sec:329', 'IPC:1860:Sec:406', 'IPC', 'Criminal breach of trust', 'BNS Section 329 replaces IPC Section 406'),
('BNS:2023:Sec:331', 'IPC:1860:Sec:409', 'IPC', 'Criminal breach of trust by public servant', 'BNS Section 331 replaces IPC Section 409')
ON CONFLICT (bns_section, legacy_act) DO NOTHING;

-- Create indexes for legacy mappings
CREATE INDEX IF NOT EXISTS legacy_mappings_bns_idx ON legacy_mappings (bns_section);
CREATE INDEX IF NOT EXISTS legacy_mappings_legacy_idx ON legacy_mappings (legacy_section, legacy_act);

-- Create function for temporal filtering
CREATE OR REPLACE FUNCTION filter_by_temporal_validity(
    as_on_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE(
    document_id VARCHAR,
    title VARCHAR,
    document_type VARCHAR,
    is_valid BOOLEAN
) AS $
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.title,
        d.document_type,
        CASE
            -- For statutes: check effective_from and effective_to
            WHEN d.document_type IN ('statute', 'bns') THEN
                (d.metadata->>'effective_from')::DATE <= as_on_date AND
                ((d.metadata->>'effective_to') IS NULL OR (d.metadata->>'effective_to')::DATE > as_on_date)
            -- For judgments: check decision_date
            WHEN d.document_type = 'judgment' THEN
                (d.metadata->>'decision_date')::DATE <= as_on_date
            -- For other types, include by default
            ELSE TRUE
        END as is_valid
    FROM legal_documents d;
END;
$ LANGUAGE plpgsql;

-- Create function to get applicable act based on date
CREATE OR REPLACE FUNCTION get_applicable_act(
    as_on_date DATE DEFAULT CURRENT_DATE
)
RETURNS VARCHAR AS $
BEGIN
    IF as_on_date >= '2024-07-01'::DATE THEN
        RETURN 'BNS';
    ELSE
        RETURN 'IPC';
    END IF;
END;
$ LANGUAGE plpgsql IMMUTABLE;

-- Create function to map legacy reference to BNS
CREATE OR REPLACE FUNCTION map_legacy_to_bns(
    legacy_section VARCHAR,
    legacy_act VARCHAR DEFAULT 'IPC'
)
RETURNS VARCHAR AS $
DECLARE
    bns_section VARCHAR;
BEGIN
    SELECT lm.bns_section INTO bns_section
    FROM legacy_mappings lm
    WHERE lm.legacy_section = map_legacy_to_bns.legacy_section
    AND lm.legacy_act = map_legacy_to_bns.legacy_act;
    
    RETURN bns_section;
END;
$ LANGUAGE plpgsql;

-- Create function to map BNS to legacy
CREATE OR REPLACE FUNCTION map_bns_to_legacy(
    bns_section VARCHAR,
    target_act VARCHAR DEFAULT 'IPC'
)
RETURNS VARCHAR AS $
DECLARE
    legacy_section VARCHAR;
BEGIN
    SELECT lm.legacy_section INTO legacy_section
    FROM legacy_mappings lm
    WHERE lm.bns_section = map_bns_to_legacy.bns_section
    AND lm.legacy_act = target_act;
    
    RETURN legacy_section;
END;
$ LANGUAGE plpgsql;

-- Update search function to include temporal filtering
CREATE OR REPLACE FUNCTION search_similar_chunks_temporal(
    query_embedding vector(1536),
    as_on_date DATE DEFAULT CURRENT_DATE,
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
    document_type VARCHAR,
    is_temporally_valid BOOLEAN
) AS $
BEGIN
    RETURN QUERY
    SELECT 
        c.id as chunk_id,
        c.document_id,
        1 - (c.embedding <=> query_embedding) as similarity_score,
        c.content,
        d.title as document_title,
        d.document_type,
        CASE
            WHEN d.document_type IN ('statute', 'bns') THEN
                (d.metadata->>'effective_from')::DATE <= as_on_date AND
                ((d.metadata->>'effective_to') IS NULL OR (d.metadata->>'effective_to')::DATE > as_on_date)
            WHEN d.document_type = 'judgment' THEN
                (d.metadata->>'decision_date')::DATE <= as_on_date
            ELSE TRUE
        END as is_temporally_valid
    FROM document_chunks c
    JOIN legal_documents d ON c.document_id = d.id
    WHERE 
        (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
        AND (document_type_filter IS NULL OR d.document_type = document_type_filter)
        AND (
            -- Temporal validity check
            CASE
                WHEN d.document_type IN ('statute', 'bns') THEN
                    (d.metadata->>'effective_from')::DATE <= as_on_date AND
                    ((d.metadata->>'effective_to') IS NULL OR (d.metadata->>'effective_to')::DATE > as_on_date)
                WHEN d.document_type = 'judgment' THEN
                    (d.metadata->>'decision_date')::DATE <= as_on_date
                ELSE TRUE
            END
        )
    ORDER BY c.embedding <=> query_embedding
    LIMIT max_results;
END;
$ LANGUAGE plpgsql;

COMMENT ON TABLE legacy_mappings IS 'Mapping between BNS sections and legacy IPC/CrPC sections';
COMMENT ON FUNCTION filter_by_temporal_validity IS 'Filter documents by temporal validity for a given as-on date';
COMMENT ON FUNCTION get_applicable_act IS 'Determine which criminal code (BNS or IPC) applies for a given date';
COMMENT ON FUNCTION search_similar_chunks_temporal IS 'Vector similarity search with temporal filtering';

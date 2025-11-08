-- Database initialization script for Indian Legal AI Assistant
-- This script sets up the database with required extensions and initial configuration

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create database user if not exists (for development)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'legal_ai_user') THEN
        CREATE ROLE legal_ai_user WITH LOGIN PASSWORD 'legal_ai_password';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT CONNECT ON DATABASE legal_ai TO legal_ai_user;
GRANT USAGE ON SCHEMA public TO legal_ai_user;
GRANT CREATE ON SCHEMA public TO legal_ai_user;

-- Create application-specific schemas
CREATE SCHEMA IF NOT EXISTS legal_ai AUTHORIZATION legal_ai_user;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION legal_ai_user;

-- Grant permissions on schemas
GRANT ALL PRIVILEGES ON SCHEMA legal_ai TO legal_ai_user;
GRANT ALL PRIVILEGES ON SCHEMA audit TO legal_ai_user;

-- Set default search path
ALTER ROLE legal_ai_user SET search_path TO legal_ai, public;

-- Create initial configuration table
CREATE TABLE IF NOT EXISTS legal_ai.system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert initial system configuration
INSERT INTO legal_ai.system_config (key, value, description) VALUES
    ('database_version', '"1.0.0"', 'Database schema version'),
    ('vector_dimensions', '1536', 'OpenAI embedding dimensions'),
    ('max_chunk_size', '500', 'Maximum tokens per document chunk'),
    ('default_search_limit', '10', 'Default number of search results')
ON CONFLICT (key) DO NOTHING;

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION legal_ai.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create audit logging function
CREATE OR REPLACE FUNCTION audit.log_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO audit.audit_log (
            table_name,
            operation,
            old_values,
            changed_at,
            changed_by
        ) VALUES (
            TG_TABLE_NAME,
            TG_OP,
            row_to_json(OLD),
            NOW(),
            current_user
        );
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit.audit_log (
            table_name,
            operation,
            old_values,
            new_values,
            changed_at,
            changed_by
        ) VALUES (
            TG_TABLE_NAME,
            TG_OP,
            row_to_json(OLD),
            row_to_json(NEW),
            NOW(),
            current_user
        );
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO audit.audit_log (
            table_name,
            operation,
            new_values,
            changed_at,
            changed_by
        ) VALUES (
            TG_TABLE_NAME,
            TG_OP,
            row_to_json(NEW),
            NOW(),
            current_user
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    changed_by VARCHAR(255) DEFAULT current_user
);

-- Create index on audit log for performance
CREATE INDEX IF NOT EXISTS idx_audit_log_table_name ON audit.audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit.audit_log(changed_at);

-- Log successful initialization
INSERT INTO legal_ai.system_config (key, value, description) VALUES
    ('database_initialized_at', to_jsonb(NOW()), 'Database initialization timestamp')
ON CONFLICT (key) DO UPDATE SET 
    value = to_jsonb(NOW()),
    updated_at = NOW();

-- Display initialization message
DO $$
BEGIN
    RAISE NOTICE 'Indian Legal AI Assistant database initialized successfully';
    RAISE NOTICE 'Extensions enabled: uuid-ossp, pgcrypto, vector';
    RAISE NOTICE 'Schemas created: legal_ai, audit';
    RAISE NOTICE 'Ready for application startup';
END
$$;
-- Initial setup for legal_kb database
\set ON_ERROR_STOP on

-- Ensure required extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create read-write application role
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'legal_kb_user') THEN
        CREATE ROLE legal_kb_user WITH LOGIN PASSWORD 'legal_kb_password';
    END IF;
END
$$;

-- Grant privileges on public schema to application role
GRANT CONNECT ON DATABASE legal_kb TO legal_kb_user;
GRANT USAGE ON SCHEMA public TO legal_kb_user;
GRANT CREATE ON SCHEMA public TO legal_kb_user;

-- Ensure future objects are accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO legal_kb_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO legal_kb_user;

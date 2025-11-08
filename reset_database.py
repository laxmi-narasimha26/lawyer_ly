#!/usr/bin/env python3
"""
Reset the database for token-aware schema
"""
import psycopg2
import sys
import os
from pathlib import Path

# Add legal_kb to path
sys.path.insert(0, str(Path(__file__).parent / "legal_kb"))

from config import Config

def reset_database():
    """Reset the database and create token-aware schema"""
    config = Config()
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Connected to database")
        
        # Drop existing tables (in correct order due to foreign keys)
        drop_tables = [
            "legal_citations",
            "document_chunks", 
            "legal_documents",
            "query_cache",
            "system_metrics",
            "legal_synonyms",
            "cross_references",
            "authority_weights",
            "legacy_mappings",
            "citation_patterns",
            "statute_chunks",
            "case_chunks"
        ]
        
        for table in drop_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"Dropped table: {table}")
            except Exception as e:
                print(f"Could not drop {table}: {e}")
        
        # Drop functions
        functions = [
            "update_updated_at_column()",
            "clean_expired_cache()",
            "search_similar_statutes(vector, float, integer, varchar, date)",
            "search_similar_cases(vector, float, integer, varchar, date)",
            "search_similar_chunks(vector, float, integer, varchar)"
        ]
        
        for func in functions:
            try:
                cursor.execute(f"DROP FUNCTION IF EXISTS {func} CASCADE")
                print(f"Dropped function: {func}")
            except Exception as e:
                print(f"Could not drop function {func}: {e}")
        
        print("Existing schema cleaned")
        
        # Read and execute new schema
        schema_path = Path("legal_kb/database/token_aware_schema.sql")
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        cursor.execute(schema_sql)
        print("Token-aware schema created successfully")
        
        # Verify tables exist
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"Created tables: {[t[0] for t in tables]}")
        
        cursor.close()
        conn.close()
        
        print("Database reset completed successfully!")
        return True
        
    except Exception as e:
        print(f"Database reset failed: {e}")
        return False

if __name__ == "__main__":
    success = reset_database()
    sys.exit(0 if success else 1)
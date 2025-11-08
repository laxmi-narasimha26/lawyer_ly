#!/usr/bin/env python3
"""
Set up the token-aware database schema
"""
import psycopg2
import sys
import os
from pathlib import Path

# Add legal_kb to path
sys.path.insert(0, str(Path(__file__).parent / "legal_kb"))

from config import Config

def setup_database():
    """Set up the database with token-aware schema"""
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
        
        print("Connected to database")
        
        # Read and execute schema
        schema_path = Path("legal_kb/database/token_aware_schema.sql")
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        cursor = conn.cursor()
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
        
        print("Database setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        return False

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
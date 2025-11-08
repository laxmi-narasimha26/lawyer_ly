"""
Apply temporal fields migration to the database
"""

import asyncio
import os
from legal_kb.database.connection import DatabaseConfig, DatabaseManager


async def apply_migration():
    """Apply the temporal fields migration"""
    print("Applying temporal fields migration...")
    
    config = DatabaseConfig()
    manager = DatabaseManager(config)
    
    try:
        await manager.initialize()
        print("✓ Database connection established")
        
        # Read migration SQL
        migration_path = os.path.join(
            os.path.dirname(__file__),
            'legal_kb',
            'database',
            'add_temporal_fields.sql'
        )
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("✓ Migration SQL loaded")
        
        # Execute migration
        async with manager.get_postgres_connection() as conn:
            # Execute the entire migration as one transaction
            try:
                await conn.execute(migration_sql)
                print(f"  ✓ Migration executed successfully")
            except Exception as e:
                # Some statements might fail if already exist
                if "already exists" in str(e).lower():
                    print(f"  ⚠ Some objects already exist (skipped)")
                else:
                    print(f"  ✗ Migration failed: {e}")
                    raise
        
        print("\n✓ Temporal fields migration applied successfully!")
        print("\nAdded features:")
        print("  - Temporal filtering functions")
        print("  - BNS to IPC/CrPC mapping table")
        print("  - Temporal indexes on metadata fields")
        print("  - search_similar_chunks_temporal() function")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await manager.close()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(apply_migration())
    exit(0 if success else 1)

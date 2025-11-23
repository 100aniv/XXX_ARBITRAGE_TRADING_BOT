"""
Apply D76 Alert Storage Migration

This script applies the database migration for alert_history table.
"""

import os
import sys
import psycopg2
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_connection_string():
    """Get PostgreSQL connection string from environment"""
    return os.getenv(
        'DATABASE_URL',
        'postgresql://arbitrage_user:arbitrage_pass@localhost:5432/arbitrage_db'
    )


def apply_migration():
    """Apply D76 alert storage migration"""
    migration_file = project_root / 'db' / 'migrations' / 'd76_alert_storage.sql'
    
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False
        
    # Read migration SQL
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
        
    # Apply migration
    conn_string = get_connection_string()
    
    try:
        print(f"📦 Connecting to database...")
        conn = psycopg2.connect(conn_string)
        
        with conn.cursor() as cur:
            print(f"🔧 Applying D76 alert storage migration...")
            cur.execute(migration_sql)
            
        conn.commit()
        print("✅ Migration applied successfully!")
        
        # Verify
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'alert_history'
            """)
            table_exists = cur.fetchone()[0]
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM pg_indexes 
                WHERE tablename = 'alert_history'
            """)
            index_count = cur.fetchone()[0]
            
        print(f"📊 Verification:")
        print(f"   - alert_history table: {'✅ EXISTS' if table_exists else '❌ NOT FOUND'}")
        print(f"   - Indexes created: {index_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


if __name__ == '__main__':
    success = apply_migration()
    sys.exit(0 if success else 1)

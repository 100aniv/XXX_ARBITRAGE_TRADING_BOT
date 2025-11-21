#!/usr/bin/env python3
"""
Apply D72-4 Logging & Monitoring Migration

Creates system_logs table and related views/functions.
"""

import psycopg2
import sys
from pathlib import Path


def apply_migration():
    """Apply D72-4 database migration"""
    # Database config
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "arbitrage",
        "user": "arbitrage",
        "password": "arbitrage"
    }
    
    # Read migration SQL
    migration_file = Path(__file__).parent.parent / "db" / "migrations" / "d72_4_logging_monitoring.sql"
    
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    # Connect and apply
    conn = None
    try:
        print(f"📦 Connecting to database...")
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        
        print(f"📄 Applying migration: d72_4_logging_monitoring.sql")
        
        with conn.cursor() as cur:
            cur.execute(migration_sql)
        
        conn.commit()
        print("✅ Migration applied successfully")
        
        # Verify tables
        print("\n🔍 Verifying migration...")
        with conn.cursor() as cur:
            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'system_logs'
                )
            """)
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                print("  ✓ Table 'system_logs' created")
            else:
                print("  ✗ Table 'system_logs' not found")
                return False
            
            # Count indexes
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'system_logs'
            """)
            index_count = cur.fetchone()[0]
            print(f"  ✓ {index_count} indexes created")
            
            # Check views
            views = ['v_recent_errors', 'v_error_summary', 'v_log_volume_hourly']
            for view in views:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.views 
                        WHERE table_name = %s
                    )
                """, (view,))
                exists = cur.fetchone()[0]
                status = "✓" if exists else "✗"
                print(f"  {status} View '{view}'")
            
            # Check functions
            functions = ['cleanup_old_logs', 'get_log_statistics', 'search_logs']
            for func in functions:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_proc 
                        WHERE proname = %s
                    )
                """, (func,))
                exists = cur.fetchone()[0]
                status = "✓" if exists else "✗"
                print(f"  {status} Function '{func}'")
        
        print("\n✅ D72-4 migration complete!")
        return True
    
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
    
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
D72-3: Apply PostgreSQL Optimization Migration

인덱스, Retention, Vacuum 정책 적용
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import time


def apply_migration():
    """Apply D72-3 migration"""
    print("=" * 70)
    print("D72-3 POSTGRESQL MIGRATION")
    print("=" * 70)
    
    # Read migration SQL
    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'db', 'migrations', 'd72_postgres_optimize.sql'
    )
    
    print(f"\n[STEP 1] Reading migration file...")
    print(f"  Path: {migration_file}")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    print(f"  ✅ Read {len(sql)} characters")
    
    # Connect to PostgreSQL
    print(f"\n[STEP 2] Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='arbitrage',
            user='arbitrage',
            password='arbitrage'
        )
        print("  ✅ Connected")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False
    
    # Apply migration
    print(f"\n[STEP 3] Applying migration...")
    try:
        with conn.cursor() as cursor:
            # Execute migration
            start_time = time.time()
            cursor.execute(sql)
            conn.commit()
            elapsed = time.time() - start_time
            
            print(f"  ✅ Migration applied in {elapsed:.2f}s")
    except Exception as e:
        print(f"  ❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        return False
    
    # Verify indexes
    print(f"\n[STEP 4] Verifying indexes...")
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    tablename,
                    indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('session_snapshots', 'position_snapshots', 'metrics_snapshots', 'risk_guard_snapshots')
                ORDER BY tablename, indexname
            """)
            
            indexes = cursor.fetchall()
            
            # Group by table
            by_table = {}
            for table, index in indexes:
                if table not in by_table:
                    by_table[table] = []
                by_table[table].append(index)
            
            print(f"  Total indexes: {len(indexes)}")
            for table, idx_list in by_table.items():
                print(f"  {table}: {len(idx_list)} indexes")
                for idx in idx_list:
                    print(f"    - {idx}")
    
    except Exception as e:
        print(f"  ❌ Verification failed: {e}")
        conn.close()
        return False
    
    # Verify functions
    print(f"\n[STEP 5] Verifying functions...")
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    proname,
                    pg_get_function_identity_arguments(oid) as args
                FROM pg_proc
                WHERE proname IN (
                    'cleanup_old_snapshots_30d',
                    'vacuum_snapshot_tables',
                    'get_snapshot_table_stats',
                    'test_query_performance'
                )
                ORDER BY proname
            """)
            
            functions = cursor.fetchall()
            
            print(f"  Total functions: {len(functions)}")
            for func_name, args in functions:
                print(f"    ✅ {func_name}({args})")
    
    except Exception as e:
        print(f"  ❌ Function verification failed: {e}")
        conn.close()
        return False
    
    # Verify views
    print(f"\n[STEP 6] Verifying views...")
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT viewname
                FROM pg_views
                WHERE schemaname = 'public'
                  AND viewname LIKE 'v_%'
                ORDER BY viewname
            """)
            
            views = cursor.fetchall()
            
            print(f"  Total views: {len(views)}")
            for (view_name,) in views:
                print(f"    ✅ {view_name}")
    
    except Exception as e:
        print(f"  ❌ View verification failed: {e}")
        conn.close()
        return False
    
    # Get table stats
    print(f"\n[STEP 7] Table statistics...")
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM get_snapshot_table_stats()")
            stats = cursor.fetchall()
            
            for table_name, total_rows, table_size, index_size, total_size in stats:
                print(f"  {table_name}:")
                print(f"    Table size: {table_size} MB")
                print(f"    Index size: {index_size} MB")
                print(f"    Total: {total_size} MB")
    
    except Exception as e:
        print(f"  ⚠️  Stats query failed (table might be empty): {e}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ D72-3 MIGRATION COMPLETED")
    print("=" * 70)
    
    return True


if __name__ == '__main__':
    success = apply_migration()
    sys.exit(0 if success else 1)

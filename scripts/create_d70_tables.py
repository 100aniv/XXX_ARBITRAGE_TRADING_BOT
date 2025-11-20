#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D70: State Persistence Tables Creation Script

PostgreSQL에 D70 상태 영속화/복원용 테이블들을 생성합니다.
arbitrage-postgres (5432)에만 실행됩니다.
"""

import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """arbitrage-postgres 연결 생성"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "arbitrage"),
            user=os.getenv("POSTGRES_USER", "arbitrage"),
            password=os.getenv("POSTGRES_PASSWORD", "arbitrage")
        )
        logger.info("[D70_MIGRATION] Connected to arbitrage-postgres")
        return conn
    except Exception as e:
        logger.error(f"[D70_MIGRATION] Failed to connect to DB: {e}")
        raise


def execute_migration_file(conn, sql_file_path: Path):
    """마이그레이션 SQL 파일 실행"""
    if not sql_file_path.exists():
        raise FileNotFoundError(f"Migration file not found: {sql_file_path}")
    
    logger.info(f"[D70_MIGRATION] Reading SQL from: {sql_file_path}")
    with sql_file_path.open('r', encoding='utf-8') as f:
        sql_content = f.read()
    
    cursor = conn.cursor()
    try:
        # SQL 파일 실행
        cursor.execute(sql_content)
        conn.commit()
        logger.info("[D70_MIGRATION] Migration executed successfully")
    except Exception as e:
        conn.rollback()
        logger.error(f"[D70_MIGRATION] Migration failed: {e}")
        raise
    finally:
        cursor.close()


def verify_tables(conn):
    """생성된 테이블 확인"""
    expected_tables = [
        'session_snapshots',
        'position_snapshots',
        'metrics_snapshots',
        'risk_guard_snapshots'
    ]
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
              AND table_name IN %s
            ORDER BY table_name
        """, (tuple(expected_tables),))
        
        created_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"[D70_MIGRATION] Created tables: {created_tables}")
        
        missing_tables = set(expected_tables) - set(created_tables)
        if missing_tables:
            logger.warning(f"[D70_MIGRATION] Missing tables: {missing_tables}")
            return False
        
        logger.info("[D70_MIGRATION] ✅ All required tables exist")
        return True
    
    finally:
        cursor.close()


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("D70: State Persistence Tables Creation")
    logger.info("=" * 60)
    
    # 마이그레이션 파일 경로
    migration_file = project_root / "db" / "migrations" / "d70_state_persistence.sql"
    
    try:
        # DB 연결
        conn = get_db_connection()
        
        # 마이그레이션 실행
        execute_migration_file(conn, migration_file)
        
        # 테이블 확인
        if verify_tables(conn):
            logger.info("=" * 60)
            logger.info("[D70_MIGRATION] ✅ Migration completed successfully")
            logger.info("=" * 60)
            return 0
        else:
            logger.error("[D70_MIGRATION] ❌ Migration verification failed")
            return 1
    
    except Exception as e:
        logger.error(f"[D70_MIGRATION] ❌ Migration failed: {e}")
        return 1
    
    finally:
        if 'conn' in locals():
            conn.close()
            logger.info("[D70_MIGRATION] DB connection closed")


if __name__ == "__main__":
    sys.exit(main())

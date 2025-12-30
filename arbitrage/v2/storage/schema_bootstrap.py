"""
D204-2 REOPEN: V2 Schema Bootstrap (자동 적용 + 검증)

목적:
- v2_schema.sql 자동 실행
- 테이블 존재 검증 (v2_orders, v2_fills, v2_trades, v2_ledger, v2_pnl_daily)
- 실패 시 exit code != 0

사용법:
    python -m arbitrage.v2.storage.schema_bootstrap
    python -m arbitrage.v2.storage.schema_bootstrap --connection-string "postgresql://..."
    
패턴 재사용:
- V2LedgerStorage 연결 방식
- db/migrations/v2_schema.sql
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemaBootstrap:
    """V2 스키마 자동 부트스트랩"""
    
    # 필수 테이블 목록
    REQUIRED_TABLES = [
        "v2_orders",
        "v2_fills",
        "v2_trades",
        "v2_ledger",
        "v2_pnl_daily",
    ]
    
    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: PostgreSQL 연결 문자열
                예: "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
        """
        self.connection_string = connection_string
        self.conn = None
        
    def connect(self):
        """DB 연결"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            logger.info(f"[SchemaBootstrap] Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"[SchemaBootstrap] Failed to connect: {e}")
            raise
    
    def disconnect(self):
        """DB 연결 해제"""
        if self.conn:
            self.conn.close()
            logger.info(f"[SchemaBootstrap] Disconnected from PostgreSQL")
    
    def apply_schema(self, schema_sql_path: Path) -> bool:
        """
        v2_schema.sql 실행
        
        Args:
            schema_sql_path: v2_schema.sql 파일 경로
            
        Returns:
            True if success, False otherwise
        """
        if not schema_sql_path.exists():
            logger.error(f"[SchemaBootstrap] Schema file not found: {schema_sql_path}")
            return False
        
        try:
            # SQL 파일 읽기
            with open(schema_sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()
            
            logger.info(f"[SchemaBootstrap] Read {len(sql)} characters from {schema_sql_path}")
            
            # 실행
            with self.conn.cursor() as cur:
                cur.execute(sql)
                self.conn.commit()
            
            logger.info(f"[SchemaBootstrap] Schema applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"[SchemaBootstrap] Failed to apply schema: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def check_tables(self) -> Dict[str, bool]:
        """
        필수 테이블 존재 검증
        
        Returns:
            Dict[table_name, exists]
        """
        results = {}
        
        try:
            with self.conn.cursor() as cur:
                for table_name in self.REQUIRED_TABLES:
                    # SELECT to_regclass('public.table_name')
                    # Returns: oid if exists, NULL otherwise
                    cur.execute(
                        "SELECT to_regclass(%s) IS NOT NULL AS exists",
                        (f"public.{table_name}",)
                    )
                    row = cur.fetchone()
                    exists = row[0] if row else False
                    results[table_name] = exists
                    
                    status = "✅" if exists else "❌"
                    logger.info(f"[SchemaBootstrap] {status} {table_name}: exists={exists}")
            
            return results
            
        except Exception as e:
            logger.error(f"[SchemaBootstrap] Failed to check tables: {e}")
            return {}
    
    def verify(self) -> bool:
        """
        전체 검증
        
        Returns:
            True if all required tables exist, False otherwise
        """
        check_results = self.check_tables()
        
        if not check_results:
            logger.error(f"[SchemaBootstrap] Table check failed (empty results)")
            return False
        
        missing_tables = [
            table for table, exists in check_results.items()
            if not exists
        ]
        
        if missing_tables:
            logger.error(f"[SchemaBootstrap] Missing tables: {missing_tables}")
            return False
        
        logger.info(f"[SchemaBootstrap] ✅ All {len(self.REQUIRED_TABLES)} tables exist")
        return True


def bootstrap(
    connection_string: str = "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
    schema_sql_path: Path = None,
) -> int:
    """
    Main bootstrap function
    
    Args:
        connection_string: PostgreSQL 연결 문자열
        schema_sql_path: v2_schema.sql 파일 경로 (None이면 자동 탐색)
        
    Returns:
        0 if success, 1 if failure
    """
    # 스키마 파일 경로 자동 탐색
    if schema_sql_path is None:
        # 프로젝트 루트에서 db/migrations/v2_schema.sql
        project_root = Path(__file__).parent.parent.parent.parent
        schema_sql_path = project_root / "db" / "migrations" / "v2_schema.sql"
    
    logger.info(f"[SchemaBootstrap] ========================================")
    logger.info(f"[SchemaBootstrap] V2 Schema Bootstrap (D204-2 REOPEN)")
    logger.info(f"[SchemaBootstrap] ========================================")
    logger.info(f"[SchemaBootstrap] Connection: {connection_string}")
    logger.info(f"[SchemaBootstrap] Schema SQL: {schema_sql_path}")
    
    bs = SchemaBootstrap(connection_string)
    
    try:
        # Step 1: DB 연결
        bs.connect()
        
        # Step 2: 스키마 적용
        logger.info(f"[SchemaBootstrap] Step 2: Applying schema...")
        if not bs.apply_schema(schema_sql_path):
            logger.error(f"[SchemaBootstrap] ❌ FAIL: Schema apply failed")
            return 1
        
        # Step 3: 테이블 검증
        logger.info(f"[SchemaBootstrap] Step 3: Verifying tables...")
        if not bs.verify():
            logger.error(f"[SchemaBootstrap] ❌ FAIL: Table verification failed")
            return 1
        
        # 성공
        logger.info(f"[SchemaBootstrap] ========================================")
        logger.info(f"[SchemaBootstrap] ✅ SUCCESS: All tables ready")
        logger.info(f"[SchemaBootstrap] ========================================")
        return 0
        
    except Exception as e:
        logger.error(f"[SchemaBootstrap] ❌ FAIL: Unexpected error: {e}")
        return 1
        
    finally:
        bs.disconnect()


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="V2 Schema Bootstrap (D204-2)")
    parser.add_argument(
        "--connection-string",
        default="postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
        help="PostgreSQL connection string"
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=None,
        help="Path to v2_schema.sql (auto-detect if not provided)"
    )
    
    args = parser.parse_args()
    
    exit_code = bootstrap(
        connection_string=args.connection_string,
        schema_sql_path=args.schema_path,
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

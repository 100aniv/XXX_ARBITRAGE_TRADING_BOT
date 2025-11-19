"""
D68 - PostgreSQL 테이블 생성 스크립트
"""

import sys
import os
import psycopg2
import logging

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tuning_table():
    """tuning_results 테이블 생성"""
    
    # PostgreSQL 연결 (arbitrage 전용 infra 스택)
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,  # arbitrage-postgres 포트
            dbname="arbitrage",
            user="arbitrage",
            password="arbitrage"
        )
        logger.info("Connected to PostgreSQL")
        
        cursor = conn.cursor()
        
        # SQL 파일 읽기
        sql_file_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'db',
            'migrations',
            'd68_tuning_results.sql'
        )
        
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 실행
        cursor.execute(sql_script)
        conn.commit()
        
        logger.info("✅ tuning_results table created successfully")
        
        # 테이블 확인
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'tuning_results';
        """)
        
        result = cursor.fetchone()
        if result:
            logger.info(f"✅ Table verified: {result[0]}")
        else:
            logger.error("❌ Table not found after creation")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create table: {e}")
        return False


if __name__ == "__main__":
    success = create_tuning_table()
    sys.exit(0 if success else 1)

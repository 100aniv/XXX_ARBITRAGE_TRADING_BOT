#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D70: State Persistence Smoke Test

StateStore와 상태 저장/복원 로직의 기본 동작을 검증하는 smoke test.
D70-3의 풀 시나리오 테스트 전에 인프라가 제대로 작동하는지 확인.

Usage:
    python scripts/run_d70_smoke.py
"""

import logging
import os
import sys
from pathlib import Path

import psycopg2
import redis

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.state_store import StateStore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_redis_connection():
    """Redis 연결 테스트"""
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6380")),
            db=0,
            decode_responses=True,
            socket_connect_timeout=2
        )
        r.ping()
        logger.info("[D70_SMOKE] ✅ Redis connection successful")
        return r
    except Exception as e:
        logger.error(f"[D70_SMOKE] ❌ Redis connection failed: {e}")
        return None


def test_postgres_connection():
    """PostgreSQL 연결 테스트"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "arbitrage"),
            user=os.getenv("POSTGRES_USER", "arbitrage"),
            password=os.getenv("POSTGRES_PASSWORD", "arbitrage")
        )
        logger.info("[D70_SMOKE] ✅ PostgreSQL connection successful")
        return conn
    except Exception as e:
        logger.error(f"[D70_SMOKE] ❌ PostgreSQL connection failed: {e}")
        return None


def test_state_store_basic():
    """StateStore 기본 동작 테스트"""
    logger.info("=" * 60)
    logger.info("[D70_SMOKE] Testing StateStore Basic Operations")
    logger.info("=" * 60)
    
    # 연결
    redis_client = test_redis_connection()
    db_conn = test_postgres_connection()
    
    if not redis_client or not db_conn:
        logger.error("[D70_SMOKE] ❌ Cannot proceed without Redis/PostgreSQL")
        return False
    
    try:
        # StateStore 초기화
        store = StateStore(redis_client, db_conn, env="test")
        logger.info("[D70_SMOKE] ✅ StateStore initialized")
        
        # 테스트 데이터 준비
        session_id = "test_session_001"
        test_state = {
            'session': {
                'session_id': session_id,
                'start_time': 1700000000.0,
                'mode': 'paper',
                'paper_campaign_id': 'C1',
                'config': {'symbol_a': 'KRW-BTC', 'symbol_b': 'BTCUSDT'},
                'loop_count': 10,
                'status': 'running'
            },
            'positions': {
                'active_orders': {},
                'paper_position_open_times': {}
            },
            'metrics': {
                'total_trades_opened': 5,
                'total_trades_closed': 3,
                'total_winning_trades': 2,
                'total_pnl_usd': 12.34,
                'max_dd_usd': -5.67,
                'per_symbol_pnl': {},
                'per_symbol_trades_opened': {},
                'per_symbol_trades_closed': {},
                'per_symbol_winning_trades': {},
                'portfolio_initial_capital': 10000.0,
                'portfolio_equity': 10012.34
            },
            'risk_guard': {
                'session_start_time': 1700000000.0,
                'daily_loss_usd': 5.67,
                'per_symbol_loss': {},
                'per_symbol_trades_rejected': {},
                'per_symbol_trades_allowed': {},
                'per_symbol_capital_used': {},
                'per_symbol_position_count': {}
            }
        }
        
        # 1. Redis 저장 테스트
        logger.info("[D70_SMOKE] Testing Redis save...")
        success = store.save_state_to_redis(session_id, test_state)
        if success:
            logger.info("[D70_SMOKE] ✅ Redis save successful")
        else:
            logger.error("[D70_SMOKE] ❌ Redis save failed")
            return False
        
        # 2. Redis 로드 테스트
        logger.info("[D70_SMOKE] Testing Redis load...")
        loaded_state = store.load_state_from_redis(session_id)
        if loaded_state and loaded_state['session']['session_id'] == session_id:
            logger.info("[D70_SMOKE] ✅ Redis load successful")
        else:
            logger.error("[D70_SMOKE] ❌ Redis load failed")
            return False
        
        # 3. PostgreSQL 스냅샷 저장 테스트
        logger.info("[D70_SMOKE] Testing PostgreSQL snapshot save...")
        snapshot_id = store.save_snapshot_to_db(session_id, test_state, snapshot_type="test")
        if snapshot_id:
            logger.info(f"[D70_SMOKE] ✅ PostgreSQL snapshot save successful: snapshot_id={snapshot_id}")
        else:
            logger.error("[D70_SMOKE] ❌ PostgreSQL snapshot save failed")
            return False
        
        # 4. PostgreSQL 스냅샷 로드 테스트
        logger.info("[D70_SMOKE] Testing PostgreSQL snapshot load...")
        loaded_snapshot = store.load_latest_snapshot(session_id)
        if loaded_snapshot and loaded_snapshot['session']['session_id'] == session_id:
            logger.info("[D70_SMOKE] ✅ PostgreSQL snapshot load successful")
            logger.info(f"  - loop_count: {loaded_snapshot['session']['loop_count']}")
            logger.info(f"  - trades_opened: {loaded_snapshot['metrics']['total_trades_opened']}")
            logger.info(f"  - pnl: ${loaded_snapshot['metrics']['total_pnl_usd']:.2f}")
        else:
            logger.error("[D70_SMOKE] ❌ PostgreSQL snapshot load failed")
            return False
        
        # 5. 스냅샷 검증 테스트
        logger.info("[D70_SMOKE] Testing snapshot validation...")
        if store.validate_snapshot(loaded_snapshot):
            logger.info("[D70_SMOKE] ✅ Snapshot validation passed")
        else:
            logger.error("[D70_SMOKE] ❌ Snapshot validation failed")
            return False
        
        # 6. Redis 삭제 테스트
        logger.info("[D70_SMOKE] Testing Redis delete...")
        if store.delete_state_from_redis(session_id):
            logger.info("[D70_SMOKE] ✅ Redis delete successful")
        else:
            logger.warning("[D70_SMOKE] ⚠️  Redis delete warning (non-critical)")
        
        logger.info("=" * 60)
        logger.info("[D70_SMOKE] ✅ All basic tests passed!")
        logger.info("=" * 60)
        return True
    
    except Exception as e:
        logger.error(f"[D70_SMOKE] ❌ Test failed: {e}", exc_info=True)
        return False
    
    finally:
        if redis_client:
            redis_client.close()
        if db_conn:
            db_conn.close()


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("D70: State Persistence Smoke Test")
    logger.info("=" * 60)
    
    success = test_state_store_basic()
    
    if success:
        logger.info("[D70_SMOKE] ✅ Smoke test PASSED")
        return 0
    else:
        logger.error("[D70_SMOKE] ❌ Smoke test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

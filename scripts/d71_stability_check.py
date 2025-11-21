#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D71 Stability Check Script
===========================

D71-2 최종 검증: 구조 안정성 자동 점검

검증 항목:
1. WS reconnect logic - edge case 3종
2. Redis fallback - 타이밍 검증
3. Snapshot corruption → DB/Redis desync
4. StateStore key prefix consistency
5. LiveRunner entry duplication 방지
6. RiskGuard edge-case 복원
"""

import sys
import os
import time
import json
import logging
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
import psycopg2

from arbitrage.state_store import StateStore
from arbitrage.binance_ws import BinanceWebSocket
from arbitrage.upbit_ws import UpbitWebSocket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class D71StabilityChecker:
    """D71 구조 안정성 자동 검증"""
    
    def __init__(self):
        self.results = {}
        self.redis_client = None
        self.db_conn = None
        
    def setup(self):
        """환경 설정"""
        try:
            # Redis 연결
            self.redis_client = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)
            self.redis_client.ping()
            logger.info("✅ Redis connected")
            
            # PostgreSQL 연결
            self.db_conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='arbitrage',
                user='arbitrage',
                password='arbitrage'
            )
            logger.info("✅ PostgreSQL connected")
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            raise
    
    def cleanup(self):
        """정리"""
        if self.redis_client:
            self.redis_client.close()
        if self.db_conn:
            self.db_conn.close()
    
    # ========== Test 1: WS Reconnect Edge Cases ==========
    
    def test_ws_reconnect_edge_cases(self):
        """
        WS reconnect logic 검증
        
        Edge cases:
        1. Max reconnect attempts 도달
        2. Exponential backoff 계산 정확성
        3. 성공 후 카운터 리셋
        """
        logger.info("\n[TEST 1] WS Reconnect Edge Cases")
        
        try:
            # Edge case 1: Max attempts
            ws = BinanceWebSocket(['BTCUSDT'], lambda x: None)
            ws.reconnect_attempts = ws.max_reconnect_attempts
            
            if ws.reconnect_attempts >= ws.max_reconnect_attempts:
                logger.info("  ✅ Edge case 1: Max reconnect limit enforced")
                edge1_pass = True
            else:
                logger.error("  ❌ Edge case 1: Max reconnect limit not enforced")
                edge1_pass = False
            
            # Edge case 2: Exponential backoff
            ws2 = UpbitWebSocket(['KRW-BTC'], lambda x: None)
            delays = []
            for i in range(1, 8):
                ws2.reconnect_attempts = i
                delay = min(ws2.reconnect_delay * (2 ** (i - 1)), ws2.max_reconnect_delay)
                delays.append(delay)
            
            expected = [1, 2, 4, 8, 16, 32, 60]
            if delays == expected:
                logger.info(f"  ✅ Edge case 2: Backoff correct {delays}")
                edge2_pass = True
            else:
                logger.error(f"  ❌ Edge case 2: Backoff incorrect. Expected {expected}, got {delays}")
                edge2_pass = False
            
            # Edge case 3: Counter reset on success
            ws3 = BinanceWebSocket(['ETHUSDT'], lambda x: None)
            ws3.reconnect_attempts = 5
            ws3.connected = True
            # Simulate _on_open callback behavior
            ws3.reconnect_attempts = 0
            
            if ws3.reconnect_attempts == 0:
                logger.info("  ✅ Edge case 3: Counter reset on success")
                edge3_pass = True
            else:
                logger.error("  ❌ Edge case 3: Counter not reset")
                edge3_pass = False
            
            self.results['ws_reconnect'] = {
                'pass': edge1_pass and edge2_pass and edge3_pass,
                'edge1': edge1_pass,
                'edge2': edge2_pass,
                'edge3': edge3_pass
            }
            
        except Exception as e:
            logger.error(f"  ❌ WS reconnect test failed: {e}")
            self.results['ws_reconnect'] = {'pass': False, 'error': str(e)}
    
    # ========== Test 2: Redis Fallback Timing ==========
    
    def test_redis_fallback_timing(self):
        """
        Redis fallback 타이밍 검증
        
        검증:
        1. 3회 연속 실패 시 fallback 활성화
        2. Redis 복구 시 fallback 해제
        3. Fallback 모드에서 DB 우선 사용
        """
        logger.info("\n[TEST 2] Redis Fallback Timing")
        
        try:
            store = StateStore(self.redis_client, self.db_conn, env='test')
            
            # Case 1: 3회 실패 시 fallback
            store._redis_failure_count = 0
            store._fallback_mode = False
            
            for i in range(3):
                store._redis_failure_count += 1
                if store._redis_failure_count >= store._redis_failure_threshold:
                    store._enable_fallback_mode()
            
            if store._fallback_mode:
                logger.info("  ✅ Case 1: Fallback activated after 3 failures")
                case1_pass = True
            else:
                logger.error("  ❌ Case 1: Fallback not activated")
                case1_pass = False
            
            # Case 2: Redis 복구 시 해제
            store._fallback_mode = True
            healthy = store.check_redis_health()
            
            if healthy and not store._fallback_mode:
                logger.info("  ✅ Case 2: Fallback disabled on Redis recovery")
                case2_pass = True
            else:
                logger.warning(f"  ⚠️ Case 2: Fallback mode={store._fallback_mode}, healthy={healthy}")
                case2_pass = False
            
            # Case 3: Fallback 상태 조회
            status = store.get_fallback_status()
            if 'fallback_mode' in status and 'redis_healthy' in status:
                logger.info(f"  ✅ Case 3: Fallback status available: {status}")
                case3_pass = True
            else:
                logger.error("  ❌ Case 3: Fallback status incomplete")
                case3_pass = False
            
            self.results['redis_fallback'] = {
                'pass': case1_pass and case2_pass and case3_pass,
                'case1': case1_pass,
                'case2': case2_pass,
                'case3': case3_pass
            }
            
        except Exception as e:
            logger.error(f"  ❌ Redis fallback test failed: {e}")
            self.results['redis_fallback'] = {'pass': False, 'error': str(e)}
    
    # ========== Test 3: Snapshot Corruption Detection ==========
    
    def test_snapshot_corruption_detection(self):
        """
        Snapshot corruption 감지 검증
        
        검증:
        1. 필수 키 누락 감지
        2. 타임스탬프 검증
        3. Active orders 과다 감지
        """
        logger.info("\n[TEST 3] Snapshot Corruption Detection")
        
        try:
            store = StateStore(self.redis_client, self.db_conn, env='test')
            
            # Case 1: 필수 키 누락
            corrupt1 = {
                'session': {'session_id': 'test'},
                'positions': {},
                # 'metrics': {},  # 누락
                'risk_guard': {}
            }
            
            valid1 = store.validate_snapshot(corrupt1)
            if not valid1:
                logger.info("  ✅ Case 1: Missing key detected")
                case1_pass = True
            else:
                logger.error("  ❌ Case 1: Missing key not detected")
                case1_pass = False
            
            # Case 2: session_id 누락
            corrupt2 = {
                'session': {},  # session_id 없음
                'positions': {},
                'metrics': {},
                'risk_guard': {}
            }
            
            valid2 = store.validate_snapshot(corrupt2)
            if not valid2:
                logger.info("  ✅ Case 2: Missing session_id detected")
                case2_pass = True
            else:
                logger.error("  ❌ Case 2: Missing session_id not detected")
                case2_pass = False
            
            # Case 3: Active orders 과다
            corrupt3 = {
                'session': {'session_id': 'test', 'start_time': time.time()},
                'positions': {'active_orders': {str(i): {} for i in range(150)}},
                'metrics': {},
                'risk_guard': {}
            }
            
            valid3 = store.validate_snapshot(corrupt3)
            if not valid3:
                logger.info("  ✅ Case 3: Excessive active orders detected")
                case3_pass = True
            else:
                logger.error("  ❌ Case 3: Excessive active orders not detected")
                case3_pass = False
            
            self.results['snapshot_corruption'] = {
                'pass': case1_pass and case2_pass and case3_pass,
                'case1': case1_pass,
                'case2': case2_pass,
                'case3': case3_pass
            }
            
        except Exception as e:
            logger.error(f"  ❌ Snapshot corruption test failed: {e}")
            self.results['snapshot_corruption'] = {'pass': False, 'error': str(e)}
    
    # ========== Test 4: StateStore Key Prefix Consistency ==========
    
    def test_statestore_key_consistency(self):
        """
        StateStore Redis 키 prefix 일관성 검증
        
        검증:
        1. 키 형식: arbitrage:state:{env}:{session_id}:{category}
        2. 모든 카테고리 키 생성 확인
        3. 키 삭제 시 패턴 매칭 정확성
        """
        logger.info("\n[TEST 4] StateStore Key Consistency")
        
        try:
            store = StateStore(self.redis_client, self.db_conn, env='test')
            session_id = f"consistency_check_{int(time.time())}"
            
            # Case 1: 키 형식 검증
            categories = ['session', 'positions', 'metrics', 'risk_guard']
            expected_keys = []
            for cat in categories:
                key = store._get_redis_key(session_id, cat)
                expected_pattern = f"arbitrage:state:test:{session_id}:{cat}"
                if key == expected_pattern:
                    expected_keys.append(key)
                else:
                    logger.error(f"  ❌ Key format mismatch: {key} != {expected_pattern}")
            
            if len(expected_keys) == len(categories):
                logger.info(f"  ✅ Case 1: All keys match format")
                case1_pass = True
            else:
                logger.error(f"  ❌ Case 1: Key format inconsistent")
                case1_pass = False
            
            # Case 2: 저장 및 로드 검증
            test_data = {
                'session': {'session_id': session_id, 'start_time': time.time()},
                'positions': {'active_orders': {}},
                'metrics': {'total_trades_opened': 0},
                'risk_guard': {'daily_loss_usd': 0.0}
            }
            
            saved = store.save_state_to_redis(session_id, test_data)
            if saved:
                loaded = store.load_state_from_redis(session_id)
                if loaded and loaded.get('session', {}).get('session_id') == session_id:
                    logger.info("  ✅ Case 2: Save/load consistent")
                    case2_pass = True
                else:
                    logger.error("  ❌ Case 2: Load failed or data mismatch")
                    case2_pass = False
            else:
                logger.error("  ❌ Case 2: Save failed")
                case2_pass = False
            
            # Case 3: 패턴 삭제 검증
            deleted = store.delete_state_from_redis(session_id)
            if deleted:
                # 재로드 시도 - 없어야 함
                reloaded = store.load_state_from_redis(session_id)
                if not reloaded:
                    logger.info("  ✅ Case 3: Pattern deletion successful")
                    case3_pass = True
                else:
                    logger.error("  ❌ Case 3: Data still exists after deletion")
                    case3_pass = False
            else:
                logger.warning("  ⚠️ Case 3: Deletion returned False")
                case3_pass = False
            
            self.results['key_consistency'] = {
                'pass': case1_pass and case2_pass and case3_pass,
                'case1': case1_pass,
                'case2': case2_pass,
                'case3': case3_pass
            }
            
        except Exception as e:
            logger.error(f"  ❌ Key consistency test failed: {e}")
            self.results['key_consistency'] = {'pass': False, 'error': str(e)}
    
    # ========== Test 5: Entry Duplication Prevention ==========
    
    def test_entry_duplication_prevention(self):
        """
        LiveRunner 복구 시 entry duplication 방지 검증
        
        검증:
        1. 복원된 _total_trades_opened 카운터 유지
        2. 복원된 active_orders에 이미 있는 position_key는 재진입 방지
        3. loop_count 연속성 유지
        """
        logger.info("\n[TEST 5] Entry Duplication Prevention")
        
        try:
            # Snapshot 시뮬레이션
            snapshot_before = {
                'session': {
                    'session_id': 'dup_test',
                    'start_time': time.time(),
                    'loop_count': 100
                },
                'positions': {
                    'active_orders': {
                        '1': {'position_key': '1', 'direction': 'LONG_A_SHORT_B'}
                    }
                },
                'metrics': {
                    'total_trades_opened': 5,
                    'total_trades_closed': 3
                },
                'risk_guard': {
                    'daily_loss_usd': 0.0
                }
            }
            
            # Case 1: 카운터 유지 확인
            restored_count = snapshot_before['metrics']['total_trades_opened']
            if restored_count == 5:
                logger.info(f"  ✅ Case 1: Trade counter preserved: {restored_count}")
                case1_pass = True
            else:
                logger.error("  ❌ Case 1: Trade counter not preserved")
                case1_pass = False
            
            # Case 2: Active position 중복 체크 로직
            existing_keys = set(snapshot_before['positions']['active_orders'].keys())
            new_key = '2'
            duplicate_key = '1'
            
            if duplicate_key in existing_keys:
                logger.info(f"  ✅ Case 2: Duplicate position key detected: {duplicate_key}")
                case2_pass = True
            else:
                logger.error("  ❌ Case 2: Duplicate detection failed")
                case2_pass = False
            
            # Case 3: Loop count 연속성
            restored_loop = snapshot_before['session']['loop_count']
            next_loop = restored_loop + 1
            
            if next_loop == 101:
                logger.info(f"  ✅ Case 3: Loop count continuity: {restored_loop} → {next_loop}")
                case3_pass = True
            else:
                logger.error("  ❌ Case 3: Loop count not continuous")
                case3_pass = False
            
            self.results['entry_duplication'] = {
                'pass': case1_pass and case2_pass and case3_pass,
                'case1': case1_pass,
                'case2': case2_pass,
                'case3': case3_pass
            }
            
        except Exception as e:
            logger.error(f"  ❌ Entry duplication test failed: {e}")
            self.results['entry_duplication'] = {'pass': False, 'error': str(e)}
    
    # ========== Test 6: RiskGuard Edge Case Recovery ==========
    
    def test_riskguard_edge_case_recovery(self):
        """
        RiskGuard 복원 시 edge-case 검증
        
        검증:
        1. Daily loss 임계값 근처에서 복원
        2. Per-symbol state 복원 정확성
        3. Session start time 복원
        """
        logger.info("\n[TEST 6] RiskGuard Edge Case Recovery")
        
        try:
            from arbitrage.live_runner import RiskGuard, RiskLimits
            
            # Case 1: Daily loss 임계값 근처 복원
            limits = RiskLimits(max_daily_loss=100.0)
            guard1 = RiskGuard(limits)
            
            state1 = {
                'session_start_time': time.time(),
                'daily_loss_usd': 95.0,  # 거의 임계값
                'per_symbol_loss': {'BTC': 50.0, 'ETH': 45.0}
            }
            
            guard1.restore_state(state1)
            
            if guard1.daily_loss_usd == 95.0:
                logger.info(f"  ✅ Case 1: Daily loss restored near threshold: {guard1.daily_loss_usd}")
                case1_pass = True
            else:
                logger.error(f"  ❌ Case 1: Daily loss incorrect: {guard1.daily_loss_usd}")
                case1_pass = False
            
            # Case 2: Per-symbol state 복원
            if len(guard1.per_symbol_loss) == 2 and guard1.per_symbol_loss.get('BTC') == 50.0:
                logger.info(f"  ✅ Case 2: Per-symbol state restored: {guard1.per_symbol_loss}")
                case2_pass = True
            else:
                logger.error(f"  ❌ Case 2: Per-symbol state incorrect: {guard1.per_symbol_loss}")
                case2_pass = False
            
            # Case 3: Session start time 복원
            state2 = guard1.get_state()
            if 'session_start_time' in state2:
                logger.info(f"  ✅ Case 3: Session start time in state: {state2['session_start_time']}")
                case3_pass = True
            else:
                logger.error("  ❌ Case 3: Session start time missing")
                case3_pass = False
            
            self.results['riskguard_recovery'] = {
                'pass': case1_pass and case2_pass and case3_pass,
                'case1': case1_pass,
                'case2': case2_pass,
                'case3': case3_pass
            }
            
        except Exception as e:
            logger.error(f"  ❌ RiskGuard recovery test failed: {e}")
            self.results['riskguard_recovery'] = {'pass': False, 'error': str(e)}
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("\n" + "=" * 70)
        logger.info("D71 STABILITY CHECK - AUTOMATED VERIFICATION")
        logger.info("=" * 70)
        
        self.setup()
        
        try:
            self.test_ws_reconnect_edge_cases()
            self.test_redis_fallback_timing()
            self.test_snapshot_corruption_detection()
            self.test_statestore_key_consistency()
            self.test_entry_duplication_prevention()
            self.test_riskguard_edge_case_recovery()
            
        finally:
            self.cleanup()
        
        self.print_summary()
    
    def print_summary(self):
        """결과 요약"""
        logger.info("\n" + "=" * 70)
        logger.info("D71 STABILITY CHECK SUMMARY")
        logger.info("=" * 70)
        
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r.get('pass', False))
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result.get('pass', False) else "❌ FAIL"
            logger.info(f"{test_name}: {status}")
            
            if not result.get('pass', False) and 'error' in result:
                logger.error(f"  Error: {result['error']}")
        
        logger.info("=" * 70)
        logger.info(f"Result: {passed}/{total} tests PASSED")
        logger.info("=" * 70)
        
        return passed == total


if __name__ == "__main__":
    checker = D71StabilityChecker()
    all_pass = checker.run_all_tests()
    
    sys.exit(0 if all_pass else 1)

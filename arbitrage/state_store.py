#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D70: State Store Module

상태 영속화 및 복원을 위한 통합 SSOT 모듈.
Redis (실시간) + PostgreSQL (스냅샷) Hybrid Strategy.

책임:
- 세션 상태 저장/로드 (Redis)
- 주기적 스냅샷 저장/로드 (PostgreSQL)
- 상태 직렬화/역직렬화
- 일관성 검증
"""

import json
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import psycopg2
import redis

logger = logging.getLogger(__name__)


class StateStore:
    """
    상태 영속화/복원 통합 모듈
    
    Redis: 실시간 상태 (arbitrage:state:{env}:{session_id}:{category})
    PostgreSQL: 영구 스냅샷 (session_snapshots, position_snapshots, metrics_snapshots, risk_guard_snapshots)
    
    Usage:
        store = StateStore(redis_client, db_conn, env='paper')
        store.save_state_to_redis(session_id, state_data)
        snapshot = store.load_latest_snapshot(session_id)
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        db_conn: Optional[psycopg2.extensions.connection] = None,
        env: str = "paper"
    ):
        """
        Args:
            redis_client: Redis 클라이언트 (선택)
            db_conn: PostgreSQL 연결 (선택)
            env: 환경 (paper/live/backtest)
        """
        self.redis_client = redis_client
        self.db_conn = db_conn
        self.env = env
        
        # Redis/DB 사용 가능 여부
        self.redis_available = redis_client is not None
        self.db_available = db_conn is not None
        
        if not self.redis_available:
            logger.warning("[STATE_STORE] Redis not available, state persistence disabled")
        if not self.db_available:
            logger.warning("[STATE_STORE] PostgreSQL not available, snapshot persistence disabled")
    
    # ========== Redis Operations ==========
    
    def _get_redis_key(self, session_id: str, category: str) -> str:
        """Redis 키 생성"""
        return f"arbitrage:state:{self.env}:{session_id}:{category}"
    
    def save_state_to_redis(self, session_id: str, state_data: Dict[str, Any]) -> bool:
        """
        Redis에 현재 상태 저장
        
        Args:
            session_id: 세션 ID
            state_data: 상태 데이터 (session, positions, metrics, risk_guard)
        
        Returns:
            성공 여부
        """
        if not self.redis_available:
            logger.debug("[STATE_STORE] Redis not available, skipping save")
            return False
        
        try:
            for category, data in state_data.items():
                key = self._get_redis_key(session_id, category)
                serialized = self._serialize_for_redis(data)
                self.redis_client.set(key, serialized)
            
            logger.debug(f"[STATE_STORE] Saved state to Redis: {session_id}")
            return True
        
        except Exception as e:
            logger.error(f"[STATE_STORE] Failed to save to Redis: {e}")
            return False
    
    def load_state_from_redis(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Redis에서 상태 로드
        
        Args:
            session_id: 세션 ID
        
        Returns:
            상태 데이터 또는 None
        """
        if not self.redis_available:
            logger.debug("[STATE_STORE] Redis not available, cannot load")
            return None
        
        try:
            categories = ['session', 'positions', 'metrics', 'risk_guard']
            state_data = {}
            
            for category in categories:
                key = self._get_redis_key(session_id, category)
                data = self.redis_client.get(key)
                if data:
                    state_data[category] = self._deserialize_from_redis(data)
            
            if not state_data:
                logger.warning(f"[STATE_STORE] No state found in Redis: {session_id}")
                return None
            
            logger.info(f"[STATE_STORE] Loaded state from Redis: {session_id}")
            return state_data
        
        except Exception as e:
            logger.error(f"[STATE_STORE] Failed to load from Redis: {e}")
            return None
    
    def delete_state_from_redis(self, session_id: str) -> bool:
        """
        Redis에서 상태 삭제
        
        Args:
            session_id: 세션 ID
        
        Returns:
            성공 여부
        """
        if not self.redis_available:
            return False
        
        try:
            pattern = f"arbitrage:state:{self.env}:{session_id}:*"
            keys = list(self.redis_client.scan_iter(match=pattern))
            if keys:
                self.redis_client.delete(*keys)
            
            logger.info(f"[STATE_STORE] Deleted state from Redis: {session_id}")
            return True
        
        except Exception as e:
            logger.error(f"[STATE_STORE] Failed to delete from Redis: {e}")
            return False
    
    # ========== PostgreSQL Operations ==========
    
    def save_snapshot_to_db(
        self,
        session_id: str,
        state_data: Dict[str, Any],
        snapshot_type: str = "periodic"
    ) -> Optional[int]:
        """
        PostgreSQL에 스냅샷 저장
        
        Args:
            session_id: 세션 ID
            state_data: 상태 데이터 (session, positions, metrics, risk_guard)
            snapshot_type: 스냅샷 타입 (initial/periodic/on_trade/on_stop)
        
        Returns:
            snapshot_id 또는 None
        """
        if not self.db_available:
            logger.debug("[STATE_STORE] PostgreSQL not available, skipping snapshot")
            return None
        
        cursor = None
        try:
            cursor = self.db_conn.cursor()
            
            # 1. session_snapshots 저장
            session_data = state_data.get('session', {})
            cursor.execute("""
                INSERT INTO session_snapshots (
                    session_id, session_start_time, mode, paper_campaign_id,
                    config, loop_count, status, snapshot_type
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING snapshot_id
            """, (
                session_id,
                datetime.fromtimestamp(session_data.get('start_time', time.time())),
                session_data.get('mode', self.env),
                session_data.get('paper_campaign_id'),
                json.dumps(session_data.get('config', {})),
                session_data.get('loop_count', 0),
                session_data.get('status', 'running'),
                snapshot_type
            ))
            snapshot_id = cursor.fetchone()[0]
            
            # 2. position_snapshots 저장
            positions_data = state_data.get('positions', {})
            active_orders = positions_data.get('active_orders', {})
            for position_key, order_data in active_orders.items():
                cursor.execute("""
                    INSERT INTO position_snapshots (
                        snapshot_id, position_key, trade_data, order_a_data, order_b_data, position_open_time
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    snapshot_id,
                    position_key,
                    json.dumps(order_data.get('trade', {})),
                    json.dumps(order_data.get('order_a', {})),
                    json.dumps(order_data.get('order_b', {})),
                    datetime.fromtimestamp(order_data.get('position_open_time', time.time()))
                        if order_data.get('position_open_time') else None
                ))
            
            # 3. metrics_snapshots 저장
            metrics_data = state_data.get('metrics', {})
            cursor.execute("""
                INSERT INTO metrics_snapshots (
                    snapshot_id, total_trades_opened, total_trades_closed, total_winning_trades,
                    total_pnl_usd, max_dd_usd, per_symbol_pnl, per_symbol_trades_opened,
                    per_symbol_trades_closed, per_symbol_winning_trades,
                    portfolio_initial_capital, portfolio_equity
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                snapshot_id,
                metrics_data.get('total_trades_opened', 0),
                metrics_data.get('total_trades_closed', 0),
                metrics_data.get('total_winning_trades', 0),
                metrics_data.get('total_pnl_usd', 0.0),
                metrics_data.get('max_dd_usd', 0.0),
                json.dumps(metrics_data.get('per_symbol_pnl', {})),
                json.dumps(metrics_data.get('per_symbol_trades_opened', {})),
                json.dumps(metrics_data.get('per_symbol_trades_closed', {})),
                json.dumps(metrics_data.get('per_symbol_winning_trades', {})),
                metrics_data.get('portfolio_initial_capital', 10000.0),
                metrics_data.get('portfolio_equity', 10000.0)
            ))
            
            # 4. risk_guard_snapshots 저장
            risk_guard_data = state_data.get('risk_guard', {})
            cursor.execute("""
                INSERT INTO risk_guard_snapshots (
                    snapshot_id, session_start_time, daily_loss_usd,
                    per_symbol_loss, per_symbol_trades_rejected, per_symbol_trades_allowed,
                    per_symbol_capital_used, per_symbol_position_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                snapshot_id,
                datetime.fromtimestamp(risk_guard_data.get('session_start_time', time.time())),
                risk_guard_data.get('daily_loss_usd', 0.0),
                json.dumps(risk_guard_data.get('per_symbol_loss', {})),
                json.dumps(risk_guard_data.get('per_symbol_trades_rejected', {})),
                json.dumps(risk_guard_data.get('per_symbol_trades_allowed', {})),
                json.dumps(risk_guard_data.get('per_symbol_capital_used', {})),
                json.dumps(risk_guard_data.get('per_symbol_position_count', {}))
            ))
            
            self.db_conn.commit()
            logger.info(f"[STATE_STORE] Saved snapshot to DB: snapshot_id={snapshot_id}, type={snapshot_type}")
            return snapshot_id
        
        except Exception as e:
            if self.db_conn:
                self.db_conn.rollback()
            logger.error(f"[STATE_STORE] Failed to save snapshot: {e}")
            return None
        
        finally:
            if cursor:
                cursor.close()
    
    def load_latest_snapshot(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        PostgreSQL에서 최신 스냅샷 로드
        
        Args:
            session_id: 세션 ID
        
        Returns:
            스냅샷 데이터 또는 None
        """
        if not self.db_available:
            logger.debug("[STATE_STORE] PostgreSQL not available, cannot load snapshot")
            return None
        
        cursor = None
        try:
            cursor = self.db_conn.cursor()
            
            # 1. 최신 session_snapshot 조회
            cursor.execute("""
                SELECT snapshot_id, session_start_time, mode, paper_campaign_id,
                       config, loop_count, status, created_at
                FROM session_snapshots
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"[STATE_STORE] No snapshot found for session: {session_id}")
                return None
            
            snapshot_id, start_time, mode, campaign_id, config, loop_count, status, created_at = row
            
            # 2. position_snapshots 조회
            cursor.execute("""
                SELECT position_key, trade_data, order_a_data, order_b_data, position_open_time
                FROM position_snapshots
                WHERE snapshot_id = %s
            """, (snapshot_id,))
            
            active_orders = {}
            for pos_row in cursor.fetchall():
                position_key, trade_data, order_a_data, order_b_data, position_open_time = pos_row
                active_orders[position_key] = {
                    'trade': json.loads(trade_data) if isinstance(trade_data, str) else trade_data,
                    'order_a': json.loads(order_a_data) if isinstance(order_a_data, str) else order_a_data,
                    'order_b': json.loads(order_b_data) if isinstance(order_b_data, str) else order_b_data,
                    'position_open_time': position_open_time.timestamp() if position_open_time else None
                }
            
            # 3. metrics_snapshots 조회
            cursor.execute("""
                SELECT total_trades_opened, total_trades_closed, total_winning_trades,
                       total_pnl_usd, max_dd_usd, per_symbol_pnl, per_symbol_trades_opened,
                       per_symbol_trades_closed, per_symbol_winning_trades,
                       portfolio_initial_capital, portfolio_equity
                FROM metrics_snapshots
                WHERE snapshot_id = %s
            """, (snapshot_id,))
            
            metrics_row = cursor.fetchone()
            if metrics_row:
                metrics_data = {
                    'total_trades_opened': metrics_row[0],
                    'total_trades_closed': metrics_row[1],
                    'total_winning_trades': metrics_row[2],
                    'total_pnl_usd': float(metrics_row[3]),
                    'max_dd_usd': float(metrics_row[4]),
                    'per_symbol_pnl': json.loads(metrics_row[5]) if isinstance(metrics_row[5], str) else (metrics_row[5] or {}),
                    'per_symbol_trades_opened': json.loads(metrics_row[6]) if isinstance(metrics_row[6], str) else (metrics_row[6] or {}),
                    'per_symbol_trades_closed': json.loads(metrics_row[7]) if isinstance(metrics_row[7], str) else (metrics_row[7] or {}),
                    'per_symbol_winning_trades': json.loads(metrics_row[8]) if isinstance(metrics_row[8], str) else (metrics_row[8] or {}),
                    'portfolio_initial_capital': float(metrics_row[9]),
                    'portfolio_equity': float(metrics_row[10])
                }
            else:
                metrics_data = {}
            
            # 4. risk_guard_snapshots 조회
            cursor.execute("""
                SELECT session_start_time, daily_loss_usd,
                       per_symbol_loss, per_symbol_trades_rejected, per_symbol_trades_allowed,
                       per_symbol_capital_used, per_symbol_position_count
                FROM risk_guard_snapshots
                WHERE snapshot_id = %s
            """, (snapshot_id,))
            
            risk_row = cursor.fetchone()
            if risk_row:
                risk_guard_data = {
                    'session_start_time': risk_row[0].timestamp(),
                    'daily_loss_usd': float(risk_row[1]),
                    'per_symbol_loss': json.loads(risk_row[2]) if isinstance(risk_row[2], str) else (risk_row[2] or {}),
                    'per_symbol_trades_rejected': json.loads(risk_row[3]) if isinstance(risk_row[3], str) else (risk_row[3] or {}),
                    'per_symbol_trades_allowed': json.loads(risk_row[4]) if isinstance(risk_row[4], str) else (risk_row[4] or {}),
                    'per_symbol_capital_used': json.loads(risk_row[5]) if isinstance(risk_row[5], str) else (risk_row[5] or {}),
                    'per_symbol_position_count': json.loads(risk_row[6]) if isinstance(risk_row[6], str) else (risk_row[6] or {})
                }
            else:
                risk_guard_data = {}
            
            # 스냅샷 데이터 조합
            snapshot_data = {
                'session': {
                    'session_id': session_id,
                    'start_time': start_time.timestamp(),
                    'mode': mode,
                    'paper_campaign_id': campaign_id,
                    'config': json.loads(config) if isinstance(config, str) else config,
                    'loop_count': loop_count,
                    'status': status
                },
                'positions': {
                    'active_orders': active_orders
                },
                'metrics': metrics_data,
                'risk_guard': risk_guard_data
            }
            
            logger.info(f"[STATE_STORE] Loaded snapshot from DB: session_id={session_id}, snapshot_id={snapshot_id}")
            return snapshot_data
        
        except Exception as e:
            logger.error(f"[STATE_STORE] Failed to load snapshot: {e}")
            return None
        
        finally:
            if cursor:
                cursor.close()
    
    # ========== Serialization ==========
    
    def _serialize_for_redis(self, data: Any) -> str:
        """Redis 저장용 직렬화 (JSON)"""
        return json.dumps(data, default=self._json_default)
    
    def _deserialize_from_redis(self, data: str) -> Any:
        """Redis 로드용 역직렬화 (JSON)"""
        return json.loads(data)
    
    @staticmethod
    def _json_default(obj):
        """JSON 직렬화 헬퍼"""
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    # ========== Validation ==========
    
    def validate_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """
        스냅샷 무결성 검증
        
        Args:
            snapshot: 스냅샷 데이터
        
        Returns:
            검증 통과 여부
        """
        try:
            # 필수 키 확인
            required_keys = ['session', 'positions', 'metrics', 'risk_guard']
            for key in required_keys:
                if key not in snapshot:
                    logger.error(f"[STATE_STORE] Missing required key: {key}")
                    return False
            
            # 세션 데이터 확인
            session = snapshot['session']
            if not session.get('session_id'):
                logger.error("[STATE_STORE] Missing session_id")
                return False
            
            # 타임스탬프 확인 (1일 이내)
            start_time = session.get('start_time', 0)
            age = time.time() - start_time
            if age > 86400:
                logger.warning(f"[STATE_STORE] Snapshot is old: {age/3600:.1f} hours")
            
            # 포지션 수량 확인
            active_orders = snapshot['positions'].get('active_orders', {})
            if len(active_orders) > 100:
                logger.error(f"[STATE_STORE] Too many active orders: {len(active_orders)}")
                return False
            
            logger.debug("[STATE_STORE] Snapshot validation passed")
            return True
        
        except Exception as e:
            logger.error(f"[STATE_STORE] Snapshot validation failed: {e}")
            return False

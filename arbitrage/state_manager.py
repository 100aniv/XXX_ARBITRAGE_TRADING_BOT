#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — State Manager (Redis-backed)
================================================

Redis 기반 실시간 상태 관리:
- 포지션 상태
- 주문 상태
- 신호 상태
- 실행 결과

D21: Redis 통합 및 in-memory fallback
- Redis 미사용 시 in-memory 모드로 자동 fallback
- Namespace 기반 key 체계화 (live:docker, paper:local, shadow:docker 등)
- Observability 메트릭 지원
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import redis
import numpy as np

from arbitrage.types import (
    Position, Order, Signal, ExecutionResult, PortfolioState, OrderSide
)

logger = logging.getLogger(__name__)


class StateManager:
    """
    Redis 기반 상태 관리자 (D21: in-memory fallback 지원)
    
    실시간 거래 상태를 Redis에 저장하고 조회.
    Redis 미사용 시 자동으로 in-memory 모드로 전환.
    """
    
    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: int = 0,
        namespace: str = "default",
        enabled: bool = True,
        key_prefix: str = "arbitrage"
    ):
        """
        Args:
            redis_host: Redis 호스트 (None이면 in-memory 모드)
            redis_port: Redis 포트
            redis_db: Redis 데이터베이스
            namespace: 네임스페이스 (예: live:docker, paper:local, shadow:docker)
            enabled: Redis 사용 여부 (False면 항상 in-memory)
            key_prefix: 키 프리픽스 (기본값: arbitrage)
        """
        # 환경 변수에서 Redis 정보 읽기 (파라미터가 None이면)
        if redis_host is None:
            redis_host = os.getenv("REDIS_HOST", "localhost")
        if redis_port is None:
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.namespace = namespace
        self.key_prefix = key_prefix
        self.enabled = enabled
        
        self._redis: Optional[redis.Redis] = None
        self._in_memory_store: Dict[str, Any] = {}  # in-memory fallback
        self._redis_connected = False
        
        # 자동 연결 시도
        if self.enabled:
            self._try_connect()
    
    def _try_connect(self) -> None:
        """Redis 연결 시도 (실패 시 in-memory 모드로 fallback)"""
        try:
            self._redis = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_keepalive=True
            )
            self._redis.ping()
            self._redis_connected = True
            logger.info(f"[STATE_MANAGER] Redis connected: {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.warning(f"[STATE_MANAGER] Redis connection failed: {e}. Using in-memory state.")
            self._redis = None
            self._redis_connected = False
    
    def connect(self) -> None:
        """Redis 연결 (명시적 호출)"""
        if not self.enabled:
            logger.warning("[STATE_MANAGER] StateManager is disabled. Using in-memory state.")
            return
        self._try_connect()
    
    def disconnect(self) -> None:
        """Redis 연결 해제"""
        if self._redis:
            self._redis.close()
            self._redis_connected = False
            logger.info("[STATE_MANAGER] Redis disconnected")
    
    def _get_key(self, *parts: str) -> str:
        """키 생성 (namespace 포함)"""
        # namespace:key_prefix:parts
        return f"{self.namespace}:{self.key_prefix}:{':'.join(parts)}"
    
    def _set_redis_or_memory(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Redis 또는 in-memory에 저장"""
        if self._redis_connected and self._redis:
            try:
                if isinstance(value, dict):
                    self._redis.hset(key, mapping=value)
                else:
                    self._redis.set(key, value)
                if ttl:
                    self._redis.expire(key, ttl)
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis write failed: {e}. Falling back to in-memory.")
                self._in_memory_store[key] = value
        else:
            self._in_memory_store[key] = value
    
    def _get_redis_or_memory(self, key: str) -> Optional[Any]:
        """Redis 또는 in-memory에서 조회"""
        if self._redis_connected and self._redis:
            try:
                # 먼저 hash 타입으로 시도
                data = self._redis.hgetall(key)
                if data:
                    return data
                # hash가 아니면 string 타입으로 시도
                value = self._redis.get(key)
                return value
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis read failed: {e}. Falling back to in-memory.")
                return self._in_memory_store.get(key)
        else:
            return self._in_memory_store.get(key)
    
    # ========== 가격 관리 ==========
    
    def set_price(self, exchange: str, symbol: str, bid: float, ask: float) -> None:
        """
        가격 저장
        
        Args:
            exchange: 거래소
            symbol: 심볼
            bid: 매수호가
            ask: 매도호가
        """
        key = self._get_key("prices", exchange, symbol)
        data = {
            "bid": str(bid),
            "ask": str(ask),
            "mid": str((bid + ask) / 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._set_redis_or_memory(key, data, ttl=60)
    
    def get_price(self, exchange: str, symbol: str) -> Optional[Dict]:
        """가격 조회"""
        key = self._get_key("prices", exchange, symbol)
        return self._get_redis_or_memory(key)
    
    # ========== 신호 관리 ==========
    
    def set_signal(self, signal: Signal) -> None:
        """
        신호 저장
        
        Args:
            signal: Signal 객체
        """
        key = self._get_key("signal", signal.symbol)
        data = {
            "symbol": signal.symbol,
            "buy_exchange": signal.buy_exchange.value,
            "sell_exchange": signal.sell_exchange.value,
            "buy_price": str(signal.buy_price),
            "sell_price": str(signal.sell_price),
            "spread": str(signal.spread),
            "spread_pct": str(signal.spread_pct),
            "timestamp": signal.timestamp.isoformat()
        }
        self._set_redis_or_memory(key, data, ttl=300)
    
    def get_signal(self, symbol: str) -> Optional[Dict]:
        """신호 조회"""
        key = self._get_key("signal", symbol)
        return self._get_redis_or_memory(key)
    
    def get_all_signals(self) -> Dict[str, Dict]:
        """모든 신호 조회"""
        if self._redis_connected and self._redis:
            try:
                pattern = self._get_key("signal", "*")
                keys = self._redis.keys(pattern)
                signals = {}
                for key in keys:
                    symbol = key.split(":")[-1]
                    data = self._redis.hgetall(key)
                    if data:
                        signals[symbol] = data
                return signals
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis read failed: {e}. Falling back to in-memory.")
        
        # in-memory fallback
        signals = {}
        for key, value in self._in_memory_store.items():
            if "signal" in key:
                symbol = key.split(":")[-1]
                signals[symbol] = value
        return signals
    
    # ========== 주문 관리 ==========
    
    def set_order(self, order: Order) -> None:
        """
        주문 저장
        
        Args:
            order: Order 객체
        """
        key = self._get_key("orders", order.order_id)
        data = {
            "order_id": order.order_id,
            "exchange": order.exchange.value,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": str(order.quantity),
            "price": str(order.price),
            "status": order.status.value,
            "filled_quantity": str(order.filled_quantity),
            "fill_rate": str(order.fill_rate),
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat()
        }
        self._set_redis_or_memory(key, data, ttl=86400)
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """주문 조회"""
        key = self._get_key("orders", order_id)
        return self._get_redis_or_memory(key)
    
    def get_all_orders(self) -> Dict[str, Dict]:
        """모든 주문 조회"""
        if self._redis_connected and self._redis:
            try:
                pattern = self._get_key("orders", "*")
                keys = self._redis.keys(pattern)
                orders = {}
                for key in keys:
                    order_id = key.split(":")[-1]
                    data = self._redis.hgetall(key)
                    if data:
                        orders[order_id] = data
                return orders
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis read failed: {e}. Falling back to in-memory.")
        
        # in-memory fallback
        orders = {}
        for key, value in self._in_memory_store.items():
            if "orders" in key:
                order_id = key.split(":")[-1]
                orders[order_id] = value
        return orders
    
    # ========== 포지션 관리 ==========
    
    def set_position(self, position: Position) -> None:
        """
        포지션 저장
        
        Args:
            position: Position 객체
        """
        key = self._get_key("positions", position.symbol)
        data = {
            "symbol": position.symbol,
            "quantity": str(position.quantity),
            "entry_price": str(position.entry_price),
            "current_price": str(position.current_price),
            "side": position.side.value,
            "pnl": str(position.pnl),
            "pnl_pct": str(position.pnl_pct),
            "timestamp": position.timestamp.isoformat()
        }
        self._set_redis_or_memory(key, data, ttl=86400)
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """포지션 조회"""
        key = self._get_key("positions", symbol)
        return self._get_redis_or_memory(key)
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """모든 포지션 조회"""
        if self._redis_connected and self._redis:
            try:
                pattern = self._get_key("positions", "*")
                keys = self._redis.keys(pattern)
                positions = {}
                for key in keys:
                    symbol = key.split(":")[-1]
                    data = self._redis.hgetall(key)
                    if data:
                        positions[symbol] = data
                return positions
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis read failed: {e}. Falling back to in-memory.")
        
        # in-memory fallback
        positions = {}
        for key, value in self._in_memory_store.items():
            if "positions" in key:
                symbol = key.split(":")[-1]
                positions[symbol] = value
        return positions
    
    def delete_position(self, symbol: str) -> None:
        """포지션 삭제"""
        key = self._get_key("positions", symbol)
        if self._redis_connected and self._redis:
            try:
                self._redis.delete(key)
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis delete failed: {e}")
        if key in self._in_memory_store:
            del self._in_memory_store[key]
    
    # ========== 실행 결과 관리 ==========
    
    def set_execution(self, execution: ExecutionResult) -> None:
        """
        실행 결과 저장
        
        Args:
            execution: ExecutionResult 객체
        """
        key = self._get_key("execution", execution.symbol, str(execution.timestamp.timestamp()))
        data = {
            "symbol": execution.symbol,
            "buy_order_id": execution.buy_order_id,
            "sell_order_id": execution.sell_order_id,
            "buy_price": str(execution.buy_price),
            "sell_price": str(execution.sell_price),
            "quantity": str(execution.quantity),
            "gross_pnl": str(execution.gross_pnl),
            "net_pnl": str(execution.net_pnl),
            "fees": str(execution.fees),
            "pnl_pct": str(execution.pnl_pct),
            "timestamp": execution.timestamp.isoformat()
        }
        self._set_redis_or_memory(key, data, ttl=86400)
    
    def get_executions(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        실행 결과 조회
        
        Args:
            symbol: 심볼
            limit: 조회 개수
        
        Returns:
            실행 결과 리스트
        """
        if self._redis_connected and self._redis:
            try:
                pattern = self._get_key("execution", symbol, "*")
                keys = self._redis.keys(pattern)
                keys = sorted(keys, reverse=True)[:limit]
                executions = []
                for key in keys:
                    data = self._redis.hgetall(key)
                    if data:
                        executions.append(data)
                return executions
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis read failed: {e}. Falling back to in-memory.")
        
        # in-memory fallback
        executions = []
        for key, value in sorted(self._in_memory_store.items(), reverse=True):
            if f"execution:{symbol}" in key:
                executions.append(value)
                if len(executions) >= limit:
                    break
        return executions
    
    # ========== 메트릭 관리 ==========
    
    def set_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        메트릭 저장
        
        Args:
            metrics: 메트릭 딕셔너리
        """
        key = self._get_key("metrics", "live")
        
        # 숫자 값만 저장
        data = {}
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                data[k] = str(v)
        
        if data:
            self._set_redis_or_memory(key, data, ttl=300)
    
    def get_metrics(self) -> Dict[str, float]:
        """메트릭 조회"""
        key = self._get_key("metrics", "live")
        data = self._get_redis_or_memory(key)
        
        if not data:
            return {}
        
        # 문자열을 숫자로 변환
        metrics = {}
        for k, v in data.items():
            try:
                metrics[k] = float(v)
            except ValueError:
                metrics[k] = v
        
        return metrics
    
    # ========== 포트폴리오 상태 관리 ==========
    
    def set_portfolio_state(self, state: PortfolioState) -> None:
        """
        포트폴리오 상태 저장
        
        Args:
            state: PortfolioState 객체
        """
        key = self._get_key("portfolio", "state")
        data = {
            "total_balance": str(state.total_balance),
            "available_balance": str(state.available_balance),
            "total_position_value": str(state.total_position_value),
            "utilization_rate": str(state.utilization_rate),
            "timestamp": state.timestamp.isoformat()
        }
        self._set_redis_or_memory(key, data, ttl=300)
    
    def get_portfolio_state(self) -> Optional[Dict]:
        """포트폴리오 상태 조회"""
        key = self._get_key("portfolio", "state")
        return self._get_redis_or_memory(key)
    
    # ========== 통계 관리 ==========
    
    def increment_stat(self, stat_name: str, value: float = 1.0) -> None:
        """
        통계 증가
        
        Args:
            stat_name: 통계 이름
            value: 증가값
        """
        key = self._get_key("stats", stat_name)
        if self._redis_connected and self._redis:
            try:
                self._redis.incrbyfloat(key, value)
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis incr failed: {e}. Falling back to in-memory.")
                current = float(self._in_memory_store.get(key, 0))
                self._in_memory_store[key] = str(current + value)
        else:
            current = float(self._in_memory_store.get(key, 0))
            self._in_memory_store[key] = str(current + value)
    
    def get_stat(self, stat_name: str) -> float:
        """통계 조회"""
        key = self._get_key("stats", stat_name)
        if self._redis_connected and self._redis:
            try:
                value = self._redis.get(key)
                return float(value) if value else 0.0
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis read failed: {e}. Falling back to in-memory.")
        
        value = self._in_memory_store.get(key)
        return float(value) if value else 0.0
    
    def reset_stats(self) -> None:
        """통계 리셋"""
        if self._redis_connected and self._redis:
            try:
                pattern = self._get_key("stats", "*")
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.warning(f"[STATE_MANAGER] Redis delete failed: {e}")
        
        # in-memory 리셋
        keys_to_delete = [k for k in self._in_memory_store.keys() if "stats" in k]
        for k in keys_to_delete:
            del self._in_memory_store[k]
    
    # ========== 헬스 체크 ==========
    
    def set_heartbeat(self, component: str) -> None:
        """
        하트비트 저장
        
        Args:
            component: 컴포넌트 이름
        """
        key = self._get_key("heartbeat", component)
        self._set_redis_or_memory(key, datetime.now(timezone.utc).isoformat(), ttl=60)
    
    def get_heartbeat(self, component: str) -> Optional[str]:
        """하트비트 조회"""
        key = self._get_key("heartbeat", component)
        return self._get_redis_or_memory(key)

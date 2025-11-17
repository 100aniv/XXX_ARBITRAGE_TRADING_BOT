#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Tests — State Manager
==========================

Redis 기반 상태 관리자 테스트.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from arbitrage.state_manager import StateManager
from arbitrage.types import (
    Price, Order, Position, Signal, ExecutionResult,
    OrderSide, OrderStatus, ExchangeType
)


class TestStateManager:
    """StateManager 테스트"""
    
    @pytest.fixture
    def state_manager(self):
        """상태 관리자 픽스처"""
        # Redis 연결을 Mock으로 처리
        with patch('arbitrage.state_manager.redis.Redis'):
            manager = StateManager(
                redis_host="localhost",
                redis_port=6379,
                redis_db=0,
                namespace="test:local",
                enabled=True,
                key_prefix="arbitrage"
            )
            manager._redis = MagicMock()
            manager._redis_connected = True
            return manager
    
    def test_initialization(self, state_manager):
        """초기화"""
        assert state_manager.redis_host == "localhost"
        assert state_manager.redis_port == 6379
        assert state_manager.key_prefix == "arbitrage"
        assert state_manager.namespace == "test:local"
    
    def test_get_key(self, state_manager):
        """키 생성 (namespace 포함)"""
        key = state_manager._get_key("prices", "upbit", "KRW-BTC")
        assert key == "test:local:arbitrage:prices:upbit:KRW-BTC"
    
    def test_set_price(self, state_manager):
        """가격 저장"""
        state_manager.set_price("upbit", "KRW-BTC", 50_000_000, 50_100_000)
        
        # hset 호출 확인
        state_manager._redis.hset.assert_called_once()
        state_manager._redis.expire.assert_called_once()
    
    def test_get_price(self, state_manager):
        """가격 조회"""
        state_manager._redis.hgetall.return_value = {
            "bid": "50000000",
            "ask": "50100000"
        }
        
        price = state_manager.get_price("upbit", "KRW-BTC")
        
        assert price is not None
        assert price["bid"] == "50000000"
    
    def test_set_signal(self, state_manager):
        """신호 저장"""
        signal = Signal(
            symbol="BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=50_000_000,
            sell_price=50_500_000,
            spread=500_000,
            spread_pct=1.0
        )
        
        state_manager.set_signal(signal)
        
        state_manager._redis.hset.assert_called_once()
        state_manager._redis.expire.assert_called_once()
    
    def test_set_order(self, state_manager):
        """주문 저장"""
        order = Order(
            order_id="order_123",
            exchange=ExchangeType.UPBIT,
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_000_000,
            status=OrderStatus.PENDING
        )
        
        state_manager.set_order(order)
        
        state_manager._redis.hset.assert_called_once()
        state_manager._redis.expire.assert_called_once()
    
    def test_set_position(self, state_manager):
        """포지션 저장"""
        position = Position(
            symbol="KRW-BTC",
            quantity=1.0,
            entry_price=50_000_000,
            current_price=50_500_000,
            side=OrderSide.BUY
        )
        
        state_manager.set_position(position)
        
        state_manager._redis.hset.assert_called_once()
        state_manager._redis.expire.assert_called_once()
    
    def test_delete_position(self, state_manager):
        """포지션 삭제"""
        state_manager.delete_position("KRW-BTC")
        
        state_manager._redis.delete.assert_called_once()
    
    def test_set_execution(self, state_manager):
        """실행 결과 저장"""
        execution = ExecutionResult(
            symbol="BTC",
            buy_order_id="buy_123",
            sell_order_id="sell_123",
            buy_price=50_000_000,
            sell_price=50_500_000,
            quantity=1.0,
            gross_pnl=500_000,
            net_pnl=499_000,
            fees=1_000
        )
        
        state_manager.set_execution(execution)
        
        state_manager._redis.hset.assert_called_once()
        state_manager._redis.expire.assert_called_once()
    
    def test_set_metrics(self, state_manager):
        """메트릭 저장"""
        metrics = {
            "total_balance": 10_000_000,
            "available_balance": 9_000_000,
            "positions_count": 5
        }
        
        state_manager.set_metrics(metrics)
        
        state_manager._redis.hset.assert_called_once()
        state_manager._redis.expire.assert_called_once()
    
    def test_get_metrics(self, state_manager):
        """메트릭 조회"""
        state_manager._redis.hgetall.return_value = {
            "total_balance": "10000000",
            "available_balance": "9000000"
        }
        
        metrics = state_manager.get_metrics()
        
        assert metrics["total_balance"] == 10_000_000
        assert metrics["available_balance"] == 9_000_000
    
    def test_increment_stat(self, state_manager):
        """통계 증가"""
        state_manager.increment_stat("trades", 1.0)
        
        state_manager._redis.incrbyfloat.assert_called_once()
    
    def test_get_stat(self, state_manager):
        """통계 조회"""
        state_manager._redis.get.return_value = "100"
        
        stat = state_manager.get_stat("trades")
        
        assert stat == 100.0
    
    def test_set_heartbeat(self, state_manager):
        """하트비트 저장"""
        state_manager.set_heartbeat("live_trader")
        
        state_manager._redis.set.assert_called_once()
    
    def test_get_heartbeat(self, state_manager):
        """하트비트 조회"""
        state_manager._redis.get.return_value = datetime.utcnow().isoformat()
        
        heartbeat = state_manager.get_heartbeat("live_trader")
        
        assert heartbeat is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

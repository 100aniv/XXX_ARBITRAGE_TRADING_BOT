#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D21 Tests — StateManager Redis Integration & Observability

StateManager의 Redis 통합 및 in-memory fallback 테스트:
- Redis 연결 성공/실패 시나리오
- Namespace 기반 key 생성
- In-memory fallback 동작
- Observability 메트릭 저장/조회
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from arbitrage.state_manager import StateManager
from arbitrage.types import (
    Price, Order, Position, Signal, ExecutionResult,
    OrderSide, OrderStatus, ExchangeType
)


class TestStateManagerRedisIntegration:
    """StateManager Redis 통합 테스트"""
    
    def test_state_manager_with_redis_enabled(self):
        """Redis enabled 상태에서 StateManager 생성"""
        with patch('arbitrage.state_manager.redis.Redis') as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True
            
            manager = StateManager(
                redis_host="localhost",
                redis_port=6379,
                redis_db=0,
                namespace="test:redis",
                enabled=True
            )
            
            # Redis 연결 시도 확인
            assert manager.enabled == True
            assert manager._redis_connected == True
    
    def test_state_manager_with_redis_disabled(self):
        """Redis disabled 상태에서 StateManager 생성"""
        manager = StateManager(
            redis_host="localhost",
            redis_port=6379,
            namespace="test:disabled",
            enabled=False
        )
        
        # Redis 연결 시도 안 함
        assert manager.enabled == False
        assert manager._redis_connected == False
        assert manager._redis is None
    
    def test_state_manager_redis_connection_failure(self):
        """Redis 연결 실패 시 in-memory fallback"""
        with patch('arbitrage.state_manager.redis.Redis') as mock_redis:
            mock_redis.side_effect = Exception("Connection refused")
            
            manager = StateManager(
                redis_host="localhost",
                redis_port=6379,
                namespace="test:fallback",
                enabled=True
            )
            
            # Redis 연결 실패, in-memory 모드로 fallback
            assert manager._redis_connected == False
            assert manager._redis is None
            assert isinstance(manager._in_memory_store, dict)


class TestStateManagerNamespace:
    """StateManager Namespace 테스트"""
    
    @pytest.fixture
    def manager_live(self):
        """Live 모드 StateManager"""
        manager = StateManager(
            redis_host="localhost",
            redis_port=6379,
            namespace="live:docker",
            enabled=False  # in-memory 모드
        )
        return manager
    
    @pytest.fixture
    def manager_paper(self):
        """Paper 모드 StateManager"""
        manager = StateManager(
            redis_host="localhost",
            redis_port=6379,
            namespace="paper:local",
            enabled=False  # in-memory 모드
        )
        return manager
    
    @pytest.fixture
    def manager_shadow(self):
        """Shadow 모드 StateManager"""
        manager = StateManager(
            redis_host="localhost",
            redis_port=6379,
            namespace="shadow:docker",
            enabled=False  # in-memory 모드
        )
        return manager
    
    def test_namespace_in_key_live(self, manager_live):
        """Live 모드에서 namespace가 key에 포함"""
        key = manager_live._get_key("position", "BTC_KRW")
        assert key == "live:docker:arbitrage:position:BTC_KRW"
    
    def test_namespace_in_key_paper(self, manager_paper):
        """Paper 모드에서 namespace가 key에 포함"""
        key = manager_paper._get_key("position", "BTC_KRW")
        assert key == "paper:local:arbitrage:position:BTC_KRW"
    
    def test_namespace_in_key_shadow(self, manager_shadow):
        """Shadow 모드에서 namespace가 key에 포함"""
        key = manager_shadow._get_key("position", "BTC_KRW")
        assert key == "shadow:docker:arbitrage:position:BTC_KRW"


class TestStateManagerInMemoryFallback:
    """StateManager In-Memory Fallback 테스트"""
    
    @pytest.fixture
    def manager(self):
        """In-memory 모드 StateManager"""
        manager = StateManager(
            redis_host="localhost",
            redis_port=6379,
            namespace="test:memory",
            enabled=False  # in-memory 모드
        )
        return manager
    
    def test_set_and_get_price_in_memory(self, manager):
        """In-memory에서 가격 저장/조회"""
        manager.set_price("upbit", "BTC_KRW", 50_000_000, 50_100_000)
        
        price = manager.get_price("upbit", "BTC_KRW")
        
        assert price is not None
        assert price["bid"] == "50000000"
        assert price["ask"] == "50100000"
    
    def test_set_and_get_position_in_memory(self, manager):
        """In-memory에서 포지션 저장/조회"""
        position = Position(
            symbol="BTC_KRW",
            quantity=1.0,
            entry_price=50_000_000,
            current_price=50_500_000,
            side=OrderSide.BUY
        )
        
        manager.set_position(position)
        
        retrieved = manager.get_position("BTC_KRW")
        
        assert retrieved is not None
        assert retrieved["symbol"] == "BTC_KRW"
        assert retrieved["quantity"] == "1.0"
    
    def test_increment_stat_in_memory(self, manager):
        """In-memory에서 통계 증가"""
        manager.increment_stat("trades_total", 1.0)
        manager.increment_stat("trades_total", 2.0)
        
        stat = manager.get_stat("trades_total")
        
        assert stat == 3.0
    
    def test_set_and_get_metrics_in_memory(self, manager):
        """In-memory에서 메트릭 저장/조회"""
        metrics = {
            "trades_total": 42,
            "safety_violations": 0,
            "circuit_breaker_triggers": 0
        }
        
        manager.set_metrics(metrics)
        
        retrieved = manager.get_metrics()
        
        assert retrieved["trades_total"] == 42
        assert retrieved["safety_violations"] == 0
        assert retrieved["circuit_breaker_triggers"] == 0


class TestStateManagerObservability:
    """StateManager Observability 메트릭 테스트"""
    
    @pytest.fixture
    def manager(self):
        """In-memory 모드 StateManager"""
        manager = StateManager(
            redis_host="localhost",
            redis_port=6379,
            namespace="live:docker",
            enabled=False  # in-memory 모드
        )
        return manager
    
    def test_observability_metrics_trades(self, manager):
        """거래 수 메트릭"""
        manager.increment_stat("trades_total", 1.0)
        manager.increment_stat("trades_today", 1.0)
        
        assert manager.get_stat("trades_total") == 1.0
        assert manager.get_stat("trades_today") == 1.0
    
    def test_observability_metrics_safety(self, manager):
        """안전 메트릭"""
        manager.increment_stat("safety_violations_total", 1.0)
        manager.increment_stat("circuit_breaker_triggers_total", 1.0)
        
        assert manager.get_stat("safety_violations_total") == 1.0
        assert manager.get_stat("circuit_breaker_triggers_total") == 1.0
    
    def test_observability_metrics_heartbeat(self, manager):
        """하트비트 메트릭"""
        manager.set_heartbeat("live_trader")
        
        heartbeat = manager.get_heartbeat("live_trader")
        
        assert heartbeat is not None
        assert isinstance(heartbeat, str)
    
    def test_observability_metrics_comprehensive(self, manager):
        """종합 메트릭 조회"""
        # 메트릭 설정
        metrics = {
            "trades_total": 42,
            "trades_today": 5,
            "safety_violations_total": 0,
            "circuit_breaker_triggers_total": 0,
            "avg_trade_pnl": 1500.50
        }
        
        manager.set_metrics(metrics)
        
        # 메트릭 조회
        retrieved = manager.get_metrics()
        
        assert retrieved["trades_total"] == 42
        assert retrieved["trades_today"] == 5
        assert retrieved["safety_violations_total"] == 0
        assert retrieved["circuit_breaker_triggers_total"] == 0
        assert retrieved["avg_trade_pnl"] == 1500.50


class TestStateManagerModeNamespaces:
    """StateManager 모드별 Namespace 테스트"""
    
    def test_live_mode_namespace_structure(self):
        """Live 모드 namespace 구조"""
        manager = StateManager(
            namespace="live:docker",
            enabled=False
        )
        
        # Live 모드 key 예시
        position_key = manager._get_key("position", "upbit", "BTC_KRW")
        metrics_key = manager._get_key("metrics", "live")
        
        assert "live:docker" in position_key
        assert "live:docker" in metrics_key
    
    def test_paper_mode_namespace_structure(self):
        """Paper 모드 namespace 구조"""
        manager = StateManager(
            namespace="paper:local",
            enabled=False
        )
        
        # Paper 모드 key 예시
        position_key = manager._get_key("position", "upbit", "BTC_KRW")
        metrics_key = manager._get_key("metrics", "live")
        
        assert "paper:local" in position_key
        assert "paper:local" in metrics_key
    
    def test_shadow_mode_namespace_structure(self):
        """Shadow 모드 namespace 구조"""
        manager = StateManager(
            namespace="shadow:docker",
            enabled=False
        )
        
        # Shadow 모드 key 예시
        position_key = manager._get_key("position", "upbit", "BTC_KRW")
        metrics_key = manager._get_key("metrics", "live")
        
        assert "shadow:docker" in position_key
        assert "shadow:docker" in metrics_key


class TestStateManagerEnvironmentVariables:
    """StateManager 환경 변수 테스트"""
    
    def test_redis_host_from_env(self):
        """환경 변수에서 Redis 호스트 읽기"""
        with patch.dict('os.environ', {'REDIS_HOST': 'redis-server'}):
            manager = StateManager(
                redis_host=None,  # None이면 환경 변수 읽음
                redis_port=6379,
                enabled=False
            )
            
            assert manager.redis_host == "redis-server"
    
    def test_redis_port_from_env(self):
        """환경 변수에서 Redis 포트 읽기"""
        with patch.dict('os.environ', {'REDIS_PORT': '6380'}):
            manager = StateManager(
                redis_host="localhost",
                redis_port=None,  # None이면 환경 변수 읽음
                enabled=False
            )
            
            assert manager.redis_port == 6380
    
    def test_redis_defaults_when_env_not_set(self):
        """환경 변수 미설정 시 기본값 사용"""
        with patch.dict('os.environ', {}, clear=True):
            manager = StateManager(
                redis_host=None,
                redis_port=None,
                enabled=False
            )
            
            assert manager.redis_host == "localhost"
            assert manager.redis_port == 6379


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

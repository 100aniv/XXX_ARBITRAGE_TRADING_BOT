# -*- coding: utf-8 -*-
"""
D79-3: Cross-Exchange Engine Integration - Tests

CrossExchangeIntegration 레이어 및 엔진 통합 테스트.

테스트 범위:
1. Integration Layer 기본 기능
2. Entry/Exit tick 시나리오
3. Health/Secrets 연동
4. PositionManager 연동
"""

import pytest
import time
import redis
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from arbitrage.cross_exchange import (
    CrossExchangeIntegration,
    CrossExchangeDecision,
    CrossExchangeAction,
    CrossExchangeUniverseProvider,
    SpreadModel,
    FXConverter,
    CrossExchangeStrategy,
    CrossExchangePositionManager,
    SymbolMapper,
)
from arbitrage.cross_exchange.spread_model import CrossSpread


class TestCrossExchangeIntegrationBasic:
    """CrossExchangeIntegration 기본 기능 테스트"""
    
    def test_integration_initialization(self):
        """Integration 초기화"""
        # Mock dependencies
        universe_provider = Mock()
        spread_model = Mock()
        fx_converter = Mock()
        strategy = Mock()
        position_manager = Mock()
        health_monitor = Mock()
        settings = Mock()
        
        integration = CrossExchangeIntegration(
            universe_provider=universe_provider,
            spread_model=spread_model,
            fx_converter=fx_converter,
            strategy=strategy,
            position_manager=position_manager,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        assert integration.universe_provider == universe_provider
        assert integration.strategy == strategy
        assert integration.position_manager == position_manager
        assert integration.tick_count == 0
    
    def test_integration_metrics(self):
        """Integration 메트릭"""
        # Setup
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        position_manager.get_inventory.return_value = {"positive": 0, "negative": 0}
        
        integration = CrossExchangeIntegration(
            universe_provider=Mock(),
            spread_model=Mock(),
            fx_converter=Mock(),
            strategy=Mock(),
            position_manager=position_manager,
            health_monitor=Mock(),
            settings=Mock(),
        )
        
        metrics = integration.get_metrics()
        assert "tick_count" in metrics
        assert "entry_signals_generated" in metrics
        assert "exit_signals_generated" in metrics
        assert "open_positions" in metrics


class TestCrossExchangeIntegrationEntry:
    """Entry tick 시나리오 테스트"""
    
    def test_entry_tick_no_universe(self):
        """Entry tick - Universe 없음"""
        # Setup
        universe_provider = Mock()
        universe_provider.select_universe.return_value = []
        
        integration = CrossExchangeIntegration(
            universe_provider=universe_provider,
            spread_model=Mock(),
            fx_converter=Mock(),
            strategy=Mock(),
            position_manager=Mock(),
            health_monitor=Mock(),
            settings=Mock(),
        )
        
        # Execute
        decisions = integration.tick_entry()
        
        # Verify
        assert decisions == []
    
    def test_entry_tick_health_degraded(self):
        """Entry tick - Health degraded → NO_ACTION"""
        # Setup
        universe_provider = Mock()
        spread_model = Mock()
        fx_converter = Mock()
        strategy = Mock()
        position_manager = Mock()
        health_monitor = Mock()
        settings = Mock()
        
        # Health degraded
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        health_monitor.get_status.return_value = ExchangeHealthStatus.DOWN
        
        # Mock universe
        mapping = Mock()
        mapping.upbit_symbol = "KRW-BTC"
        mapping.binance_symbol = "BTCUSDT"
        universe_provider.select_universe.return_value = [mapping]
        
        # Mock FX
        fx_rate = Mock()
        fx_rate.confidence = 1.0
        fx_converter.get_fx_rate.return_value = fx_rate
        
        # Mock spread
        mock_spread = Mock(spec=CrossSpread)
        mock_spread.spread_percent = 0.8
        mock_spread.upbit_volume_krw = 200_000_000
        mock_spread.binance_volume_usdt = 150_000
        spread_model.calculate_spread.return_value = mock_spread
        
        # Strategy returns NO_ACTION (health degraded)
        signal = Mock()
        signal.action = CrossExchangeAction.NO_ACTION
        signal.reason = "health degraded"
        strategy.evaluate_entry.return_value = signal
        
        integration = CrossExchangeIntegration(
            universe_provider=universe_provider,
            spread_model=spread_model,
            fx_converter=fx_converter,
            strategy=strategy,
            position_manager=position_manager,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        # Execute
        decisions = integration.tick_entry()
        
        # Verify: No entry (health degraded)
        assert len(decisions) == 0


class TestCrossExchangeIntegrationExit:
    """Exit tick 시나리오 테스트"""
    
    def test_exit_tick_no_positions(self):
        """Exit tick - 포지션 없음"""
        # Setup
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        integration = CrossExchangeIntegration(
            universe_provider=Mock(),
            spread_model=Mock(),
            fx_converter=Mock(),
            strategy=Mock(),
            position_manager=position_manager,
            health_monitor=Mock(),
            settings=Mock(),
        )
        
        # Execute
        decisions = integration.tick_exit()
        
        # Verify
        assert decisions == []


class TestCrossExchangeIntegrationRealComponents:
    """실제 컴포넌트 연동 테스트 (Redis 필요)"""
    
    @pytest.fixture
    def redis_client(self):
        """Redis 클라이언트"""
        try:
            client = redis.Redis(host='localhost', port=6379, db=15, decode_responses=True)
            client.ping()
            yield client
            # Cleanup
            client.flushdb()
        except redis.ConnectionError:
            pytest.skip("Redis not available")
    
    def test_integration_with_real_components(self, redis_client):
        """실제 컴포넌트와 통합 테스트"""
        # Setup real components
        symbol_mapper = SymbolMapper()
        fx_converter = FXConverter()  # No clients (fallback mode)
        spread_model = SpreadModel(fx_converter=fx_converter)
        
        # Mock universe provider (avoid requiring real clients)
        universe_provider = Mock()
        universe_provider.select_universe = Mock(return_value=[])
        
        strategy = CrossExchangeStrategy(
            min_spread_percent=0.5,
            tp_spread_percent=0.2,
            sl_spread_percent=-0.3,
        )
        
        position_manager = CrossExchangePositionManager(
            redis_client=redis_client,
        )
        
        # Mock health monitor and settings
        health_monitor = Mock()
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        health_monitor.get_status.return_value = ExchangeHealthStatus.HEALTHY
        
        settings = Mock()
        settings.upbit_access_key = "test_key"
        settings.upbit_secret_key = "test_secret"
        settings.binance_api_key = "test_key"
        settings.binance_api_secret = "test_secret"
        
        # Create integration
        integration = CrossExchangeIntegration(
            universe_provider=universe_provider,
            spread_model=spread_model,
            fx_converter=fx_converter,
            strategy=strategy,
            position_manager=position_manager,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        # Verify
        assert integration is not None
        metrics = integration.get_metrics()
        assert metrics["tick_count"] == 0
        assert metrics["open_positions"] == 0


def test_integration_import():
    """Integration 모듈 import 테스트"""
    from arbitrage.cross_exchange import CrossExchangeIntegration, CrossExchangeDecision
    assert CrossExchangeIntegration is not None
    assert CrossExchangeDecision is not None

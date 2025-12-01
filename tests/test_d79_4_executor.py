# -*- coding: utf-8 -*-
"""
D79-4: Cross-Exchange Executor Tests

CrossExchangeExecutor 및 Orchestrator 테스트.

테스트 범위:
1. Order size calculation
2. Full fill success scenario
3. RiskGuard block scenario
4. Partial fill / Rollback scenario
5. Health degraded / No trade scenario
6. Orchestrator integration
"""

import pytest
import time
import redis
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from arbitrage.cross_exchange import (
    CrossExchangeExecutor,
    CrossExchangeOrchestrator,
    CrossExchangeIntegration,
    CrossExchangeDecision,
    CrossExchangeAction,
    CrossExchangePositionManager,
    CrossExchangeStrategy,
    FXConverter,
    LegExecutionResult,
    CrossExecutionResult,
)
from arbitrage.exchanges.base import OrderResult, OrderStatus, OrderSide, OrderType


class FakeExchangeClient:
    """Fake exchange client for testing"""
    
    def __init__(self, name: str, fill_immediately: bool = True):
        self.name = name
        self.fill_immediately = fill_immediately
        self.orders = []
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs
    ) -> OrderResult:
        """Fake order creation"""
        order_id = f"{self.name}_{len(self.orders) + 1}"
        
        status = OrderStatus.FILLED if self.fill_immediately else OrderStatus.OPEN
        filled_qty = qty if self.fill_immediately else 0.0
        
        order = OrderResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            order_type=order_type,
            status=status,
            filled_qty=filled_qty,
        )
        
        self.orders.append(order)
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Fake order cancellation"""
        return True
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """Fake order status query"""
        for order in self.orders:
            if order.order_id == order_id:
                return order
        raise ValueError(f"Order not found: {order_id}")


class TestCrossExchangeExecutorBasic:
    """CrossExchangeExecutor 기본 기능 테스트"""
    
    def test_executor_initialization(self):
        """Executor 초기화"""
        upbit_client = FakeExchangeClient("upbit")
        binance_client = FakeExchangeClient("binance")
        position_manager = Mock()
        fx_converter = FXConverter()
        health_monitor = Mock()
        settings = Mock()
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        assert executor is not None
        assert executor.total_executions == 0
    
    def test_build_order_sizes(self):
        """주문 수량 계산"""
        # Setup
        upbit_client = FakeExchangeClient("upbit")
        binance_client = FakeExchangeClient("binance")
        position_manager = Mock()
        fx_converter = FXConverter()
        health_monitor = Mock()
        settings = Mock()
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,  # 100M KRW
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        # Execute
        sizes = executor._build_order_sizes(decision)
        
        # Verify
        assert "upbit_qty" in sizes
        assert "binance_qty" in sizes
        assert "upbit_price" in sizes
        assert "binance_price" in sizes
        assert sizes["upbit_qty"] > 0
        assert sizes["binance_qty"] > 0


class TestCrossExchangeExecutorScenarios:
    """CrossExchangeExecutor 시나리오 테스트"""
    
    def test_execute_decision_full_fill_success(self):
        """전체 체결 성공 시나리오"""
        # Setup: Both exchanges fill immediately
        upbit_client = FakeExchangeClient("upbit", fill_immediately=True)
        binance_client = FakeExchangeClient("binance", fill_immediately=True)
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        health_monitor.get_status.return_value = ExchangeHealthStatus.HEALTHY
        
        settings = Mock()
        settings.upbit_access_key = "test"
        settings.upbit_secret_key = "test"
        settings.binance_api_key = "test"
        settings.binance_api_secret = "test"
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test entry",
            timestamp=time.time(),
            entry_side="positive",
        )
        
        # Execute
        result = executor.execute_decision(decision)
        
        # Verify
        assert result.status == "success"
        assert result.upbit.is_filled()
        assert result.binance.is_filled()
        assert len(upbit_client.orders) == 1
        assert len(binance_client.orders) == 1
        assert executor.successful_executions == 1
    
    def test_execute_decision_risk_guard_block(self):
        """RiskGuard block 시나리오"""
        # Setup: Health degraded
        upbit_client = FakeExchangeClient("upbit")
        binance_client = FakeExchangeClient("binance")
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        health_monitor.get_status.return_value = ExchangeHealthStatus.DOWN
        
        settings = Mock()
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test entry",
            timestamp=time.time(),
        )
        
        # Execute
        result = executor.execute_decision(decision)
        
        # Verify: Blocked (no orders placed)
        assert result.status in ["blocked", "failed"]
        assert "Health" in result.note or "degraded" in result.note.lower()
        assert len(upbit_client.orders) == 0
        assert len(binance_client.orders) == 0
        assert executor.failed_executions == 1
    
    def test_execute_decision_partial_fill_triggers_rollback(self):
        """부분 체결 → 롤백 시나리오"""
        # Setup: Upbit fills, Binance doesn't
        upbit_client = FakeExchangeClient("upbit", fill_immediately=True)
        binance_client = FakeExchangeClient("binance", fill_immediately=False)
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        health_monitor.get_status.return_value = ExchangeHealthStatus.HEALTHY
        
        settings = Mock()
        settings.upbit_access_key = "test"
        settings.upbit_secret_key = "test"
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test entry",
            timestamp=time.time(),
        )
        
        # Execute
        result = executor.execute_decision(decision)
        
        # Verify: Partial fill detected
        assert result.status in ["partial_hedged", "rolled_back"]
        assert result.upbit.is_filled()
        assert not result.binance.is_filled()
        assert "Partial fill" in result.note or "exposure" in result.note.lower()
        assert executor.partial_hedged_executions == 1
    
    def test_execute_decision_health_degraded_no_trade(self):
        """Health degraded → 주문 실행 안 함"""
        # Setup
        upbit_client = FakeExchangeClient("upbit")
        binance_client = FakeExchangeClient("binance")
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        health_monitor.get_status.side_effect = lambda x: (
            ExchangeHealthStatus.DEGRADED if x == "upbit" else ExchangeHealthStatus.DOWN
        )
        
        settings = Mock()
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test entry",
            timestamp=time.time(),
        )
        
        # Execute
        result = executor.execute_decision(decision)
        
        # Verify: No trade (health degraded)
        assert result.status in ["blocked", "failed"]
        assert len(upbit_client.orders) == 0
        assert len(binance_client.orders) == 0


class TestCrossExchangeOrchestrator:
    """CrossExchangeOrchestrator 테스트"""
    
    def test_orchestrator_initialization(self):
        """Orchestrator 초기화"""
        integration = Mock()
        executor = Mock()
        
        orchestrator = CrossExchangeOrchestrator(
            integration=integration,
            executor=executor,
            enable_execution=True,
        )
        
        assert orchestrator is not None
        assert orchestrator.enable_execution is True
    
    def test_orchestrator_process_entry_tick_paper_mode(self):
        """Orchestrator Entry tick (Paper 모드)"""
        # Setup
        integration = Mock()
        executor = Mock()
        
        # Mock integration to return decisions
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        integration.tick_entry.return_value = [decision]
        
        orchestrator = CrossExchangeOrchestrator(
            integration=integration,
            executor=executor,
            enable_execution=False,  # Paper mode
        )
        
        # Execute
        decisions, results = orchestrator.process_entry_tick()
        
        # Verify
        assert len(decisions) == 1
        assert len(results) == 0  # No execution (Paper mode)
        integration.tick_entry.assert_called_once()
        executor.execute_decision.assert_not_called()
    
    def test_orchestrator_process_entry_tick_real_execution(self):
        """Orchestrator Entry tick (실제 실행)"""
        # Setup
        integration = Mock()
        executor = Mock()
        
        # Mock integration to return decisions
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        integration.tick_entry.return_value = [decision]
        
        # Mock executor to return result
        result = Mock(spec=CrossExecutionResult)
        result.status = "success"
        executor.execute_decision.return_value = result
        
        orchestrator = CrossExchangeOrchestrator(
            integration=integration,
            executor=executor,
            enable_execution=True,  # Real execution
        )
        
        # Execute
        decisions, results = orchestrator.process_entry_tick()
        
        # Verify
        assert len(decisions) == 1
        assert len(results) == 1
        integration.tick_entry.assert_called_once()
        executor.execute_decision.assert_called_once_with(decision)
    
    def test_orchestrator_process_exit_tick(self):
        """Orchestrator Exit tick"""
        # Setup
        integration = Mock()
        executor = Mock()
        
        # Mock integration to return decisions
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.EXIT_TP,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.2,
            reason="TP",
            timestamp=time.time(),
        )
        integration.tick_exit.return_value = [decision]
        
        # Mock executor to return result
        result = Mock(spec=CrossExecutionResult)
        result.status = "success"
        executor.execute_decision.return_value = result
        
        orchestrator = CrossExchangeOrchestrator(
            integration=integration,
            executor=executor,
            enable_execution=True,
        )
        
        # Execute
        decisions, results = orchestrator.process_exit_tick()
        
        # Verify
        assert len(decisions) == 1
        assert len(results) == 1
        integration.tick_exit.assert_called_once()
        executor.execute_decision.assert_called_once_with(decision)


def test_executor_import():
    """Executor 모듈 import 테스트"""
    from arbitrage.cross_exchange import (
        CrossExchangeExecutor,
        LegExecutionResult,
        CrossExecutionResult,
        CrossExchangeOrchestrator,
    )
    assert CrossExchangeExecutor is not None
    assert LegExecutionResult is not None
    assert CrossExecutionResult is not None
    assert CrossExchangeOrchestrator is not None

# -*- coding: utf-8 -*-
"""
D79-6: Cross-Exchange Monitoring & Metrics Tests

CrossExchangeMetrics + RiskGuard/Executor 통합 테스트.
"""

import time
from unittest.mock import Mock

import pytest

from arbitrage.monitoring.cross_exchange_metrics import (
    CrossExchangeMetrics,
    InMemoryMetricsBackend,
    CrossExchangePnLSnapshot,
    CrossExecutionResult,
)
from arbitrage.cross_exchange.risk_guard import (
    CrossExchangeRiskGuard,
    CrossExchangeRiskGuardConfig,
    CrossRiskDecision,
    CrossRiskReasonCode,
    CrossExchangePnLTracker,
)
from arbitrage.cross_exchange.integration import CrossExchangeDecision, CrossExchangeAction
from arbitrage.cross_exchange.executor import CrossExchangeExecutor, LegExecutionResult
from arbitrage.cross_exchange.position_manager import CrossExchangePositionManager
from arbitrage.cross_exchange.fx_converter import FXConverter
from arbitrage.domain.cross_sync import InventoryTracker, Inventory


class TestCrossExchangeMetricsBasic:
    """CrossExchangeMetrics 기본 동작 테스트"""
    
    def test_metrics_initialization(self):
        """Metrics 초기화"""
        metrics = CrossExchangeMetrics()
        
        assert metrics.backend is not None
        assert isinstance(metrics.backend, InMemoryMetricsBackend)
        assert metrics.alert_manager is None
        
        snapshot = metrics.get_metrics_snapshot()
        assert "counters" in snapshot
        assert "gauges" in snapshot
    
    def test_record_risk_decision_block(self):
        """RiskGuard decision 기록 (BLOCK)"""
        metrics = CrossExchangeMetrics()
        
        decision = CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code=CrossRiskReasonCode.CROSS_EXPOSURE_LIMIT.value,
            details={"exposure_risk": 0.82, "limit": 0.6},
        )
        
        context = {
            "symbol_upbit": "KRW-BTC",
            "symbol_binance": "BTCUSDT",
            "action": "entry_positive",
            "first_trigger_reason": "cross_exposure_limit",
        }
        
        metrics.record_risk_decision(decision, context)
        
        snapshot = metrics.get_metrics_snapshot()
        
        # Debug: print all counter keys
        # print("Counter keys:", list(snapshot["counters"].keys()))
        
        # Counter 확인 (labels가 alphabetical order로 정렬됨: reason < tier)
        # 하지만 실제로는 순서가 다를 수 있으므로, 두 가지 모두 체크
        key1 = "risk_guard_blocks_total{reason=cross_exposure_limit,tier=cross_exchange}"
        key2 = "risk_guard_blocks_total{tier=cross_exchange,reason=cross_exposure_limit}"
        assert snapshot["counters"].get(key1, 0) + snapshot["counters"].get(key2, 0) == 1
        
        assert snapshot["counters"]["risk_first_trigger_total{reason=cross_exposure_limit}"] == 1
        assert snapshot["counters"]["risk_final_block_total{reason=cross_exposure_limit}"] == 1
        
        # Gauge 확인
        assert snapshot["gauges"]["cross_exposure_ratio{symbol=KRW-BTC}"] == 0.82
    
    def test_record_risk_decision_allow(self):
        """RiskGuard decision 기록 (ALLOW)"""
        metrics = CrossExchangeMetrics()
        
        decision = CrossRiskDecision(
            allowed=True,
            tier="none",
            reason_code="OK",
            details={},
        )
        
        context = {
            "symbol_upbit": "KRW-BTC",
            "symbol_binance": "BTCUSDT",
            "action": "entry_positive",
        }
        
        metrics.record_risk_decision(decision, context)
        
        snapshot = metrics.get_metrics_snapshot()
        
        # ALLOW 시에는 counter 증가 없음
        assert "risk_guard_blocks_total" not in str(snapshot["counters"])


class TestCrossExchangeMetricsFirstTriggerVsFinalBlock:
    """First Trigger vs Final Block 구분 테스트"""
    
    def test_first_trigger_different_from_final_block(self):
        """여러 룰 동시 감지 시 first_trigger와 final_block 구분"""
        metrics = CrossExchangeMetrics()
        
        # exposure_limit이 먼저 감지되었지만, daily_loss_limit이 최종 block
        decision = CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code=CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value,
            details={"daily_pnl": -5_500_000, "limit": -5_000_000},
        )
        
        context = {
            "symbol_upbit": "KRW-BTC",
            "first_trigger_reason": "cross_exposure_limit",  # 첫 감지
        }
        
        metrics.record_risk_decision(decision, context)
        
        snapshot = metrics.get_metrics_snapshot()
        
        # First trigger는 exposure_limit
        assert snapshot["counters"]["risk_first_trigger_total{reason=cross_exposure_limit}"] == 1
        
        # Final block은 daily_loss_limit
        assert snapshot["counters"]["risk_final_block_total{reason=cross_daily_loss_limit}"] == 1
        
        # exposure_limit은 final_block에 카운트되지 않음
        assert "risk_final_block_total{reason=cross_exposure_limit}" not in snapshot["counters"]


class TestCrossExchangeMetricsExecutionResult:
    """Execution Result 기록 테스트"""
    
    def test_record_execution_success(self):
        """Executor 성공 결과 기록"""
        metrics = CrossExchangeMetrics()
        
        upbit_result = LegExecutionResult(
            exchange="upbit",
            order_id="UPBIT-123",
            status="filled",
            filled_qty=0.001,
            requested_qty=0.001,
            avg_price=50_000_000.0,
        )
        
        binance_result = LegExecutionResult(
            exchange="binance",
            order_id="BINANCE-456",
            status="filled",
            filled_qty=0.001,
            requested_qty=0.001,
            avg_price=38_000.0,
        )
        
        result = CrossExecutionResult(
            status="success",
            upbit_result=upbit_result,
            binance_result=binance_result,
            total_latency=1.234,  # 초
        )
        
        metrics.record_execution_result(result)
        
        snapshot = metrics.get_metrics_snapshot()
        
        # Counter: 주문 성공
        assert snapshot["counters"]["cross_orders_total{exchange=upbit,status=filled}"] == 1
        assert snapshot["counters"]["cross_orders_total{exchange=binance,status=filled}"] == 1
        
        # Histogram: Latency
        assert len(snapshot["histograms"]["cross_order_fill_duration_seconds{exchange=combined}"]["values"]) == 1
        assert snapshot["histograms"]["cross_order_fill_duration_seconds{exchange=combined}"]["values"][0] == 1.234
    
    def test_record_execution_rollback(self):
        """Executor rollback 결과 기록"""
        metrics = CrossExchangeMetrics()
        
        result = CrossExecutionResult(
            status="rollback",
            upbit_result=None,
            binance_result=None,
            total_latency=0.5,
            rollback_reason="partial_fill",
        )
        
        metrics.record_execution_result(result)
        
        snapshot = metrics.get_metrics_snapshot()
        
        # Counter: Rollback
        assert snapshot["counters"]["cross_rollbacks_total{reason=partial_fill}"] == 1


class TestCrossExchangeMetricsPnLSnapshot:
    """PnL Snapshot 기록 테스트"""
    
    def test_record_pnl_snapshot(self):
        """PnL 스냅샷 기록"""
        from decimal import Decimal
        from arbitrage.common.currency import Currency, Money
        
        metrics = CrossExchangeMetrics()
        
        # D80-1: CrossExchangePnLSnapshot은 이제 Money 객체 요구
        snapshot = CrossExchangePnLSnapshot(
            daily_pnl=Money(Decimal("1234567.89"), Currency.KRW),
            unrealized_pnl=Money(Decimal("567890.12"), Currency.KRW),
            consecutive_loss_count=2,
            win_count=48,
            loss_count=32,
            symbol="KRW-BTC",
        )
        
        metrics.record_pnl_snapshot(snapshot)
        
        result = metrics.get_metrics_snapshot()
        
        # Gauge: Daily PnL
        assert result["gauges"]["cross_daily_pnl_krw{symbol=KRW-BTC}"] == 1_234_567.89
        
        # Gauge: Unrealized PnL
        assert result["gauges"]["cross_unrealized_pnl_krw{symbol=KRW-BTC}"] == 567_890.12
        
        # Gauge: Consecutive loss (empty labels → no braces in key)
        assert result["gauges"]["cross_consecutive_loss_count"] == 2.0
        
        # Gauge: Winrate
        expected_winrate = 48 / (48 + 32)
        assert result["gauges"]["cross_winrate{symbol=KRW-BTC}"] == pytest.approx(expected_winrate)


class TestRiskGuardWithMetricsIntegration:
    """RiskGuard + Metrics 통합 테스트"""
    
    def test_risk_guard_exposure_limit_metrics(self):
        """RiskGuard exposure_limit 차단 → Metrics 자동 기록"""
        metrics = CrossExchangeMetrics()
        
        inventory_tracker = InventoryTracker(
            imbalance_threshold=0.3,
            exposure_threshold=0.5,  # 50% 임계값
        )
        
        # Upbit 쪽으로 집중 (exposure_risk > 0.5)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=10.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=0.5,  # 50% limit
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            metrics_collector=metrics,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # BLOCK 확인
        assert result.allowed is False
        assert result.reason_code == CrossRiskReasonCode.CROSS_EXPOSURE_LIMIT.value
        
        # Metrics 자동 기록 확인
        snapshot = metrics.get_metrics_snapshot()
        assert snapshot["counters"]["risk_final_block_total{reason=cross_exposure_limit}"] == 1
        assert "cross_exposure_ratio{symbol=KRW-BTC}" in snapshot["gauges"]
    
    def test_risk_guard_daily_loss_limit_metrics_and_alert(self):
        """RiskGuard daily_loss_limit 차단 → Metrics + Alert"""
        alert_manager = Mock()
        metrics = CrossExchangeMetrics(alert_manager=alert_manager)
        
        inventory_tracker = InventoryTracker(exposure_threshold=1.0)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,
            max_daily_loss_krw=1_000_000,  # 100만원 limit
        )
        
        pnl_tracker = CrossExchangePnLTracker()
        pnl_tracker.add_trade(-1_500_000)  # Daily loss 초과
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            pnl_tracker=pnl_tracker,
            metrics_collector=metrics,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # BLOCK 확인
        assert result.allowed is False
        assert result.reason_code == CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value
        
        # Metrics 기록 확인
        snapshot = metrics.get_metrics_snapshot()
        assert snapshot["counters"]["risk_final_block_total{reason=cross_daily_loss_limit}"] == 1
        
        # Alert 전송 확인
        alert_manager.send_alert.assert_called_once()
        call_args = alert_manager.send_alert.call_args[1]
        assert call_args["level"] == "P1"
        assert "Circuit Breaker" in call_args["title"]


class TestExecutorWithMetricsIntegration:
    """Executor + Metrics 통합 테스트"""
    
    def test_executor_success_metrics(self):
        """Executor 성공 실행 → Metrics 자동 기록"""
        from tests.test_d79_4_executor import FakeExchangeClient
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        
        metrics = CrossExchangeMetrics()
        
        upbit_client = FakeExchangeClient("upbit", fill_immediately=True)
        binance_client = FakeExchangeClient("binance", fill_immediately=True)
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
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
            metrics_collector=metrics,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = executor.execute_decision(decision)
        
        # 성공 확인
        assert result.status == "success"
        
        # Metrics 자동 기록 확인
        snapshot = metrics.get_metrics_snapshot()
        assert "cross_orders_total{exchange=upbit,status=filled}" in snapshot["counters"]
        assert "cross_orders_total{exchange=binance,status=filled}" in snapshot["counters"]
        assert len(snapshot["histograms"]) > 0


class TestPrometheusExport:
    """Prometheus export 테스트"""
    
    def test_export_prometheus_text(self):
        """Prometheus text format export"""
        metrics = CrossExchangeMetrics()
        
        # 몇 가지 metrics 기록
        decision = CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code="cross_exposure_limit",
            details={"exposure_risk": 0.82},
        )
        
        context = {"symbol_upbit": "KRW-BTC", "symbol_binance": "BTCUSDT", "action": "entry_positive"}
        metrics.record_risk_decision(decision, context)
        
        # Export
        export_text = metrics.export_prometheus()
        
        # 간단한 검증
        assert "risk_guard_blocks_total" in export_text
        assert "risk_final_block_total" in export_text
        assert isinstance(export_text, str)


def test_monitoring_import():
    """모듈 import 테스트"""
    from arbitrage.monitoring.cross_exchange_metrics import (
        CrossExchangeMetrics,
        InMemoryMetricsBackend,
        CrossExchangePnLSnapshot,
        CrossExecutionResult,
    )
    
    assert CrossExchangeMetrics is not None
    assert InMemoryMetricsBackend is not None
    assert CrossExchangePnLSnapshot is not None
    assert CrossExecutionResult is not None

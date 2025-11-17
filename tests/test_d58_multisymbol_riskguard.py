# -*- coding: utf-8 -*-
"""
D58: Multi-Symbol Risk Guard Integration Phase 1 - Tests

RiskGuard 멀티심볼 구조 및 symbol-aware 인터페이스 검증.
"""

import pytest
import time
from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
    ArbitrageTrade,
)
from arbitrage.live_runner import RiskGuard, RiskGuardDecision, RiskLimits
from arbitrage.monitoring.metrics_collector import MetricsCollector


class TestRiskGuardSymbolAware:
    """RiskGuard symbol-aware 메서드 테스트"""
    
    def test_riskguard_symbol_aware_fields(self):
        """RiskGuard symbol-aware 필드 존재 확인"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # D58 필드 확인
        assert hasattr(guard, 'per_symbol_loss')
        assert hasattr(guard, 'per_symbol_trades_rejected')
        assert hasattr(guard, 'per_symbol_trades_allowed')
        assert guard.per_symbol_loss == {}
        assert guard.per_symbol_trades_rejected == {}
        assert guard.per_symbol_trades_allowed == {}
    
    def test_check_trade_allowed_for_symbol_ok(self):
        """symbol-aware trade check - OK"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=5000.0,
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # symbol-aware check
        result = guard.check_trade_allowed_for_symbol("KRW-BTC", trade, 0)
        
        assert result == RiskGuardDecision.OK
        assert guard.per_symbol_trades_allowed["KRW-BTC"] == 1
    
    def test_check_trade_allowed_for_symbol_rejected_notional(self):
        """symbol-aware trade check - rejected (notional)"""
        limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 거래 생성 (명목가 초과)
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=10000.0,  # 초과
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # symbol-aware check
        result = guard.check_trade_allowed_for_symbol("KRW-BTC", trade, 0)
        
        assert result == RiskGuardDecision.TRADE_REJECTED
        assert guard.per_symbol_trades_rejected["KRW-BTC"] == 1
    
    def test_check_trade_allowed_for_symbol_rejected_max_trades(self):
        """symbol-aware trade check - rejected (max trades)"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=5000.0,
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # symbol-aware check (이미 1개 거래 활성)
        result = guard.check_trade_allowed_for_symbol("KRW-BTC", trade, 1)
        
        assert result == RiskGuardDecision.TRADE_REJECTED
        assert guard.per_symbol_trades_rejected["KRW-BTC"] == 1
    
    def test_check_trade_allowed_for_symbol_session_stop(self):
        """symbol-aware trade check - session stop"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 손실 업데이트 (한계 도달)
        guard.daily_loss_usd = 1000.0
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=5000.0,
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # symbol-aware check
        result = guard.check_trade_allowed_for_symbol("KRW-BTC", trade, 0)
        
        assert result == RiskGuardDecision.SESSION_STOP
    
    def test_update_symbol_loss(self):
        """symbol-aware loss update"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        # 손실 업데이트
        guard.update_symbol_loss("KRW-BTC", -100.0)
        guard.update_symbol_loss("KRW-BTC", -50.0)
        guard.update_symbol_loss("BTCUSDT", -75.0)
        
        # 확인
        assert guard.per_symbol_loss["KRW-BTC"] == 150.0
        assert guard.per_symbol_loss["BTCUSDT"] == 75.0
        assert guard.daily_loss_usd == 225.0
    
    def test_get_symbol_stats(self):
        """symbol-aware stats 조회"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=5000.0,
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # 거래 허용 및 손실 업데이트
        guard.check_trade_allowed_for_symbol("KRW-BTC", trade, 0)
        guard.update_symbol_loss("KRW-BTC", -100.0)
        
        # 통계 조회
        stats = guard.get_symbol_stats("KRW-BTC")
        
        assert stats['loss'] == 100.0
        assert stats['trades_allowed'] == 1
        assert stats['trades_rejected'] == 0
    
    def test_multiple_symbols_independent_tracking(self):
        """여러 심볼의 독립적인 추적"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=5000.0,
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # 심볼별 거래 처리
        guard.check_trade_allowed_for_symbol("KRW-BTC", trade, 0)
        guard.check_trade_allowed_for_symbol("BTCUSDT", trade, 0)
        guard.check_trade_allowed_for_symbol("KRW-ETH", trade, 0)
        
        # 심볼별 손실 업데이트
        guard.update_symbol_loss("KRW-BTC", -100.0)
        guard.update_symbol_loss("BTCUSDT", -50.0)
        guard.update_symbol_loss("KRW-ETH", -75.0)
        
        # 각 심볼의 통계 확인
        btc_stats = guard.get_symbol_stats("KRW-BTC")
        usdt_stats = guard.get_symbol_stats("BTCUSDT")
        eth_stats = guard.get_symbol_stats("KRW-ETH")
        
        assert btc_stats['loss'] == 100.0
        assert btc_stats['trades_allowed'] == 1
        
        assert usdt_stats['loss'] == 50.0
        assert usdt_stats['trades_allowed'] == 1
        
        assert eth_stats['loss'] == 75.0
        assert eth_stats['trades_allowed'] == 1
        
        # 전체 손실 확인
        assert guard.daily_loss_usd == 225.0


class TestMetricsCollectorGuardMetrics:
    """MetricsCollector symbol-aware guard metrics 테스트"""
    
    def test_metrics_collector_guard_fields(self):
        """MetricsCollector guard metrics 필드 확인"""
        collector = MetricsCollector()
        
        # D58 필드 확인
        assert hasattr(collector, 'per_symbol_guard_rejected')
        assert hasattr(collector, 'per_symbol_guard_allowed')
        assert hasattr(collector, 'per_symbol_guard_loss')
        assert collector.per_symbol_guard_rejected == {}
        assert collector.per_symbol_guard_allowed == {}
        assert collector.per_symbol_guard_loss == {}


class TestBackwardCompatibilityD58:
    """D58 추가 후 기존 기능 호환성"""
    
    def test_riskguard_backward_compatible(self):
        """기존 RiskGuard 기능 유지"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 기존 메서드 호출 (변경 없음)
        guard.update_daily_loss(-100.0)
        
        # 확인
        assert guard.daily_loss_usd == 100.0
    
    def test_riskguard_check_trade_allowed_backward_compatible(self):
        """기존 check_trade_allowed 메서드 유지"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp="2025-11-18T01:00:00Z",
            side="LONG_A_SHORT_B",
            notional_usd=5000.0,
            entry_spread_bps=50.0,
            is_open=True,
        )
        
        # 기존 메서드 호출
        result = guard.check_trade_allowed(trade, 0)
        
        assert result == RiskGuardDecision.OK

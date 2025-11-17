# -*- coding: utf-8 -*-
"""
D61: Multi-Symbol Paper Execution (Phase 3) - Tests

PaperExecutor, ExecutorFactory의 멀티심볼 거래 실행 검증.
"""

import pytest
from datetime import datetime
from dataclasses import dataclass

from arbitrage.types import (
    ExchangeType,
    OrderSide,
    PortfolioState,
    SymbolRiskLimits,
)
from arbitrage.live_runner import RiskGuard, RiskLimits
from arbitrage.execution import PaperExecutor, ExecutorFactory


# D61: Test용 ArbitrageTrade 정의 (간단한 버전)
@dataclass
class ArbitrageTrade:
    """테스트용 거래 정보"""
    trade_id: str
    symbol: str
    buy_exchange: ExchangeType
    sell_exchange: ExchangeType
    buy_price: float
    sell_price: float
    quantity: float
    notional_usd: float
    spread_bps: float


class TestPaperExecutor:
    """PaperExecutor 기본 기능 테스트"""
    
    def test_paper_executor_creation(self):
        """PaperExecutor 생성"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        assert executor.symbol == "KRW-BTC"
        assert executor.execution_count == 0
        assert executor.total_pnl == 0.0
    
    def test_paper_executor_buy_execution(self):
        """매수 거래 실행"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 생성
        trade = ArbitrageTrade(
            trade_id="TRADE_001",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=100.0,
            sell_price=110.0,
            quantity=1.0,
            notional_usd=100.0,
            spread_bps=1000.0,
        )
        
        # 실행
        results = executor.execute_trades([trade])
        
        # 확인
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].quantity == 1.0
        assert results[0].buy_price == 100.0
        assert results[0].sell_price == 110.0
        assert results[0].pnl == 10.0
    
    def test_paper_executor_sell_execution(self):
        """매도 거래 실행"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = PaperExecutor(
            symbol="BTCUSDT",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 생성
        trade = ArbitrageTrade(
            trade_id="TRADE_002",
            symbol="BTCUSDT",
            buy_exchange=ExchangeType.BINANCE,
            sell_exchange=ExchangeType.UPBIT,
            buy_price=50000.0,
            sell_price=50500.0,
            quantity=0.1,
            notional_usd=5000.0,
            spread_bps=100.0,
        )
        
        # 실행
        results = executor.execute_trades([trade])
        
        # 확인
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].pnl == 50.0  # (50500 - 50000) * 0.1
    
    def test_paper_executor_pnl_calculation(self):
        """PnL 계산"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 1
        trade1 = ArbitrageTrade(
            trade_id="TRADE_001",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=100.0,
            sell_price=110.0,
            quantity=1.0,
            notional_usd=100.0,
            spread_bps=1000.0,
        )
        
        # 거래 2
        trade2 = ArbitrageTrade(
            trade_id="TRADE_002",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=105.0,
            sell_price=115.0,
            quantity=1.0,
            notional_usd=105.0,
            spread_bps=952.0,
        )
        
        # 실행
        executor.execute_trades([trade1, trade2])
        
        # PnL 확인
        pnl = executor.get_pnl()
        assert pnl == 20.0  # 10.0 + 10.0


class TestMultipleExecutors:
    """여러 Executor의 독립 관리"""
    
    def test_multiple_executors_independent(self):
        """여러 Executor의 독립적 관리"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        # Executor 1
        executor1 = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # Executor 2
        executor2 = PaperExecutor(
            symbol="BTCUSDT",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 1
        trade1 = ArbitrageTrade(
            trade_id="TRADE_001",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=100.0,
            sell_price=110.0,
            quantity=1.0,
            notional_usd=100.0,
            spread_bps=1000.0,
        )
        
        # 거래 2
        trade2 = ArbitrageTrade(
            trade_id="TRADE_002",
            symbol="BTCUSDT",
            buy_exchange=ExchangeType.BINANCE,
            sell_exchange=ExchangeType.UPBIT,
            buy_price=50000.0,
            sell_price=50500.0,
            quantity=0.1,
            notional_usd=5000.0,
            spread_bps=100.0,
        )
        
        # 실행
        executor1.execute_trades([trade1])
        executor2.execute_trades([trade2])
        
        # 확인: 각 executor가 독립적으로 관리
        assert executor1.get_pnl() == 10.0
        assert executor2.get_pnl() == 50.0
        assert executor1.execution_count == 1
        assert executor2.execution_count == 1
    
    def test_symbol_specific_positions(self):
        """심볼별 포지션 관리"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 실행
        trade = ArbitrageTrade(
            trade_id="TRADE_001",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=100.0,
            sell_price=110.0,
            quantity=1.0,
            notional_usd=100.0,
            spread_bps=1000.0,
        )
        
        executor.execute_trades([trade])
        
        # 포지션 확인
        positions = executor.get_positions()
        assert len(positions) == 1
        assert list(positions.values())[0].symbol == "KRW-BTC"


class TestExecutorFactory:
    """ExecutorFactory 테스트"""
    
    def test_executor_factory_creation(self):
        """ExecutorFactory 생성"""
        factory = ExecutorFactory()
        
        assert factory is not None
        assert len(factory.get_all_executors()) == 0
    
    def test_create_paper_executor(self):
        """Paper Executor 생성"""
        factory = ExecutorFactory()
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        assert executor is not None
        assert executor.symbol == "KRW-BTC"
        assert len(factory.get_all_executors()) == 1
    
    def test_get_executor(self):
        """Executor 조회"""
        factory = ExecutorFactory()
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor1 = factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        executor2 = factory.get_executor("KRW-BTC")
        
        assert executor1 == executor2
    
    def test_multiple_executors_factory(self):
        """팩토리에서 여러 Executor 관리"""
        factory = ExecutorFactory()
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        # 여러 Executor 생성
        executor1 = factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        executor2 = factory.create_paper_executor(
            symbol="BTCUSDT",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 확인
        assert len(factory.get_all_executors()) == 2
        assert factory.get_executor("KRW-BTC") == executor1
        assert factory.get_executor("BTCUSDT") == executor2


class TestRiskGuardIntegration:
    """RiskGuard 통합 테스트"""
    
    def test_execution_respects_capital_limits(self):
        """거래 실행이 자본 한도를 준수"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        # 심볼별 한도 설정
        limits = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=100.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=50.0,
        )
        guard.set_symbol_limits(limits)
        
        executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 생성 (자본 한도 초과)
        trade = ArbitrageTrade(
            trade_id="TRADE_001",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=100.0,
            sell_price=110.0,
            quantity=2.0,  # 200 > 100 (한도)
            notional_usd=200.0,
            spread_bps=1000.0,
        )
        
        # 실행
        results = executor.execute_trades([trade])
        
        # 확인: 거래가 거절됨
        assert len(results) == 1
        assert results[0].status == "failed"


class TestBackwardCompatibilityD61:
    """D61 추가 후 기존 기능 호환성"""
    
    def test_single_symbol_execution_unchanged(self):
        """단일심볼 실행이 변경되지 않음"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        guard = RiskGuard(RiskLimits())
        
        executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio,
            risk_guard=guard,
        )
        
        # 거래 실행
        trade = ArbitrageTrade(
            trade_id="TRADE_001",
            symbol="KRW-BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=100.0,
            sell_price=110.0,
            quantity=1.0,
            notional_usd=100.0,
            spread_bps=1000.0,
        )
        
        results = executor.execute_trades([trade])
        
        # 확인
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].pnl == 10.0

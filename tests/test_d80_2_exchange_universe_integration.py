# -*- coding: utf-8 -*-
"""
D80-2: Multi-Currency Exchange & Universe Integration Tests

Universe/Exchange Adapter/Executor의 Currency 통합 테스트.
"""

import pytest
from decimal import Decimal

from arbitrage.common.currency import Currency, Money, StaticFxRateProvider
from arbitrage.cross_exchange.universe_provider import CrossSymbol
from arbitrage.exchanges.base import BaseExchange, OrderBookSnapshot, Balance
from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.cross_exchange.executor import CrossExchangeExecutor, CrossExecutionResult


# =============================================================================
# A. Universe Tests (4~6 tests)
# =============================================================================

def test_cross_symbol_has_base_currency():
    """CrossSymbol에 base_currency 속성이 존재하는지 확인"""
    symbol = CrossSymbol(
        mapping=None,
        upbit_volume_24h=1_000_000_000.0,
        binance_volume_24h=100_000.0,
        combined_score=1_000_000.0,
        base_currency=Currency.KRW
    )
    
    assert hasattr(symbol, 'base_currency')
    assert symbol.base_currency == Currency.KRW


def test_cross_symbol_base_currency_krw():
    """CrossSymbol의 base_currency가 KRW로 설정되는지 확인"""
    symbol = CrossSymbol(
        mapping=None,
        upbit_volume_24h=1_000_000_000.0,
        binance_volume_24h=100_000.0,
        combined_score=1_000_000.0,
        base_currency=Currency.KRW
    )
    
    assert symbol.base_currency == Currency.KRW


def test_cross_symbol_base_currency_usdt():
    """CrossSymbol의 base_currency가 USDT로 설정되는지 확인"""
    symbol = CrossSymbol(
        mapping=None,
        upbit_volume_24h=1_000_000_000.0,
        binance_volume_24h=100_000.0,
        combined_score=1_000_000.0,
        base_currency=Currency.USDT
    )
    
    assert symbol.base_currency == Currency.USDT


def test_cross_symbol_base_currency_default():
    """CrossSymbol의 base_currency 기본값이 KRW인지 확인"""
    symbol = CrossSymbol(
        mapping=None,
        upbit_volume_24h=1_000_000_000.0,
        binance_volume_24h=100_000.0,
        combined_score=1_000_000.0,
        # base_currency 명시 안 함 -> 기본값 사용
    )
    
    assert symbol.base_currency == Currency.KRW


def test_import_currency_with_cross_symbol():
    """Currency와 CrossSymbol이 함께 import되는지 확인"""
    from arbitrage.common.currency import Currency
    from arbitrage.cross_exchange.universe_provider import CrossSymbol
    
    # Import 성공 확인
    assert Currency is not None
    assert CrossSymbol is not None


# =============================================================================
# B. Exchange Adapter Tests (6~8 tests)
# =============================================================================

def test_base_exchange_has_base_currency():
    """BaseExchange에 base_currency 속성이 있는지 확인"""
    exchange = PaperExchange()
    
    assert hasattr(exchange, 'base_currency')
    assert isinstance(exchange.base_currency, Currency)


def test_upbit_exchange_base_currency_krw():
    """UpbitSpotExchange의 base_currency가 KRW인지 확인"""
    exchange = UpbitSpotExchange(config={})
    
    assert exchange.base_currency == Currency.KRW


def test_binance_exchange_base_currency_usdt():
    """BinanceFuturesExchange의 base_currency가 USDT인지 확인"""
    exchange = BinanceFuturesExchange(config={})
    
    assert exchange.base_currency == Currency.USDT


def test_paper_exchange_base_currency_default_krw():
    """PaperExchange의 기본 base_currency가 KRW인지 확인"""
    exchange = PaperExchange(config={})
    
    assert exchange.base_currency == Currency.KRW


def test_paper_exchange_base_currency_config_usdt():
    """PaperExchange의 base_currency를 config로 USDT로 변경 가능한지 확인"""
    exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    assert exchange.base_currency == Currency.USDT


def test_base_exchange_make_money_helper():
    """BaseExchange.make_money() 헬퍼가 동작하는지 확인"""
    exchange = PaperExchange(config={})
    
    money = exchange.make_money(10000)
    
    assert isinstance(money, Money)
    assert money.amount == Decimal("10000")
    assert money.currency == Currency.KRW


def test_upbit_make_money_krw():
    """Upbit.make_money(10000) → Money(Decimal("10000"), Currency.KRW)"""
    exchange = UpbitSpotExchange(config={})
    
    money = exchange.make_money(10000)
    
    assert isinstance(money, Money)
    assert money.amount == Decimal("10000")
    assert money.currency == Currency.KRW


def test_binance_make_money_usdt():
    """Binance.make_money(100) → Money(Decimal("100"), Currency.USDT)"""
    exchange = BinanceFuturesExchange(config={})
    
    money = exchange.make_money(100)
    
    assert isinstance(money, Money)
    assert money.amount == Decimal("100")
    assert money.currency == Currency.USDT


def test_make_money_explicit_currency():
    """make_money()에 명시적으로 currency 전달 가능한지 확인"""
    exchange = PaperExchange(config={})
    
    money_usd = exchange.make_money(100, Currency.USD)
    
    assert isinstance(money_usd, Money)
    assert money_usd.amount == Decimal("100")
    assert money_usd.currency == Currency.USD


# =============================================================================
# C. Executor Tests (4~6 tests)
# =============================================================================

@pytest.mark.live_api
def test_executor_estimate_order_cost_returns_money():
    """Executor._estimate_order_cost()가 Money를 반환하는지 확인"""
    # Mock executor (필수 의존성만 주입)
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # Minimal executor (real dependencies는 None으로 처리)
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,  # Not needed for this test
        fx_converter=None,
        health_monitor=None,
        settings=None,
    )
    
    # _estimate_order_cost 호출
    cost = executor._estimate_order_cost(
        exchange=upbit_exchange,
        symbol="KRW-BTC",
        price=100_000_000.0,
        qty=0.001
    )
    
    assert isinstance(cost, Money)
    assert cost.currency == Currency.KRW


@pytest.mark.live_api
def test_executor_upbit_notional_money_krw():
    """Executor에서 Upbit notional이 Money(KRW)로 계산되는지 확인"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
    )
    
    upbit_cost = executor._estimate_order_cost(
        exchange=upbit_exchange,
        symbol="KRW-BTC",
        price=50_000_000.0,
        qty=0.002
    )
    
    assert upbit_cost.currency == Currency.KRW
    assert upbit_cost.amount == Decimal("100000")  # 50M * 0.002


@pytest.mark.live_api
def test_executor_binance_notional_money_usdt():
    """Executor에서 Binance notional이 Money(USDT)로 계산되는지 확인"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
    )
    
    binance_cost = executor._estimate_order_cost(
        exchange=binance_exchange,
        symbol="BTCUSDT",
        price=40_000.0,
        qty=0.1
    )
    
    assert binance_cost.currency == Currency.USDT
    assert binance_cost.amount == Decimal("4000")  # 40,000 * 0.1


def test_cross_execution_result_has_pnl_money():
    """CrossExecutionResult에 pnl (Money) 필드가 있는지 확인"""
    from arbitrage.cross_exchange.executor import CrossExecutionResult, LegExecutionResult
    from arbitrage.cross_exchange.integration import CrossExchangeDecision, CrossExchangeAction
    import time
    
    # Mock decision
    decision = CrossExchangeDecision(
        action=CrossExchangeAction.NO_ACTION,
        symbol_upbit="KRW-BTC",
        symbol_binance="BTCUSDT",
        notional_krw=100_000_000.0,
        spread_percent=0.0,
        reason="test",
        timestamp=time.time(),
    )
    
    # Mock leg results
    upbit_leg = LegExecutionResult(
        exchange="upbit",
        order_id="test",
        status="filled",
        filled_qty=0.001,
        requested_qty=0.001,
        avg_price=100_000_000.0
    )
    
    binance_leg = LegExecutionResult(
        exchange="binance",
        order_id="test",
        status="filled",
        filled_qty=0.001,
        requested_qty=0.001,
        avg_price=70_000.0
    )
    
    # Create result with Money pnl
    result = CrossExecutionResult(
        decision=decision,
        upbit=upbit_leg,
        binance=binance_leg,
        status="success",
        pnl=Money(Decimal("10000"), Currency.KRW)
    )
    
    assert hasattr(result, 'pnl')
    assert isinstance(result.pnl, Money)
    assert result.pnl.currency == Currency.KRW


def test_cross_execution_result_pnl_krw_deprecated():
    """CrossExecutionResult의 pnl_krw (deprecated) 필드 backward compat 확인"""
    from arbitrage.cross_exchange.executor import CrossExecutionResult, LegExecutionResult
    from arbitrage.cross_exchange.integration import CrossExchangeDecision, CrossExchangeAction
    import time
    
    decision = CrossExchangeDecision(
        action=CrossExchangeAction.NO_ACTION,
        symbol_upbit="KRW-BTC",
        symbol_binance="BTCUSDT",
        notional_krw=100_000_000.0,
        spread_percent=0.0,
        reason="test",
        timestamp=time.time(),
    )
    
    upbit_leg = LegExecutionResult(
        exchange="upbit",
        order_id="test",
        status="filled",
        filled_qty=0.001,
        requested_qty=0.001,
        avg_price=100_000_000.0
    )
    
    binance_leg = LegExecutionResult(
        exchange="binance",
        order_id="test",
        status="filled",
        filled_qty=0.001,
        requested_qty=0.001,
        avg_price=70_000.0
    )
    
    # pnl (Money) 설정
    result = CrossExecutionResult(
        decision=decision,
        upbit=upbit_leg,
        binance=binance_leg,
        status="success",
        pnl=Money(Decimal("10000"), Currency.KRW)
    )
    
    # pnl_krw_amount property로 backward compat 접근 가능
    assert result.pnl_krw_amount == 10000.0


@pytest.mark.live_api
def test_executor_existing_interface_unchanged():
    """Executor 인터페이스가 유지되는지 확인 (import, basic flow)"""
    from arbitrage.cross_exchange.executor import CrossExchangeExecutor, CrossExecutionResult
    
    # Import 성공 확인
    assert CrossExchangeExecutor is not None
    assert CrossExecutionResult is not None
    
    # 기본 인스턴스 생성 가능 확인
    upbit_exchange = PaperExchange(config={})
    binance_exchange = PaperExchange(config={})
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
    )
    
    assert executor is not None
    assert executor.base_currency == Currency.KRW


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

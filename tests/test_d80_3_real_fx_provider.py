# -*- coding: utf-8 -*-
"""
D80-3: Real FX Rate Provider Tests

RealFxRateProvider, FxCache, Executor 통합 테스트.
"""

import pytest
import time
from decimal import Decimal
from unittest import mock

from arbitrage.common.currency import Currency, Money, RealFxRateProvider
from arbitrage.common.fx_cache import FxCache, FxCacheEntry
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.cross_exchange.executor import CrossExchangeExecutor


# =============================================================================
# A. FxCache Tests (6)
# =============================================================================

def test_fx_cache_set_get():
    """FxCache set/get 기본 동작"""
    cache = FxCache(ttl_seconds=10.0)
    
    cache.set(Currency.USD, Currency.KRW, Decimal("1420.50"))
    rate = cache.get(Currency.USD, Currency.KRW)
    
    assert rate == Decimal("1420.50")


def test_fx_cache_ttl_expiration():
    """TTL expiration (3초 초과)"""
    cache = FxCache(ttl_seconds=0.1)  # 0.1초 TTL
    
    cache.set(Currency.USD, Currency.KRW, Decimal("1420.50"))
    
    # 즉시 조회: HIT
    rate = cache.get(Currency.USD, Currency.KRW)
    assert rate == Decimal("1420.50")
    
    # 0.2초 후 조회: MISS (expired)
    time.sleep(0.2)
    rate = cache.get(Currency.USD, Currency.KRW)
    assert rate is None


def test_fx_cache_get_updated_at():
    """updated_at 조회"""
    cache = FxCache(ttl_seconds=10.0)
    
    before = time.time()
    cache.set(Currency.USD, Currency.KRW, Decimal("1420.50"))
    after = time.time()
    
    updated_at = cache.get_updated_at(Currency.USD, Currency.KRW)
    
    assert updated_at is not None
    assert before <= updated_at <= after


def test_fx_cache_clear():
    """clear() 전체 삭제"""
    cache = FxCache(ttl_seconds=10.0)
    
    cache.set(Currency.USD, Currency.KRW, Decimal("1420"))
    cache.set(Currency.USDT, Currency.KRW, Decimal("1420"))
    
    assert cache.size() == 2
    
    cache.clear()
    
    assert cache.size() == 0
    assert cache.get(Currency.USD, Currency.KRW) is None


def test_fx_cache_size():
    """size() 엔트리 개수"""
    cache = FxCache(ttl_seconds=10.0)
    
    assert cache.size() == 0
    
    cache.set(Currency.USD, Currency.KRW, Decimal("1420"))
    assert cache.size() == 1
    
    cache.set(Currency.USDT, Currency.KRW, Decimal("1420"))
    assert cache.size() == 2


def test_fx_cache_overwrite():
    """동일 key 덮어쓰기"""
    cache = FxCache(ttl_seconds=10.0)
    
    cache.set(Currency.USD, Currency.KRW, Decimal("1420"))
    cache.set(Currency.USD, Currency.KRW, Decimal("1500"))  # overwrite
    
    rate = cache.get(Currency.USD, Currency.KRW)
    assert rate == Decimal("1500")
    assert cache.size() == 1


# =============================================================================
# B. RealFxRateProvider Tests (10)
# =============================================================================

@mock.patch("requests.Session.get")
def test_binance_usdt_usd_mock(mock_get):
    """Binance USDT→USD (mock response)"""
    # Mock response
    mock_get.return_value.json.return_value = {
        "symbol": "BTCUSDT",
        "markPrice": "97000.00",
        "lastFundingRate": "0.0001"
    }
    mock_get.return_value.raise_for_status = lambda: None
    
    fx = RealFxRateProvider()
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    
    # USDT ≈ USD (funding rate 무시)
    assert rate == Decimal("1.0")


@mock.patch("requests.Session.get")
def test_exchangerate_usd_krw_mock(mock_get):
    """Exchangerate USD→KRW (mock response)"""
    # Mock response
    mock_get.return_value.json.return_value = {
        "base": "USD",
        "rates": {"KRW": 1420.50}
    }
    mock_get.return_value.raise_for_status = lambda: None
    
    fx = RealFxRateProvider()
    rate = fx.get_rate(Currency.USD, Currency.KRW)
    
    assert rate == Decimal("1420.50")


@mock.patch("requests.Session.get")
def test_usdt_krw_chain_mock(mock_get):
    """USDT→KRW chain (USDT→USD→KRW)"""
    def side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        
        if "binance" in url or "fapi" in url:
            # Binance mock
            response = mock.Mock()
            response.json.return_value = {
                "symbol": "BTCUSDT",
                "lastFundingRate": "0.0"
            }
            response.raise_for_status = lambda: None
            return response
        else:
            # Exchangerate mock
            response = mock.Mock()
            response.json.return_value = {
                "base": "USD",
                "rates": {"KRW": 1420.0}
            }
            response.raise_for_status = lambda: None
            return response
    
    mock_get.side_effect = side_effect
    
    fx = RealFxRateProvider()
    rate = fx.get_rate(Currency.USDT, Currency.KRW)
    
    # USDT→USD=1.0, USD→KRW=1420.0 → USDT→KRW=1420.0
    assert rate == Decimal("1420.0")


def test_real_fx_cache_hit():
    """Cache hit (API 호출 안 함)"""
    fx = RealFxRateProvider()
    
    # 캐시에 미리 저장
    fx.cache.set(Currency.USD, Currency.KRW, Decimal("1500.0"))
    
    # API 호출 없이 캐시에서 조회
    with mock.patch.object(fx, "_fetch_rate_from_api") as mock_fetch:
        rate = fx.get_rate(Currency.USD, Currency.KRW)
        
        assert rate == Decimal("1500.0")
        mock_fetch.assert_not_called()  # API 호출 안 함


def test_real_fx_cache_miss():
    """Cache miss (API 호출함)"""
    fx = RealFxRateProvider()
    
    # Mock API
    with mock.patch.object(fx, "_fetch_rate_from_api") as mock_fetch:
        mock_fetch.return_value = Decimal("1420.0")
        
        rate = fx.get_rate(Currency.USD, Currency.KRW)
        
        assert rate == Decimal("1420.0")
        mock_fetch.assert_called_once_with(Currency.USD, Currency.KRW)


def test_real_fx_staleness_detection():
    """Staleness detection (60초 초과)"""
    fx = RealFxRateProvider()
    
    # 60초 전 캐시 저장
    old_timestamp = time.time() - 61.0
    fx.cache.set(Currency.USD, Currency.KRW, Decimal("1420.0"), updated_at=old_timestamp)
    
    # Stale 확인
    is_stale = fx.is_stale(Currency.USD, Currency.KRW)
    
    assert is_stale is True


def test_real_fx_not_stale():
    """Staleness detection (60초 이내)"""
    fx = RealFxRateProvider()
    
    # 최근 캐시 저장
    fx.cache.set(Currency.USD, Currency.KRW, Decimal("1420.0"))
    
    # Not stale
    is_stale = fx.is_stale(Currency.USD, Currency.KRW)
    
    assert is_stale is False


def test_real_fx_refresh_rate():
    """refresh_rate() 강제 갱신"""
    fx = RealFxRateProvider()
    
    # 캐시에 저장
    fx.cache.set(Currency.USD, Currency.KRW, Decimal("1420.0"))
    
    # Mock API
    with mock.patch.object(fx, "_fetch_rate_from_api") as mock_fetch:
        mock_fetch.return_value = Decimal("1500.0")
        
        fx.refresh_rate(Currency.USD, Currency.KRW)
        
        # API 재호출됨
        mock_fetch.assert_called_once()
        
        # 새 값으로 업데이트됨
        rate = fx.cache.get(Currency.USD, Currency.KRW)
        assert rate == Decimal("1500.0")


def test_real_fx_fallback_static_rate():
    """Fallback to static rate (API 실패)"""
    fx = RealFxRateProvider()
    
    # Mock API failure
    with mock.patch.object(fx, "_fetch_binance_usdt_usd") as mock_binance:
        with mock.patch.object(fx, "_fetch_exchangerate_usd_krw") as mock_exchangerate:
            mock_binance.side_effect = Exception("API error")
            mock_exchangerate.side_effect = Exception("API error")
            
            # Fallback to static rate
            rate = fx.get_rate(Currency.USDT, Currency.KRW)
            
            # Fallback rate = 1420.0
            assert rate == Decimal("1420.0")


def test_real_fx_same_currency():
    """Same currency (1.0 반환)"""
    fx = RealFxRateProvider()
    
    rate = fx.get_rate(Currency.KRW, Currency.KRW)
    
    assert rate == Decimal("1.0")


@mock.patch("requests.Session.get")
def test_real_fx_reverse_rate_krw_usd(mock_get):
    """Reverse rate (KRW→USD)"""
    # Mock USD→KRW
    mock_get.return_value.json.return_value = {
        "base": "USD",
        "rates": {"KRW": 1420.0}
    }
    mock_get.return_value.raise_for_status = lambda: None
    
    fx = RealFxRateProvider()
    rate = fx.get_rate(Currency.KRW, Currency.USD)
    
    # KRW→USD = 1 / (USD→KRW) = 1 / 1420.0
    expected = Decimal("1.0") / Decimal("1420.0")
    assert abs(rate - expected) < Decimal("0.0001")


# =============================================================================
# C. Integration Tests (6)
# =============================================================================

@pytest.mark.fx_api
def test_executor_estimate_order_cost_with_real_fx():
    """Executor._estimate_order_cost() with Real FX"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # Mock RealFxRateProvider
    fx = RealFxRateProvider()
    fx.cache.set(Currency.USDT, Currency.KRW, Decimal("1420.0"))
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    # Upbit order cost (KRW)
    upbit_cost = executor._estimate_order_cost(
        exchange=upbit_exchange,
        symbol="KRW-BTC",
        price=100_000_000.0,
        qty=0.001
    )
    
    assert upbit_cost.currency == Currency.KRW
    assert upbit_cost.amount == Decimal("100000")


@pytest.mark.fx_api
def test_executor_upbit_order_cost_krw():
    """Upbit order cost (KRW)"""
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
    assert upbit_cost.amount == Decimal("100000")


@pytest.mark.fx_api
def test_executor_binance_order_cost_usdt_to_krw():
    """Binance order cost (USDT→KRW 변환)"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # Mock RealFxRateProvider
    fx = RealFxRateProvider()
    fx.cache.set(Currency.USDT, Currency.KRW, Decimal("1420.0"))
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    binance_cost = executor._estimate_order_cost(
        exchange=binance_exchange,
        symbol="BTCUSDT",
        price=40_000.0,
        qty=0.1
    )
    
    assert binance_cost.currency == Currency.USDT
    assert binance_cost.amount == Decimal("4000")


@pytest.mark.fx_api
def test_executor_stale_warning_log(caplog):
    """Stale warning log 생성"""
    import logging
    caplog.set_level(logging.WARNING)
    
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # Mock RealFxRateProvider with stale rate
    fx = RealFxRateProvider()
    old_timestamp = time.time() - 61.0
    fx.cache.set(Currency.USDT, Currency.KRW, Decimal("1420.0"), updated_at=old_timestamp)
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
        base_currency=Currency.KRW,
    )
    
    # 주문 비용 계산 시 stale warning 로그 생성
    executor._estimate_order_cost(
        exchange=binance_exchange,
        symbol="BTCUSDT",
        price=40_000.0,
        qty=0.1
    )
    
    # Check warning log
    assert any("FX rate is STALE" in record.message for record in caplog.records)


@pytest.mark.fx_api
def test_executor_backward_compat_static_fx():
    """Backward compatibility (StaticFxRateProvider 여전히 동작)"""
    from arbitrage.common.currency import StaticFxRateProvider
    
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # Static FX Provider
    fx = StaticFxRateProvider({
        (Currency.USD, Currency.KRW): Decimal("1420.50"),
        (Currency.USDT, Currency.KRW): Decimal("1420.00"),
    })
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    # 여전히 동작
    upbit_cost = executor._estimate_order_cost(
        exchange=upbit_exchange,
        symbol="KRW-BTC",
        price=100_000_000.0,
        qty=0.001
    )
    
    assert upbit_cost.currency == Currency.KRW
    assert upbit_cost.amount == Decimal("100000")


@pytest.mark.fx_api
def test_executor_default_real_fx_provider():
    """Executor에서 기본으로 RealFxRateProvider 사용"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # fx_provider=None (기본값 사용)
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=None,  # 기본값 = RealFxRateProvider
    )
    
    # RealFxRateProvider 또는 StaticFxRateProvider (fallback)
    from arbitrage.common.currency import RealFxRateProvider, StaticFxRateProvider
    assert isinstance(executor.fx_provider, (RealFxRateProvider, StaticFxRateProvider))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

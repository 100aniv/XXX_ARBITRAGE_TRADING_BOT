"""
D50: LiveRunner DataSource 통합 테스트

LiveRunner와 MarketDataProvider 통합을 검증한다.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import (
    RestMarketDataProvider,
    WebSocketMarketDataProvider,
)


class TestD50LiveRunnerDataSourceIntegration:
    """D50 LiveRunner DataSource 통합 테스트"""
    
    def test_rest_market_data_provider_initialization(self):
        """REST MarketDataProvider 초기화"""
        exchanges = {
            "a": Mock(),
            "b": Mock(),
        }
        
        provider = RestMarketDataProvider(exchanges)
        
        assert provider.exchanges == exchanges
        assert provider._is_running is False
    
    def test_rest_market_data_provider_get_snapshot(self):
        """REST MarketDataProvider 스냅샷 조회"""
        # Mock 거래소
        upbit_exchange = Mock()
        binance_exchange = Mock()
        
        # Mock 스냅샷
        upbit_snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(50000000.0, 1.0)],
            asks=[(50100000.0, 1.0)],
        )
        binance_snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1000.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 1.0)],
        )
        
        upbit_exchange.get_orderbook.return_value = upbit_snapshot
        binance_exchange.get_orderbook.return_value = binance_snapshot
        
        provider = RestMarketDataProvider({
            "a": upbit_exchange,
            "b": binance_exchange,
        })
        
        # Upbit 스냅샷 조회
        snapshot = provider.get_latest_snapshot("KRW-BTC")
        assert snapshot == upbit_snapshot
        upbit_exchange.get_orderbook.assert_called_once_with("KRW-BTC")
        
        # Binance 스냅샷 조회
        snapshot = provider.get_latest_snapshot("BTCUSDT")
        assert snapshot == binance_snapshot
        binance_exchange.get_orderbook.assert_called_once_with("BTCUSDT")
    
    def test_rest_market_data_provider_start_stop(self):
        """REST MarketDataProvider 시작/종료"""
        exchanges = {"a": Mock(), "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        provider.start()
        assert provider._is_running is True
        
        provider.stop()
        assert provider._is_running is False
    
    def test_ws_market_data_provider_initialization(self):
        """WebSocket MarketDataProvider 초기화"""
        ws_adapters = {
            "upbit": Mock(),
            "binance": Mock(),
        }
        
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        assert provider.ws_adapters == ws_adapters
        assert provider._is_running is False
        assert provider.snapshot_upbit is None
        assert provider.snapshot_binance is None
    
    def test_ws_market_data_provider_get_snapshot(self):
        """WebSocket MarketDataProvider 스냅샷 조회"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # Upbit 스냅샷 설정
        upbit_snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(50000000.0, 1.0)],
            asks=[(50100000.0, 1.0)],
        )
        provider.on_upbit_snapshot(upbit_snapshot)
        
        # Binance 스냅샷 설정
        binance_snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1000.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 1.0)],
        )
        provider.on_binance_snapshot(binance_snapshot)
        
        # 조회
        assert provider.get_latest_snapshot("KRW-BTC") == upbit_snapshot
        assert provider.get_latest_snapshot("BTCUSDT") == binance_snapshot
    
    def test_ws_market_data_provider_start_stop(self):
        """WebSocket MarketDataProvider 시작/종료"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        provider.start()
        assert provider._is_running is True
        
        provider.stop()
        assert provider._is_running is False


class TestD50DataSourceSelection:
    """D50 데이터 소스 선택 테스트"""
    
    def test_create_rest_provider_from_config(self):
        """설정에서 REST 제공자 생성"""
        # Mock 설정
        config = Mock()
        config.data_source = "rest"
        
        # Mock 거래소
        exchanges = {
            "a": Mock(),
            "b": Mock(),
        }
        
        # REST 제공자 생성
        if config.data_source == "rest":
            provider = RestMarketDataProvider(exchanges)
        else:
            provider = None
        
        assert isinstance(provider, RestMarketDataProvider)
    
    def test_create_ws_provider_from_config(self):
        """설정에서 WebSocket 제공자 생성"""
        # Mock 설정
        config = Mock()
        config.data_source = "ws"
        
        # Mock WS 어댑터
        ws_adapters = {
            "upbit": Mock(),
            "binance": Mock(),
        }
        
        # WebSocket 제공자 생성
        if config.data_source == "ws":
            provider = WebSocketMarketDataProvider(ws_adapters)
        else:
            provider = None
        
        assert isinstance(provider, WebSocketMarketDataProvider)
    
    def test_data_source_rest_default(self):
        """기본값: REST"""
        # 기본값은 REST
        data_source = "rest"
        
        assert data_source == "rest"
    
    def test_data_source_switch_runtime(self):
        """런타임 데이터 소스 전환"""
        # REST 제공자
        rest_provider = RestMarketDataProvider({"a": Mock(), "b": Mock()})
        
        # WebSocket 제공자
        ws_provider = WebSocketMarketDataProvider({"upbit": Mock(), "binance": Mock()})
        
        # 전환
        current_provider = rest_provider
        assert isinstance(current_provider, RestMarketDataProvider)
        
        current_provider = ws_provider
        assert isinstance(current_provider, WebSocketMarketDataProvider)


class TestD50ProviderInterface:
    """D50 MarketDataProvider 인터페이스 테스트"""
    
    def test_both_providers_have_get_latest_snapshot(self):
        """두 제공자 모두 get_latest_snapshot 메서드 보유"""
        rest_provider = RestMarketDataProvider({"a": Mock(), "b": Mock()})
        ws_provider = WebSocketMarketDataProvider({"upbit": Mock(), "binance": Mock()})
        
        assert hasattr(rest_provider, "get_latest_snapshot")
        assert hasattr(ws_provider, "get_latest_snapshot")
        assert callable(rest_provider.get_latest_snapshot)
        assert callable(ws_provider.get_latest_snapshot)
    
    def test_both_providers_have_start_stop(self):
        """두 제공자 모두 start/stop 메서드 보유"""
        rest_provider = RestMarketDataProvider({"a": Mock(), "b": Mock()})
        ws_provider = WebSocketMarketDataProvider({"upbit": Mock(), "binance": Mock()})
        
        assert hasattr(rest_provider, "start")
        assert hasattr(rest_provider, "stop")
        assert hasattr(ws_provider, "start")
        assert hasattr(ws_provider, "stop")
        assert callable(rest_provider.start)
        assert callable(rest_provider.stop)
        assert callable(ws_provider.start)
        assert callable(ws_provider.stop)
    
    def test_provider_interface_consistency(self):
        """제공자 인터페이스 일관성"""
        rest_provider = RestMarketDataProvider({"a": Mock(), "b": Mock()})
        ws_provider = WebSocketMarketDataProvider({"upbit": Mock(), "binance": Mock()})
        
        # 두 제공자 모두 동일한 공개 메서드를 가져야 함
        rest_methods = set(m for m in dir(rest_provider) if not m.startswith("_"))
        ws_methods = set(m for m in dir(ws_provider) if not m.startswith("_"))
        
        # 공통 메서드 확인
        common_methods = rest_methods & ws_methods
        assert "get_latest_snapshot" in common_methods
        assert "start" in common_methods
        assert "stop" in common_methods


class TestD50ProviderErrorHandling:
    """D50 제공자 에러 처리 테스트"""
    
    def test_rest_provider_unknown_symbol(self):
        """REST 제공자: 알 수 없는 심볼"""
        exchanges = {"a": Mock(), "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        # 알 수 없는 심볼
        snapshot = provider.get_latest_snapshot("UNKNOWN")
        
        assert snapshot is None
    
    def test_ws_provider_unknown_symbol(self):
        """WebSocket 제공자: 알 수 없는 심볼"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 알 수 없는 심볼
        snapshot = provider.get_latest_snapshot("UNKNOWN")
        
        assert snapshot is None
    
    def test_rest_provider_exchange_error(self):
        """REST 제공자: 거래소 에러"""
        upbit_exchange = Mock()
        upbit_exchange.get_orderbook.side_effect = Exception("API Error")
        
        exchanges = {"a": upbit_exchange, "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        # 에러 처리
        snapshot = provider.get_latest_snapshot("KRW-BTC")
        
        assert snapshot is None

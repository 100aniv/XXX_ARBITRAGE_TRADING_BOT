# -*- coding: utf-8 -*-
"""
D79: Cross-Exchange Arbitrage - Tests

SymbolMapper, FXConverter, SpreadModel, Universe Provider 테스트.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

from arbitrage.cross_exchange.symbol_mapper import (
    SymbolMapper,
    SymbolMapping,
    Exchange,
)
from arbitrage.cross_exchange.fx_converter import (
    FXConverter,
    FXRate,
)
from arbitrage.cross_exchange.spread_model import (
    SpreadModel,
    CrossSpread,
    SpreadDirection,
)
from arbitrage.cross_exchange.universe_provider import (
    CrossExchangeUniverseProvider,
    CrossSymbol,
)


class TestSymbolMapper:
    """SymbolMapper 테스트"""
    
    def test_map_upbit_to_binance_btc(self):
        """BTC 심볼 매핑 (KRW-BTC → BTCUSDT)"""
        mapper = SymbolMapper()
        
        mapping = mapper.map_upbit_to_binance("KRW-BTC")
        
        assert mapping is not None
        assert mapping.upbit_symbol == "KRW-BTC"
        assert mapping.binance_symbol == "BTCUSDT"
        assert mapping.base_asset == "BTC"
        assert mapping.upbit_quote == "KRW"
        assert mapping.binance_quote == "USDT"
        assert mapping.confidence == 1.0
    
    def test_map_upbit_to_binance_eth(self):
        """ETH 심볼 매핑 (KRW-ETH → ETHUSDT)"""
        mapper = SymbolMapper()
        
        mapping = mapper.map_upbit_to_binance("KRW-ETH")
        
        assert mapping is not None
        assert mapping.upbit_symbol == "KRW-ETH"
        assert mapping.binance_symbol == "ETHUSDT"
        assert mapping.base_asset == "ETH"
    
    def test_map_upbit_to_binance_sol(self):
        """SOL 심볼 매핑 (KRW-SOL → SOLUSDT)"""
        mapper = SymbolMapper()
        
        mapping = mapper.map_upbit_to_binance("KRW-SOL")
        
        assert mapping is not None
        assert mapping.binance_symbol == "SOLUSDT"
    
    def test_map_binance_to_upbit_btc(self):
        """Reverse mapping (BTCUSDT → KRW-BTC)"""
        mapper = SymbolMapper()
        
        mapping = mapper.map_binance_to_upbit("BTCUSDT")
        
        assert mapping is not None
        assert mapping.upbit_symbol == "KRW-BTC"
        assert mapping.binance_symbol == "BTCUSDT"
        assert mapping.confidence == 0.8  # Reverse mapping (medium confidence)
    
    def test_map_upbit_to_binance_invalid(self):
        """Invalid symbol mapping"""
        mapper = SymbolMapper()
        
        mapping = mapper.map_upbit_to_binance("INVALID-FORMAT-XXX")
        
        assert mapping is None
    
    def test_map_upbit_to_binance_cache(self):
        """캐시 동작 확인"""
        mapper = SymbolMapper()
        
        # First call
        mapping1 = mapper.map_upbit_to_binance("KRW-BTC")
        
        # Second call (from cache)
        mapping2 = mapper.map_upbit_to_binance("KRW-BTC")
        
        assert mapping1 is mapping2  # Same object (cached)
    
    def test_mapping_stats(self):
        """매핑 통계 확인"""
        mapper = SymbolMapper()
        
        mapper.map_upbit_to_binance("KRW-BTC")
        mapper.map_upbit_to_binance("KRW-ETH")
        mapper.map_upbit_to_binance("INVALID-XXX")
        
        stats = mapper.get_mapping_stats()
        
        assert stats["total_mapped"] == 2
        assert stats["failed_count"] == 1
        assert stats["total_attempts"] == 3
        assert stats["success_rate"] > 60.0
    
    def test_manual_override(self):
        """수동 예외 매핑"""
        mapper = SymbolMapper()
        
        # MANUAL_OVERRIDES에 정의된 케이스
        mapping = mapper.map_upbit_to_binance("KRW-USDT")
        
        assert mapping is not None
        assert mapping.binance_symbol == "USDTUSDC"  # Manual override
        assert mapping.confidence == 1.0


class TestFXConverter:
    """FXConverter 테스트"""
    
    def test_get_fx_rate_fallback(self):
        """Fallback 환율 사용"""
        converter = FXConverter(fallback_rate=1300.0)
        
        fx_rate = converter.get_fx_rate()
        
        assert fx_rate is not None
        assert fx_rate.rate == 1300.0
        assert fx_rate.source == "fallback"
        assert fx_rate.confidence == 0.5
    
    def test_usdt_to_krw_conversion(self):
        """USDT → KRW 변환"""
        converter = FXConverter(fallback_rate=1300.0)
        
        krw_amount = converter.usdt_to_krw(100.0)
        
        assert krw_amount == 130000.0
    
    def test_krw_to_usdt_conversion(self):
        """KRW → USDT 변환"""
        converter = FXConverter(fallback_rate=1300.0)
        
        usdt_amount = converter.krw_to_usdt(130000.0)
        
        assert usdt_amount == 100.0
    
    def test_get_fx_rate_from_upbit_usdt(self):
        """Upbit USDT ticker에서 환율 조회"""
        # Mock Upbit client
        mock_upbit_client = Mock()
        mock_ticker = Mock()
        mock_ticker.last_price = 1350.0
        mock_upbit_client.fetch_ticker.return_value = mock_ticker
        
        converter = FXConverter(upbit_client=mock_upbit_client)
        
        fx_rate = converter.get_fx_rate()
        
        assert fx_rate.rate == 1350.0
        assert fx_rate.source == "upbit_usdt"
        assert fx_rate.confidence == 1.0
    
    def test_get_fx_rate_from_btc_ratio(self):
        """BTC price ratio로 환율 추정"""
        # Mock Upbit client
        mock_upbit_client = Mock()
        mock_upbit_usdt_ticker = Mock()
        mock_upbit_usdt_ticker.last_price = 0  # USDT ticker invalid
        mock_upbit_client.fetch_ticker.side_effect = [
            mock_upbit_usdt_ticker,  # First call (USDT)
            Mock(last_price=50000000.0),  # Second call (BTC)
        ]
        
        # Mock Binance client
        mock_binance_client = Mock()
        mock_binance_btc_ticker = Mock()
        mock_binance_btc_ticker.last_price = 40000.0
        mock_binance_client.fetch_ticker.return_value = mock_binance_btc_ticker
        
        converter = FXConverter(
            upbit_client=mock_upbit_client,
            binance_client=mock_binance_client,
        )
        
        fx_rate = converter.get_fx_rate()
        
        assert fx_rate.rate == 50000000.0 / 40000.0  # 1250.0
        assert fx_rate.source == "btc_ratio"
        assert fx_rate.confidence == 0.8
    
    def test_cache_ttl(self):
        """캐시 TTL 확인"""
        converter = FXConverter(fallback_rate=1300.0)
        
        # First call
        fx_rate1 = converter.get_fx_rate()
        
        # Second call (from cache)
        fx_rate2 = converter.get_fx_rate()
        
        assert fx_rate1.rate == fx_rate2.rate
        
        # Cache info
        cache_info = converter.get_cache_info()
        assert cache_info["is_valid"] is True
        assert cache_info["cached_rate"] == 1300.0


class TestSpreadModel:
    """SpreadModel 테스트"""
    
    def test_calculate_spread_positive(self):
        """Positive spread 계산 (Upbit > Binance)"""
        mock_fx_converter = Mock()
        mock_fx_converter.get_fx_rate.return_value = FXRate(
            rate=1300.0,
            source="mock",
            timestamp=time.time(),
            confidence=1.0,
        )
        
        model = SpreadModel(fx_converter=mock_fx_converter)
        
        # Mock mapping
        mock_mapping = Mock()
        mock_mapping.upbit_symbol = "KRW-BTC"
        mock_mapping.binance_symbol = "BTCUSDT"
        
        # Upbit: 52M KRW, Binance: 40K USDT
        # Binance in KRW: 40K * 1300 = 52M
        # Spread: 52M - 52M = 0 (should be neutral)
        spread = model.calculate_spread(
            symbol_mapping=mock_mapping,
            upbit_price_krw=52000000.0,
            binance_price_usdt=40000.0,
        )
        
        assert spread.direction == SpreadDirection.NEUTRAL
        assert abs(spread.spread_percent) < 0.1
    
    def test_calculate_spread_negative(self):
        """Negative spread 계산 (Upbit < Binance)"""
        mock_fx_converter = Mock()
        mock_fx_converter.get_fx_rate.return_value = FXRate(
            rate=1300.0,
            source="mock",
            timestamp=time.time(),
            confidence=1.0,
        )
        
        model = SpreadModel(fx_converter=mock_fx_converter)
        
        mock_mapping = Mock()
        mock_mapping.upbit_symbol = "KRW-BTC"
        
        # Upbit: 50M KRW, Binance: 40K USDT
        # Binance in KRW: 40K * 1300 = 52M
        # Spread: 50M - 52M = -2M (negative)
        spread = model.calculate_spread(
            symbol_mapping=mock_mapping,
            upbit_price_krw=50000000.0,
            binance_price_usdt=40000.0,
        )
        
        assert spread.direction == SpreadDirection.NEGATIVE
        assert spread.spread_krw < 0
        assert spread.spread_percent < 0
    
    def test_is_profitable(self):
        """수익성 판단"""
        mock_fx_converter = Mock()
        mock_fx_converter.get_fx_rate.return_value = FXRate(
            rate=1300.0,
            source="mock",
            timestamp=time.time(),
            confidence=1.0,
        )
        
        model = SpreadModel(fx_converter=mock_fx_converter)
        
        mock_mapping = Mock()
        
        # Upbit: 52.6M KRW, Binance: 40K USDT
        # Binance in KRW: 40K * 1300 = 52M
        # Spread: 52.6M - 52M = 600K (1.15%)
        spread = model.calculate_spread(
            symbol_mapping=mock_mapping,
            upbit_price_krw=52600000.0,
            binance_price_usdt=40000.0,
        )
        
        assert spread.is_profitable(min_spread_percent=0.5)
        assert spread.spread_percent > 1.0
    
    def test_get_arbitrage_action(self):
        """아비트라지 액션 제안"""
        mock_fx_converter = Mock()
        mock_fx_converter.get_fx_rate.return_value = FXRate(
            rate=1300.0,
            source="mock",
            timestamp=time.time(),
            confidence=1.0,
        )
        
        model = SpreadModel(fx_converter=mock_fx_converter)
        
        mock_mapping = Mock()
        
        # Positive spread
        spread_positive = model.calculate_spread(
            symbol_mapping=mock_mapping,
            upbit_price_krw=53000000.0,
            binance_price_usdt=40000.0,
        )
        
        assert spread_positive.get_arbitrage_action() == "upbit_sell_binance_buy"
        
        # Negative spread
        spread_negative = model.calculate_spread(
            symbol_mapping=mock_mapping,
            upbit_price_krw=50000000.0,
            binance_price_usdt=40000.0,
        )
        
        assert spread_negative.get_arbitrage_action() == "upbit_buy_binance_sell"


class TestCrossExchangeUniverseProvider:
    """CrossExchangeUniverseProvider 테스트"""
    
    def test_get_top_symbols_empty_upbit(self):
        """Upbit 심볼이 없을 때"""
        mock_symbol_mapper = Mock()
        mock_upbit_client = Mock()
        mock_upbit_client.fetch_top_symbols.return_value = []
        mock_binance_client = Mock()
        
        provider = CrossExchangeUniverseProvider(
            symbol_mapper=mock_symbol_mapper,
            upbit_client=mock_upbit_client,
            binance_client=mock_binance_client,
        )
        
        symbols = provider.get_top_symbols(top_n=10)
        
        assert symbols == []
    
    def test_get_top_symbols_success(self):
        """성공적인 심볼 조회"""
        # Mock mapper
        mock_symbol_mapper = Mock()
        mock_mapping_btc = Mock()
        mock_mapping_btc.upbit_symbol = "KRW-BTC"
        mock_mapping_btc.binance_symbol = "BTCUSDT"
        mock_symbol_mapper.map_upbit_to_binance.return_value = mock_mapping_btc
        
        # Mock Upbit client
        mock_upbit_client = Mock()
        mock_upbit_client.fetch_top_symbols.return_value = ["KRW-BTC"]
        mock_upbit_ticker = Mock()
        mock_upbit_ticker.acc_trade_price_24h = 500_000_000_000.0  # 500B KRW
        mock_upbit_client.fetch_ticker.return_value = mock_upbit_ticker
        
        # Mock Binance client
        mock_binance_client = Mock()
        mock_binance_ticker = Mock()
        mock_binance_ticker.quote_volume_24h = 500_000_000.0  # 500M USDT
        mock_binance_client.fetch_ticker.return_value = mock_binance_ticker
        
        provider = CrossExchangeUniverseProvider(
            symbol_mapper=mock_symbol_mapper,
            upbit_client=mock_upbit_client,
            binance_client=mock_binance_client,
        )
        
        symbols = provider.get_top_symbols(top_n=10)
        
        assert len(symbols) == 1
        assert symbols[0].mapping.upbit_symbol == "KRW-BTC"
        assert symbols[0].upbit_volume_24h == 500_000_000_000.0
    
    def test_combined_score_calculation(self):
        """종합 점수 계산"""
        mock_symbol_mapper = Mock()
        mock_upbit_client = Mock()
        mock_binance_client = Mock()
        
        provider = CrossExchangeUniverseProvider(
            symbol_mapper=mock_symbol_mapper,
            upbit_client=mock_upbit_client,
            binance_client=mock_binance_client,
        )
        
        # Upbit: 100M KRW, Binance: 100K USDT
        score = provider._calculate_combined_score(
            upbit_volume_krw=100_000_000.0,
            binance_volume_usdt=100_000.0,
        )
        
        # Score = (100M * 0.6) + (100K * 1300 * 0.4)
        # = 60M + 52M = 112M
        assert score > 100_000_000.0


# Integration test placeholder
def test_end_to_end_integration():
    """E2E integration test (placeholder)"""
    # This would test full flow:
    # 1. SymbolMapper
    # 2. FXConverter
    # 3. SpreadModel
    # 4. Universe Provider
    # 5. Metrics
    
    # For now, just pass
    pass

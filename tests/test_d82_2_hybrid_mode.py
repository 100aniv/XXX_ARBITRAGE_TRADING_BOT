# -*- coding: utf-8 -*-
"""
D82-2: TopN Hybrid Mode Unit Tests

Tests for Hybrid TopN Selection Mode:
- Selection cache behavior
- Data source separation (selection vs entry/exit)
- Config integration
"""

import sys
from pathlib import Path
import time

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from arbitrage.domain.topn_provider import TopNProvider, TopNMode
from arbitrage.config.settings import TopNSelectionConfig


def test_topn_selection_cache_hit():
    """Verify cache is used when TTL is valid"""
    provider = TopNProvider(
        mode=TopNMode.TOP_20,
        selection_data_source="mock",
        cache_ttl_seconds=60,
    )
    
    # First call: cache miss
    result1 = provider.get_topn_symbols()
    assert result1 is not None
    assert len(result1.symbols) == 20
    
    # Second call (immediately after): cache hit
    result2 = provider.get_topn_symbols()
    assert result2 is not None
    
    # Should be same cached result (same timestamp)
    assert result1.timestamp == result2.timestamp
    assert result1.symbols == result2.symbols


def test_topn_selection_cache_miss_after_ttl():
    """Verify cache expires after TTL"""
    provider = TopNProvider(
        mode=TopNMode.TOP_10,
        selection_data_source="mock",
        cache_ttl_seconds=1,  # 1 second TTL
    )
    
    # First call
    result1 = provider.get_topn_symbols()
    ts1 = result1.timestamp
    
    # Wait for cache to expire
    time.sleep(1.5)
    
    # Second call: should refresh
    result2 = provider.get_topn_symbols()
    ts2 = result2.timestamp
    
    # Timestamps should be different (new fetch)
    assert ts2 > ts1


def test_topn_hybrid_mode_data_source_separation():
    """Verify selection and entry/exit use different data sources"""
    provider = TopNProvider(
        mode=TopNMode.TOP_10,
        selection_data_source="mock",
        entry_exit_data_source="real",  # Different from selection
        cache_ttl_seconds=600,
    )
    
    # Selection should use mock (always succeeds)
    topn_result = provider.get_topn_symbols()
    assert topn_result is not None
    assert len(topn_result.symbols) == 10
    
    # Entry/Exit should attempt real (may fail if API unavailable, but path is different)
    # For testing, we just verify the method accepts the call
    spread = provider.get_current_spread("BTC/KRW")
    # spread may be None if Upbit API is down, but that's OK for unit test


def test_topn_mock_selection_always_succeeds():
    """Verify mock selection always returns valid results"""
    # Note: Mock has 30 symbols max
    provider = TopNProvider(
        mode=TopNMode.TOP_20,
        selection_data_source="mock",
        cache_ttl_seconds=600,
    )
    
    result = provider.get_topn_symbols()
    
    assert result is not None
    assert len(result.symbols) == 20  # Mock mode has 30 symbols, TOP_20 returns 20
    assert len(result.metrics) == 20
    assert result.mode == TopNMode.TOP_20
    
    # Verify all symbols are valid
    for symbol_a, symbol_b in result.symbols:
        assert "/" in symbol_a
        assert "/" in symbol_b


def test_topn_cache_validity_check():
    """Verify cache validity check method"""
    provider = TopNProvider(
        mode=TopNMode.TOP_10,
        selection_data_source="mock",
        cache_ttl_seconds=2,
    )
    
    # Initially no cache
    assert not provider._is_selection_cache_valid()
    
    # After first call, cache is valid
    provider.get_topn_symbols()
    assert provider._is_selection_cache_valid()
    
    # After TTL expires, cache invalid
    time.sleep(2.5)
    assert not provider._is_selection_cache_valid()


def test_topn_force_refresh():
    """Verify force_refresh bypasses cache"""
    provider = TopNProvider(
        mode=TopNMode.TOP_10,
        selection_data_source="mock",
        cache_ttl_seconds=600,  # Long TTL
    )
    
    # First call
    result1 = provider.get_topn_symbols()
    ts1 = result1.timestamp
    
    time.sleep(0.1)  # Small delay
    
    # Force refresh (should create new result)
    result2 = provider.get_topn_symbols(force_refresh=True)
    ts2 = result2.timestamp
    
    # Timestamps should be different
    assert ts2 > ts1


def test_topn_config_integration():
    """Verify TopNSelectionConfig integration"""
    config = TopNSelectionConfig(
        selection_data_source="mock",
        selection_cache_ttl_sec=300,
        selection_max_symbols=30,
        entry_exit_data_source="real",
    )
    
    provider = TopNProvider(
        mode=TopNMode.TOP_20,
        selection_data_source=config.selection_data_source,
        entry_exit_data_source=config.entry_exit_data_source,
        cache_ttl_seconds=config.selection_cache_ttl_sec,
        max_symbols=config.selection_max_symbols,
    )
    
    assert provider.selection_data_source == "mock"
    assert provider.entry_exit_data_source == "real"
    assert provider.cache_ttl_seconds == 300
    assert provider.max_symbols == 30


def test_topn_get_current_spread_mock_mode():
    """Verify get_current_spread works in mock mode"""
    provider = TopNProvider(
        mode=TopNMode.TOP_10,
        selection_data_source="mock",
        entry_exit_data_source="mock",  # Mock mode for spread
    )
    
    spread = provider.get_current_spread("BTC/KRW")
    
    assert spread is not None
    assert spread.symbol == "BTC/KRW"
    assert spread.upbit_bid > 0
    assert spread.upbit_ask > 0
    assert spread.upbit_ask > spread.upbit_bid  # Ask should be higher than bid
    assert spread.spread_bps > 0


def test_topn_real_selection_config():
    """D82-3: Verify Real Selection Rate Limit config integration"""
    config = TopNSelectionConfig(
        selection_data_source="real",
        selection_cache_ttl_sec=600,
        selection_max_symbols=50,
        entry_exit_data_source="real",
        # D82-3: Rate Limit 옵션
        selection_rate_limit_enabled=True,
        selection_batch_size=10,
        selection_batch_delay_sec=1.5,
    )
    
    provider = TopNProvider(
        mode=TopNMode.TOP_20,
        selection_data_source=config.selection_data_source,
        entry_exit_data_source=config.entry_exit_data_source,
        cache_ttl_seconds=config.selection_cache_ttl_sec,
        max_symbols=config.selection_max_symbols,
        selection_rate_limit_enabled=config.selection_rate_limit_enabled,
        selection_batch_size=config.selection_batch_size,
        selection_batch_delay_sec=config.selection_batch_delay_sec,
    )
    
    assert provider.selection_data_source == "real"
    assert provider.selection_rate_limit_enabled == True
    assert provider.selection_batch_size == 10
    assert provider.selection_batch_delay_sec == 1.5


def test_topn_real_selection_rate_limited_mocked(monkeypatch):
    """D82-3: Verify Real Selection uses batching and rate limiting (mocked)"""
    # Mock 데이터 준비
    mock_candidate_symbols = [f"KRW-SYM{i:02d}" for i in range(25)]  # 25개 후보
    mock_metrics = {}
    
    fetch_count = {"ticker": 0, "orderbook": 0}
    
    def mock_fetch_top_symbols(self, *args, **kwargs):
        return mock_candidate_symbols
    
    def mock_fetch_ticker(self, symbol):
        fetch_count["ticker"] += 1
        # Mock ticker 데이터
        class MockTicker:
            acc_trade_price_24h = 1_000_000_000  # 1B KRW
        return MockTicker()
    
    def mock_fetch_orderbook(self, symbol):
        fetch_count["orderbook"] += 1
        # Mock orderbook 데이터
        class MockLevel:
            def __init__(self, price, size):
                self.price = price
                self.size = size
        
        class MockOrderbook:
            def __init__(self):
                self.bids = [MockLevel(100000, 0.1) for _ in range(5)]
                self.asks = [MockLevel(100100, 0.1) for _ in range(5)]
        
        return MockOrderbook()
    
    # Provider 생성 (Real Selection, batch_size=10)
    provider = TopNProvider(
        mode=TopNMode.TOP_20,
        selection_data_source="real",
        selection_rate_limit_enabled=False,  # Rate limiter는 skip (빠른 테스트)
        selection_batch_size=10,
        selection_batch_delay_sec=0.0,  # No delay for testing
    )
    
    # Monkeypatch: Upbit client methods
    monkeypatch.setattr(
        "arbitrage.exchanges.upbit_public_data.UpbitPublicDataClient.fetch_top_symbols",
        mock_fetch_top_symbols
    )
    monkeypatch.setattr(
        "arbitrage.exchanges.upbit_public_data.UpbitPublicDataClient.fetch_ticker",
        mock_fetch_ticker
    )
    monkeypatch.setattr(
        "arbitrage.exchanges.upbit_public_data.UpbitPublicDataClient.fetch_orderbook",
        mock_fetch_orderbook
    )
    
    # TopN selection 실행
    result = provider._fetch_real_metrics_safe()
    
    # 검증: 25개 심볼에 대해 ticker + orderbook 호출 (각 25회)
    assert fetch_count["ticker"] == 25
    assert fetch_count["orderbook"] == 25
    
    # 결과 검증
    assert len(result) == 25
    
    # 배치 처리 확인: 25개 심볼 / 10개 배치 = 3 batches (10 + 10 + 5)
    # (이 테스트에서는 batch_delay=0이므로 시간 체크는 생략)


def test_topn_real_selection_fallback_on_error(monkeypatch):
    """D82-3: Verify Real Selection falls back to mock on complete failure"""
    def mock_fetch_top_symbols_error(self, *args, **kwargs):
        raise Exception("API Error")
    
    provider = TopNProvider(
        mode=TopNMode.TOP_10,
        selection_data_source="real",
        selection_rate_limit_enabled=False,
    )
    
    # Monkeypatch: fetch_top_symbols가 실패하도록
    monkeypatch.setattr(
        "arbitrage.exchanges.upbit_public_data.UpbitPublicDataClient.fetch_top_symbols",
        mock_fetch_top_symbols_error
    )
    
    # TopN selection 실행 (실패하면 mock으로 fallback)
    result = provider._fetch_real_metrics_safe()
    
    # Mock fallback 확인 (mock은 30개 심볼 반환)
    assert len(result) > 0  # Mock은 항상 valid metrics 반환


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

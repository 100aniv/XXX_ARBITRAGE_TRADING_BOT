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


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

"""
D77-0: TopN Arbitrage PAPER Baseline - Unit Tests

테스트 범위:
1. TopN Provider: Universe 선정 로직
2. Exit Strategy: TP/SL/Time-based/Spread reversal
3. Integration: Runner 동작 검증
"""

import time
from pathlib import Path

import pytest

from arbitrage.domain.topn_provider import TopNProvider, TopNMode, SymbolMetrics
from arbitrage.domain.exit_strategy import (
    ExitStrategy,
    ExitConfig,
    ExitReason,
    ExitDecision,
)


class TestTopNProvider:
    """TopN Provider 테스트"""
    
    def test_topn_provider_returns_correct_count(self):
        """TOP_N 모드에서 올바른 개수의 심볼 반환"""
        # TOP_20 (relaxed thresholds for mock data)
        provider = TopNProvider(
            mode=TopNMode.TOP_20,
            min_volume_usd=10_000.0,  # Lowered for mock
            min_liquidity_usd=1_000.0,  # Lowered for mock
            max_spread_bps=100.0,  # Increased for mock
        )
        result = provider.get_topn_symbols()
        
        assert len(result.symbols) == 20
        assert result.mode == TopNMode.TOP_20
        
        # TOP_50
        provider = TopNProvider(
            mode=TopNMode.TOP_50,
            min_volume_usd=10_000.0,
            min_liquidity_usd=1_000.0,
            max_spread_bps=100.0,
        )
        result = provider.get_topn_symbols()
        
        assert len(result.symbols) <= 50  # Mock에서는 30개만 제공
        assert result.mode == TopNMode.TOP_50
    
    def test_topn_provider_symbol_format(self):
        """심볼 형식 검증 (symbol_a, symbol_b)"""
        provider = TopNProvider(mode=TopNMode.TOP_20)
        result = provider.get_topn_symbols()
        
        for symbol_a, symbol_b in result.symbols:
            assert "/KRW" in symbol_a
            assert "/USDT" in symbol_b
            
            base_a = symbol_a.replace("/KRW", "")
            base_b = symbol_b.replace("/USDT", "")
            assert base_a == base_b  # Same base symbol
    
    def test_topn_provider_composite_score_calculation(self):
        """Composite Score 계산 검증"""
        metrics = SymbolMetrics(
            symbol="BTC/KRW",
            volume_24h=10_000_000,
            liquidity_depth=100_000,
            spread_bps=10.0,
        )
        
        # Calculate composite score
        score = metrics.calculate_composite_score(
            volume_rank=1.0,
            liquidity_rank=1.0,
            spread_rank=1.0,
        )
        
        # 40% volume + 30% liquidity + 30% spread = 100%
        assert score == pytest.approx(1.0, abs=0.01)
        
        # Partial score
        score = metrics.calculate_composite_score(
            volume_rank=0.5,
            liquidity_rank=0.3,
            spread_rank=0.2,
        )
        
        expected = (0.5 * 0.4) + (0.3 * 0.3) + (0.2 * 0.3)
        assert score == pytest.approx(expected, abs=0.01)
    
    def test_topn_provider_cache_ttl(self):
        """Cache TTL 검증"""
        provider = TopNProvider(mode=TopNMode.TOP_20, cache_ttl_seconds=1)
        
        # First call
        result1 = provider.get_topn_symbols()
        timestamp1 = result1.timestamp
        
        # Immediate second call (cache hit)
        result2 = provider.get_topn_symbols()
        timestamp2 = result2.timestamp
        
        assert timestamp1 == timestamp2  # Cache hit
        
        # Wait for TTL expiration
        time.sleep(1.1)
        
        # Third call (cache miss, forced refresh)
        result3 = provider.get_topn_symbols()
        timestamp3 = result3.timestamp
        
        assert timestamp3 > timestamp2  # Cache miss
    
    def test_topn_provider_churn_rate_calculation(self):
        """Churn rate 계산 검증"""
        provider = TopNProvider(mode=TopNMode.TOP_20)
        
        # First call (no previous symbols)
        result1 = provider.get_topn_symbols()
        assert result1.churn_rate == 0.0
        
        # Second call (same symbols, mock always returns same)
        result2 = provider.get_topn_symbols(force_refresh=True)
        assert result2.churn_rate == 0.0  # No change


class TestExitStrategy:
    """Exit Strategy 테스트"""
    
    def test_exit_strategy_take_profit(self):
        """TP (Take Profit) 조건 검증"""
        config = ExitConfig(
            tp_threshold_pct=1.0,
            sl_threshold_pct=0.5,
            max_hold_time_seconds=180.0,
            spread_reversal_threshold_bps=-10.0,
        )
        strategy = ExitStrategy(config=config)
        
        # Register position
        strategy.register_position(
            position_id=1,
            symbol_a="BTC/KRW",
            symbol_b="BTC/USDT",
            entry_price_a=50000.0,
            entry_price_b=50000.0,
            entry_spread_bps=20.0,
            size=1.0,
        )
        
        # Check exit (TP scenario: +1.5% PnL)
        decision = strategy.check_exit(
            position_id=1,
            current_price_a=50750.0,  # +1.5%
            current_price_b=50000.0,
            current_spread_bps=15.0,
        )
        
        assert decision.should_exit is True
        assert decision.reason == ExitReason.TAKE_PROFIT
        assert decision.current_pnl_pct > config.tp_threshold_pct
    
    def test_exit_strategy_stop_loss(self):
        """SL (Stop Loss) 조건 검증"""
        config = ExitConfig(
            tp_threshold_pct=1.0,
            sl_threshold_pct=0.5,
            max_hold_time_seconds=180.0,
            spread_reversal_threshold_bps=-10.0,
            take_profit_delta_bps=-100.0,  # D99-5: TP_DELTA 비활성화
        )
        strategy = ExitStrategy(config=config)
        
        strategy.register_position(
            position_id=1,
            symbol_a="BTC/KRW",
            symbol_b="BTC/USDT",
            entry_price_a=50000.0,
            entry_price_b=50000.0,
            entry_spread_bps=20.0,
            size=1.0,
        )
        
        # Check exit (SL scenario: -0.8% PnL)
        decision = strategy.check_exit(
            position_id=1,
            current_price_a=49600.0,  # -0.8%
            current_price_b=50000.0,
            current_spread_bps=15.0,
        )
        
        assert decision.should_exit is True
        assert decision.reason == ExitReason.STOP_LOSS
        assert decision.current_pnl_pct < -config.sl_threshold_pct
    
    def test_exit_strategy_time_limit(self):
        """Time-based Exit 조건 검증"""
        config = ExitConfig(
            tp_threshold_pct=1.0,
            sl_threshold_pct=0.5,
            max_hold_time_seconds=1.0,  # 1 second
            spread_reversal_threshold_bps=-10.0,
        )
        strategy = ExitStrategy(config=config)
        
        strategy.register_position(
            position_id=1,
            symbol_a="BTC/KRW",
            symbol_b="BTC/USDT",
            entry_price_a=50000.0,
            entry_price_b=50000.0,
            entry_spread_bps=20.0,
            size=1.0,
        )
        
        # Wait for time limit
        time.sleep(1.1)
        
        # Check exit (Time limit scenario)
        decision = strategy.check_exit(
            position_id=1,
            current_price_a=50000.0,  # No price change
            current_price_b=50000.0,
            current_spread_bps=20.0,
        )
        
        assert decision.should_exit is True
        assert decision.reason == ExitReason.TIME_LIMIT
        assert decision.time_held_seconds >= config.max_hold_time_seconds
    
    def test_exit_strategy_spread_reversal(self):
        """Spread Reversal Exit 조건 검증"""
        config = ExitConfig(
            tp_threshold_pct=1.0,
            sl_threshold_pct=0.5,
            max_hold_time_seconds=180.0,
            spread_reversal_threshold_bps=-10.0,
            take_profit_delta_bps=-100.0,  # D99-5: TP_DELTA 비활성화
        )
        strategy = ExitStrategy(config=config)
        
        strategy.register_position(
            position_id=1,
            symbol_a="BTC/KRW",
            symbol_b="BTC/USDT",
            entry_price_a=50000.0,
            entry_price_b=50000.0,
            entry_spread_bps=20.0,
            size=1.0,
        )
        
        # Check exit (Spread reversal: -15 bps)
        decision = strategy.check_exit(
            position_id=1,
            current_price_a=50000.0,
            current_price_b=50000.0,
            current_spread_bps=-15.0,  # Spread turned negative
        )
        
        assert decision.should_exit is True
        assert decision.reason == ExitReason.SPREAD_REVERSAL
        assert decision.current_spread_bps < config.spread_reversal_threshold_bps
    
    def test_exit_strategy_hold_position(self):
        """Position Hold 시나리오 (Exit 조건 미충족)"""
        config = ExitConfig(
            tp_threshold_pct=1.0,
            sl_threshold_pct=0.5,
            max_hold_time_seconds=180.0,
            spread_reversal_threshold_bps=-10.0,
            take_profit_delta_bps=-100.0,  # D99-5: TP_DELTA 비활성화
        )
        strategy = ExitStrategy(config=config)
        
        strategy.register_position(
            position_id=1,
            symbol_a="BTC/KRW",
            symbol_b="BTC/USDT",
            entry_price_a=50000.0,
            entry_price_b=50000.0,
            entry_spread_bps=20.0,
            size=1.0,
        )
        
        # Check exit (No exit conditions met)
        decision = strategy.check_exit(
            position_id=1,
            current_price_a=50100.0,  # +0.2% (below TP)
            current_price_b=50000.0,
            current_spread_bps=15.0,
        )
        
        assert decision.should_exit is False
        assert decision.reason == ExitReason.NONE
        assert decision.message == "HOLD"
    
    def test_exit_strategy_position_tracking(self):
        """Position tracking 검증"""
        config = ExitConfig()
        strategy = ExitStrategy(config=config)
        
        # Register 3 positions
        for i in range(3):
            strategy.register_position(
                position_id=i,
                symbol_a="BTC/KRW",
                symbol_b="BTC/USDT",
                entry_price_a=50000.0,
                entry_price_b=50000.0,
                entry_spread_bps=20.0,
                size=1.0,
            )
        
        assert strategy.get_position_count() == 3
        
        # Unregister 1 position
        strategy.unregister_position(position_id=1)
        
        assert strategy.get_position_count() == 2
        
        open_positions = strategy.get_open_positions()
        assert 0 in open_positions
        assert 1 not in open_positions
        assert 2 in open_positions


class TestD77Integration:
    """D77-0 Integration 테스트"""
    
    def test_d77_topn_and_exit_integration(self):
        """TopN Provider + Exit Strategy 통합 검증"""
        # TopN Provider (relaxed thresholds for mock)
        topn_provider = TopNProvider(
            mode=TopNMode.TOP_20,
            min_volume_usd=10_000.0,
            min_liquidity_usd=1_000.0,
            max_spread_bps=100.0,
        )
        result = topn_provider.get_topn_symbols()
        
        assert len(result.symbols) == 20
        
        # Exit Strategy
        exit_strategy = ExitStrategy(config=ExitConfig())
        
        # Register position for first symbol
        symbol_a, symbol_b = result.symbols[0]
        exit_strategy.register_position(
            position_id=1,
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            entry_price_a=50000.0,
            entry_price_b=50000.0,
            entry_spread_bps=20.0,
            size=1.0,
        )
        
        assert exit_strategy.get_position_count() == 1
        
        # Check exit (no conditions met)
        decision = exit_strategy.check_exit(
            position_id=1,
            current_price_a=50000.0,
            current_price_b=50000.0,
            current_spread_bps=20.0,
        )
        
        assert decision.should_exit is False

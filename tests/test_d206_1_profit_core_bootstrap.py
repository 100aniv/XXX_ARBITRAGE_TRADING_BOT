"""
D206-1 ProfitCore Bootstrap Test

목적: V1 ArbitrageEngine 로직(detect_opportunity, on_snapshot)이 V2 Engine에 정상 이식되었는지 검증

AC 검증:
- AC-1: detect_opportunity 로직 동작 (spread 계산, edge 검증)
- AC-2: on_snapshot 로직 동작 (거래 개설/종료)
- AC-3: 수수료/슬리피지 반영 (total_cost_bps)
"""

import pytest
from arbitrage.v2.core.engine import ArbitrageEngine, EngineConfig


def test_d206_1_detect_opportunity_basic():
    """AC-1: detect_opportunity가 양수 edge를 감지하는지 검증"""
    config = EngineConfig(
        taker_fee_a_bps=10.0,
        taker_fee_b_bps=10.0,
        slippage_bps=5.0,
        max_open_trades=1,
        exchange_a_to_b_rate=1.0,
    )
    engine = ArbitrageEngine(config)
    
    # Snapshot: bid_b(110) > ask_a(100) → 1000 bps spread
    snapshot = {
        'best_bid_a': 99.0,
        'best_ask_a': 100.0,
        'best_bid_b': 110.0,
        'best_ask_b': 111.0,
        'timestamp': '2026-01-16T00:00:00Z',
    }
    
    opp = engine._detect_single_opportunity(snapshot)
    
    assert opp is not None, "Should detect opportunity with 1000 bps spread"
    assert opp['side'] == 'LONG_A_SHORT_B', "Should favor LONG_A_SHORT_B"
    assert opp['spread_bps'] == pytest.approx(1000.0, abs=1.0), "Spread should be ~1000 bps"
    assert opp['net_edge_bps'] == pytest.approx(975.0, abs=1.0), "Net edge = 1000 - 25 (fees+slip)"


def test_d206_1_detect_opportunity_no_edge():
    """AC-1: net_edge < 0이면 기회를 감지하지 않아야 함"""
    config = EngineConfig(
        taker_fee_a_bps=10.0,
        taker_fee_b_bps=10.0,
        slippage_bps=5.0,
        max_open_trades=1,
        exchange_a_to_b_rate=1.0,
    )
    engine = ArbitrageEngine(config)
    
    # Snapshot: bid_b(100.1) - ask_a(100) = 0.1 → 10 bps spread (< 25 bps cost)
    snapshot = {
        'best_bid_a': 99.9,
        'best_ask_a': 100.0,
        'best_bid_b': 100.1,
        'best_ask_b': 100.2,
        'timestamp': '2026-01-16T00:00:00Z',
    }
    
    opp = engine._detect_single_opportunity(snapshot)
    
    assert opp is None, "Should NOT detect opportunity (net_edge < 0)"


def test_d206_1_on_snapshot_open_trade():
    """AC-2: on_snapshot이 거래를 개설하는지 검증"""
    config = EngineConfig(
        taker_fee_a_bps=10.0,
        taker_fee_b_bps=10.0,
        slippage_bps=5.0,
        max_open_trades=1,
        exchange_a_to_b_rate=1.0,
    )
    engine = ArbitrageEngine(config)
    
    snapshot = {
        'best_bid_a': 99.0,
        'best_ask_a': 100.0,
        'best_bid_b': 110.0,
        'best_ask_b': 111.0,
        'timestamp': '2026-01-16T00:00:00Z',
    }
    
    trades_changed = engine._process_snapshot(snapshot)
    
    assert len(trades_changed) == 1, "Should open 1 trade"
    assert trades_changed[0]['is_open'] is True
    assert trades_changed[0]['side'] == 'LONG_A_SHORT_B'
    assert len(engine._open_trades) == 1, "Engine should track 1 open trade"


def test_d206_1_on_snapshot_close_on_reversal():
    """AC-2: on_snapshot이 스프레드 역전 시 거래를 종료하는지 검증"""
    config = EngineConfig(
        taker_fee_a_bps=10.0,
        taker_fee_b_bps=10.0,
        slippage_bps=5.0,
        max_open_trades=1,
        close_on_spread_reversal=True,
        exchange_a_to_b_rate=1.0,
    )
    engine = ArbitrageEngine(config)
    
    # Open trade
    snapshot_open = {
        'best_bid_a': 99.0,
        'best_ask_a': 100.0,
        'best_bid_b': 110.0,
        'best_ask_b': 111.0,
        'timestamp': '2026-01-16T00:00:00Z',
    }
    engine._process_snapshot(snapshot_open)
    assert len(engine._open_trades) == 1
    
    # Spread reverses: both directions become negative
    # LONG_A_SHORT_B: bid_b(95) - ask_a(100) = -500 bps (negative)
    # LONG_B_SHORT_A: bid_a(99) - ask_b(99.5) = -50 bps (negative)
    snapshot_close = {
        'best_bid_a': 99.0,
        'best_ask_a': 100.0,
        'best_bid_b': 95.0,
        'best_ask_b': 99.5,
        'timestamp': '2026-01-16T00:01:00Z',
    }
    
    trades_changed = engine._process_snapshot(snapshot_close)
    
    assert len(trades_changed) == 1, "Should close 1 trade (no new trade)"
    assert trades_changed[0]['is_open'] is False
    assert trades_changed[0]['exit_reason'] == 'spread_reversal'
    assert len(engine._open_trades) == 0, "Engine should have 0 open trades"


def test_d206_1_total_cost_bps():
    """AC-3: 수수료 + 슬리피지가 total_cost_bps로 정확히 계산되는지 검증"""
    config = EngineConfig(
        taker_fee_a_bps=10.0,
        taker_fee_b_bps=15.0,
        slippage_bps=8.0,
        max_open_trades=1,
        exchange_a_to_b_rate=1.0,
    )
    engine = ArbitrageEngine(config)
    
    expected_cost = 10.0 + 15.0 + 8.0  # 33 bps
    assert engine._total_cost_bps == pytest.approx(expected_cost, abs=0.01)
    
    # Snapshot: 50 bps spread → net_edge = 50 - 33 = 17 bps
    snapshot = {
        'best_bid_a': 99.5,
        'best_ask_a': 100.0,
        'best_bid_b': 100.5,
        'best_ask_b': 101.0,
        'timestamp': '2026-01-16T00:00:00Z',
    }
    
    opp = engine._detect_single_opportunity(snapshot)
    assert opp is not None
    assert opp['net_edge_bps'] == pytest.approx(17.0, abs=1.0), "Net edge = 50 - 33"

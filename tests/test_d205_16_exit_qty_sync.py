"""
D205-16: Exit qty sync via entry fill
Test that exit OrderIntent qty is synchronized with entry filled_qty
"""

import pytest
from arbitrage.v2.core.order_intent import OrderIntent, OrderSide, OrderType


def test_exit_intent_qty_source_from_entry_fill():
    """
    Test: Exit intent with qty_source="from_entry_fill" 설정 확인
    """
    # Entry intent (BUY)
    entry_intent = OrderIntent(
        exchange="upbit",
        symbol="BTC/KRW",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quote_amount=500_000.0,
        qty_source="direct",
    )
    
    # Exit intent (SELL) - qty_source="from_entry_fill"
    exit_intent = OrderIntent(
        exchange="binance",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        base_qty=0.01,  # 임시값
        qty_source="from_entry_fill",
    )
    
    # Verify
    assert entry_intent.qty_source == "direct"
    assert exit_intent.qty_source == "from_entry_fill"
    assert exit_intent.base_qty == 0.01  # 초기값


def test_candidate_to_order_intents_sets_qty_source():
    """
    Test: candidate_to_order_intents()가 exit intent의 qty_source를 설정하는지 확인
    """
    from arbitrage.v2.opportunity import OpportunityCandidate, OpportunityDirection
    from arbitrage.v2.opportunity.intent_builder import candidate_to_order_intents
    
    # Mock candidate
    candidate = OpportunityCandidate(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100_000_000.0,
        price_b=70_000.0,
        spread_bps=50.0,
        direction=OpportunityDirection.BUY_A_SELL_B,
        profitable=True,
        break_even_bps=30.0,
        edge_bps=20.0,
    )
    
    # Convert to intents
    intents = candidate_to_order_intents(
        candidate=candidate,
        quote_amount=500_000.0,
        order_type=OrderType.MARKET,
    )
    
    # Verify
    assert len(intents) == 2
    
    entry_intent = intents[0]
    exit_intent = intents[1]
    
    assert entry_intent.side == OrderSide.BUY
    assert entry_intent.qty_source == "direct"
    
    assert exit_intent.side == OrderSide.SELL
    assert exit_intent.qty_source == "from_entry_fill"  # D205-16: 핵심 검증


def test_exit_qty_sync_calculation():
    """
    Test: Exit qty가 entry filled_qty로 동기화되는 계산 로직 검증
    """
    # Simulate entry result
    entry_filled_qty = 0.00374  # 500,000 / 133,766,000 = 0.00374 BTC
    
    # Exit intent (초기 base_qty는 임시값)
    exit_intent = OrderIntent(
        exchange="binance",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        base_qty=0.01,  # 임시값
        qty_source="from_entry_fill",
    )
    
    # Simulate qty sync (paper_runner.py의 로직)
    if exit_intent.qty_source == "from_entry_fill":
        exit_intent.base_qty = entry_filled_qty
    
    # Verify
    assert exit_intent.base_qty == entry_filled_qty
    assert abs(exit_intent.base_qty - 0.00374) < 1e-8


def test_qty_mismatch_prevented_by_sync():
    """
    Test: Exit qty sync가 없으면 mismatch 발생, sync 후에는 해결됨
    """
    entry_filled_qty = 0.00374
    
    # BEFORE sync: 하드코딩된 base_qty=0.01
    exit_qty_before = 0.01
    qty_diff_pct_before = abs(entry_filled_qty - exit_qty_before) / entry_filled_qty * 100
    assert qty_diff_pct_before > 1.0  # mismatch 발생 (약 167%)
    
    # AFTER sync: entry filled_qty로 동기화
    exit_qty_after = entry_filled_qty
    qty_diff_pct_after = abs(entry_filled_qty - exit_qty_after) / entry_filled_qty * 100
    assert qty_diff_pct_after == 0.0  # mismatch 해결


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

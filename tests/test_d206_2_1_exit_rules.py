"""
D206-2-1: Exit Rules (TP/SL) Tests

V2 native Exit Rules 검증 (V1에 없는 기능).
"""

import pytest
from decimal import Decimal

from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.v2.core.engine import ArbitrageEngine as V2Engine, EngineConfig as V2Config


class TestTakeProfitExitRule:
    """Take Profit Exit Rule 테스트"""
    
    def test_take_profit_trigger(self):
        """TP 도달 시 종료"""
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            take_profit_bps=50.0,  # 50 bps 목표 수익
            close_on_spread_reversal=False,  # TP만 테스트
        )
        v2_engine = V2Engine(v2_config)
        
        # Open trade (entry_spread = 891.09 bps, cost = 25 bps, net_edge = 866.09 bps)
        snapshot_open = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=110.0,
            best_ask_b=111.0,
        )
        
        trades_open = v2_engine._process_snapshot(snapshot_open)
        assert len(trades_open) == 1
        assert trades_open[0].is_open
        
        # TP 도달 (unrealized_pnl = entry_spread - current_spread - cost >= TP)
        # entry_spread = 891.09, cost = 25
        # TP = 50이려면 current_spread <= 891.09 - 25 - 50 = 816.09
        # current_spread = (bid_b - ask_a) / ask_a * 10000 = (108 - 101) / 101 * 10000 = 693.07
        # unrealized_pnl = 891.09 - 693.07 - 25 = 173.02 >= 50 (TP trigger)
        snapshot_tp = OrderBookSnapshot(
            timestamp="2026-01-16T22:01:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=108.0,  # bid_b lowered to trigger TP
            best_ask_b=109.0,
        )
        
        trades_tp = v2_engine._process_snapshot(snapshot_tp)
        assert len(trades_tp) == 1
        assert not trades_tp[0].is_open
        assert trades_tp[0].exit_reason == "take_profit"
        assert trades_tp[0].pnl_bps > 50.0  # TP 기준 이상


class TestStopLossExitRule:
    """Stop Loss Exit Rule 테스트"""
    
    def test_stop_loss_trigger(self):
        """SL 도달 시 종료"""
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            stop_loss_bps=50.0,  # 50 bps 손절 한계
            close_on_spread_reversal=False,  # SL만 테스트
        )
        v2_engine = V2Engine(v2_config)
        
        # Open trade
        snapshot_open = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=110.0,
            best_ask_b=111.0,
        )
        
        trades_open = v2_engine._process_snapshot(snapshot_open)
        assert len(trades_open) == 1
        
        # SL 도달 (unrealized_pnl <= -SL)
        # entry_spread = 891.09, cost = 25
        # SL = -50이려면 current_spread >= 891.09 + 25 + 50 = 966.09
        # current_spread = (bid_b - ask_a) / ask_a * 10000 = (111 - 101) / 101 * 10000 = 990.10
        # unrealized_pnl = 891.09 - 990.10 - 25 = -124.01 <= -50 (SL trigger)
        snapshot_sl = OrderBookSnapshot(
            timestamp="2026-01-16T22:01:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=111.0,  # bid_b increased (spread widened, loss)
            best_ask_b=112.0,
        )
        
        trades_sl = v2_engine._process_snapshot(snapshot_sl)
        assert len(trades_sl) == 1
        assert not trades_sl[0].is_open
        assert trades_sl[0].exit_reason == "stop_loss"
        assert trades_sl[0].pnl_bps < -50.0  # SL 기준 이하


class TestExitRulePriority:
    """Exit Rule 우선순위 테스트"""
    
    def test_tp_priority_over_spread_reversal(self):
        """TP가 spread_reversal보다 먼저 체크됨"""
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            take_profit_bps=50.0,
            close_on_spread_reversal=True,
        )
        v2_engine = V2Engine(v2_config)
        
        # Open
        snapshot_open = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=110.0,
            best_ask_b=111.0,
        )
        v2_engine._process_snapshot(snapshot_open)
        
        # TP 도달 + spread < 0 (동시 조건)
        # TP가 먼저 체크되므로 exit_reason = "take_profit"
        snapshot_exit = OrderBookSnapshot(
            timestamp="2026-01-16T22:01:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=108.0,  # TP trigger
            best_ask_b=109.0,
        )
        
        trades_exit = v2_engine._process_snapshot(snapshot_exit)
        assert len(trades_exit) == 1
        assert trades_exit[0].exit_reason == "take_profit"

"""
D206-2: V1 vs V2 Strategy Parity Tests

V1 ArbitrageEngine vs V2 ArbitrageEngine 결과 100% 일치 검증.
"""

import pytest
from decimal import Decimal

from arbitrage.arbitrage_core import (
    ArbitrageEngine as V1Engine,
    ArbitrageConfig as V1Config,
    OrderBookSnapshot,
)
from arbitrage.v2.core.engine import (
    ArbitrageEngine as V2Engine,
    EngineConfig as V2Config,
)
from arbitrage.domain.fee_model import create_fee_model_upbit_binance
from arbitrage.domain.market_spec import create_market_spec_upbit_binance


class TestV1V2DetectOpportunityParity:
    """detect_opportunity() V1 vs V2 parity"""
    
    def test_case_1_normal_opportunity(self):
        """Case 1: 정상 기회 발생 (spread > threshold, net edge > 0)"""
        # V1 Engine
        v1_config = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            exchange_a_to_b_rate=1.0,
        )
        v1_engine = V1Engine(v1_config)
        
        # V2 Engine
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1.0,
        )
        v2_engine = V2Engine(v2_config)
        
        # Snapshot (large spread for clear opportunity)
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=110.0,  # Large spread
            best_ask_b=111.0,
        )
        
        # Execute
        v1_opp = v1_engine.detect_opportunity(snapshot)
        v2_opp = v2_engine._detect_single_opportunity(snapshot)
        
        # Assert
        assert v1_opp is not None
        assert v2_opp is not None
        assert v1_opp.side == v2_opp.side
        assert abs(v1_opp.spread_bps - v2_opp.spread_bps) < 1e-8
        assert abs(v1_opp.gross_edge_bps - v2_opp.gross_edge_bps) < 1e-8
        assert abs(v1_opp.net_edge_bps - v2_opp.net_edge_bps) < 1e-8
        assert abs(v1_opp.notional_usd - v2_opp.notional_usd) < 1e-8
    
    def test_case_2_fee_kills_edge(self):
        """Case 2: Fee 반영으로 net edge 음수 (거래 불가)"""
        v1_config = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=50.0,  # High fee
            taker_fee_b_bps=50.0,
            slippage_bps=20.0,
            max_position_usd=1000.0,
            exchange_a_to_b_rate=1.0,
        )
        v1_engine = V1Engine(v1_config)
        
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=50.0,
            taker_fee_b_bps=50.0,
            slippage_bps=20.0,
            exchange_a_to_b_rate=1.0,
        )
        v2_engine = V2Engine(v2_config)
        
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=102.0,  # Small spread (120 bps < fee 120 bps)
            best_ask_b=103.0,
        )
        
        v1_opp = v1_engine.detect_opportunity(snapshot)
        v2_opp = v2_engine._detect_single_opportunity(snapshot)
        
        # Both should return None (net edge < 0)
        assert v1_opp is None
        assert v2_opp is None
    
    def test_case_3_fx_variation(self):
        """Case 3: FX 변화로 결과 달라짐"""
        # FX rate 1.0
        v1_config_fx1 = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            exchange_a_to_b_rate=1.0,
        )
        v1_engine_fx1 = V1Engine(v1_config_fx1)
        
        v2_config_fx1 = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1.0,
        )
        v2_engine_fx1 = V2Engine(v2_config_fx1)
        
        # FX rate 1.5
        v1_config_fx2 = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            exchange_a_to_b_rate=1.5,
        )
        v1_engine_fx2 = V1Engine(v1_config_fx2)
        
        v2_config_fx2 = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1.5,
        )
        v2_engine_fx2 = V2Engine(v2_config_fx2)
        
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=105.0,
            best_ask_b=106.0,
        )
        
        # FX 1.0
        v1_opp_fx1 = v1_engine_fx1.detect_opportunity(snapshot)
        v2_opp_fx1 = v2_engine_fx1._detect_single_opportunity(snapshot)
        
        # FX 1.5
        v1_opp_fx2 = v1_engine_fx2.detect_opportunity(snapshot)
        v2_opp_fx2 = v2_engine_fx2._detect_single_opportunity(snapshot)
        
        # V1/V2 FX 1.0 parity
        assert v1_opp_fx1 is not None
        assert v2_opp_fx1 is not None
        assert abs(v1_opp_fx1.net_edge_bps - v2_opp_fx1.net_edge_bps) < 1e-8
        
        # V1/V2 FX 1.5 parity
        assert v1_opp_fx2 is not None
        assert v2_opp_fx2 is not None
        assert abs(v1_opp_fx2.net_edge_bps - v2_opp_fx2.net_edge_bps) < 1e-8
        
        # FX 변화 확인 (1.5 > 1.0 spread)
        assert v1_opp_fx2.spread_bps != v1_opp_fx1.spread_bps
        assert v2_opp_fx2.spread_bps != v2_opp_fx1.spread_bps
    
    def test_case_4_max_open_trades(self):
        """Case 4: Max open trades 도달"""
        v1_config = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            max_open_trades=1,
        )
        v1_engine = V1Engine(v1_config)
        
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_open_trades=1,
        )
        v2_engine = V2Engine(v2_config)
        
        snapshot1 = OrderBookSnapshot(
            timestamp="2026-01-16T22:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=110.0,
            best_ask_b=111.0,
        )
        
        snapshot2 = OrderBookSnapshot(
            timestamp="2026-01-16T22:01:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=115.0,
            best_ask_b=116.0,
        )
        
        # First opportunity
        v1_opp1 = v1_engine.detect_opportunity(snapshot1)
        v2_opp1 = v2_engine._detect_single_opportunity(snapshot1)
        assert v1_opp1 is not None
        assert v2_opp1 is not None
        
        # Open trade
        v1_trades = v1_engine.on_snapshot(snapshot1)
        v2_trades = v2_engine._process_snapshot(snapshot1)
        assert len(v1_trades) == 1
        assert len(v2_trades) == 1
        
        # Second opportunity (max trades reached)
        v1_opp2 = v1_engine.detect_opportunity(snapshot2)
        v2_opp2 = v2_engine._detect_single_opportunity(snapshot2)
        
        # Both should return None
        assert v1_opp2 is None
        assert v2_opp2 is None


class TestV1V2OnSnapshotParity:
    """on_snapshot() V1 vs V2 parity"""
    
    def test_case_5_spread_reversal(self):
        """Case 5: spread_reversal 종료"""
        v1_config = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            close_on_spread_reversal=True,
        )
        v1_engine = V1Engine(v1_config)
        
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            close_on_spread_reversal=True,
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
        
        v1_trades_open = v1_engine.on_snapshot(snapshot_open)
        v2_trades_open = v2_engine._process_snapshot(snapshot_open)
        
        assert len(v1_trades_open) == 1
        assert len(v2_trades_open) == 1
        assert v1_trades_open[0].is_open
        assert v2_trades_open[0].is_open
        
        # Spread reversal
        snapshot_close = OrderBookSnapshot(
            timestamp="2026-01-16T22:01:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=90.0,  # Reversed
            best_ask_b=91.0,
        )
        
        v1_trades_close = v1_engine.on_snapshot(snapshot_close)
        v2_trades_close = v2_engine._process_snapshot(snapshot_close)
        
        # Both should close
        assert len(v1_trades_close) == 1
        assert len(v2_trades_close) == 1
        assert not v1_trades_close[0].is_open
        assert not v2_trades_close[0].is_open
        assert v1_trades_close[0].exit_reason == "spread_reversal"
        assert v2_trades_close[0].exit_reason == "spread_reversal"
    
    def test_case_6_pnl_precision(self):
        """Case 6: PnL 정밀도 검증 (소수점 8자리)"""
        v1_config = V1Config(
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            close_on_spread_reversal=True,
        )
        v1_engine = V1Engine(v1_config)
        
        v2_config = V2Config(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
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
        
        v1_engine.on_snapshot(snapshot_open)
        v2_engine._process_snapshot(snapshot_open)
        
        # Close
        snapshot_close = OrderBookSnapshot(
            timestamp="2026-01-16T22:01:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=90.0,
            best_ask_b=91.0,
        )
        
        v1_trades = v1_engine.on_snapshot(snapshot_close)
        v2_trades = v2_engine._process_snapshot(snapshot_close)
        
        v1_pnl_bps = v1_trades[0].pnl_bps
        v2_pnl_bps = v2_trades[0].pnl_bps
        
        v1_pnl_usd = v1_trades[0].pnl_usd
        v2_pnl_usd = v2_trades[0].pnl_usd
        
        # Precision: 소수점 8자리, 0.0001% 오차
        assert abs(v1_pnl_bps - v2_pnl_bps) < 1e-8
        assert abs(v1_pnl_usd - v2_pnl_usd) < 1e-8


class TestFeeModelIntegration:
    """FeeModel 통합 테스트"""
    
    def test_fee_model_integration(self):
        """FeeModel V1→V2 통합 검증"""
        fee_model = create_fee_model_upbit_binance()
        
        v2_config = V2Config(
            fee_model=fee_model,
            slippage_bps=5.0,
        )
        v2_engine = V2Engine(v2_config)
        
        # total_cost_bps = fee_model.total_entry_fee_bps() + slippage
        expected_cost = 5.0 + 10.0 + 5.0  # UPBIT 5 + BINANCE 10 + slippage 5
        assert abs(v2_engine._total_cost_bps - expected_cost) < 1e-8


class TestMarketSpecIntegration:
    """MarketSpec 통합 테스트"""
    
    def test_market_spec_integration(self):
        """MarketSpec V1→V2 통합 검증"""
        market_spec = create_market_spec_upbit_binance(krw_usd_rate=1370.0)
        
        v2_config = V2Config(
            market_spec=market_spec,
        )
        v2_engine = V2Engine(v2_config)
        
        # fx_rate = 1370
        assert abs(v2_engine._exchange_a_to_b_rate - 1370.0) < 1e-8

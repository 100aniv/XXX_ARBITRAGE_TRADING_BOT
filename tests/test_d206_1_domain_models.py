"""
D206-1: Domain Model Integration Tests

V1 domain models (OrderBookSnapshot, ArbitrageOpportunity, ArbitrageTrade)
V2 통합 검증.
"""

import pytest
from datetime import datetime

from arbitrage.v2.domain import (
    OrderBookSnapshot,
    ArbitrageOpportunity,
    ArbitrageTrade,
    Side,
)


class TestOrderBookSnapshot:
    """OrderBookSnapshot dataclass 테스트"""
    
    def test_valid_snapshot(self):
        """정상 스냅샷 생성"""
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T21:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=200.0,
            best_ask_b=202.0,
        )
        
        assert snapshot.timestamp == "2026-01-16T21:00:00Z"
        assert snapshot.best_bid_a == 100.0
        assert snapshot.best_ask_a == 101.0
    
    def test_invalid_crossed_market_a(self):
        """Exchange A crossed market 검증"""
        with pytest.raises(ValueError, match="crossed market"):
            OrderBookSnapshot(
                timestamp="2026-01-16T21:00:00Z",
                best_bid_a=102.0,  # bid >= ask
                best_ask_a=101.0,
                best_bid_b=200.0,
                best_ask_b=202.0,
            )
    
    def test_invalid_negative_price(self):
        """음수 가격 검증"""
        with pytest.raises(ValueError, match="must be > 0"):
            OrderBookSnapshot(
                timestamp="2026-01-16T21:00:00Z",
                best_bid_a=-100.0,
                best_ask_a=101.0,
                best_bid_b=200.0,
                best_ask_b=202.0,
            )
    
    def test_roundtrip_serialization(self):
        """JSON roundtrip 직렬화"""
        original = OrderBookSnapshot(
            timestamp="2026-01-16T21:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=200.0,
            best_ask_b=202.0,
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
        )
        
        data = original.to_dict()
        restored = OrderBookSnapshot.from_dict(data)
        
        assert restored.timestamp == original.timestamp
        assert restored.best_bid_a == original.best_bid_a
        assert restored.symbol == original.symbol
    
    def test_ui_dict(self):
        """UI 직렬화"""
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T21:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=200.0,
            best_ask_b=202.0,
            exchange_a="upbit",
            exchange_b="binance",
        )
        
        ui = snapshot.to_ui_dict()
        assert 'exchanges' in ui
        assert ui['exchanges']['a']['name'] == 'upbit'
        assert ui['exchanges']['b']['bid'] == 200.0


class TestArbitrageOpportunity:
    """ArbitrageOpportunity dataclass 테스트"""
    
    def test_valid_opportunity(self):
        """정상 기회 생성"""
        opp = ArbitrageOpportunity(
            timestamp="2026-01-16T21:00:00Z",
            side="LONG_A_SHORT_B",
            spread_bps=50.0,
            gross_edge_bps=50.0,
            net_edge_bps=25.0,
            notional_usd=1000.0,
        )
        
        assert opp.side == "LONG_A_SHORT_B"
        assert opp.net_edge_bps == 25.0
        assert opp.is_profitable()
    
    def test_invalid_edge_consistency(self):
        """net_edge > gross_edge 검증"""
        with pytest.raises(ValueError, match="cannot exceed"):
            ArbitrageOpportunity(
                timestamp="2026-01-16T21:00:00Z",
                side="LONG_A_SHORT_B",
                spread_bps=50.0,
                gross_edge_bps=20.0,
                net_edge_bps=25.0,  # net > gross (invalid)
                notional_usd=1000.0,
            )
    
    def test_invalid_notional(self):
        """notional_usd <= 0 검증"""
        with pytest.raises(ValueError, match="must be > 0"):
            ArbitrageOpportunity(
                timestamp="2026-01-16T21:00:00Z",
                side="LONG_A_SHORT_B",
                spread_bps=50.0,
                gross_edge_bps=50.0,
                net_edge_bps=25.0,
                notional_usd=0.0,  # invalid
            )
    
    def test_roundtrip_serialization(self):
        """JSON roundtrip 직렬화"""
        original = ArbitrageOpportunity(
            timestamp="2026-01-16T21:00:00Z",
            side="LONG_B_SHORT_A",
            spread_bps=50.0,
            gross_edge_bps=50.0,
            net_edge_bps=25.0,
            notional_usd=1000.0,
            symbol="BTC/KRW",
        )
        
        data = original.to_dict()
        restored = ArbitrageOpportunity.from_dict(data)
        
        assert restored.side == original.side
        assert restored.net_edge_bps == original.net_edge_bps
    
    def test_ui_dict(self):
        """UI 직렬화"""
        opp = ArbitrageOpportunity(
            timestamp="2026-01-16T21:00:00Z",
            side="LONG_A_SHORT_B",
            spread_bps=50.0,
            gross_edge_bps=50.0,
            net_edge_bps=25.0,
            notional_usd=1000.0,
            exchange_a="upbit",
            exchange_b="binance",
        )
        
        ui = opp.to_ui_dict()
        assert ui['direction'] == 'A→B'
        assert ui['spread']['net_edge_bps'] == 25.0


class TestArbitrageTrade:
    """ArbitrageTrade dataclass 테스트"""
    
    def test_valid_open_trade(self):
        """정상 open trade 생성"""
        trade = ArbitrageTrade(
            open_timestamp="2026-01-16T21:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
        )
        
        assert trade.is_open
        assert trade.pnl_usd is None
        assert not trade.is_profitable()
    
    def test_close_trade(self):
        """거래 종료 및 PnL 계산"""
        trade = ArbitrageTrade(
            open_timestamp="2026-01-16T21:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
        )
        
        trade.close(
            close_timestamp="2026-01-16T21:01:00Z",
            exit_spread_bps=10.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exit_reason="spread_reversal",
        )
        
        assert not trade.is_open
        assert trade.pnl_bps == 15.0  # 50 - 10 - 10 - 10 - 5
        assert trade.pnl_usd == 1.5  # 15 bps * 1000 / 10000
        assert trade.exit_reason == "spread_reversal"
        assert trade.is_profitable()
    
    def test_invalid_closed_trade_without_timestamp(self):
        """close_timestamp 없는 closed trade 검증"""
        with pytest.raises(ValueError, match="must have close_timestamp"):
            ArbitrageTrade(
                open_timestamp="2026-01-16T21:00:00Z",
                side="LONG_A_SHORT_B",
                entry_spread_bps=50.0,
                notional_usd=1000.0,
                is_open=False,  # closed but no close_timestamp
            )
    
    def test_roundtrip_serialization(self):
        """JSON roundtrip 직렬화"""
        original = ArbitrageTrade(
            open_timestamp="2026-01-16T21:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            symbol="BTC/KRW",
        )
        original.close(
            close_timestamp="2026-01-16T21:01:00Z",
            exit_spread_bps=10.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        )
        
        data = original.to_dict()
        restored = ArbitrageTrade.from_dict(data)
        
        assert restored.pnl_bps == original.pnl_bps
        assert not restored.is_open
    
    def test_ui_dict(self):
        """UI 직렬화"""
        trade = ArbitrageTrade(
            open_timestamp="2026-01-16T21:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
        )
        trade.close(
            close_timestamp="2026-01-16T21:01:00Z",
            exit_spread_bps=10.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        )
        
        ui = trade.to_ui_dict()
        assert ui['status'] == 'closed'
        assert ui['pnl']['color'] == 'green'
        assert ui['direction'] == 'A→B'


class TestEngineIntegration:
    """Engine Domain Model 통합 테스트"""
    
    def test_engine_detect_opportunity_with_dataclass(self):
        """Engine이 OrderBookSnapshot을 받아 ArbitrageOpportunity 반환"""
        from arbitrage.v2.core.engine import ArbitrageEngine, EngineConfig
        
        config = EngineConfig(
            min_spread_bps=10.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        )
        engine = ArbitrageEngine(config)
        
        # OrderBookSnapshot 생성
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T21:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=104.0,
            best_ask_b=105.0,
        )
        
        # Opportunity 탐지
        opp = engine._detect_single_opportunity(snapshot)
        
        assert opp is not None
        assert isinstance(opp, ArbitrageOpportunity)
        assert opp.notional_usd == 1000.0
    
    def test_engine_process_snapshot_with_dataclass(self):
        """Engine이 OrderBookSnapshot으로 ArbitrageTrade 생성"""
        from arbitrage.v2.core.engine import ArbitrageEngine, EngineConfig
        
        config = EngineConfig(
            min_spread_bps=10.0,
            max_position_usd=1000.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        )
        engine = ArbitrageEngine(config)
        
        # OrderBookSnapshot 생성
        snapshot = OrderBookSnapshot(
            timestamp="2026-01-16T21:00:00Z",
            best_bid_a=100.0,
            best_ask_a=101.0,
            best_bid_b=130.0,
            best_ask_b=131.0,
        )
        
        # Snapshot 처리
        trades = engine._process_snapshot(snapshot)
        
        assert len(trades) == 1
        assert isinstance(trades[0], ArbitrageTrade)
        assert trades[0].is_open

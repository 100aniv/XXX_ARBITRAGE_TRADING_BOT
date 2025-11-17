"""
D45: ArbitrageEngine 스프레드 계산 개선 테스트

환율 정규화 및 bid/ask 스프레드 확장 검증
"""

import pytest
from arbitrage.arbitrage_core import (
    ArbitrageConfig,
    ArbitrageEngine,
    OrderBookSnapshot,
)


class TestD45SpreadCalculation:
    """D45 스프레드 계산 개선 테스트"""

    def test_exchange_rate_normalization(self):
        """환율 정규화 검증"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,  # 1 BTC = 2.5 * 40000 USDT
        )
        engine = ArbitrageEngine(config)

        # 호가 설정 (bid < ask 조건 만족)
        # A: bid=99500, ask=100500 (KRW)
        # B: bid=40300, ask=40400 (USDT)
        # 정규화: bid_b_normalized = 40300 * 2.5 = 100750
        # spread = (100750 - 100500) / 100500 * 10000 = 25 bps
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99500.0,
            best_ask_a=100500.0,
            best_bid_b=40300.0,
            best_ask_b=40400.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        
        assert opportunity is not None, "거래 신호가 생성되어야 함"
        assert opportunity.side == "LONG_A_SHORT_B"
        # spread = (100750 - 100500) / 100500 * 10000 = 25 bps
        assert 20 < opportunity.spread_bps < 30, f"스프레드가 약 25 bps여야 함, 실제: {opportunity.spread_bps}"

    def test_bid_ask_spread_expansion(self):
        """bid/ask 스프레드 확장 검증"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,  # 1% 스프레드
        )
        engine = ArbitrageEngine(config)

        # 현실적인 호가 (bid < ask)
        # A: bid=99500, ask=100500
        # B: bid=40300, ask=40400
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99500.0,
            best_ask_a=100500.0,
            best_bid_b=40300.0,
            best_ask_b=40400.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        
        assert opportunity is not None
        assert opportunity.side == "LONG_A_SHORT_B"

    def test_spread_calculation_both_directions(self):
        """양방향 스프레드 계산 검증"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
        )
        engine = ArbitrageEngine(config)

        # LONG_B_SHORT_A 신호 생성 시나리오
        # A: bid=102000, ask=103000
        # B: bid=39000, ask=39100
        # bid_b_normalized = 39000 * 2.5 = 97500
        # spread_b_to_a = (102000 - 97500) / 97500 * 10000 = 462 bps
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=102000.0,
            best_ask_a=103000.0,
            best_bid_b=39000.0,
            best_ask_b=39100.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        
        assert opportunity is not None
        assert opportunity.side == "LONG_B_SHORT_A"

    def test_no_signal_when_spread_negative(self):
        """스프레드가 음수일 때 신호 미생성"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
        )
        engine = ArbitrageEngine(config)

        # 음수 스프레드
        # A: bid=100000, ask=101000
        # B: bid=39000, ask=39000
        # bid_b_normalized = 39000 * 2.5 = 97500
        # spread_a_to_b = (97500 - 101000) / 101000 * 10000 = -347 bps (음수!)
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100000.0,
            best_ask_a=101000.0,
            best_bid_b=39000.0,
            best_ask_b=39000.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        
        assert opportunity is None, "음수 스프레드에서는 신호가 생성되지 않아야 함"

    def test_spread_calculation_with_fees(self):
        """수수료 포함 스프레드 계산"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
        )
        engine = ArbitrageEngine(config)

        # 스프레드 = 25 bps
        # 총 비용 = 5 + 4 + 5 = 14 bps
        # net_edge = 25 - 14 = 11 bps < 20 bps (min_spread_bps) → 신호 미생성
        # 더 큰 스프레드를 위해 호가 조정
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99000.0,
            best_ask_a=100500.0,
            best_bid_b=40500.0,
            best_ask_b=40600.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        
        assert opportunity is not None
        assert opportunity.net_edge_bps > 0, "순 엣지가 양수여야 함"

    def test_spread_reversal_close_trade(self):
        """스프레드 역전 시 거래 종료"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
            close_on_spread_reversal=True,
        )
        engine = ArbitrageEngine(config)

        # 첫 번째 스냅샷: 양수 스프레드 (거래 개설)
        snapshot1 = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99500.0,
            best_ask_a=100500.0,
            best_bid_b=40300.0,
            best_ask_b=40400.0,
        )

        trades1 = engine.on_snapshot(snapshot1)
        assert len(trades1) == 1, "거래가 개설되어야 함"
        assert trades1[0].is_open

        # 두 번째 스냅샷: 음수 스프레드 (거래 종료)
        # A: bid=101000, ask=102000
        # B: bid=40000, ask=40100
        # bid_b_normalized = 40000 * 2.5 = 100000
        # spread = (100000 - 102000) / 102000 * 10000 = -196 bps (음수!)
        snapshot2 = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:01Z",
            best_bid_a=101000.0,
            best_ask_a=102000.0,
            best_bid_b=40000.0,
            best_ask_b=40100.0,
        )

        trades2 = engine.on_snapshot(snapshot2)
        # trades2에는 종료된 거래 1개 + 새로 개설된 거래 1개 = 2개
        # 첫 번째 거래는 종료되고, 두 번째 거래는 새로 개설됨
        assert len(trades2) >= 1, "거래가 변경되어야 함"
        closed_trades = [t for t in trades2 if not t.is_open]
        assert len(closed_trades) >= 1, "종료된 거래가 있어야 함"

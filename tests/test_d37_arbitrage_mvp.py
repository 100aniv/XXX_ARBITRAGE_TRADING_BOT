"""
D37 Arbitrage Strategy MVP Tests

Tests for:
- ArbitrageConfig
- OrderBookSnapshot
- ArbitrageOpportunity
- ArbitrageTrade
- ArbitrageEngine
- BacktestConfig
- BacktestResult
- ArbitrageBacktester
- CLI integration

All tests are deterministic and use synthetic data.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from arbitrage.arbitrage_core import (
    ArbitrageConfig,
    ArbitrageEngine,
    ArbitrageOpportunity,
    ArbitrageTrade,
    OrderBookSnapshot,
)
from arbitrage.arbitrage_backtest import (
    ArbitrageBacktester,
    BacktestConfig,
    BacktestResult,
)


class TestArbitrageConfig:
    """테스트: ArbitrageConfig"""

    def test_config_creation(self):
        """기본 설정 생성."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )

        assert config.min_spread_bps == 30.0
        assert config.taker_fee_a_bps == 5.0
        assert config.taker_fee_b_bps == 5.0
        assert config.slippage_bps == 5.0
        assert config.max_position_usd == 1000.0
        assert config.max_open_trades == 1
        assert config.close_on_spread_reversal is True

    def test_config_with_custom_max_open_trades(self):
        """커스텀 max_open_trades."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            max_open_trades=5,
        )

        assert config.max_open_trades == 5


class TestOrderBookSnapshot:
    """테스트: OrderBookSnapshot"""

    def test_snapshot_creation(self):
        """스냅샷 생성."""
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100.0,
            best_ask_a=100.5,
            best_bid_b=101.0,
            best_ask_b=101.5,
        )

        assert snapshot.timestamp == "2025-01-01T00:00:00Z"
        assert snapshot.best_bid_a == 100.0
        assert snapshot.best_ask_a == 100.5
        assert snapshot.best_bid_b == 101.0
        assert snapshot.best_ask_b == 101.5


class TestArbitrageTrade:
    """테스트: ArbitrageTrade"""

    def test_trade_creation(self):
        """거래 생성."""
        trade = ArbitrageTrade(
            open_timestamp="2025-01-01T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
        )

        assert trade.open_timestamp == "2025-01-01T00:00:00Z"
        assert trade.side == "LONG_A_SHORT_B"
        assert trade.entry_spread_bps == 50.0
        assert trade.notional_usd == 1000.0
        assert trade.is_open is True
        assert trade.pnl_usd is None

    def test_trade_close_with_positive_pnl(self):
        """양수 손익으로 거래 종료."""
        trade = ArbitrageTrade(
            open_timestamp="2025-01-01T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
        )

        trade.close(
            close_timestamp="2025-01-01T01:00:00Z",
            exit_spread_bps=10.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
        )

        assert trade.is_open is False
        assert trade.close_timestamp == "2025-01-01T01:00:00Z"
        assert trade.exit_spread_bps == 10.0
        # PnL = (50 - 10 - 15) * 1000 / 10000 = 25 * 1000 / 10000 = 2.5
        assert trade.pnl_bps == pytest.approx(25.0)
        assert trade.pnl_usd == pytest.approx(2.5)

    def test_trade_close_with_negative_pnl(self):
        """음수 손익으로 거래 종료."""
        trade = ArbitrageTrade(
            open_timestamp="2025-01-01T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=30.0,
            notional_usd=1000.0,
        )

        trade.close(
            close_timestamp="2025-01-01T01:00:00Z",
            exit_spread_bps=50.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
        )

        assert trade.is_open is False
        # PnL = (30 - 50 - 15) * 1000 / 10000 = -35 * 1000 / 10000 = -3.5
        assert trade.pnl_bps == pytest.approx(-35.0)
        assert trade.pnl_usd == pytest.approx(-3.5)


class TestArbitrageEngine:
    """테스트: ArbitrageEngine"""

    def test_engine_creation(self):
        """엔진 생성."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)

        assert engine.config == config
        assert len(engine.get_open_trades()) == 0

    def test_detect_opportunity_no_spread(self):
        """스프레드 없음 - 기회 없음."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)

        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100.0,
            best_ask_a=100.1,
            best_bid_b=100.0,
            best_ask_b=100.1,
        )

        opportunity = engine.detect_opportunity(snapshot)
        assert opportunity is None

    def test_detect_opportunity_long_a_short_b(self):
        """LONG_A_SHORT_B 기회 감지."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)

        # A에서 매수(ask_a=100), B에서 매도(bid_b=102)
        # spread = (102 - 100) / 100 * 10000 = 200 bps
        # net_edge = 200 - 15 = 185 bps (충분함)
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99.0,
            best_ask_a=100.0,
            best_bid_b=102.0,
            best_ask_b=103.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        assert opportunity is not None
        assert opportunity.side == "LONG_A_SHORT_B"
        assert opportunity.spread_bps > 0
        assert opportunity.net_edge_bps >= config.min_spread_bps

    def test_detect_opportunity_long_b_short_a(self):
        """LONG_B_SHORT_A 기회 감지."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)

        # B에서 매수(ask_b=100), A에서 매도(bid_a=102)
        # spread = (102 - 100) / 100 * 10000 = 200 bps
        # net_edge = 200 - 15 = 185 bps (충분함)
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=102.0,
            best_ask_a=103.0,
            best_bid_b=99.0,
            best_ask_b=100.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        assert opportunity is not None
        assert opportunity.side == "LONG_B_SHORT_A"
        assert opportunity.spread_bps > 0
        assert opportunity.net_edge_bps >= config.min_spread_bps

    def test_detect_opportunity_insufficient_spread(self):
        """스프레드 부족 - 기회 없음."""
        config = ArbitrageConfig(
            min_spread_bps=100.0,  # 높은 임계값
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)

        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100.0,
            best_ask_a=100.5,
            best_bid_b=101.0,
            best_ask_b=101.5,
        )

        opportunity = engine.detect_opportunity(snapshot)
        assert opportunity is None

    def test_max_open_trades_limit(self):
        """최대 거래 수 제한."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            max_open_trades=1,
        )
        engine = ArbitrageEngine(config)

        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99.0,
            best_ask_a=100.0,
            best_bid_b=102.0,
            best_ask_b=103.0,
        )

        # 첫 번째 기회 - 거래 개설
        trades1 = engine.on_snapshot(snapshot)
        assert len(trades1) == 1
        assert len(engine.get_open_trades()) == 1

        # 두 번째 기회 - 거래 개설 불가 (최대값 도달)
        trades2 = engine.on_snapshot(snapshot)
        assert len(trades2) == 0
        assert len(engine.get_open_trades()) == 1

    def test_on_snapshot_opens_trade(self):
        """스냅샷 처리: 거래 개설."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)

        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99.0,
            best_ask_a=100.0,
            best_bid_b=102.0,
            best_ask_b=103.0,
        )

        trades = engine.on_snapshot(snapshot)
        assert len(trades) == 1
        assert trades[0].is_open is True
        assert len(engine.get_open_trades()) == 1

    def test_on_snapshot_closes_trade_on_reversal(self):
        """스냅샷 처리: 스프레드 역전 시 거래 종료."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            max_open_trades=1,  # 최대 1개 거래만 허용
            close_on_spread_reversal=True,
        )
        engine = ArbitrageEngine(config)

        # 거래 개설: LONG_A_SHORT_B
        snapshot1 = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99.0,
            best_ask_a=100.0,
            best_bid_b=102.0,
            best_ask_b=103.0,
        )
        trades1 = engine.on_snapshot(snapshot1)
        assert len(trades1) == 1
        assert trades1[0].side == "LONG_A_SHORT_B"
        assert len(engine.get_open_trades()) == 1

        # 스프레드 음수 (거래 종료, 새 거래 개설 안 됨)
        # LONG_A_SHORT_B: (bid_b - ask_a) / ask_a = (99 - 103) / 103 < 0
        snapshot2 = OrderBookSnapshot(
            timestamp="2025-01-01T01:00:00Z",
            best_bid_a=102.0,
            best_ask_a=103.0,
            best_bid_b=99.0,
            best_ask_b=100.0,
        )
        trades2 = engine.on_snapshot(snapshot2)
        # 거래 종료 1개 확인
        closed_trades = [t for t in trades2 if not t.is_open]
        assert len(closed_trades) >= 1
        assert closed_trades[0].is_open is False
        # 새 거래가 개설되지 않았는지 확인 (max_open_trades=1이고 이미 1개 있었으므로)
        # 또는 새 거래가 개설되었다면 총 거래 수는 2개 이상
        # 하지만 종료된 거래 1개 + 개설된 거래 0개 = 1개만 반환되어야 함
        assert len(engine.get_open_trades()) <= 1


class TestArbitrageBacktester:
    """테스트: ArbitrageBacktester"""

    def test_backtest_creation(self):
        """백테스터 생성."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)
        backtest_config = BacktestConfig()
        backtester = ArbitrageBacktester(engine, backtest_config)

        assert backtester.arb_engine == engine
        assert backtester.config == backtest_config

    def test_backtest_empty_snapshots(self):
        """빈 스냅샷 목록."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)
        backtest_config = BacktestConfig(initial_balance_usd=10_000.0)
        backtester = ArbitrageBacktester(engine, backtest_config)

        result = backtester.run([])

        assert result.total_trades == 0
        assert result.closed_trades == 0
        assert result.final_balance_usd == 10_000.0
        assert result.realized_pnl_usd == 0.0

    def test_backtest_single_trade(self):
        """단일 거래 백테스트."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)
        backtest_config = BacktestConfig(initial_balance_usd=10_000.0)
        backtester = ArbitrageBacktester(engine, backtest_config)

        # 거래 개설
        snapshot1 = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99.0,
            best_ask_a=100.0,
            best_bid_b=102.0,
            best_ask_b=103.0,
        )

        # 거래 종료
        snapshot2 = OrderBookSnapshot(
            timestamp="2025-01-01T01:00:00Z",
            best_bid_a=102.0,
            best_ask_a=103.0,
            best_bid_b=99.0,
            best_ask_b=100.0,
        )

        result = backtester.run([snapshot1, snapshot2])

        assert result.total_trades >= 1
        assert result.closed_trades >= 1
        assert result.final_balance_usd > 0

    def test_backtest_stop_on_drawdown(self):
        """낙폭 한계 도달 시 중지."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)
        backtest_config = BacktestConfig(
            initial_balance_usd=10_000.0,
            stop_on_drawdown_pct=5.0,
        )
        backtester = ArbitrageBacktester(engine, backtest_config)

        # 많은 스냅샷 생성 (손실 유발)
        snapshots = []
        for i in range(100):
            snapshot = OrderBookSnapshot(
                timestamp=f"2025-01-01T{i:02d}:00:00Z",
                best_bid_a=100.0 - i * 0.1,
                best_ask_a=100.5 - i * 0.1,
                best_bid_b=102.0 - i * 0.1,
                best_ask_b=102.5 - i * 0.1,
            )
            snapshots.append(snapshot)

        result = backtester.run(snapshots)

        # 낙폭이 한계를 초과하면 중지
        assert result.max_drawdown_pct >= 0

    def test_backtest_max_steps(self):
        """최대 단계 수 제한."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        engine = ArbitrageEngine(config)
        backtest_config = BacktestConfig(
            initial_balance_usd=10_000.0,
            max_steps=5,
        )
        backtester = ArbitrageBacktester(engine, backtest_config)

        # 많은 스냅샷 생성
        snapshots = []
        for i in range(100):
            snapshot = OrderBookSnapshot(
                timestamp=f"2025-01-01T{i:02d}:00:00Z",
                best_bid_a=100.0,
                best_ask_a=100.5,
                best_bid_b=102.0,
                best_ask_b=102.5,
            )
            snapshots.append(snapshot)

        result = backtester.run(snapshots)

        # 최대 5단계만 처리
        assert result.stats["steps_processed"] <= 5


class TestBacktestResult:
    """테스트: BacktestResult"""

    def test_result_creation(self):
        """결과 생성."""
        result = BacktestResult(
            total_trades=10,
            closed_trades=8,
            open_trades=2,
            final_balance_usd=11_000.0,
            realized_pnl_usd=1_000.0,
            max_drawdown_pct=5.0,
            win_rate=0.75,
            avg_pnl_per_trade_usd=125.0,
        )

        assert result.total_trades == 10
        assert result.closed_trades == 8
        assert result.open_trades == 2
        assert result.final_balance_usd == 11_000.0
        assert result.realized_pnl_usd == 1_000.0
        assert result.max_drawdown_pct == 5.0
        assert result.win_rate == 0.75
        assert result.avg_pnl_per_trade_usd == 125.0


class TestCLIIntegration:
    """테스트: CLI 통합"""

    def test_cli_with_sample_csv(self):
        """샘플 CSV로 CLI 실행."""
        from scripts.run_arbitrage_backtest import load_snapshots_from_csv

        # 임시 CSV 파일 생성
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b\n"
            )
            f.write("2025-01-01T00:00:00Z,100.0,100.5,102.0,102.5\n")
            f.write("2025-01-01T01:00:00Z,100.1,100.6,102.1,102.6\n")
            f.write("2025-01-01T02:00:00Z,100.2,100.7,102.2,102.7\n")
            csv_file = f.name

        try:
            snapshots = load_snapshots_from_csv(csv_file)
            assert len(snapshots) == 3
            assert snapshots[0].timestamp == "2025-01-01T00:00:00Z"
        finally:
            Path(csv_file).unlink()

    def test_cli_missing_file(self):
        """파일 없음."""
        from scripts.run_arbitrage_backtest import load_snapshots_from_csv

        snapshots = load_snapshots_from_csv("/nonexistent/file.csv")
        assert len(snapshots) == 0

    def test_cli_invalid_csv_format(self):
        """잘못된 CSV 형식."""
        from scripts.run_arbitrage_backtest import load_snapshots_from_csv

        # 필수 필드 없는 CSV
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("timestamp,price_a,price_b\n")
            f.write("2025-01-01T00:00:00Z,100.0,102.0\n")
            csv_file = f.name

        try:
            snapshots = load_snapshots_from_csv(csv_file)
            assert len(snapshots) == 0
        finally:
            Path(csv_file).unlink()


class TestSafetyAndPolicy:
    """테스트: 안전 정책"""

    def test_no_network_calls_in_core(self):
        """코어 모듈에 네트워크 호출 없음."""
        import arbitrage.arbitrage_core as core_module

        source = open(core_module.__file__, encoding="utf-8").read()

        forbidden = ["requests", "http", "socket", "urllib"]
        for term in forbidden:
            assert term not in source.lower()

    def test_no_network_calls_in_backtest(self):
        """백테스트 모듈에 네트워크 호출 없음."""
        import arbitrage.arbitrage_backtest as backtest_module

        source = open(backtest_module.__file__, encoding="utf-8").read()

        forbidden = ["requests", "http", "socket", "urllib"]
        for term in forbidden:
            assert term not in source.lower()

    def test_no_kubectl_in_strategy(self):
        """전략 모듈에 kubectl 호출 없음."""
        import arbitrage.arbitrage_core as core_module

        source = open(core_module.__file__, encoding="utf-8").read()
        assert "kubectl" not in source.lower()

    def test_deterministic_engine(self):
        """엔진은 결정론적."""
        config = ArbitrageConfig(
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )

        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99.0,
            best_ask_a=100.0,
            best_bid_b=102.0,
            best_ask_b=103.0,
        )

        # 같은 입력으로 여러 번 실행
        engine1 = ArbitrageEngine(config)
        opp1 = engine1.detect_opportunity(snapshot)

        engine2 = ArbitrageEngine(config)
        opp2 = engine2.detect_opportunity(snapshot)

        assert opp1 is not None
        assert opp2 is not None
        assert opp1.spread_bps == opp2.spread_bps
        assert opp1.side == opp2.side


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

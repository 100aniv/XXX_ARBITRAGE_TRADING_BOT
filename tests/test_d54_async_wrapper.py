# -*- coding: utf-8 -*-
"""
D54: Async & Concurrency Optimization - Async Wrapper Tests

Async wrapper 기능 검증.
"""

import asyncio
import pytest
import time
from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
)
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderBookSnapshot as ExchangeOrderBookSnapshot
from arbitrage.exchanges.market_data_provider import RestMarketDataProvider
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig
from arbitrage.monitoring.metrics_collector import MetricsCollector


class TestMarketDataProviderAsync:
    """MarketDataProvider async wrapper 테스트"""
    
    @pytest.mark.asyncio
    async def test_aget_latest_snapshot(self):
        """async snapshot 조회"""
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        provider.start()
        
        # Async snapshot 조회
        snapshot = await provider.aget_latest_snapshot("KRW-BTC")
        
        assert snapshot is not None
        assert snapshot.symbol == "KRW-BTC"
        assert snapshot.bids[0][0] == 100000.0
        
        provider.stop()
    
    @pytest.mark.asyncio
    async def test_aget_latest_snapshot_multiple_symbols(self):
        """여러 심볼 async 조회"""
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        provider.start()
        
        # 병렬 조회
        snapshots = await asyncio.gather(
            provider.aget_latest_snapshot("KRW-BTC"),
            provider.aget_latest_snapshot("BTCUSDT"),
        )
        
        assert len(snapshots) == 2
        assert snapshots[0] is not None
        assert snapshots[1] is not None
        
        provider.stop()


class TestMetricsCollectorAsync:
    """MetricsCollector async wrapper 테스트"""
    
    @pytest.mark.asyncio
    async def test_aupdate_loop_metrics(self):
        """async metrics 업데이트"""
        collector = MetricsCollector()
        
        # Async 메트릭 업데이트
        await collector.aupdate_loop_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=50.0,
            data_source="rest",
            ws_connected=False,
            ws_reconnects=0,
        )
        
        metrics = collector.get_metrics()
        
        assert metrics["loop_time_ms"] == 1000.0
        assert metrics["trades_opened_total"] == 1
        assert metrics["spread_bps"] == 50.0
    
    @pytest.mark.asyncio
    async def test_aupdate_loop_metrics_multiple(self):
        """여러 async metrics 업데이트"""
        collector = MetricsCollector()
        
        # 병렬 메트릭 업데이트
        tasks = [
            collector.aupdate_loop_metrics(
                loop_time_ms=1000.0 + i * 10,
                trades_opened=1 if i % 2 == 0 else 0,
                spread_bps=50.0,
                data_source="rest",
            )
            for i in range(5)
        ]
        
        await asyncio.gather(*tasks)
        
        metrics = collector.get_metrics()
        
        assert metrics["trades_opened_total"] == 3


class TestLiveRunnerAsync:
    """LiveRunner async wrapper 테스트"""
    
    @pytest.mark.asyncio
    async def test_arun_once(self):
        """async run_once 실행"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # Async 루프 실행
        result = await runner.arun_once()
        
        assert result is True
        assert runner._loop_count == 1
    
    @pytest.mark.asyncio
    async def test_arun_forever_timeout(self):
        """async run_forever with timeout"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            poll_interval_seconds=0.1,
            max_runtime_seconds=1,
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # Async 루프 실행 (1초 타임아웃)
        await runner.arun_forever()
        
        # 약 10회 루프 실행 (1초 / 0.1초 interval)
        assert runner._loop_count >= 8


class TestAsyncBackwardCompatibility:
    """Async/Sync 호환성 테스트"""
    
    def test_sync_run_once_still_works(self):
        """sync run_once 여전히 작동"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # Sync 루프 실행
        result = runner.run_once()
        
        assert result is True
        assert runner._loop_count == 1
    
    def test_sync_metrics_collector_still_works(self):
        """sync metrics collector 여전히 작동"""
        collector = MetricsCollector()
        
        # Sync 메트릭 업데이트
        collector.update_loop_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=50.0,
            data_source="rest",
            ws_connected=False,
            ws_reconnects=0,
        )
        
        metrics = collector.get_metrics()
        
        assert metrics["loop_time_ms"] == 1000.0
        assert metrics["trades_opened_total"] == 1

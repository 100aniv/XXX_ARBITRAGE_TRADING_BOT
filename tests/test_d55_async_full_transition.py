# -*- coding: utf-8 -*-
"""
D55: Complete Async Transition - Full Async Tests

완전 비동기 실행 검증.
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


class TestMarketDataProviderAsyncStart:
    """MarketDataProvider async start/stop 테스트"""
    
    @pytest.mark.asyncio
    async def test_astart_astop(self):
        """async start/stop 메서드"""
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        
        # Async start
        await provider.astart()
        assert provider._is_running is True
        
        # Async stop
        await provider.astop()
        assert provider._is_running is False


class TestMetricsCollectorAsyncQueue:
    """MetricsCollector async queue 테스트"""
    
    @pytest.mark.asyncio
    async def test_astart_queue_processing(self):
        """async queue processing 시작"""
        collector = MetricsCollector()
        
        await collector.astart_queue_processing()
        
        assert collector._metrics_queue is not None
        assert collector._processing_task is not None
        
        await collector.astop_queue_processing()
    
    @pytest.mark.asyncio
    async def test_aqueue_metrics(self):
        """메트릭을 async queue에 추가"""
        collector = MetricsCollector()
        
        await collector.astart_queue_processing()
        
        # 메트릭 추가
        await collector.aqueue_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=50.0,
            data_source="rest",
        )
        
        # 큐 처리 대기
        await asyncio.sleep(0.1)
        
        metrics = collector.get_metrics()
        assert metrics["loop_time_ms"] == 1000.0
        assert metrics["trades_opened_total"] == 1
        
        await collector.astop_queue_processing()
    
    @pytest.mark.asyncio
    async def test_aqueue_metrics_multiple(self):
        """여러 메트릭을 async queue에 추가"""
        collector = MetricsCollector()
        
        await collector.astart_queue_processing()
        
        # 5개 메트릭 추가
        for i in range(5):
            await collector.aqueue_metrics(
                loop_time_ms=1000.0 + i * 10,
                trades_opened=1 if i % 2 == 0 else 0,
                spread_bps=50.0,
                data_source="rest",
            )
        
        # 큐 처리 대기
        await asyncio.sleep(0.2)
        
        metrics = collector.get_metrics()
        assert metrics["trades_opened_total"] == 3
        
        await collector.astop_queue_processing()


class TestLiveRunnerFullAsync:
    """LiveRunner 완전 async 실행 테스트"""
    
    @pytest.mark.asyncio
    async def test_arun_once_with_async_provider(self):
        """async provider와 함께 arun_once 실행"""
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
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        await provider.astart()
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
            market_data_provider=provider,
        )
        
        # Async 루프 실행
        result = await runner.arun_once()
        
        assert result is True
        assert runner._loop_count == 1
        
        await provider.astop()
    
    @pytest.mark.asyncio
    async def test_arun_forever_with_queue_metrics(self):
        """async queue metrics와 함께 arun_forever 실행"""
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
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        await provider.astart()
        
        collector = MetricsCollector()
        await collector.astart_queue_processing()
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
            market_data_provider=provider,
            metrics_collector=collector,
        )
        
        # Async 루프 실행 (1초 타임아웃)
        await runner.arun_forever()
        
        # 약 10회 루프 실행 (1초 / 0.1초 interval)
        assert runner._loop_count >= 8
        
        await provider.astop()
        await collector.astop_queue_processing()


class TestAsyncFullTransitionBackwardCompatibility:
    """D55 async 전환 후 sync 호환성 테스트"""
    
    def test_sync_provider_still_works(self):
        """sync provider 여전히 작동"""
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        
        # Sync start/stop
        provider.start()
        assert provider._is_running is True
        
        provider.stop()
        assert provider._is_running is False
    
    def test_sync_metrics_collector_still_works(self):
        """sync metrics collector 여전히 작동"""
        collector = MetricsCollector()
        
        # Sync 메트릭 업데이트
        collector.update_loop_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=50.0,
            data_source="rest",
        )
        
        metrics = collector.get_metrics()
        assert metrics["loop_time_ms"] == 1000.0
        assert metrics["trades_opened_total"] == 1
    
    @pytest.mark.skip(reason="D99-18 P17: Runner는 async로 전환됨. sync wrapper는 deprecated (실사용처 없음)")
    def test_sync_runner_still_works(self):
        """sync runner 여전히 작동 (DEPRECATED)"""
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

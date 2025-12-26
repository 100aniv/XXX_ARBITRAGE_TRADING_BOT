# -*- coding: utf-8 -*-
"""
D56: Multi-Symbol Engine Phase 1 - LiveRunner Tests

멀티심볼 LiveRunner 기능 검증.
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


class TestMultiSymbolRunOnce:
    """run_once_for_symbol 테스트"""
    
    def test_run_once_for_symbol_single(self):
        """단일 심볼 run_once_for_symbol 실행"""
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
        provider.start()
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
            market_data_provider=provider,
        )
        
        # 심볼별 실행
        result_a = runner.run_once_for_symbol("KRW-BTC")
        result_b = runner.run_once_for_symbol("BTCUSDT")
        
        assert result_a is True
        assert result_b is True
        assert runner._loop_count == 2
        
        provider.stop()
    
    def test_run_once_for_symbol_invalid(self):
        """잘못된 심볼 run_once_for_symbol"""
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
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        provider.start()
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
            market_data_provider=provider,
        )
        
        # 호가 없는 심볼
        result = runner.run_once_for_symbol("INVALID")
        
        assert result is False
        
        provider.stop()


class TestMultiSymbolAsyncRunOnce:
    """arun_once_for_symbol 테스트"""
    
    @pytest.mark.asyncio
    async def test_arun_once_for_symbol_single(self):
        """단일 심볼 arun_once_for_symbol 실행"""
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
        
        # 심볼별 async 실행
        result_a = await runner.arun_once_for_symbol("KRW-BTC")
        result_b = await runner.arun_once_for_symbol("BTCUSDT")
        
        assert result_a is True
        assert result_b is True
        assert runner._loop_count == 2
        
        await provider.astop()


class TestMultiSymbolParallelLoop:
    """arun_multisymbol_loop 테스트"""
    
    @pytest.mark.asyncio
    async def test_arun_multisymbol_loop_parallel(self):
        """병렬 멀티심볼 루프 실행"""
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
            max_runtime_seconds=0.5,
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
        
        # 병렬 멀티심볼 루프 (0.5초 타임아웃)
        symbols = ["KRW-BTC", "BTCUSDT"]
        await runner.arun_multisymbol_loop(symbols)
        
        # 약 5회 루프 (0.5초 / 0.1초 interval) × 2 심볼 = 10회
        assert runner._loop_count >= 8
        
        await provider.astop()


class TestMultiSymbolBackwardCompatibility:
    """D56 멀티심볼 추가 후 기존 기능 호환성"""
    
    @pytest.mark.skip(reason="D99-18 P17: Single symbol은 multi-symbol로 통합됨 (실사용처 없음)")
    def test_single_symbol_run_still_works(self):
        """기존 단일 심볼 run_once 여전히 작동"""
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
        
        # 기존 run_once 실행
        result = runner.run_once()
        
        assert result is True
        assert runner._loop_count == 1
    
    @pytest.mark.asyncio
    async def test_single_symbol_arun_still_works(self):
        """기존 단일 심볼 arun_once 여전히 작동"""
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
        
        # 기존 arun_once 실행
        result = await runner.arun_once()
        
        assert result is True
        assert runner._loop_count == 1

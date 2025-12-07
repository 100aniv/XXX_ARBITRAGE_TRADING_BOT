#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D83-3: Multi-exchange L2 Aggregation 유닛 테스트

테스트 시나리오:
1. 기본 Aggregation (양쪽 거래소 정상)
2. 한쪽 소스 Stale
3. 양쪽 소스 Stale
4. Empty Orderbook
5. Symbol Mapping
6. Best Bid/Ask 선택 로직
7. Aggregator Stats
"""

import time
import unittest
from typing import List, Tuple

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.multi_exchange_l2_provider import (
    ExchangeId,
    SourceStatus,
    MultiExchangeL2Snapshot,
    MultiExchangeL2Aggregator,
    MultiExchangeL2Provider,
)


class FakeSnapshot:
    """
    테스트용 Fake OrderBookSnapshot.
    """
    def __init__(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
    ):
        self.bids = bids
        self.asks = asks
        self.timestamp = time.time()
    
    def best_bid(self) -> float:
        """Best bid price"""
        return self.bids[0][0] if self.bids else None
    
    def best_ask(self) -> float:
        """Best ask price"""
        return self.asks[0][0] if self.asks else None


class TestMultiExchangeL2Aggregator(unittest.TestCase):
    """
    MultiExchangeL2Aggregator 유닛 테스트.
    """
    
    def test_basic_aggregation(self):
        """
        기본 Aggregation 테스트.
        
        Upbit: bid=100, ask=101
        Binance: bid=99, ask=100.5
        
        기대 결과:
        - best_bid=100 (Upbit)
        - best_ask=100.5 (Binance)
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷
        upbit_snapshot = FakeSnapshot(
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        aggregator.update(ExchangeId.UPBIT, upbit_snapshot)
        
        # Binance 스냅샷
        binance_snapshot = FakeSnapshot(
            bids=[(99.0, 1.0)],
            asks=[(100.5, 1.0)],
        )
        aggregator.update(ExchangeId.BINANCE, binance_snapshot)
        
        # Aggregation
        result = aggregator.build_aggregated_snapshot()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.best_bid, 100.0)
        self.assertEqual(result.best_ask, 100.5)
        self.assertEqual(result.best_bid_exchange, ExchangeId.UPBIT)
        self.assertEqual(result.best_ask_exchange, ExchangeId.BINANCE)
        self.assertEqual(result.source_status[ExchangeId.UPBIT], SourceStatus.ACTIVE)
        self.assertEqual(result.source_status[ExchangeId.BINANCE], SourceStatus.ACTIVE)
    
    def test_one_source_stale(self):
        """
        한쪽 소스 Stale 테스트.
        
        Upbit: 최신 (0.5초 전)
        Binance: Stale (3초 전, threshold=2초)
        
        기대 결과:
        - Upbit만 사용
        - best_bid/ask는 Upbit 기준
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷 (최신)
        upbit_snapshot = FakeSnapshot(
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        aggregator.update(ExchangeId.UPBIT, upbit_snapshot)
        
        # Binance 스냅샷 (Stale)
        binance_snapshot = FakeSnapshot(
            bids=[(99.0, 1.0)],
            asks=[(100.5, 1.0)],
        )
        # Timestamp를 3초 전으로 강제 설정
        aggregator._timestamps[ExchangeId.BINANCE] = time.time() - 3.0
        aggregator._snapshots[ExchangeId.BINANCE] = binance_snapshot
        
        # Aggregation
        result = aggregator.build_aggregated_snapshot()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.best_bid, 100.0)  # Upbit만 사용
        self.assertEqual(result.best_ask, 101.0)  # Upbit만 사용
        self.assertEqual(result.best_bid_exchange, ExchangeId.UPBIT)
        self.assertEqual(result.best_ask_exchange, ExchangeId.UPBIT)
        self.assertEqual(result.source_status[ExchangeId.UPBIT], SourceStatus.ACTIVE)
        self.assertEqual(result.source_status[ExchangeId.BINANCE], SourceStatus.STALE)
    
    def test_all_sources_stale(self):
        """
        양쪽 소스 Stale 테스트.
        
        Upbit: Stale (3초 전)
        Binance: Stale (4초 전)
        
        기대 결과:
        - None 반환
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷 (Stale)
        upbit_snapshot = FakeSnapshot(
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        aggregator._timestamps[ExchangeId.UPBIT] = time.time() - 3.0
        aggregator._snapshots[ExchangeId.UPBIT] = upbit_snapshot
        
        # Binance 스냅샷 (Stale)
        binance_snapshot = FakeSnapshot(
            bids=[(99.0, 1.0)],
            asks=[(100.5, 1.0)],
        )
        aggregator._timestamps[ExchangeId.BINANCE] = time.time() - 4.0
        aggregator._snapshots[ExchangeId.BINANCE] = binance_snapshot
        
        # Aggregation
        result = aggregator.build_aggregated_snapshot()
        
        self.assertIsNone(result)
    
    def test_empty_orderbook(self):
        """
        Empty Orderbook 테스트.
        
        Upbit: bids=[], asks=[]
        Binance: 정상
        
        기대 결과:
        - Binance만 사용
        - best_bid/ask는 Binance 기준
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷 (Empty)
        upbit_snapshot = FakeSnapshot(
            bids=[],
            asks=[],
        )
        aggregator.update(ExchangeId.UPBIT, upbit_snapshot)
        
        # Binance 스냅샷 (정상)
        binance_snapshot = FakeSnapshot(
            bids=[(99.0, 1.0)],
            asks=[(100.5, 1.0)],
        )
        aggregator.update(ExchangeId.BINANCE, binance_snapshot)
        
        # Aggregation
        result = aggregator.build_aggregated_snapshot()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.best_bid, 99.0)  # Binance만 사용
        self.assertEqual(result.best_ask, 100.5)  # Binance만 사용
        self.assertEqual(result.best_bid_exchange, ExchangeId.BINANCE)
        self.assertEqual(result.best_ask_exchange, ExchangeId.BINANCE)
    
    def test_best_bid_selection(self):
        """
        Best Bid 선택 로직 테스트.
        
        Upbit: bid=100.5
        Binance: bid=100.3
        
        기대 결과:
        - best_bid=100.5 (Upbit, 더 높은 값)
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷
        upbit_snapshot = FakeSnapshot(
            bids=[(100.5, 1.0)],
            asks=[(101.0, 1.0)],
        )
        aggregator.update(ExchangeId.UPBIT, upbit_snapshot)
        
        # Binance 스냅샷
        binance_snapshot = FakeSnapshot(
            bids=[(100.3, 1.0)],
            asks=[(101.5, 1.0)],
        )
        aggregator.update(ExchangeId.BINANCE, binance_snapshot)
        
        # Aggregation
        result = aggregator.build_aggregated_snapshot()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.best_bid, 100.5)
        self.assertEqual(result.best_bid_exchange, ExchangeId.UPBIT)
    
    def test_best_ask_selection(self):
        """
        Best Ask 선택 로직 테스트.
        
        Upbit: ask=101.2
        Binance: ask=101.0
        
        기대 결과:
        - best_ask=101.0 (Binance, 더 낮은 값)
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷
        upbit_snapshot = FakeSnapshot(
            bids=[(100.0, 1.0)],
            asks=[(101.2, 1.0)],
        )
        aggregator.update(ExchangeId.UPBIT, upbit_snapshot)
        
        # Binance 스냅샷
        binance_snapshot = FakeSnapshot(
            bids=[(99.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        aggregator.update(ExchangeId.BINANCE, binance_snapshot)
        
        # Aggregation
        result = aggregator.build_aggregated_snapshot()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.best_ask, 101.0)
        self.assertEqual(result.best_ask_exchange, ExchangeId.BINANCE)
    
    def test_aggregator_stats(self):
        """
        Aggregator Stats 테스트.
        """
        aggregator = MultiExchangeL2Aggregator(staleness_threshold_seconds=2.0)
        
        # Upbit 스냅샷
        upbit_snapshot = FakeSnapshot(
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        aggregator.update(ExchangeId.UPBIT, upbit_snapshot)
        
        # Binance 스냅샷
        binance_snapshot = FakeSnapshot(
            bids=[(99.0, 1.0)],
            asks=[(100.5, 1.0)],
        )
        aggregator.update(ExchangeId.BINANCE, binance_snapshot)
        
        # Aggregation 3회
        for _ in range(3):
            aggregator.build_aggregated_snapshot()
        
        # Stats 확인
        stats = aggregator.get_stats()
        self.assertEqual(stats["aggregation_count"], 3)
        self.assertEqual(stats["both_active_count"], 3)
        self.assertEqual(stats["single_active_count"], 0)
        self.assertEqual(stats["no_active_count"], 0)


class TestMultiExchangeL2Snapshot(unittest.TestCase):
    """
    MultiExchangeL2Snapshot 유닛 테스트.
    """
    
    def test_get_spread_bps(self):
        """
        Spread (bps) 계산 테스트.
        
        best_bid=100, best_ask=101
        mid=100.5, spread=1
        spread_bps = (1 / 100.5) * 10000 = 99.5 bps
        """
        snapshot = MultiExchangeL2Snapshot(
            per_exchange={},
            best_bid=100.0,
            best_ask=101.0,
            best_bid_exchange=ExchangeId.UPBIT,
            best_ask_exchange=ExchangeId.BINANCE,
            timestamp=time.time(),
            source_status={},
        )
        
        spread_bps = snapshot.get_spread_bps()
        self.assertIsNotNone(spread_bps)
        self.assertAlmostEqual(spread_bps, 99.5, places=1)
    
    def test_get_spread_bps_none(self):
        """
        Spread 계산 (bid/ask 중 하나라도 None)
        """
        snapshot = MultiExchangeL2Snapshot(
            per_exchange={},
            best_bid=None,
            best_ask=101.0,
            best_bid_exchange=None,
            best_ask_exchange=ExchangeId.BINANCE,
            timestamp=time.time(),
            source_status={},
        )
        
        spread_bps = snapshot.get_spread_bps()
        self.assertIsNone(spread_bps)
    
    def test_get_exchange_snapshot(self):
        """
        특정 거래소 스냅샷 조회 테스트.
        """
        upbit_snap = FakeSnapshot(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)])
        binance_snap = FakeSnapshot(bids=[(99.0, 1.0)], asks=[(100.5, 1.0)])
        
        snapshot = MultiExchangeL2Snapshot(
            per_exchange={
                ExchangeId.UPBIT: upbit_snap,
                ExchangeId.BINANCE: binance_snap,
            },
            best_bid=100.0,
            best_ask=100.5,
            best_bid_exchange=ExchangeId.UPBIT,
            best_ask_exchange=ExchangeId.BINANCE,
            timestamp=time.time(),
            source_status={},
        )
        
        # Upbit 조회
        upbit_result = snapshot.get_exchange_snapshot(ExchangeId.UPBIT)
        self.assertIsNotNone(upbit_result)
        self.assertEqual(upbit_result.best_bid(), 100.0)
        
        # Binance 조회
        binance_result = snapshot.get_exchange_snapshot(ExchangeId.BINANCE)
        self.assertIsNotNone(binance_result)
        self.assertEqual(binance_result.best_bid(), 99.0)


class TestMultiExchangeL2Provider(unittest.TestCase):
    """
    MultiExchangeL2Provider 유닛 테스트.
    
    주의:
    - 실제 WebSocket 연결 테스트는 제외 (통합 테스트에서 수행)
    - Symbol Mapping, 초기화 로직만 검증
    """
    
    def test_symbol_mapping(self):
        """
        Symbol Mapping 테스트.
        
        BTC → Upbit: "KRW-BTC", Binance: "BTCUSDT"
        """
        # Provider는 초기화만 (start는 호출하지 않음)
        # Mock Provider를 주입할 수 없으므로, SYMBOL_MAPPING만 검증
        from arbitrage.exchanges.multi_exchange_l2_provider import MultiExchangeL2Provider
        
        upbit_symbol = MultiExchangeL2Provider.SYMBOL_MAPPING["BTC"][ExchangeId.UPBIT]
        binance_symbol = MultiExchangeL2Provider.SYMBOL_MAPPING["BTC"][ExchangeId.BINANCE]
        
        self.assertEqual(upbit_symbol, "KRW-BTC")
        self.assertEqual(binance_symbol, "BTCUSDT")


if __name__ == "__main__":
    unittest.main()

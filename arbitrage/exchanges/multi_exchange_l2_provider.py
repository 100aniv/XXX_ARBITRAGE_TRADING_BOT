# -*- coding: utf-8 -*-
"""
D83-3: Multi-exchange L2 Aggregation

Multi-exchange L2 Orderbook Provider (Upbit + Binance).

Features:
- Composition: UpbitL2WebSocketProvider + BinanceL2WebSocketProvider
- Aggregation: Best bid/ask across exchanges
- Staleness detection: 2초 기본 임계값
- Thread-safe: Lock 기반 동기화
- MarketDataProvider 인터페이스 완전 준수

Architecture:
    UpbitL2WebSocketProvider ─┐
                              ├→ MultiExchangeL2Aggregator → MultiExchangeL2Snapshot
    BinanceL2WebSocketProvider┘

Usage:
    provider = MultiExchangeL2Provider(symbols=["BTC"])
    provider.start()
    
    snapshot = provider.get_latest_snapshot("BTC")
    # snapshot.best_bid, snapshot.best_ask, snapshot.per_exchange
    
    provider.stop()
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import MarketDataProvider
from arbitrage.exchanges.upbit_l2_ws_provider import UpbitL2WebSocketProvider
from arbitrage.exchanges.binance_l2_ws_provider import BinanceL2WebSocketProvider

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class ExchangeId(str, Enum):
    """
    거래소 식별자.
    
    str Enum을 사용하여 JSON serialization, logging 호환성 확보.
    """
    UPBIT = "upbit"
    BINANCE = "binance"
    # 향후 확장: BYBIT = "bybit", OKX = "okx", etc.


class SourceStatus(str, Enum):
    """
    L2 소스 상태.
    """
    ACTIVE = "active"              # 정상 (최근 업데이트 받음)
    STALE = "stale"                # 오래된 데이터 (N초 이상 업데이트 없음)
    DISCONNECTED = "disconnected"  # 연결 끊김 또는 데이터 없음


# =============================================================================
# MultiExchangeL2Snapshot
# =============================================================================

@dataclass
class MultiExchangeL2Snapshot:
    """
    Multi-exchange L2 Orderbook Snapshot.
    
    Attributes:
        per_exchange: 거래소별 L2 스냅샷
        best_bid: 모든 거래소 중 최고 매수 호가
        best_ask: 모든 거래소 중 최저 매도 호가
        best_bid_exchange: 최고 매수 호가를 제공한 거래소
        best_ask_exchange: 최저 매도 호가를 제공한 거래소
        timestamp: Aggregation 시각 (Unix timestamp)
        source_status: 거래소별 소스 상태
    """
    per_exchange: Dict[ExchangeId, OrderBookSnapshot]
    best_bid: Optional[float]
    best_ask: Optional[float]
    best_bid_exchange: Optional[ExchangeId]
    best_ask_exchange: Optional[ExchangeId]
    timestamp: float
    source_status: Dict[ExchangeId, SourceStatus]
    
    def get_spread_bps(self) -> Optional[float]:
        """
        Best bid-ask spread (basis points).
        
        Returns:
            Spread in bps, or None if bid/ask 중 하나라도 없음
        """
        if self.best_bid is None or self.best_ask is None:
            return None
        
        mid = (self.best_bid + self.best_ask) / 2.0
        spread = self.best_ask - self.best_bid
        return (spread / mid) * 10000.0
    
    def get_exchange_snapshot(self, exchange_id: ExchangeId) -> Optional[OrderBookSnapshot]:
        """
        특정 거래소의 L2 스냅샷 반환.
        
        Args:
            exchange_id: 거래소 ID
        
        Returns:
            OrderBookSnapshot or None
        """
        return self.per_exchange.get(exchange_id)


# =============================================================================
# MultiExchangeL2Aggregator
# =============================================================================

class MultiExchangeL2Aggregator:
    """
    Multi-exchange L2 Aggregator.
    
    책임:
    - 각 거래소별 최신 스냅샷 저장
    - Staleness 체크
    - Best bid/ask 집계
    - MultiExchangeL2Snapshot 생성
    """
    
    def __init__(self, staleness_threshold_seconds: float = 2.0):
        """
        Args:
            staleness_threshold_seconds: Stale 판단 임계값 (초)
        """
        self.staleness_threshold = staleness_threshold_seconds
        
        # 거래소별 최신 스냅샷 및 timestamp
        self._snapshots: Dict[ExchangeId, OrderBookSnapshot] = {}
        self._timestamps: Dict[ExchangeId, float] = {}
        
        # Thread-safety
        self._lock = Lock()
        
        # Stats
        self._aggregation_count = 0
        self._both_active_count = 0
        self._single_active_count = 0
        self._no_active_count = 0
    
    def update(self, exchange_id: ExchangeId, snapshot: OrderBookSnapshot) -> None:
        """
        거래소별 스냅샷 업데이트.
        
        Args:
            exchange_id: 거래소 ID
            snapshot: L2 스냅샷
        """
        with self._lock:
            self._snapshots[exchange_id] = snapshot
            self._timestamps[exchange_id] = time.time()
            logger.debug(
                f"[D83-3_AGGREGATOR] Updated snapshot: {exchange_id.value}, "
                f"bids={len(snapshot.bids)}, asks={len(snapshot.asks)}"
            )
    
    def build_aggregated_snapshot(self) -> Optional[MultiExchangeL2Snapshot]:
        """
        Multi-exchange L2 Snapshot 생성.
        
        Returns:
            MultiExchangeL2Snapshot or None (모든 소스가 stale인 경우)
        """
        with self._lock:
            self._aggregation_count += 1
            
            # 1. Staleness 체크
            source_status = self._check_staleness()
            
            # 2. Active 소스만 수집
            active_snapshots = {
                ex_id: snapshot
                for ex_id, snapshot in self._snapshots.items()
                if source_status.get(ex_id) == SourceStatus.ACTIVE
            }
            
            # 3. Active 소스 통계
            active_count = len(active_snapshots)
            if active_count == 0:
                self._no_active_count += 1
                logger.warning("[D83-3_AGGREGATOR] No active sources, returning None")
                return None
            elif active_count == 1:
                self._single_active_count += 1
            else:
                self._both_active_count += 1
            
            # 4. Best bid/ask 선택
            best_bid, best_bid_exchange = self._select_best_bid(active_snapshots)
            best_ask, best_ask_exchange = self._select_best_ask(active_snapshots)
            
            # 5. MultiExchangeL2Snapshot 생성
            snapshot = MultiExchangeL2Snapshot(
                per_exchange=self._snapshots.copy(),  # All snapshots (stale 포함)
                best_bid=best_bid,
                best_ask=best_ask,
                best_bid_exchange=best_bid_exchange,
                best_ask_exchange=best_ask_exchange,
                timestamp=time.time(),
                source_status=source_status,
            )
            
            logger.debug(
                f"[D83-3_AGGREGATOR] Aggregated snapshot: "
                f"best_bid={best_bid} ({best_bid_exchange}), "
                f"best_ask={best_ask} ({best_ask_exchange}), "
                f"active_sources={active_count}"
            )
            
            return snapshot
    
    def _check_staleness(self) -> Dict[ExchangeId, SourceStatus]:
        """
        각 소스의 staleness 체크.
        
        Returns:
            {exchange_id: SourceStatus} dict
        """
        now = time.time()
        status = {}
        
        for ex_id in [ExchangeId.UPBIT, ExchangeId.BINANCE]:
            if ex_id not in self._timestamps:
                status[ex_id] = SourceStatus.DISCONNECTED
                continue
            
            age = now - self._timestamps[ex_id]
            if age > self.staleness_threshold:
                status[ex_id] = SourceStatus.STALE
                logger.debug(
                    f"[D83-3_AGGREGATOR] Source {ex_id.value} is STALE (age={age:.2f}s)"
                )
            else:
                status[ex_id] = SourceStatus.ACTIVE
        
        return status
    
    def _select_best_bid(
        self, active_snapshots: Dict[ExchangeId, OrderBookSnapshot]
    ) -> tuple[Optional[float], Optional[ExchangeId]]:
        """
        Active 소스 중 최고 매수 호가 선택.
        
        Args:
            active_snapshots: Active 거래소 스냅샷
        
        Returns:
            (best_bid, exchange_id) or (None, None)
        """
        best_bid = None
        best_exchange = None
        
        for ex_id, snapshot in active_snapshots.items():
            bid = snapshot.best_bid()
            if bid is None:
                continue
            
            if best_bid is None or bid > best_bid:
                best_bid = bid
                best_exchange = ex_id
        
        return best_bid, best_exchange
    
    def _select_best_ask(
        self, active_snapshots: Dict[ExchangeId, OrderBookSnapshot]
    ) -> tuple[Optional[float], Optional[ExchangeId]]:
        """
        Active 소스 중 최저 매도 호가 선택.
        
        Args:
            active_snapshots: Active 거래소 스냅샷
        
        Returns:
            (best_ask, exchange_id) or (None, None)
        """
        best_ask = None
        best_exchange = None
        
        for ex_id, snapshot in active_snapshots.items():
            ask = snapshot.best_ask()
            if ask is None:
                continue
            
            if best_ask is None or ask < best_ask:
                best_ask = ask
                best_exchange = ex_id
        
        return best_ask, best_exchange
    
    def get_stats(self) -> Dict[str, int]:
        """
        Aggregation 통계 반환.
        
        Returns:
            {aggregation_count, both_active_count, single_active_count, no_active_count}
        """
        with self._lock:
            return {
                "aggregation_count": self._aggregation_count,
                "both_active_count": self._both_active_count,
                "single_active_count": self._single_active_count,
                "no_active_count": self._no_active_count,
            }


# =============================================================================
# MultiExchangeL2Provider
# =============================================================================

class MultiExchangeL2Provider(MarketDataProvider):
    """
    Multi-exchange L2 WebSocket Provider.
    
    특징:
    - MarketDataProvider 인터페이스 완전 준수
    - Upbit + Binance L2 Provider를 composition으로 관리
    - MultiExchangeL2Aggregator를 통한 집계
    - Thread-safe
    
    Usage:
        provider = MultiExchangeL2Provider(symbols=["BTC"])
        provider.start()
        
        snapshot = provider.get_latest_snapshot("BTC")
        # snapshot: MultiExchangeL2Snapshot
        
        provider.stop()
    """
    
    # 심볼 매핑 (표준 심볼 → 거래소별 심볼)
    SYMBOL_MAPPING = {
        "BTC": {
            ExchangeId.UPBIT: "KRW-BTC",
            ExchangeId.BINANCE: "BTCUSDT",
        },
        # 향후 확장: "ETH", "XRP", etc.
    }
    
    def __init__(
        self,
        symbols: List[str],
        staleness_threshold_seconds: float = 2.0,
        upbit_heartbeat_interval: float = 30.0,
        upbit_timeout: float = 10.0,
        upbit_max_reconnect_attempts: int = 5,
        upbit_reconnect_backoff: float = 2.0,
        binance_depth: str = "20",
        binance_interval: str = "100ms",
        binance_heartbeat_interval: float = 30.0,
        binance_timeout: float = 10.0,
        binance_max_reconnect_attempts: int = 5,
        binance_reconnect_backoff: float = 2.0,
    ):
        """
        Args:
            symbols: 표준 심볼 리스트 (예: ["BTC"])
            staleness_threshold_seconds: Stale 판단 임계값 (초)
            upbit_*: Upbit Provider 설정
            binance_*: Binance Provider 설정
        """
        self.symbols = symbols
        self.staleness_threshold = staleness_threshold_seconds
        
        # Aggregator 초기화
        self.aggregator = MultiExchangeL2Aggregator(
            staleness_threshold_seconds=staleness_threshold_seconds
        )
        
        # 거래소별 Provider 초기화
        self._exchange_providers = {}
        
        # Upbit Provider
        upbit_symbols = [self._get_exchange_symbol(sym, ExchangeId.UPBIT) for sym in symbols]
        self._exchange_providers[ExchangeId.UPBIT] = UpbitL2WebSocketProvider(
            symbols=upbit_symbols,
            heartbeat_interval=upbit_heartbeat_interval,
            timeout=upbit_timeout,
            max_reconnect_attempts=upbit_max_reconnect_attempts,
            reconnect_backoff=upbit_reconnect_backoff,
        )
        
        # Binance Provider
        binance_symbols = [self._get_exchange_symbol(sym, ExchangeId.BINANCE) for sym in symbols]
        self._exchange_providers[ExchangeId.BINANCE] = BinanceL2WebSocketProvider(
            symbols=binance_symbols,
            depth=binance_depth,
            interval=binance_interval,
            heartbeat_interval=binance_heartbeat_interval,
            timeout=binance_timeout,
            max_reconnect_attempts=binance_max_reconnect_attempts,
            reconnect_backoff=binance_reconnect_backoff,
        )
        
        # Override callback to update aggregator
        self._wrap_callbacks()
        
        logger.info(
            f"[D83-3_MULTI_L2] MultiExchangeL2Provider initialized for symbols={symbols}"
        )
    
    def _wrap_callbacks(self) -> None:
        """
        기존 Provider의 callback을 wrap하여 Aggregator 업데이트 추가.
        """
        for ex_id, provider in self._exchange_providers.items():
            original_callback = provider._on_snapshot
            
            def make_wrapped_callback(exchange_id):
                """Closure to capture exchange_id"""
                def wrapped_callback(snapshot):
                    # Aggregator 업데이트
                    self.aggregator.update(exchange_id, snapshot)
                    # 원래 callback 호출 (latest_snapshots 업데이트)
                    original_callback(snapshot)
                return wrapped_callback
            
            provider._on_snapshot = make_wrapped_callback(ex_id)
    
    def start(self) -> None:
        """
        모든 거래소 Provider 시작.
        """
        logger.info("[D83-3_MULTI_L2] Starting all exchange providers...")
        
        for ex_id, provider in self._exchange_providers.items():
            try:
                provider.start()
                logger.info(f"[D83-3_MULTI_L2] Started provider: {ex_id.value}")
            except Exception as e:
                logger.error(f"[D83-3_MULTI_L2] Failed to start {ex_id.value}: {e}")
        
        # 첫 스냅샷 대기 (최대 10초)
        logger.info("[D83-3_MULTI_L2] Waiting for first snapshots...")
        for i in range(10):
            time.sleep(1)
            snapshot = self.aggregator.build_aggregated_snapshot()
            if snapshot:
                logger.info(
                    f"[D83-3_MULTI_L2] First aggregated snapshot received: "
                    f"best_bid={snapshot.best_bid}, best_ask={snapshot.best_ask}"
                )
                break
        else:
            logger.warning("[D83-3_MULTI_L2] No aggregated snapshot after 10s")
    
    def stop(self) -> None:
        """
        모든 거래소 Provider 종료.
        """
        logger.info("[D83-3_MULTI_L2] Stopping all exchange providers...")
        
        for ex_id, provider in self._exchange_providers.items():
            try:
                provider.stop()
                logger.info(f"[D83-3_MULTI_L2] Stopped provider: {ex_id.value}")
            except Exception as e:
                logger.error(f"[D83-3_MULTI_L2] Failed to stop {ex_id.value}: {e}")
    
    def get_latest_snapshot(self, symbol: str) -> Optional[MultiExchangeL2Snapshot]:
        """
        최신 Multi-exchange L2 Snapshot 반환.
        
        Args:
            symbol: 표준 심볼 (예: "BTC")
        
        Returns:
            MultiExchangeL2Snapshot or None
        """
        # 현재는 단일 심볼만 지원 (BTC)
        if symbol not in self.symbols:
            logger.warning(f"[D83-3_MULTI_L2] Unsupported symbol: {symbol}")
            return None
        
        return self.aggregator.build_aggregated_snapshot()
    
    def _get_exchange_symbol(self, standard_symbol: str, exchange_id: ExchangeId) -> str:
        """
        표준 심볼 → 거래소별 심볼 매핑.
        
        Args:
            standard_symbol: 표준 심볼 (예: "BTC")
            exchange_id: 거래소 ID
        
        Returns:
            거래소별 심볼 (예: "KRW-BTC", "BTCUSDT")
        """
        mapping = self.SYMBOL_MAPPING.get(standard_symbol, {})
        return mapping.get(exchange_id, standard_symbol)
    
    def get_aggregator_stats(self) -> Dict[str, int]:
        """
        Aggregator 통계 반환.
        
        Returns:
            {aggregation_count, both_active_count, single_active_count, no_active_count}
        """
        return self.aggregator.get_stats()

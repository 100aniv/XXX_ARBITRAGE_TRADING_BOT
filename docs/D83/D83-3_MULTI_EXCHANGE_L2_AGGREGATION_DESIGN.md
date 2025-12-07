# D83-3: Multi-exchange L2 Aggregation 설계 문서

**작성일:** 2025-12-07  
**상태:** DESIGN  
**Phase:** D83 - L2 Orderbook Integration

---

## 1. 배경 및 문제 정의

### 1.1. 현재 상황 (AS-IS)

**D83-0 ~ D83-2 완료 내역:**
- **D83-0:** L2 Orderbook Integration (PaperExecutor에 `available_volume` 실시간 연동)
- **D83-0.5:** L2 Fill Model PAPER Smoke Validation (120초 검증, L2 + FillEventCollector 통합)
- **D83-1:** Upbit L2 WebSocket Provider (Real L2, 5분 PAPER All PASS)
- **D83-2:** Binance L2 WebSocket Provider (Real L2, 5분 PAPER All PASS)

**현재 문제:**
1. **단일 거래소 L2만 사용 가능**
   - `--l2-source upbit` 또는 `--l2-source binance` 중 하나만 선택 가능
   - Cross-exchange 관점에서 "어느 거래소가 더 좋은 호가를 제공하는지" 한 번에 볼 수 없음

2. **Cross-exchange Arbitrage 시나리오 미지원**
   - 실제 아비트라지는 Upbit와 Binance 간 spread를 기반으로 거래
   - 각 거래소의 L2 데이터를 별도로 조회하여 수동으로 비교해야 함

3. **데이터 품질/안정성 보장 부재**
   - 한쪽 거래소 WebSocket이 일시적으로 stale/죽으면 전체 시스템이 영향 받음
   - Graceful degradation 메커니즘 없음

### 1.2. D80 Multi-source FX Aggregation 패턴

**D80-5에서 구현된 패턴:**
- `MultiSourceFxRateProvider`: Binance + OKX + Bybit WebSocket 집계
- Outlier detection (median ±5%)
- Median aggregation
- 4-Tier Fallback: Multi-source (median) → WebSocket (single) → HTTP → Static

**L2 Aggregation과의 차이점:**
| 항목 | FX Aggregation (D80-5) | L2 Aggregation (D83-3) |
|------|------------------------|------------------------|
| **데이터 타입** | 단일 값 (환율) | 복합 구조 (bids/asks 배열) |
| **Aggregation 로직** | Median | Best Bid/Ask 선택 |
| **Outlier 판단** | 통계 기반 (±5%) | Timestamp 기반 (staleness) |
| **Fallback** | HTTP → Static | 한쪽 거래소만 살아있어도 OK |
| **Use Case** | PnL 표시, FX conversion | Execution, Fill Model, Slippage Model |

**공통 설계 철학:**
- **Composition over Inheritance**: 기존 Provider를 재사용
- **Thread-safety**: Lock 기반 동기화
- **Observable**: Stats/Metrics 제공

---

## 2. 요구사항

### 2.1. Functional Requirements

**FR-1: Multi-exchange L2 Snapshot 제공**
- Upbit + Binance L2 스냅샷을 통합한 `MultiExchangeL2Snapshot` 반환
- 거래소별 L2 데이터 (`per_exchange: Dict[ExchangeId, OrderBookSnapshot]`)
- Aggregated Best Bid/Ask (global best across all exchanges)
- 메타 정보 (timestamp, source status)

**FR-2: Staleness 처리**
- 각 거래소의 마지막 업데이트가 N초 (기본값: 2초) 이상 지연되면 "stale"로 간주
- Stale 소스는 aggregation에서 제외
- 하나의 소스만 살아있을 경우, 그 소스만으로 Snapshot 구성
- 모든 소스가 stale일 경우, `None` 반환 또는 예외 발생 (설정 가능)

**FR-3: MarketDataProvider 인터페이스 준수**
- `get_latest_snapshot(symbol) -> Optional[MultiExchangeL2Snapshot]`
- `start()`, `stop()` 라이프사이클 메서드
- Thread-safe (동시 호출 안전)

**FR-4: Symbol Mapping**
- 표준 심볼 (예: "BTC") → 거래소별 심볼 자동 매핑
  - Upbit: "BTC" → "KRW-BTC"
  - Binance: "BTC" → "BTCUSDT"

**FR-5: 하위 호환성 유지**
- 기존 Upbit/Binance L2 Provider 코드는 수정 없이 재사용
- 기존 `--l2-source upbit/binance/mock` 옵션 유지
- 새 옵션 추가: `--l2-source multi`

### 2.2. Non-Functional Requirements

**NFR-1: 성능**
- `get_latest_snapshot()` 호출 시 latency < 1ms (메모리 lookup)
- WebSocket 업데이트 반영 latency < 10ms

**NFR-2: 안정성**
- 한쪽 거래소 WebSocket 장애 시 graceful degradation
- Reconnection 로직은 개별 Provider가 담당 (기존 구현 재사용)

**NFR-3: 관찰 가능성 (Observability)**
- 각 거래소별 last update timestamp 제공
- Stale/Active source 수 추적
- Aggregation 통계 (얼마나 자주 양쪽 모두 active인지)

**NFR-4: 확장성**
- 향후 3개 이상 거래소 추가 가능하도록 설계
- Exchange ID를 Enum으로 관리

---

## 3. 설계

### 3.1. 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                  MultiExchangeL2Provider                    │
│                (MarketDataProvider 구현)                    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │ _exchange_providers: Dict[ExchangeId, Provider]   │    │
│  │   - ExchangeId.UPBIT: UpbitL2WebSocketProvider    │    │
│  │   - ExchangeId.BINANCE: BinanceL2WebSocketProvider│    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                 │
│                           ↓                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │      MultiExchangeL2Aggregator                     │    │
│  │  - update(exchange_id, snapshot)                   │    │
│  │  - build_aggregated_snapshot()                     │    │
│  │  - _check_staleness()                              │    │
│  │  - _select_best_bid_ask()                          │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                 │
│                           ↓                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │      MultiExchangeL2Snapshot                       │    │
│  │  - per_exchange: Dict[ExchangeId, L2Snapshot]      │    │
│  │  - best_bid: Optional[float]                       │    │
│  │  - best_ask: Optional[float]                       │    │
│  │  - best_bid_exchange: Optional[ExchangeId]         │    │
│  │  - best_ask_exchange: Optional[ExchangeId]         │    │
│  │  - timestamp: float                                │    │
│  │  - source_status: Dict[ExchangeId, SourceStatus]   │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2. 클래스 설계

#### 3.2.1. ExchangeId (Enum)

```python
from enum import Enum

class ExchangeId(str, Enum):
    """
    거래소 식별자.
    
    str Enum을 사용하여 JSON serialization, logging 호환성 확보.
    """
    UPBIT = "upbit"
    BINANCE = "binance"
    # 향후 확장: BYBIT = "bybit", OKX = "okx", etc.
```

#### 3.2.2. SourceStatus (Enum)

```python
from enum import Enum

class SourceStatus(str, Enum):
    """
    L2 소스 상태.
    """
    ACTIVE = "active"        # 정상 (최근 업데이트 받음)
    STALE = "stale"          # 오래된 데이터 (N초 이상 업데이트 없음)
    DISCONNECTED = "disconnected"  # 연결 끊김 (향후 확장)
```

#### 3.2.3. MultiExchangeL2Snapshot (DataClass)

```python
from dataclasses import dataclass
from typing import Dict, Optional
from arbitrage.exchanges.base import OrderBookSnapshot

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
```

#### 3.2.4. MultiExchangeL2Aggregator

```python
import logging
import time
from threading import Lock
from typing import Dict, Optional

logger = logging.getLogger(__name__)

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
```

#### 3.2.5. MultiExchangeL2Provider

```python
import logging
import time
from typing import List, Optional

from arbitrage.exchanges.market_data_provider import MarketDataProvider
from arbitrage.exchanges.upbit_l2_ws_provider import UpbitL2WebSocketProvider
from arbitrage.exchanges.binance_l2_ws_provider import BinanceL2WebSocketProvider

logger = logging.getLogger(__name__)

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
        upbit_symbols = [self._get_exchange_symbol("BTC", ExchangeId.UPBIT)]
        self._exchange_providers[ExchangeId.UPBIT] = UpbitL2WebSocketProvider(
            symbols=upbit_symbols,
            heartbeat_interval=upbit_heartbeat_interval,
            timeout=upbit_timeout,
            max_reconnect_attempts=upbit_max_reconnect_attempts,
            reconnect_backoff=upbit_reconnect_backoff,
        )
        
        # Binance Provider
        binance_symbols = [self._get_exchange_symbol("BTC", ExchangeId.BINANCE)]
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
            
            def wrapped_callback(snapshot, exchange_id=ex_id):
                # Aggregator 업데이트
                self.aggregator.update(exchange_id, snapshot)
                # 원래 callback 호출 (latest_snapshots 업데이트)
                original_callback(snapshot)
            
            provider._on_snapshot = wrapped_callback
    
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
```

### 3.3. 데이터 플로우

```
┌─────────────┐                    ┌──────────────────────┐
│ Upbit WS    │──────────────────→│ UpbitL2WebSocket     │
│ (KRW-BTC)   │  Depth Messages   │ Provider             │
└─────────────┘                    └──────────────────────┘
                                              │
                                              │ _on_snapshot(snapshot)
                                              ↓
                                   ┌──────────────────────┐
                                   │ MultiExchangeL2      │
                                   │ Aggregator           │
                                   │ .update(UPBIT, snap) │
                                   └──────────────────────┘
                                              ↑
                                              │ _on_snapshot(snapshot)
                                              │
┌─────────────┐                    ┌──────────────────────┐
│ Binance WS  │──────────────────→│ BinanceL2WebSocket   │
│ (BTCUSDT)   │  Depth Messages   │ Provider             │
└─────────────┘                    └──────────────────────┘

                                              ↓
                                   ┌──────────────────────┐
                                   │ MultiExchangeL2      │
                                   │ Aggregator           │
                                   │ .build_aggregated_   │
                                   │  snapshot()          │
                                   └──────────────────────┘
                                              │
                                              ↓
                                   ┌──────────────────────┐
                                   │ MultiExchangeL2      │
                                   │ Snapshot             │
                                   │ - per_exchange       │
                                   │ - best_bid/ask       │
                                   │ - source_status      │
                                   └──────────────────────┘
                                              │
                                              ↓
                                   ┌──────────────────────┐
                                   │ PaperExecutor        │
                                   │ .get_latest_snapshot │
                                   └──────────────────────┘
```

---

## 4. 향후 확장 (TO-BE)

### 4.1. 3개 이상 거래소 지원

**확장 방법:**
1. `ExchangeId` Enum에 새 거래소 추가 (예: `BYBIT`, `OKX`)
2. `SYMBOL_MAPPING`에 새 거래소 심볼 매핑 추가
3. `MultiExchangeL2Provider.__init__()`에서 새 Provider 초기화
4. Aggregator는 코드 수정 없이 작동 (동적 처리)

### 4.2. Multi-level L2 Aggregation

**현재:** Best bid/ask만 집계  
**향후:** 전체 호가창 통합 (depth 20 → cross-exchange depth 20)

**Use Case:**
- Large order 실행 시 여러 거래소에 분산 주문
- Slippage 계산 시 cross-exchange depth 고려

### 4.3. TopN Arbitrage / Arbitrage Route와 연결

**연결 방식:**
- `MultiExchangeL2Snapshot`에서 거래소별 best bid/ask 직접 조회
- Arbitrage Engine은 `get_exchange_snapshot(ExchangeId.UPBIT)` 호출로 특정 거래소 L2 접근
- Cross-exchange spread 계산 간소화

---

## 5. 테스트 전략

### 5.1. 유닛 테스트

**파일:** `tests/test_d83_3_multi_exchange_l2_provider.py`

**테스트 시나리오:**
1. **기본 Aggregation**
   - FakeUpbitProvider, FakeBinanceProvider 생성
   - Upbit: bid=100, ask=101
   - Binance: bid=99, ask=100.5
   - 결과: best_bid=100 (Upbit), best_ask=100.5 (Binance)

2. **한쪽 소스 Stale**
   - Upbit: 최신 (0.5초 전)
   - Binance: Stale (3초 전, threshold=2초)
   - 결과: Upbit만 사용, best_bid/ask는 Upbit 기준

3. **양쪽 소스 Stale**
   - Upbit: Stale (3초 전)
   - Binance: Stale (4초 전)
   - 결과: `None` 반환

4. **Empty Orderbook**
   - Upbit: bids=[], asks=[]
   - Binance: 정상
   - 결과: Binance만 사용

5. **Symbol Mapping**
   - 표준 심볼 "BTC" → Upbit "KRW-BTC", Binance "BTCUSDT" 매핑 확인

### 5.2. 통합 테스트

**Runner 통합:**
- `--l2-source multi` 옵션으로 60~120초 스모크 테스트
- Fill Events 수집 및 분석
- Upbit/Binance 모두에서 메시지 수신 확인

---

## 6. Runner 통합 (D84-2 연동)

### 6.1. CLI 옵션 추가

**기존:**
```bash
--l2-source [mock|upbit|binance|real]
```

**추가:**
```bash
--l2-source multi
```

### 6.2. Provider 생성 로직

```python
# scripts/run_d84_2_calibrated_fill_paper.py

if l2_source == "multi":
    # D83-3: Multi-exchange L2 Provider
    from arbitrage.exchanges.multi_exchange_l2_provider import MultiExchangeL2Provider
    
    market_data_provider = MultiExchangeL2Provider(
        symbols=["BTC"],
        staleness_threshold_seconds=2.0,
    )
    market_data_provider.start()
    logger.info("[D83-3] MultiExchangeL2Provider started")
    
    # 첫 스냅샷 대기 (Provider 내부에서 처리)
    
elif l2_source == "upbit":
    # 기존 Upbit Provider (D83-1)
    ...
elif l2_source == "binance":
    # 기존 Binance Provider (D83-2)
    ...
else:
    # Mock Provider (D84-2)
    ...
```

### 6.3. Executor 연동

**주의사항:**
- `PaperExecutor`는 `MarketDataProvider` 인터페이스만 의존
- `MultiExchangeL2Provider`도 동일 인터페이스 구현
- **Executor 코드 수정 불필요**

**다만, `get_latest_snapshot()` 반환 타입 변경:**
- 기존: `Optional[OrderBookSnapshot]`
- Multi: `Optional[MultiExchangeL2Snapshot]`

**해결 방법:**
- `MultiExchangeL2Snapshot`를 `OrderBookSnapshot`처럼 사용 가능하도록 인터페이스 확장
- 또는 Executor에서 `.per_exchange[ExchangeId.UPBIT]` 같은 방식으로 접근

**권장 설계:**
- `get_latest_snapshot()`는 여전히 `OrderBookSnapshot` 반환
- 내부적으로 `best_bid/ask`만 사용하는 **가상 snapshot** 생성
- Cross-exchange specific 정보가 필요한 경우, 별도 메서드 제공 (`get_multi_exchange_snapshot()`)

---

## 7. 한계 및 리스크

### 7.1. 한계

1. **단일 심볼만 지원 (BTC)**
   - 현재 Multi-symbol은 향후 확장으로 미룸
   - 이유: D84 Fill Model 검증이 BTC 중심

2. **Best bid/ask만 집계**
   - 전체 호가창 (depth 20) 통합은 미구현
   - 이유: 현재 Use Case (Fill Model, Executor)는 best만 필요

3. **WebSocket 재연결은 개별 Provider 책임**
   - Multi-provider 레벨에서 재연결 조율 없음
   - 이유: 기존 Provider 재사용, DO-NOT-TOUCH 원칙

### 7.2. 리스크

**R1: 한쪽 거래소 장애 시 성능 저하**
- **완화:** Graceful degradation (한쪽만 살아있어도 작동)

**R2: Staleness threshold 설정 오류**
- **완화:** 기본값 2초는 안전한 값, 향후 Config로 조정 가능

**R3: Thread-safety 이슈**
- **완화:** Lock 기반 동기화, 기존 Provider 패턴 재사용

---

## 8. Acceptance Criteria

**D83-3 완료 조건:**

1. **구현 완료**
   - ✅ `MultiExchangeL2Snapshot` DataClass
   - ✅ `MultiExchangeL2Aggregator` Class
   - ✅ `MultiExchangeL2Provider` (MarketDataProvider 구현)
   - ✅ `ExchangeId`, `SourceStatus` Enum

2. **유닛 테스트**
   - ✅ 10개 이상 테스트 케이스 (기본 aggregation, staleness, edge cases)
   - ✅ 100% PASS

3. **Runner 통합**
   - ✅ `--l2-source multi` 옵션 추가
   - ✅ 60~120초 스모크 PAPER 실행 성공
   - ✅ 에러/예외 없이 종료

4. **실행 검증**
   - ✅ Upbit/Binance 모두에서 L2 메시지 수신 확인
   - ✅ Aggregator가 정상 동작 (로그 상 확인)
   - ✅ Fill Events 정상 수집

5. **문서 작성**
   - ✅ `D83-3_MULTI_EXCHANGE_L2_AGGREGATION_DESIGN.md` (본 문서)
   - ✅ `D83-3_MULTI_EXCHANGE_L2_AGGREGATION_REPORT.md` (검증 리포트)

6. **회귀 테스트**
   - ✅ 기존 D83-0/1/2, D84-1/2 테스트 ALL PASS
   - ✅ 새 D83-3 테스트 ALL PASS

---

## 9. Next Steps

**D83-3 완료 후:**
1. **D84-2+:** Long-run PAPER (20분+, 100+ fill events, Multi L2 기반)
2. **D84-3:** Mock vs Real L2 (Upbit/Binance/Multi) fill distribution 비교
3. **D85-x:** Cross-exchange Slippage Model (Multi L2 depth 활용)

---

**END OF DESIGN DOCUMENT**

# D80-4: WebSocket FX Stream 설계 문서

**작성일:** 2025-12-02  
**상태:** 🟢 IMPLEMENTATION  
**목표:** WebSocket 기반 실시간 환율 스트림으로 FX Cache 업데이트 (HTTP fallback 유지)

---

## 1. 개요

### 1.1 목적
- **RealFxRateProvider 확장:** HTTP polling → WebSocket push 방식으로 FX 업데이트 지연 단축
- **Event-driven FX Cache:** WebSocket 메시지 수신 시 즉시 FxCache 갱신
- **Graceful Degradation:** WebSocket 장애 시 자동으로 HTTP/Static fallback
- **Sub-second Latency:** FX 업데이트 지연을 수초 → 수백ms 수준으로 개선

### 1.2 범위

**IN SCOPE:**
- ✅ Binance WebSocket 클라이언트 (Mark Price Stream)
- ✅ WebSocket 기반 FX Rate Provider (RealFxRateProvider composition)
- ✅ Event-driven FxCache 업데이트
- ✅ WebSocket 재연결 로직 (exponential backoff)
- ✅ WebSocket 상태 metrics (연결 상태, reconnect 횟수)
- ✅ HTTP fallback 유지 (WebSocket 실패 시 자동 전환)

**OUT OF SCOPE (향후):**
- ❌ 다중 거래소 WebSocket 집계 (Binance + OKX + Bybit)
- ❌ Triangulation (KRW→BTC via USD 중개)
- ❌ 완전한 Async Engine 리팩토링 (동기 코드와 공존)

---

## 2. 요구사항

### 2.1 Functional Requirements

#### FR-1: Binance WebSocket Mark Price Stream
- **Endpoint:** `wss://fstream.binance.com/ws/btcusdt@markPrice@1s`
- **데이터:** Mark Price (BTC/USDT 등), Funding Rate
- **업데이트 주기:** 1초마다 (3초마다로 throttle 가능)
- **환율 변환:** Mark Price의 변동을 USDT→USD 환율 proxy로 사용 (근사)

#### FR-2: Event-driven FxCache 업데이트
- WebSocket 메시지 수신 → Rate 계산 → `FxCache.set(base, quote, rate)` 호출
- Cache TTL은 기존 3초 유지 (WebSocket이 계속 push하므로 TTL은 fallback용)
- `get_rate()` 호출 시 Cache hit 우선, miss 시 HTTP fallback

#### FR-3: WebSocket 재연결 로직
- 연결 실패/중단 시 자동 재시도
- Exponential backoff: 1초 → 2초 → 4초 → 8초 → ... (최대 60초)
- 최대 재시도 횟수: 10회 (이후 HTTP-only 모드로 전환)
- 재연결 성공 시 backoff 리셋

#### FR-4: Graceful Fallback
- **WebSocket → HTTP:** WS 연결 실패 10회 이상 시 HTTP-only 모드
- **HTTP → Static:** HTTP API도 실패 시 기존 static fallback
- Fallback 시 WARNING 로그 + metrics 증가
- 시스템 전체 중단 없음

#### FR-5: WebSocket Metrics
- **Metrics 추가:**
  - `cross_fx_ws_connected` (Gauge, 0/1): WebSocket 연결 상태
  - `cross_fx_ws_reconnect_total` (Counter): 재연결 시도 횟수
  - `cross_fx_ws_message_total` (Counter): 수신 메시지 수
  - `cross_fx_ws_last_message_seconds` (Gauge): 마지막 메시지 이후 경과 시간
  - `cross_fx_ws_error_total` (Counter): WebSocket 에러 횟수
- **기존 Metrics 유지:**
  - `cross_fx_rate`, `cross_fx_last_update_seconds`, `cross_fx_stale_total`

### 2.2 Non-Functional Requirements

#### NFR-1: Non-blocking Operation
- WebSocket listener는 별도 Thread에서 실행
- 엔진 메인 루프를 블로킹하지 않음
- Thread-safe FxCache 접근 (필요 시 Lock 추가)

#### NFR-2: Reliability
- WebSocket 장애 시 system-wide stop 없음
- HTTP/Static fallback으로 계속 동작
- 재연결 로직은 무한 루프 방지 (최대 10회)

#### NFR-3: Observability
- 모든 WebSocket 이벤트(연결/끊김/에러)를 로그에 기록
- Metrics를 통해 WebSocket 상태 모니터링 가능
- Alert 발생 시 원인 추적 가능 (로그 + metrics)

---

## 3. 아키텍처

### 3.1 Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│          CrossExchangeExecutor                           │
│  - _estimate_order_cost()                                │
│  - fx_provider: WebSocketFxRateProvider                  │
└────────────────────┬─────────────────────────────────────┘
                     │
                     │ get_rate(base, quote)
                     ▼
┌──────────────────────────────────────────────────────────┐
│       WebSocketFxRateProvider                            │
│  - real_fx_provider: RealFxRateProvider (HTTP fallback) │
│  - ws_client: BinanceFxWebSocketClient                   │
│  - cache: FxCache (shared)                               │
│  + get_rate(base, quote) -> Decimal                      │
│  + start() / stop()                                      │
└────────────────────┬────────────────┬────────────────────┘
                     │                │
         ┌───────────┘                └───────────┐
         ▼                                        ▼
┌────────────────────┐                  ┌──────────────────┐
│ BinanceFxWebSocket │                  │ RealFxRateProvider│
│ Client             │                  │ (HTTP fallback)  │
│ - Thread-based     │                  │ - Binance API    │
│ - Reconnect logic  │                  │ - Exchangerate   │
│ - Message handler  │                  │ - Static fallback│
└────────────────────┘                  └──────────────────┘
         │
         │ on_message(data)
         ▼
┌──────────────────────────────────────────────────────────┐
│                FxCache (shared)                          │
│  - set(base, quote, rate, updated_at)                    │
│  - get(base, quote) -> rate                              │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

#### 3.2.1 WebSocket FX Update (정상 시나리오)
```
1. BinanceFxWebSocketClient (Background Thread)
   ↓
2. WebSocket Message: {"e":"markPriceUpdate","p":"97000.00","r":"0.0001"}
   ↓
3. on_message() → parse → rate = Decimal("1.0") (USDT≈USD)
   ↓
4. FxCache.set(Currency.USDT, Currency.USD, rate, time.time())
   ↓
5. Metrics: cross_fx_ws_message_total++, cross_fx_rate updated
   ↓
6. Executor.get_rate() → FxCache.get() → Cache HIT (< 1ms)
```

#### 3.2.2 WebSocket Failure → HTTP Fallback
```
1. WebSocket 연결 실패 또는 10회 재시도 초과
   ↓
2. WebSocketFxRateProvider.get_rate() 호출
   ↓
3. FxCache.get() → MISS (WS 업데이트 없음)
   ↓
4. real_fx_provider.get_rate() (HTTP API 호출)
   ↓
5. FxCache.set() (HTTP 결과 캐싱)
   ↓
6. Metrics: cross_fx_ws_connected=0, cross_fx_ws_error_total++
```

#### 3.2.3 WebSocket Reconnection
```
1. WebSocket 연결 끊김 감지
   ↓
2. Exponential backoff: sleep(2^retry_count seconds, max 60s)
   ↓
3. 재연결 시도
   ├─ 성공 → retry_count=0, cross_fx_ws_connected=1, cross_fx_ws_reconnect_total++
   └─ 실패 → retry_count++, 다시 2번으로
   ↓
4. retry_count > 10 → HTTP-only 모드 전환
```

---

## 4. 구현 상세

### 4.1 BinanceFxWebSocketClient

**파일:** `arbitrage/common/fx_ws_client.py` (NEW)

**책임:**
- Binance WebSocket endpoint에 연결
- Mark Price 메시지 수신 및 파싱
- FxCache 업데이트 (callback)
- 재연결 로직 (exponential backoff)

**구조:**
```python
import threading
import time
import json
import logging
from decimal import Decimal
from typing import Callable, Optional
import websocket  # websocket-client 라이브러리

logger = logging.getLogger(__name__)


class BinanceFxWebSocketClient:
    """
    Binance WebSocket FX Stream Client.
    
    Features:
    - Mark Price Stream (USDT→USD proxy)
    - Auto-reconnect (exponential backoff)
    - Thread-based (non-blocking)
    - Callback-based FxCache update
    
    Example:
        client = BinanceFxWebSocketClient(
            symbol="BTCUSDT",
            on_rate_update=lambda rate: cache.set(Currency.USDT, Currency.USD, rate)
        )
        client.start()  # Background thread
        ...
        client.stop()
    """
    
    WS_URL = "wss://fstream.binance.com/ws/{symbol}@markPrice@1s"
    MAX_RECONNECT_ATTEMPTS = 10
    MAX_BACKOFF_SECONDS = 60
    
    def __init__(
        self,
        symbol: str = "btcusdt",
        on_rate_update: Optional[Callable[[Decimal, float], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Args:
            symbol: Binance futures symbol (소문자)
            on_rate_update: Callback(rate, timestamp) - FxCache 업데이트
            on_error: Callback(exception) - 에러 핸들링
        """
        self.symbol = symbol.lower()
        self.url = self.WS_URL.format(symbol=self.symbol)
        self.on_rate_update = on_rate_update
        self.on_error = on_error
        
        self._ws = None
        self._thread = None
        self._stop_event = threading.Event()
        self._connected = False
        self._reconnect_count = 0
        
        logger.info(f"[FX_WS] BinanceFxWebSocketClient initialized (symbol={symbol})")
    
    def start(self) -> None:
        """Start WebSocket client in background thread"""
        if self._thread and self._thread.is_alive():
            logger.warning("[FX_WS] WebSocket client already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[FX_WS] WebSocket client started")
    
    def stop(self) -> None:
        """Stop WebSocket client"""
        logger.info("[FX_WS] Stopping WebSocket client...")
        self._stop_event.set()
        
        if self._ws:
            self._ws.close()
        
        if self._thread:
            self._thread.join(timeout=5.0)
        
        logger.info("[FX_WS] WebSocket client stopped")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self._connected
    
    def _run(self) -> None:
        """Main WebSocket loop (runs in background thread)"""
        while not self._stop_event.is_set():
            try:
                self._connect()
            except Exception as e:
                logger.error(f"[FX_WS] WebSocket error: {e}")
                if self.on_error:
                    self.on_error(e)
                
                # Reconnect logic
                self._reconnect_count += 1
                if self._reconnect_count > self.MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        f"[FX_WS] Max reconnect attempts ({self.MAX_RECONNECT_ATTEMPTS}) "
                        "exceeded, stopping WebSocket client"
                    )
                    break
                
                # Exponential backoff
                backoff = min(2 ** self._reconnect_count, self.MAX_BACKOFF_SECONDS)
                logger.warning(
                    f"[FX_WS] Reconnecting in {backoff}s "
                    f"(attempt {self._reconnect_count}/{self.MAX_RECONNECT_ATTEMPTS})"
                )
                time.sleep(backoff)
    
    def _connect(self) -> None:
        """Connect to WebSocket"""
        logger.info(f"[FX_WS] Connecting to {self.url}")
        
        self._ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_ws_error,
            on_close=self._on_close,
        )
        
        # Run forever (blocking in this thread)
        self._ws.run_forever()
    
    def _on_open(self, ws) -> None:
        """WebSocket connection opened"""
        self._connected = True
        self._reconnect_count = 0  # Reset on successful connection
        logger.info("[FX_WS] WebSocket connected")
    
    def _on_message(self, ws, message: str) -> None:
        """Handle WebSocket message"""
        try:
            data = json.loads(message)
            
            # Binance Mark Price message format:
            # {"e":"markPriceUpdate","E":1234567890,"s":"BTCUSDT","p":"97000.00","r":"0.0001",...}
            if data.get("e") == "markPriceUpdate":
                # USDT/USD ≈ 1.0 (근사, funding rate 무시)
                rate = Decimal("1.0")
                timestamp = time.time()
                
                # Callback to update FxCache
                if self.on_rate_update:
                    self.on_rate_update(rate, timestamp)
                
                logger.debug(
                    f"[FX_WS] Mark price update: {data.get('s')} @ {data.get('p')}, "
                    f"USDT→USD={rate}"
                )
        
        except Exception as e:
            logger.error(f"[FX_WS] Error parsing message: {e}, message={message}")
    
    def _on_ws_error(self, ws, error) -> None:
        """WebSocket error"""
        logger.error(f"[FX_WS] WebSocket error: {error}")
        self._connected = False
        if self.on_error:
            self.on_error(error)
    
    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed"""
        self._connected = False
        logger.warning(
            f"[FX_WS] WebSocket closed (code={close_status_code}, msg={close_msg})"
        )
```

**의존성:**
- `websocket-client` 라이브러리 (sync WebSocket client)
- `pip install websocket-client`

---

### 4.2 WebSocketFxRateProvider

**파일:** `arbitrage/common/currency.py` (확장)

**구조:**
```python
class WebSocketFxRateProvider:
    """
    WebSocket 기반 FX Rate Provider (D80-4).
    
    Features:
    - Binance WebSocket Mark Price Stream (USDT→USD)
    - Event-driven FxCache 업데이트
    - HTTP fallback (RealFxRateProvider composition)
    - Auto-reconnect & graceful degradation
    
    Architecture:
        WebSocket (push) → FxCache
                ↓ (fallback)
        RealFxRateProvider (HTTP) → FxCache
                ↓ (fallback)
        StaticFxRateProvider
    
    Example:
        fx = WebSocketFxRateProvider()
        fx.start()  # Start WebSocket
        rate = fx.get_rate(Currency.USDT, Currency.KRW)
        fx.stop()  # Stop WebSocket
    """
    
    def __init__(
        self,
        binance_symbol: str = "btcusdt",
        cache_ttl_seconds: float = 3.0,
        http_timeout: float = 2.0,
        enable_websocket: bool = True,
    ):
        """
        Args:
            binance_symbol: Binance futures symbol
            cache_ttl_seconds: 캐시 TTL (초)
            http_timeout: HTTP 타임아웃 (초)
            enable_websocket: WebSocket 활성화 여부 (False면 HTTP-only)
        """
        # HTTP fallback provider
        self.real_fx_provider = RealFxRateProvider(
            cache_ttl_seconds=cache_ttl_seconds,
            http_timeout=http_timeout,
        )
        
        # Shared cache (WS와 HTTP가 동일 캐시 사용)
        self.cache = self.real_fx_provider.cache
        
        # WebSocket client
        self.enable_websocket = enable_websocket
        self.ws_client = None
        
        if enable_websocket:
            from .fx_ws_client import BinanceFxWebSocketClient
            self.ws_client = BinanceFxWebSocketClient(
                symbol=binance_symbol,
                on_rate_update=self._on_ws_rate_update,
                on_error=self._on_ws_error,
            )
        
        logger.info(
            f"[FX_PROVIDER] WebSocketFxRateProvider initialized "
            f"(websocket={enable_websocket}, cache_ttl={cache_ttl_seconds}s)"
        )
    
    def start(self) -> None:
        """Start WebSocket client"""
        if self.ws_client:
            self.ws_client.start()
            logger.info("[FX_PROVIDER] WebSocket FX stream started")
    
    def stop(self) -> None:
        """Stop WebSocket client"""
        if self.ws_client:
            self.ws_client.stop()
            logger.info("[FX_PROVIDER] WebSocket FX stream stopped")
    
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """
        환율 조회 (WebSocket cache 우선, HTTP fallback).
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율 (Decimal)
        """
        # 1. Cache 조회 (WS 또는 HTTP가 업데이트)
        cached_rate = self.cache.get(base, quote)
        if cached_rate is not None:
            logger.debug(
                f"[FX_PROVIDER] Cache HIT (WS/HTTP): {base.value}→{quote.value} = {cached_rate}"
            )
            return cached_rate
        
        # 2. Cache miss → HTTP fallback
        logger.debug(
            f"[FX_PROVIDER] Cache MISS, using HTTP fallback: {base.value}→{quote.value}"
        )
        return self.real_fx_provider.get_rate(base, quote)
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """환율 업데이트 시각"""
        return self.real_fx_provider.get_updated_at(base, quote)
    
    def is_stale(self, base: Currency, quote: Currency) -> bool:
        """환율 staleness 확인"""
        return self.real_fx_provider.is_stale(base, quote)
    
    def is_websocket_connected(self) -> bool:
        """WebSocket 연결 상태 확인"""
        if not self.ws_client:
            return False
        return self.ws_client.is_connected()
    
    def _on_ws_rate_update(self, rate: Decimal, timestamp: float) -> None:
        """
        WebSocket rate update callback.
        
        Args:
            rate: USDT→USD 환율
            timestamp: 업데이트 시각
        """
        # Update cache: USDT→USD
        self.cache.set(Currency.USDT, Currency.USD, rate, updated_at=timestamp)
        logger.debug(f"[FX_PROVIDER] WS update: USDT→USD = {rate}")
        
        # Chain: USDT→KRW (USDT→USD × USD→KRW)
        # USD→KRW는 HTTP에서 가져온 값 재사용 (캐시에 있으면)
        usd_krw = self.cache.get(Currency.USD, Currency.KRW)
        if usd_krw is not None:
            usdt_krw = rate * usd_krw
            self.cache.set(Currency.USDT, Currency.KRW, usdt_krw, updated_at=timestamp)
            logger.debug(f"[FX_PROVIDER] WS chain: USDT→KRW = {usdt_krw}")
    
    def _on_ws_error(self, error: Exception) -> None:
        """WebSocket error callback"""
        logger.error(f"[FX_PROVIDER] WebSocket error: {error}")
```

---

### 4.3 Metrics Integration

**파일:** `arbitrage/monitoring/cross_exchange_metrics.py` (확장)

**새 메서드:**
```python
def record_fx_ws_metrics(
    self,
    connected: bool,
    reconnect_count: int,
    message_count: int,
    error_count: int,
    last_message_age: float,
) -> None:
    """
    WebSocket FX metrics 기록.
    
    Args:
        connected: WebSocket 연결 상태 (0/1)
        reconnect_count: 재연결 횟수
        message_count: 수신 메시지 수
        error_count: 에러 발생 횟수
        last_message_age: 마지막 메시지 이후 경과 시간 (초)
    """
    if self.backend is None:
        return
    
    labels = {}  # 필요 시 추가 label
    
    # Gauge: WebSocket 연결 상태
    self.backend.set_gauge(
        "cross_fx_ws_connected",
        labels,
        1.0 if connected else 0.0
    )
    
    # Counter: 재연결 횟수
    self.backend.set_gauge(
        "cross_fx_ws_reconnect_total",
        labels,
        float(reconnect_count)
    )
    
    # Counter: 수신 메시지 수
    self.backend.set_gauge(
        "cross_fx_ws_message_total",
        labels,
        float(message_count)
    )
    
    # Counter: 에러 발생 횟수
    self.backend.set_gauge(
        "cross_fx_ws_error_total",
        labels,
        float(error_count)
    )
    
    # Gauge: 마지막 메시지 이후 경과 시간
    self.backend.set_gauge(
        "cross_fx_ws_last_message_seconds",
        labels,
        last_message_age
    )
```

---

## 5. 테스트 전략

### 5.1 Unit Tests (~15개)

**파일:** `tests/test_d80_4_websocket_fx_provider.py` (NEW)

#### A. WebSocket Client Tests (5)
1. ✅ Message parsing (mock WebSocket message → rate extraction)
2. ✅ FxCache 업데이트 callback (on_rate_update 호출 확인)
3. ✅ Reconnect logic (연결 실패 → backoff → 재시도)
4. ✅ Max reconnect attempts (10회 초과 시 중단)
5. ✅ Start/Stop (Thread 시작/종료)

#### B. WebSocketFxRateProvider Tests (6)
6. ✅ get_rate() with WS cache hit
7. ✅ get_rate() with cache miss → HTTP fallback
8. ✅ WebSocket update → FxCache → get_rate() 반영
9. ✅ WebSocket disabled (enable_websocket=False) → HTTP-only
10. ✅ WebSocket error → HTTP fallback 동작
11. ✅ is_websocket_connected() 상태 확인

#### C. Integration Tests (4)
12. ✅ Executor + WebSocketFxRateProvider 통합
13. ✅ WebSocket update → Executor._estimate_order_cost() 반영
14. ✅ Metrics: cross_fx_ws_connected, reconnect_total, message_total
15. ✅ Backward compatibility (RealFxRateProvider 여전히 동작)

### 5.2 Mock Strategy

```python
# WebSocket message mock
def test_ws_message_parsing():
    mock_message = json.dumps({
        "e": "markPriceUpdate",
        "E": 1701449123450,
        "s": "BTCUSDT",
        "p": "97000.00",
        "r": "0.0001"
    })
    
    client = BinanceFxWebSocketClient()
    # Mock _on_message() 호출
    client._on_message(None, mock_message)
    
    # Callback이 호출되었는지 확인
    assert callback_called
```

### 5.3 Non-Functional Tests

- **재연결 로직:** 연결 실패 시 exponential backoff 동작 확인
- **Fallback:** WebSocket 장애 시 HTTP fallback 자동 전환
- **Thread Safety:** FxCache 동시 접근 시 race condition 없음

---

## 6. 기존 구조와의 통합 전략

### 6.1 Composition over Inheritance

**설계 결정:** `WebSocketFxRateProvider`는 `RealFxRateProvider`를 **composition**으로 포함

**이유:**
- ✅ `RealFxRateProvider`의 HTTP/Static fallback 로직 재사용
- ✅ 인터페이스(`FxRateProvider`) 준수
- ✅ WebSocket 장애 시 자동으로 HTTP fallback
- ✅ 기존 코드 변경 최소화

**구조:**
```python
class WebSocketFxRateProvider:
    def __init__(self):
        self.real_fx_provider = RealFxRateProvider(...)  # HTTP fallback
        self.cache = self.real_fx_provider.cache  # Shared cache
        self.ws_client = BinanceFxWebSocketClient(...)  # WebSocket
    
    def get_rate(self, base, quote):
        # 1. Cache 조회 (WS 또는 HTTP가 업데이트)
        cached = self.cache.get(base, quote)
        if cached:
            return cached
        
        # 2. HTTP fallback
        return self.real_fx_provider.get_rate(base, quote)
```

### 6.2 Executor Integration

**변경 방침:**
- Executor는 **인터페이스(`FxRateProvider`)에만 의존**
- 기본값은 여전히 `RealFxRateProvider` (HTTP-only)
- `WebSocketFxRateProvider`는 옵션으로 주입 가능

**코드 예시:**
```python
# AS-IS (D80-3)
executor = CrossExchangeExecutor(
    ...,
    fx_provider=None,  # RealFxRateProvider (HTTP)
)

# TO-BE (D80-4, 선택적)
fx = WebSocketFxRateProvider()
fx.start()  # Start WebSocket
executor = CrossExchangeExecutor(
    ...,
    fx_provider=fx,  # WebSocket + HTTP fallback
)
```

**Note:** 이번 단계에서는 **테스트 코드에서만 WebSocket 사용**, 실제 운영 모드는 이후 PHASE에서 전환

---

## 7. Risks & Mitigations

### 7.1 Risk: WebSocket Library 의존성
- **Impact:** `websocket-client` 라이브러리 장애 시 WebSocket 기능 중단
- **Mitigation:**
  - HTTP fallback 자동 전환
  - `enable_websocket=False` 옵션으로 HTTP-only 모드 지원
  - 의존성 설치 실패 시 경고 로그 + HTTP-only 모드

### 7.2 Risk: WebSocket 연결 불안정
- **Impact:** 재연결 반복으로 리소스 낭비
- **Mitigation:**
  - Exponential backoff (1s → 2s → 4s → ... → 60s)
  - 최대 재시도 10회 후 HTTP-only 모드
  - Metrics로 재연결 빈도 모니터링

### 7.3 Risk: Thread-safety
- **Impact:** FxCache 동시 접근 시 race condition
- **Mitigation:**
  - FxCache에 `threading.Lock` 추가 (향후)
  - Python GIL로 인해 Dict 접근은 대부분 thread-safe (단, 완벽하지 않음)
  - 필요 시 `queue.Queue`로 WebSocket → Main Thread 메시지 전달

---

## 8. Done Criteria

### 8.1 Implementation
- [ ] `arbitrage/common/fx_ws_client.py` 구현 (BinanceFxWebSocketClient)
- [ ] `arbitrage/common/currency.py` 확장 (WebSocketFxRateProvider)
- [ ] `arbitrage/monitoring/cross_exchange_metrics.py` 확장 (WS metrics)

### 8.2 Testing
- [ ] Unit tests: 15/15 PASS
- [ ] Integration tests: 포함
- [ ] 전체 회귀 테스트: 172 + 15 = 187 PASS

### 8.3 Documentation
- [ ] `docs/D80_4_WEBSOCKET_FX_STREAM.md` 작성
- [ ] `D_ROADMAP.md` 업데이트 (D80-4 COMPLETE)

### 8.4 Git Commit
- [ ] Git status / diff --stat 확인
- [ ] 커밋 메시지: `[D80-4] WebSocket FX Stream Provider & FX WS Metrics`

---

## 9. Next Steps (D80-5)

### D80-5: Multi-Source FX Aggregation (선택적)
- 복수 거래소 WebSocket 집계 (Binance + OKX + Bybit)
- Median/Average FX rate 계산
- Outlier detection (비정상 환율 필터링)

---

## 10. References

- [Binance WebSocket API - Mark Price Stream](https://binance-docs.github.io/apidocs/futures/en/#mark-price-stream)
- [websocket-client Documentation](https://websocket-client.readthedocs.io/)
- D80-0: Currency Domain Design
- D80-1: Core Layer Integration
- D80-2: Exchange & Universe Integration
- D80-3: Real FX Provider Design

# D83-1: Real L2 WebSocket Provider 설계

**Date:** 2025-12-06  
**Status:** 📋 DESIGN PHASE  
**Author:** Windsurf AI

---

## 📋 설계 목표

### 주요 목표
Real WebSocket 기반 L2 Orderbook Provider를 MarketDataProvider 인터페이스로 통합하여, Executor가 실제 거래소 L2 데이터를 소비할 수 있도록 한다.

### 구체적 요구사항
1. **Upbit Spot BTC/KRW** 기준 단일 심볼로 시작
2. **MarketDataProvider 인터페이스** 완전 준수
3. **WebSocket 연결 관리**: 연결, 재연결, 에러 처리
4. **최신 스냅샷 유지**: `OrderBookSnapshot` 형태로 메모리 버퍼링
5. **테스트 가능 설계**: WebSocket 레이어 주입 가능

---

## 🏗️ 아키텍처 설계

### 1. 클래스 구조

```
┌─────────────────────────────────────────┐
│   MarketDataProvider (Interface)        │
│   - get_latest_snapshot(symbol)         │
│   - start()                              │
│   - stop()                               │
└────────────┬────────────────────────────┘
             │ implements
             ▼
┌─────────────────────────────────────────┐
│   UpbitL2WebSocketProvider               │
│   - ws_adapter: UpbitWebSocketAdapter   │
│   - latest_snapshots: Dict[str, ...]    │
│   - _is_running: bool                    │
│   - _reconnect_count: int                │
└────────────┬────────────────────────────┘
             │ uses
             ▼
┌─────────────────────────────────────────┐
│   UpbitWebSocketAdapter (기존)          │
│   - connect()                            │
│   - subscribe(channels)                  │
│   - on_message(msg)                      │
└─────────────────────────────────────────┘
```

### 2. 책임 분리

#### UpbitL2WebSocketProvider
- **책임:** MarketDataProvider 인터페이스 구현, 최신 스냅샷 제공
- **역할:**
  - `UpbitWebSocketAdapter` 관리 (생성, 시작, 종료)
  - 콜백을 통해 스냅샷 수신 → 메모리 버퍼링
  - `get_latest_snapshot()` 구현

#### UpbitWebSocketAdapter (기존 재사용)
- **책임:** WebSocket 연결, 메시지 파싱, 콜백 호출
- **역할:**
  - Upbit WebSocket 연결/재연결
  - orderbook 메시지 파싱 → `OrderBookSnapshot` 변환
  - 콜백 호출 (`_on_snapshot()`)

---

## 📐 상세 설계

### 클래스: UpbitL2WebSocketProvider

#### 초기화
```python
class UpbitL2WebSocketProvider(MarketDataProvider):
    """
    Real L2 WebSocket Provider (Upbit)
    
    D83-1: Upbit Public WebSocket 기반 실시간 L2 Orderbook 제공
    """
    
    def __init__(
        self,
        symbols: List[str],
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
        max_reconnect_attempts: int = 5,
        reconnect_backoff: float = 2.0,
    ):
        """
        Args:
            symbols: 구독할 심볼 목록 (예: ["KRW-BTC"])
            heartbeat_interval: heartbeat 간격 (초)
            timeout: 연결 타임아웃 (초)
            max_reconnect_attempts: 최대 재연결 시도 횟수
            reconnect_backoff: 재연결 backoff 배수
        """
        self.symbols = symbols
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_backoff = reconnect_backoff
        
        # 최신 스냅샷 버퍼
        self.latest_snapshots: Dict[str, OrderBookSnapshot] = {}
        
        # 상태 관리
        self._is_running = False
        self._reconnect_count = 0
        self._ws_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # WebSocket Adapter (콜백 주입)
        self.ws_adapter = UpbitWebSocketAdapter(
            symbols=symbols,
            callback=self._on_snapshot,
            heartbeat_interval=heartbeat_interval,
            timeout=timeout,
        )
```

#### 메서드: start()
```python
def start(self) -> None:
    """
    WebSocket 연결 및 백그라운드 루프 시작
    
    - 별도 스레드에서 asyncio event loop 실행
    - WebSocket 연결 및 구독
    """
    if self._is_running:
        logger.warning("[D83-1_L2] Provider already running")
        return
    
    self._is_running = True
    
    # 별도 스레드에서 asyncio loop 실행
    import threading
    self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
    self._thread.start()
    
    logger.info(f"[D83-1_L2] WebSocket provider started for {self.symbols}")
```

#### 메서드: _run_event_loop()
```python
def _run_event_loop(self) -> None:
    """
    별도 스레드에서 asyncio event loop 실행
    
    - WebSocket 연결 및 구독
    - 에러 발생 시 재연결 시도
    """
    self._loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self._loop)
    
    try:
        self._loop.run_until_complete(self._connect_and_subscribe())
    except Exception as e:
        logger.error(f"[D83-1_L2] Event loop error: {e}")
    finally:
        self._loop.close()
```

#### 메서드: _connect_and_subscribe()
```python
async def _connect_and_subscribe(self) -> None:
    """
    WebSocket 연결 및 구독 (재연결 로직 포함)
    """
    while self._is_running and self._reconnect_count < self.max_reconnect_attempts:
        try:
            # 연결
            await self.ws_adapter.connect()
            
            # 구독
            await self.ws_adapter.subscribe(self.symbols)
            
            # 메시지 수신 루프 (blocking)
            while self._is_running:
                await asyncio.sleep(0.1)  # 연결 유지
            
        except Exception as e:
            self._reconnect_count += 1
            backoff_delay = self.reconnect_backoff ** self._reconnect_count
            
            logger.error(
                f"[D83-1_L2] Connection error (attempt {self._reconnect_count}/{self.max_reconnect_attempts}): {e}"
            )
            
            if self._reconnect_count < self.max_reconnect_attempts:
                logger.info(f"[D83-1_L2] Reconnecting in {backoff_delay:.1f}s...")
                await asyncio.sleep(backoff_delay)
            else:
                logger.error("[D83-1_L2] Max reconnect attempts reached, giving up")
                self._is_running = False
                break
```

#### 메서드: stop()
```python
def stop(self) -> None:
    """
    WebSocket 연결 종료
    """
    if not self._is_running:
        return
    
    self._is_running = False
    
    # WebSocket Adapter 종료
    if self._loop and not self._loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            self.ws_adapter.disconnect(),
            self._loop
        )
    
    # 스레드 종료 대기 (타임아웃)
    if self._thread:
        self._thread.join(timeout=5.0)
    
    logger.info("[D83-1_L2] WebSocket provider stopped")
```

#### 메서드: get_latest_snapshot()
```python
def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
    """
    최신 호가 스냅샷 반환
    
    Args:
        symbol: 거래 쌍 (예: "KRW-BTC")
    
    Returns:
        OrderBookSnapshot 또는 None (데이터 없음)
    """
    return self.latest_snapshots.get(symbol)
```

#### 콜백: _on_snapshot()
```python
def _on_snapshot(self, snapshot: OrderBookSnapshot) -> None:
    """
    WebSocket Adapter 콜백: 스냅샷 업데이트
    
    Args:
        snapshot: Upbit 호가 스냅샷
    """
    self.latest_snapshots[snapshot.symbol] = snapshot
    
    logger.debug(
        f"[D83-1_L2] Updated snapshot: {snapshot.symbol}, "
        f"bids={len(snapshot.bids)}, asks={len(snapshot.asks)}"
    )
```

---

## 🔄 재연결 전략

### 재연결 로직
1. **에러 발생 시:** WebSocket 연결 끊김 또는 메시지 파싱 에러
2. **재연결 시도:** `_reconnect_count < max_reconnect_attempts` 동안 반복
3. **Backoff 전략:** Exponential backoff (`reconnect_backoff ** attempt`)
   - 1차: 2초 대기
   - 2차: 4초 대기
   - 3차: 8초 대기
   - ...
4. **재구독:** 재연결 성공 시 자동으로 `subscribe()` 호출

### 에러 처리
- **연결 에러:** 로그 기록 → 재연결 시도
- **파싱 에러:** 로그 기록 → 다음 메시지 대기 (연결 유지)
- **Max attempt 도달:** 로그 기록 → Provider 종료

---

## 🧵 스레딩 모델

### 선택: 별도 스레드 + asyncio event loop

**이유:**
1. **Executor는 동기 코드:** `get_latest_snapshot()`을 동기 메서드로 호출
2. **WebSocket은 비동기:** `asyncio` 기반 연결 유지
3. **스레드 분리:** 메인 스레드 (Executor) + WebSocket 스레드

**구조:**
```
┌────────────────────────────┐
│   Main Thread              │
│   - PaperExecutor          │
│   - get_latest_snapshot()  │  (동기 호출)
└────────┬───────────────────┘
         │ 스레드 간 Dict 공유 (latest_snapshots)
         ▼
┌────────────────────────────┐
│   WebSocket Thread         │
│   - asyncio event loop     │
│   - ws_adapter.connect()   │
│   - _on_snapshot() 콜백    │
└────────────────────────────┘
```

**스레드 안전성:**
- `latest_snapshots: Dict[str, OrderBookSnapshot]`는 GIL 보호
- 단순 read/write 연산만 수행 (추가 Lock 불필요)

---

## 🧪 테스트 가능 설계

### WebSocket 레이어 주입
```python
class UpbitL2WebSocketProvider(MarketDataProvider):
    def __init__(
        self,
        symbols: List[str],
        ws_adapter: Optional[UpbitWebSocketAdapter] = None,  # 테스트용 주입
        ...
    ):
        if ws_adapter:
            self.ws_adapter = ws_adapter  # 주입된 adapter 사용
        else:
            self.ws_adapter = UpbitWebSocketAdapter(...)  # 실제 adapter 생성
```

### 테스트 전략
1. **유닛 테스트:** Fake WebSocketAdapter 주입
   - 가짜 메시지 스트림 생성
   - `_on_snapshot()` 콜백 검증
   - `get_latest_snapshot()` 반환값 검증

2. **통합 테스트:** 실제 Upbit WebSocket 연결
   - 네트워크 호출 없이 초기화/종료만 검증
   - 또는 Upbit testnet 사용 (있다면)

---

## 📊 모니터링 및 메트릭

### 로그 레벨
- **INFO:** 연결, 재연결, 종료
- **DEBUG:** 스냅샷 업데이트
- **WARNING:** 연결 끊김, 파싱 에러
- **ERROR:** 치명적 에러, max attempt 도달

### 메트릭 (향후 확장)
- `websocket_reconnect_count`: 재연결 횟수
- `latest_snapshot_age_ms`: 최신 스냅샷 age
- `snapshot_update_frequency_hz`: 스냅샷 업데이트 빈도

---

## 🔗 기존 코드와의 통합

### Executor 생성 (변경 없음)
```python
# D84-2 기존 코드
market_data_provider = MockMarketDataProvider()

# D83-1 변경 후
market_data_provider = UpbitL2WebSocketProvider(symbols=["KRW-BTC"])

# Executor 생성 (동일)
executor = executor_factory.create_paper_executor(
    ...,
    market_data_provider=market_data_provider,  # Provider만 교체
    ...
)
```

### Runner 스크립트
- CLI 인자: `--l2-source=mock|real`
- Provider 생성 로직만 분기

---

## 📝 제약 사항 및 한계

### D83-1 범위 내 제약
1. **단일 거래소:** Upbit만 지원 (Binance는 D83-2+)
2. **단일 심볼:** BTC/KRW 기준 (멀티심볼은 기존 코드 지원)
3. **Best Level만:** Multi-level aggregation은 D83-2+
4. **재연결 횟수 제한:** 5회까지만 시도

### 향후 확장 (D83-2+)
- Binance WebSocket 지원
- Multi-level aggregation (price impact 계산)
- 재연결 무제한 (auto-recover)
- Health check endpoint

---

## ✅ 설계 완료 체크리스트

- [x] MarketDataProvider 인터페이스 준수
- [x] 기존 UpbitWebSocketAdapter 재사용
- [x] 재연결 전략 정의 (exponential backoff)
- [x] 스레딩 모델 결정 (별도 스레드 + asyncio)
- [x] 테스트 가능 설계 (adapter 주입)
- [x] 에러 처리 전략
- [x] DO-NOT-TOUCH 원칙 준수 (기존 코드 영향 최소화)

---

**설계 완료 시각:** 2025-12-06  
**Next Step:** STEP 2 - 코드 구현

# D49 설계 문서: WebSocket Market Data Layer

**작성일:** 2025-11-17  
**상태:** 설계 단계

---

## 📋 Executive Summary

D49는 **WebSocket 기반 실시간 호가 스트림 레이어**를 도입합니다.

**핵심 목표:**
- REST 폴링 기반 `get_orderbook()` → **WebSocket 스트림 기반 실시간 업데이트**로 전환
- 레이턴시 개선: ~1000ms (REST 폴링) → ~100ms (WebSocket)
- REST는 **fallback 용도**로만 사용
- **엔진/전략/리스크/포트폴리오 로직은 변경 없음**

---

## 🏗️ 아키텍처 개요

### 현재 (D48): REST 기반

```
┌─────────────────────────────────────────────────┐
│ ArbitrageLiveRunner (메인 루프)                 │
│  - poll_interval_seconds = 1.0                  │
│  - 매 루프마다 get_orderbook() 호출             │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   ┌─────────────┐  ┌─────────────┐
   │ Upbit REST  │  │ Binance REST│
   │ get_order   │  │ get_order   │
   │ book()      │  │ book()      │
   └─────────────┘  └─────────────┘
        │                 │
   HTTP GET          HTTP GET
   (100ms)           (200ms)
        │                 │
   ┌────┴────────────────┴────┐
   │ REST 호출 누적 시간: ~300ms│
   │ 루프 시간: ~1000ms         │
   └────────────────────────────┘
```

**문제점:**
- 호출 빈도 제한 (레이트리밋)
- 높은 레이턴시 (300ms+)
- 불필요한 네트워크 트래픽

### 목표 (D49): WebSocket 기반

```
┌──────────────────────────────────────────────────┐
│ ArbitrageLiveRunner (메인 루프)                  │
│  - MarketDataProvider 인터페이스 사용            │
│  - get_latest_snapshot() 호출 (메모리 읽기)    │
└────────────────┬─────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   ┌──────────────┐  ┌──────────────┐
   │ Upbit WS     │  │ Binance WS   │
   │ Adapter      │  │ Adapter      │
   │ (백그라운드) │  │ (백그라운드) │
   └──────────────┘  └──────────────┘
        │                 │
   WebSocket          WebSocket
   (실시간)           (실시간)
        │                 │
   ┌────┴────────────────┴────────┐
   │ 메모리 버퍼 (최신 스냅샷)    │
   │ 루프 시간: ~10ms (메모리 읽기)│
   └────────────────────────────────┘
```

**개선점:**
- 실시간 업데이트 (< 100ms)
- 루프 시간 단축 (1000ms → 10ms)
- 네트워크 효율성 증대

---

## 📊 데이터 플로우 비교

### REST 기반 (현재)

```
시간 0ms:  LiveRunner 루프 시작
시간 0ms:  get_orderbook("KRW-BTC") 호출
시간 100ms: Upbit REST 응답 수신
시간 100ms: get_orderbook("BTCUSDT") 호출
시간 300ms: Binance REST 응답 수신
시간 300ms: ArbitrageEngine 신호 생성
시간 300ms: 거래 판단 및 주문 실행
시간 1000ms: 루프 종료 (다음 루프 대기)

총 데이터 레이턴시: ~300ms
루프 시간: ~1000ms
```

### WebSocket 기반 (목표)

```
백그라운드 (지속 실행):
  - Upbit WS 스트림 수신 → 메모리 버퍼 업데이트 (< 50ms)
  - Binance WS 스트림 수신 → 메모리 버퍼 업데이트 (< 50ms)

시간 0ms:  LiveRunner 루프 시작
시간 0ms:  get_latest_snapshot() 호출 (메모리 읽기)
시간 1ms:  스냅샷 반환 (이미 최신 상태)
시간 1ms:  ArbitrageEngine 신호 생성
시간 1ms:  거래 판단 및 주문 실행
시간 10ms: 루프 종료

총 데이터 레이턴시: < 100ms (WS 스트림 기반)
루프 시간: ~10ms (메모리 읽기만)
```

---

## 🔧 구현 구조

### 1. WebSocket Client 베이스 (`ws_client.py`)

```python
class BaseWebSocketClient(ABC):
    """
    WebSocket 클라이언트 베이스 클래스
    
    책임:
    - 연결/재연결 관리
    - ping/pong 및 heartbeat
    - 메시지 수신 루프
    - 에러 처리 및 분류
    """
    
    @abstractmethod
    async def connect(self):
        """WebSocket 연결"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """WebSocket 종료"""
        pass
    
    @abstractmethod
    async def subscribe(self, channels: List[str]):
        """채널 구독"""
        pass
    
    @abstractmethod
    async def receive_loop(self):
        """메시지 수신 루프 (백그라운드)"""
        pass
    
    @abstractmethod
    def on_message(self, message: dict):
        """메시지 핸들러 (구현체에서 오버라이드)"""
        pass
    
    def on_error(self, error: Exception):
        """에러 핸들러"""
        pass
    
    def on_reconnect(self):
        """재연결 핸들러"""
        pass
```

**라이브러리 선택:**
- `websockets` (표준 라이브러리 기반, 가볍고 안정적)
- 또는 `aiohttp` (asyncio 기반, 더 많은 기능)

### 2. Upbit WebSocket Adapter

```python
class UpbitWebSocketAdapter(BaseWebSocketClient):
    """
    Upbit WebSocket 어댑터
    
    채널:
    - orderbook.KRW-BTC (호가 스트림)
    - ticker.KRW-BTC (체결 정보)
    
    메시지 포맷:
    {
        "type": "orderbook",
        "code": "KRW-BTC",
        "orderbook": {
            "market": "KRW-BTC",
            "timestamp": 1234567890,
            "total_ask_size": 100.0,
            "total_bid_size": 100.0,
            "orderbook_units": [
                {"ask_price": 50000000, "ask_size": 1.0, ...},
                {"bid_price": 49900000, "bid_size": 1.0, ...}
            ]
        }
    }
    """
    
    def on_message(self, message: dict):
        # 메시지 파싱 → OrderbookSnapshot 변환
        snapshot = self._parse_message(message)
        self._update_buffer(snapshot)
    
    def get_latest_snapshot(self) -> OrderbookSnapshot:
        # 메모리 버퍼에서 최신 스냅샷 반환
        return self._buffer.get_latest()
```

### 3. Binance WebSocket Adapter

```python
class BinanceWebSocketAdapter(BaseWebSocketClient):
    """
    Binance WebSocket 어댑터
    
    채널:
    - btcusdt@depth20 (호가 스트림)
    - btcusdt@ticker (체결 정보)
    
    메시지 포맷:
    {
        "e": "depthUpdate",
        "E": 1234567890,
        "s": "BTCUSDT",
        "b": [["50000.0", "1.0"], ...],  # bids
        "a": [["50100.0", "1.0"], ...]   # asks
    }
    """
    
    def on_message(self, message: dict):
        # 메시지 파싱 → OrderbookSnapshot 변환
        snapshot = self._parse_message(message)
        self._update_buffer(snapshot)
    
    def get_latest_snapshot(self) -> OrderbookSnapshot:
        # 메모리 버퍼에서 최신 스냅샷 반환
        return self._buffer.get_latest()
```

### 4. 공통 도메인 모델

```python
@dataclass
class OrderbookSnapshot:
    """
    호가 스냅샷 (거래소 중립적)
    
    필드:
    - exchange: "upbit" | "binance"
    - symbol: "KRW-BTC" | "BTCUSDT"
    - timestamp: Unix timestamp (ms)
    - bids: List[Tuple[float, float]]  # [(price, size), ...]
    - asks: List[Tuple[float, float]]
    - sequence: 메시지 시퀀스 번호 (중복 감지용)
    """
    exchange: str
    symbol: str
    timestamp: int
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    sequence: Optional[int] = None
```

### 5. MarketDataProvider 인터페이스

```python
class MarketDataProvider(ABC):
    """
    호가 데이터 소스 추상화
    
    구현체:
    - RestMarketDataProvider: REST 폴링 기반
    - WebSocketMarketDataProvider: WebSocket 스트림 기반
    """
    
    @abstractmethod
    def get_latest_snapshot(self, symbol: str) -> OrderbookSnapshot:
        """최신 호가 스냅샷 반환"""
        pass
    
    @abstractmethod
    def start(self):
        """데이터 소스 시작 (WS의 경우 백그라운드 루프)"""
        pass
    
    @abstractmethod
    def stop(self):
        """데이터 소스 종료"""
        pass
```

---

## 🔄 REST Fallback 전략

### 시나리오 1: WebSocket 정상 동작

```
WS 스트림 → 메모리 버퍼 (최신)
LiveRunner → get_latest_snapshot() → 메모리 읽기 (< 1ms)
```

### 시나리오 2: WebSocket 장애 (연결 끊김)

```
WS 스트림 → [연결 끊김] → 자동 재연결 (exponential backoff)
재연결 중 (< 30초):
  - LiveRunner → get_latest_snapshot() → 메모리 버퍼 (마지막 값)
  - 또는 REST fallback 호출 (WARN 로그)

재연결 성공:
  - WS 스트림 → 메모리 버퍼 (최신 업데이트 재개)
```

### 시나리오 3: WebSocket 비활성화 (설정)

```
config: data_source: "rest"
LiveRunner → MarketDataProvider (RestMarketDataProvider)
→ get_orderbook() (기존 REST 호출)
```

---

## 📝 설정 파일 확장

### 기존 (D48)

```yaml
exchanges:
  a:
    type: upbit_spot
    config:
      api_key: ${UPBIT_API_KEY}
      api_secret: ${UPBIT_API_SECRET}
      base_url: https://api.upbit.com
      live_enabled: false
      rate_limit:
        max_requests_per_sec: 5
        max_retry: 3
        base_backoff_seconds: 0.5
```

### 확장 (D49)

```yaml
# 데이터 소스 선택
data_source: "rest"  # "rest" | "ws"

# WebSocket 설정 (data_source="ws"일 때만 사용)
ws:
  enabled: false  # 기본값: 비활성화 (안전)
  
  # 재연결 정책
  reconnect_backoff:
    initial: 1.0      # 초기 대기: 1초
    max: 30.0         # 최대 대기: 30초
    multiplier: 2.0   # exponential backoff
  
  # Upbit WebSocket 설정
  upbit:
    url: "wss://api.upbit.com/websocket/v1"
    channels:
      - "orderbook"
      - "ticker"
    heartbeat_interval: 30  # 초
  
  # Binance WebSocket 설정
  binance:
    url: "wss://fstream.binance.com/stream"
    channels:
      - "depth"
      - "ticker"
    heartbeat_interval: 30  # 초

# REST 설정 (fallback 또는 data_source="rest"일 때)
exchanges:
  a:
    type: upbit_spot
    config:
      api_key: ${UPBIT_API_KEY}
      api_secret: ${UPBIT_API_SECRET}
      base_url: https://api.upbit.com
      live_enabled: false
      rate_limit:
        max_requests_per_sec: 5
        max_retry: 3
        base_backoff_seconds: 0.5
```

---

## 🧪 테스트 전략

### 단위 테스트

1. **test_d49_ws_client.py**
   - 연결/재연결 로직
   - ping/pong 처리
   - 메시지 파싱
   - 에러 분류

2. **test_d49_upbit_ws_adapter.py**
   - Upbit 메시지 파싱
   - OrderbookSnapshot 변환
   - 버퍼 업데이트

3. **test_d49_binance_ws_adapter.py**
   - Binance 메시지 파싱
   - OrderbookSnapshot 변환
   - 버퍼 업데이트

4. **test_d49_market_data_provider.py**
   - RestMarketDataProvider (기존 동작 보장)
   - WebSocketMarketDataProvider (mock 기반)
   - 데이터 소스 선택 로직

### 통합 테스트

1. **LiveRunner + REST (기존)**
   - `data_source="rest"` → 기존 회귀 테스트 통과 확인

2. **LiveRunner + WebSocket (Mock)**
   - `data_source="ws"` → mock WS provider로 1-2 루프 검증

### 스모크 테스트

```bash
# Paper 모드 (data_source="rest")
python -m scripts.run_arbitrage_live \
  --config configs/live/arbitrage_live_paper_example.yaml \
  --mode paper \
  --max-runtime-seconds 30

# Live 모드 (data_source="rest", enabled=false)
python -m scripts.run_arbitrage_live \
  --config configs/live/arbitrage_live_upbit_binance_trading.yaml \
  --mode live_trading \
  --max-runtime-seconds 20
```

---

## ⚠️ 제약사항 및 주의사항

### 1. 엔진 코어 보호

- ✅ ArbitrageEngine 로직 변경 금지
- ✅ LiveGuard 비즈니스 규칙 변경 금지
- ✅ 포트폴리오/리스크 로직 변경 금지

### 2. WebSocket 기본값

- `ws.enabled: false` (기본값)
- 실거래 전까지 절대 활성화 금지

### 3. 라이브러리 선택

- `websockets` 또는 `aiohttp` 중 선택
- 이유: 표준 라이브러리 기반, 가볍고 안정적

### 4. 재연결 정책

- exponential backoff (1s → 2s → 4s → ... → 30s)
- 최대 30초 대기 후 재시도

### 5. 메모리 버퍼

- 최신 스냅샷만 유지 (메모리 효율)
- 시퀀스 번호로 중복 감지

---

## 📈 성능 목표

| 메트릭 | REST (현재) | WebSocket (목표) | 개선 |
|--------|-----------|-----------------|------|
| 호가 레이턴시 | ~300ms | < 100ms | 3배 |
| 루프 시간 | ~1000ms | ~10ms | 100배 |
| 네트워크 트래픽 | 높음 | 낮음 | ✅ |
| 레이트리밋 영향 | 높음 | 없음 | ✅ |

---

## 🚀 향후 단계 (D50+)

### D50: 모니터링 & 대시보드
- Grafana 통합
- 실시간 거래 통계
- WebSocket 상태 모니터링

### D51: 성능 최적화
- 호가 캐싱 (메모리)
- 병렬 요청 (asyncio)
- 자동 재연결 개선

### D52: 다중 거래소 확장
- 추가 거래소 WebSocket 지원
- 통합 호가 집계

---

## 📊 파일 구조

```
arbitrage/
├── exchanges/
│   ├── ws_client.py              # NEW: WebSocket 베이스 클래스
│   ├── upbit_spot.py             # MODIFIED: WS 어댑터 추가
│   ├── binance_futures.py        # MODIFIED: WS 어댑터 추가
│   └── market_data_provider.py   # NEW: 데이터 소스 추상화
├── live_runner.py                # MODIFIED: 최소 통합 (data_source 선택)
└── ...

tests/
├── test_d49_ws_client.py         # NEW
├── test_d49_upbit_ws_adapter.py  # NEW
├── test_d49_binance_ws_adapter.py # NEW
├── test_d49_market_data_provider.py # NEW
└── ...

configs/live/
└── arbitrage_live_upbit_binance_trading.yaml  # MODIFIED: ws 섹션 추가
```

---

**설계 문서 완료. 구현 단계로 진행.**

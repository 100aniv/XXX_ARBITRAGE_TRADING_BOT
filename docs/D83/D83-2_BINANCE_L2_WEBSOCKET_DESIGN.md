# D83-2: Binance L2 WebSocket Provider - 설계 문서

**작성일:** 2025-12-07  
**상태:** DESIGN COMPLETE

---

## 1. 목표 및 범위

### 1.1 목표

D83-1에서 구현한 Upbit L2 WebSocket Provider와 동일한 아키텍처로, **Binance L2 WebSocket Provider**를 구현한다.

**핵심 목표:**
- Binance Spot WebSocket API를 통해 실시간 L2 Orderbook 데이터를 수신
- `MarketDataProvider` 인터페이스 완전 준수
- D84-2 Runner에서 `--l2-source binance` 옵션으로 선택 가능
- BTC/USDT (Binance 표준 심볼) 기준 best-level L2 스냅샷 제공
- D83-1 Upbit Provider와 동일한 품질/안정성 보장

### 1.2 범위 (Scope)

**In-Scope:**
1. `BinanceWebSocketAdapter` 구현 (arbitrage/exchanges/binance_ws_adapter.py)
   - Binance WebSocket 연결/재연결/메시지 수신
   - depth stream 구독 및 파싱
   - OrderBookSnapshot 변환
2. `BinanceL2WebSocketProvider` 구현 (arbitrage/exchanges/binance_l2_ws_provider.py)
   - MarketDataProvider 인터페이스 구현
   - 별도 스레드 + asyncio event loop
   - 심볼 매핑 (BTCUSDT ↔ BTC)
3. D84-2 Runner 통합
   - `--l2-source` 확장: mock, real, upbit, binance
   - 하위 호환성 유지 (real → upbit alias)
4. 유닛 테스트 (tests/test_d83_2_binance_l2_provider.py)
   - FakeBinanceWebSocketAdapter 기반 테스트
5. Binance Real L2 PAPER 5분 스모크 테스트
   - Acceptance Criteria 검증

**Out-of-Scope (향후 단계):**
- Multi-exchange L2 Aggregation (Upbit + Binance 동시 사용) → D83-3
- Multi-symbol TopN 스캔 → 기존 엔진/다른 단계
- 20분+ Long-run PAPER → D84-2+
- Mock vs Real L2 분포 비교 → D84-3

### 1.3 제약 조건

**DO-NOT-TOUCH:**
- Executor 핵심 로직 (포지션/리스크/TP·SL)
- D77/D80/D82 기존 안정화 인프라
- MarketDataProvider 인터페이스 정의

**재사용 우선:**
- D83-1 UpbitL2WebSocketProvider 구조 그대로 재사용
- BaseWebSocketClient 공통 베이스 클래스 활용
- 기존 Runner/Executor/FillModel 통합 패턴 유지

---

## 2. 아키텍처 설계

### 2.1 컴포넌트 구조

```
┌─────────────────────────────────────────────────────────┐
│              D84-2 Runner (Main Thread)                 │
│  - ArgumentParser: --l2-source [mock|real|upbit|binance]│
│  - Provider 선택 로직                                    │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ (선택)
      ┌──────────┴──────────┬──────────────┐
      │                     │              │
      ▼                     ▼              ▼
┌──────────┐      ┌──────────────┐  ┌──────────────┐
│   Mock   │      │    Upbit     │  │   Binance    │
│ Provider │      │ L2 Provider  │  │ L2 Provider  │
└──────────┘      └──────┬───────┘  └──────┬───────┘
                         │                 │
                  ┌──────┴───────┐  ┌──────┴────────┐
                  │ Upbit WS     │  │ Binance WS    │
                  │ Adapter      │  │ Adapter       │
                  └──────┬───────┘  └──────┬────────┘
                         │                 │
                  ┌──────┴───────┐  ┌──────┴────────┐
                  │ Base WS      │  │ Base WS       │
                  │ Client       │  │ Client        │
                  └──────────────┘  └───────────────┘
```

### 2.2 BinanceWebSocketAdapter 설계

**위치:** `arbitrage/exchanges/binance_ws_adapter.py`

**책임:**
- Binance Spot WebSocket 연결 (`wss://stream.binance.com:9443/ws`)
- L2 Orderbook stream 구독 (`btcusdt@depth@100ms` 또는 `btcusdt@depth20@100ms`)
- 메시지 파싱 → `OrderBookSnapshot` 변환
- 콜백 기반으로 Provider에 스냅샷 전달

**주요 메서드:**
```python
class BinanceWebSocketAdapter(BaseWebSocketClient):
    def __init__(
        symbols: List[str],
        callback: Callable[[OrderBookSnapshot], None],
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
    )
    
    async def subscribe(channels: List[str]) -> None
        # Binance 구독 메시지 전송
        # {"method": "SUBSCRIBE", "params": ["btcusdt@depth@100ms"], "id": 1}
    
    def on_message(message: Dict[str, Any]) -> None
        # 수신 메시지 파싱 및 콜백 호출
    
    def _parse_message(message: Dict) -> Optional[OrderBookSnapshot]
        # Binance depth 메시지 → OrderBookSnapshot
```

**Binance WebSocket 메시지 포맷:**
```json
{
  "e": "depthUpdate",
  "E": 1710000000000,
  "s": "BTCUSDT",
  "U": 123456,
  "u": 123457,
  "b": [["50000.00", "1.5"], ["49999.00", "2.3"]],
  "a": [["50001.00", "1.2"], ["50002.00", "0.8"]]
}
```

**파싱 로직:**
- `"b"`: bids (price, qty)
- `"a"`: asks (price, qty)
- `"E"`: timestamp (milliseconds)
- `"s"`: symbol (BTCUSDT)

### 2.3 BinanceL2WebSocketProvider 설계

**위치:** `arbitrage/exchanges/binance_l2_ws_provider.py`

**책임:**
- `MarketDataProvider` 인터페이스 구현
- WebSocket 연결 관리 (재연결 포함)
- 최신 스냅샷 버퍼링 (심볼별)
- 스레드 안전성 보장

**주요 메서드:**
```python
class BinanceL2WebSocketProvider(MarketDataProvider):
    def __init__(
        symbols: List[str],
        ws_adapter: Optional[BinanceWebSocketAdapter] = None,
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
        max_reconnect_attempts: int = 5,
        reconnect_backoff: float = 2.0,
    )
    
    def start() -> None
        # 별도 스레드에서 asyncio loop 실행
    
    def stop() -> None
        # WebSocket 연결 종료
    
    def get_latest_snapshot(symbol: str) -> Optional[OrderBookSnapshot]
        # 최신 스냅샷 반환 (스레드 안전)
    
    def _on_snapshot(snapshot: OrderBookSnapshot) -> None
        # Adapter 콜백: 스냅샷 업데이트
        # BTCUSDT → BTC 매핑 포함
```

**스레딩/이벤트 루프 모델:**
```
Main Thread                     WebSocket Thread
    │                                │
    │ start()                        │
    │────────────────────────────────>│
    │                                │ _run_event_loop()
    │                                │   asyncio.new_event_loop()
    │                                │   _connect_and_subscribe()
    │                                │     adapter.connect()
    │                                │     adapter.subscribe()
    │                                │     adapter.receive_loop()
    │                                │       ↓
    │                                │   on_message()
    │                                │     _parse_message()
    │                                │     callback(_on_snapshot)
    │                                │       ↓
    │                                │   latest_snapshots[BTCUSDT] = ...
    │                                │   latest_snapshots[BTC] = ...
    │                                │
    │ get_latest_snapshot("BTC")     │
    │<───────────────────────────────│
    │ return latest_snapshots["BTC"] │
```

**심볼 매핑 전략:**
- Binance 심볼: `BTCUSDT`, `ETHUSDT`
- 표준 심볼: `BTC`, `ETH`
- 매핑 로직 (D83-1 Upbit과 동일):
  ```python
  # Binance 형식 저장
  self.latest_snapshots[snapshot.symbol] = snapshot  # BTCUSDT
  
  # 표준 심볼 변환 저장
  if snapshot.symbol.endswith("USDT"):
      standard_symbol = snapshot.symbol.replace("USDT", "")
      self.latest_snapshots[standard_symbol] = snapshot  # BTC
  ```

### 2.4 D84-2 Runner 통합 전략

**파일:** `scripts/run_d84_2_calibrated_fill_paper.py`

**변경 사항:**
1. `--l2-source` 인자 확장:
   ```python
   parser.add_argument(
       "--l2-source",
       type=str,
       choices=["mock", "real", "upbit", "binance"],
       default="mock",
       help="L2 Orderbook source: mock (기본값), real (=upbit), upbit, binance"
   )
   ```

2. Provider 선택 로직:
   ```python
   l2_source = args.l2_source
   
   # 하위 호환: real → upbit
   if l2_source == "real":
       l2_source = "upbit"
   
   if l2_source == "mock":
       provider = MockMarketDataProvider()
   elif l2_source == "upbit":
       provider = UpbitL2WebSocketProvider(symbols=["KRW-BTC"])
   elif l2_source == "binance":
       provider = BinanceL2WebSocketProvider(symbols=["BTCUSDT"])
   else:
       raise ValueError(f"Unknown l2_source: {l2_source}")
   ```

**하위 호환성 보장:**
- 기존 `--l2-source real` → `upbit`으로 자동 매핑
- 기존 테스트/문서에서 사용하던 명령어 그대로 작동

---

## 3. 데이터 플로우

### 3.1 WebSocket 메시지 수신 플로우

```
Binance Server
    │
    │ (WebSocket binary/text message)
    ▼
BaseWebSocketClient.receive_loop()
    │ (bytes → UTF-8 decode, D83-1.6 적용)
    │ json.loads()
    ▼
BinanceWebSocketAdapter.on_message(message: Dict)
    │ _parse_message()
    │   - Extract bids/asks from message["b"]/message["a"]
    │   - Convert to OrderBookSnapshot
    ▼
BinanceWebSocketAdapter.callback(snapshot)
    │
    ▼
BinanceL2WebSocketProvider._on_snapshot(snapshot)
    │ latest_snapshots[BTCUSDT] = snapshot
    │ latest_snapshots[BTC] = snapshot
    ▼
(Main Thread) Executor.get_latest_snapshot("BTC")
    │
    ▼
BinanceL2WebSocketProvider.get_latest_snapshot("BTC")
    │
    └─> return latest_snapshots["BTC"]
```

### 3.2 심볼 매핑 플로우

```
Binance Symbol: BTCUSDT
    │
    ▼
_on_snapshot()
    │
    ├─> latest_snapshots["BTCUSDT"] = snapshot
    │
    └─> if symbol.endswith("USDT"):
            standard = symbol.replace("USDT", "")
            latest_snapshots["BTC"] = snapshot
```

---

## 4. 에러 처리 및 재연결

### 4.1 재연결 전략

**D83-1 Upbit과 동일:**
- Exponential backoff (초기: 1초, 최대: 30초, 배수: 2.0)
- 최대 재연결 시도: 5회
- 재연결 성공 시 카운터 리셋

### 4.2 에러 분류

1. **연결 에러** (`WebSocketConnectionError`)
   - 재연결 시도
   - 로그 레벨: WARNING

2. **프로토콜 에러** (`WebSocketProtocolError`)
   - JSON 파싱 실패, 메시지 포맷 불일치
   - 로그 레벨: ERROR
   - 해당 메시지만 스킵, 연결 유지

3. **타임아웃 에러** (`WebSocketTimeoutError`)
   - Heartbeat 실패
   - 재연결 시도

### 4.3 Stale Snapshot 경고

D83-1과 동일:
- 5초 이상 오래된 스냅샷은 경고 로그
- Executor는 정상 사용 가능 (fallback 로직은 Executor 책임)

---

## 5. 테스트 전략

### 5.1 유닛 테스트

**파일:** `tests/test_d83_2_binance_l2_provider.py`

**FakeBinanceWebSocketAdapter 구현:**
```python
class FakeBinanceWebSocketAdapter:
    def __init__(self, symbols, callback, **kwargs):
        self.symbols = symbols
        self.callback = callback
    
    async def connect(self):
        pass  # no-op
    
    async def subscribe(self, channels):
        pass  # no-op
    
    async def receive_loop(self):
        await asyncio.sleep(0.1)  # prevent busy-wait
    
    def inject_snapshot(self, snapshot: OrderBookSnapshot):
        """테스트용 스냅샷 주입"""
        self.callback(snapshot)
```

**테스트 케이스:**
1. `test_init`: Provider 초기화
2. `test_snapshot_update_via_callback`: 콜백 경로로 스냅샷 갱신
3. `test_get_latest_snapshot`: 표준 심볼(`BTC`)로 조회
4. `test_get_latest_snapshot_no_data`: 데이터 없을 때 None
5. `test_multiple_snapshots_symbol_mapping`: `BTCUSDT`/`BTC` 양쪽 저장 확인
6. `test_snapshot_overwrite`: 최신 스냅샷으로 덮어쓰기
7. `test_get_connection_status` (선택): 연결 상태 반환

### 5.2 Runner 설정 테스트

**파일:** `tests/test_d84_2_runner_config.py`

**추가 테스트:**
- `test_l2_source_binance`: `--l2-source binance` → BinanceL2WebSocketProvider
- `test_l2_source_real_alias`: `--l2-source real` → UpbitL2WebSocketProvider (하위 호환)

### 5.3 회귀 테스트

**실행 명령:**
```bash
pytest -q \
  tests/test_d83_0_l2_available_volume.py \
  tests/test_d83_1_real_l2_provider.py \
  tests/test_d83_2_binance_l2_provider.py \
  tests/test_d84_1_calibrated_fill_model.py \
  tests/test_d84_2_runner_config.py
```

**목표:** 모두 PASS (기존 테스트 회귀 없음)

---

## 6. Acceptance Criteria (D83-2 전용)

**Binance Real L2 PAPER 5분 스모크 테스트:**

| 항목 | 목표 | 측정 방법 |
|------|------|----------|
| **Duration** | ≥ 300초 | 실행 로그 타임스탬프 |
| **Fill Events** | ≥ 40개 | fill_events_*.jsonl 라인 수 |
| **BUY std/mean** | > 0.1 | available_volume 표준편차/평균 |
| **SELL std/mean** | > 0.1 | available_volume 표준편차/평균 |
| **WebSocket Reconnect** | ≤ 1회 | 로그에서 "Reconnecting" 카운트 |
| **Fatal Exception** | 0개 | 로그에서 Traceback/Exception 검색 |

**실행 명령:**
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --smoke \
  --l2-source binance
```

**분석 명령:**
```bash
python scripts/analyze_d84_2_fill_results.py \
  --events-file logs/d84-2/fill_events_<timestamp>.jsonl
```

---

## 7. 구현 우선순위

### Phase 1: Core Implementation (3시간 예상)
1. `BinanceWebSocketAdapter` 구현 (60분)
2. `BinanceL2WebSocketProvider` 구현 (60분)
3. Runner 통합 (30분)
4. 유닛 테스트 작성 (30분)

### Phase 2: Validation (1시간 예상)
1. 유닛 테스트 실행 및 디버깅 (20분)
2. 회귀 테스트 (10분)
3. Binance Real L2 PAPER 5분 스모크 (30분)

### Phase 3: Documentation (30분 예상)
1. `D83-2_BINANCE_L2_WEBSOCKET_REPORT.md` 작성
2. `D_ROADMAP.md` 업데이트

---

## 8. 위험 요소 및 완화 전략

### 8.1 Binance API 메시지 포맷 차이

**위험:** Upbit과 다른 메시지 구조로 인한 파싱 실패  
**완화:**
- D83-1.6에서 학습한 디버깅 기법 적용 (DEBUG 로그, 독립 디버그 스크립트)
- 먼저 간단한 독립 스크립트로 Binance WebSocket 메시지 포맷 확인

### 8.2 심볼 매핑 오류

**위험:** `BTCUSDT` ↔ `BTC` 매핑 누락/오류  
**완화:**
- 유닛 테스트에서 명시적으로 검증
- Upbit과 동일한 패턴 사용

### 8.3 WebSocket 연결 불안정

**위험:** Binance WebSocket 연결 끊김, 재연결 실패  
**완화:**
- D83-1에서 검증된 재연결 로직 재사용
- 스모크 테스트에서 reconnect 횟수 모니터링

### 8.4 하위 호환성 깨짐

**위험:** 기존 `--l2-source real` 명령어 동작 변경  
**완화:**
- `real` → `upbit` alias 명시적 구현
- 기존 테스트 케이스로 회귀 검증

---

## 9. Next Steps (D83-2 이후)

### D83-3: Multi-exchange L2 Aggregation
- Upbit + Binance L2 데이터 동시 사용
- 거래소별 최적 호가 선택
- Cross-exchange arbitrage 기회 탐지

### D84-2+: Long-run PAPER (20분+)
- Binance L2 기반 100+ fill events 수집
- Zone별 Fill Ratio 분포 분석

### D84-3: Mock vs Real L2 분포 비교
- Mock/Upbit/Binance L2 기반 fill distribution 비교
- CalibratedFillModel 정확도 검증

---

## 10. 설계 승인

**설계 완료 일시:** 2025-12-07  
**설계 승인자:** D83-2 자동화 엔진 (Windsurf AI)  
**다음 단계:** 구현 시작 (BinanceWebSocketAdapter)

---

**END OF DESIGN DOCUMENT**

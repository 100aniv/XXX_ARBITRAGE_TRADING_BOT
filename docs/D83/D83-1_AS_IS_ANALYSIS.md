# D83-1: AS-IS 분석 – Real L2 WebSocket Provider 통합 준비

**Date:** 2025-12-06  
**Status:** 📋 ANALYSIS PHASE  
**Author:** Windsurf AI

---

## 📋 현재 MarketDataProvider 인터페이스 및 책임

### 1. MarketDataProvider 인터페이스

**위치:** `arbitrage/exchanges/market_data_provider.py`

**핵심 메서드:**
```python
class MarketDataProvider(ABC):
    """호가 데이터 소스 추상화 인터페이스"""
    
    @abstractmethod
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """최신 호가 스냅샷 반환"""
        pass
    
    @abstractmethod
    def start(self) -> None:
        """데이터 소스 시작"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """데이터 소스 종료"""
        pass
    
    async def aget_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Async wrapper (D54)"""
        pass
```

**책임:**
- 최신 L2 OrderBookSnapshot 제공
- 데이터 소스 생명주기 관리 (start/stop)
- 멀티심볼 지원 (symbol 인자)

### 2. 기존 구현체

#### ① RestMarketDataProvider
- REST API 기반 폴링
- `exchange.get_orderbook(symbol)` 호출
- 실시간성 낮음 (폴링 주기에 의존)

#### ② WebSocketMarketDataProvider
- WebSocket 기반 실시간 스트림
- **현재 상태:** 인터페이스만 존재, 실제 구현 미완료
- 특징:
  - Per-symbol snapshot storage (`latest_snapshots: Dict[str, OrderBookSnapshot]`)
  - 콜백 기반 업데이트 (`on_upbit_snapshot()`, `on_binance_snapshot()`)
  - D63에서 Queue 기반 비동기 처리 추가

#### ③ MockMarketDataProvider
- D83-0.5, D84-2에서 사용
- 테스트용 Mock 구현
- 시간에 따라 volume 변동 (0.5~1.5x random)

---

## 📋 _get_available_volume_from_orderbook() 동작 방식

### 위치 및 역할
**파일:** `arbitrage/execution/executor.py`, Line 350-406  
**역할:** Fill Model에 L2 기반 available_volume 제공

### 동작 흐름

```python
def _get_available_volume_from_orderbook(
    self, symbol: str, side: OrderSide, target_price: float, fallback_quantity: float
) -> float:
    """
    D83-0: L2 Orderbook에서 available_volume 계산
    
    1. Provider 없으면 → fallback (기존 로직)
    2. Snapshot 없으면 → fallback
    3. L2 levels 없으면 → fallback
    4. Best Level의 volume 반환 (1단계)
    """
    # 1. Provider 체크
    if self.market_data_provider is None:
        return fallback_quantity * self.default_available_volume_factor
    
    # 2. Snapshot 가져오기
    snapshot = self.market_data_provider.get_latest_snapshot(symbol)
    if snapshot is None:
        return fallback_quantity * self.default_available_volume_factor
    
    # 3. L2 levels 추출
    levels = snapshot.asks if side == OrderSide.BUY else snapshot.bids
    if not levels:
        return fallback_quantity * self.default_available_volume_factor
    
    # 4. Best Level의 volume 반환
    best_price, best_volume = levels[0]
    return best_volume
```

### 핵심 특징
- **D83-0 Baseline:** Best level volume만 사용 (1단계)
- **Future (D83-1+):** Multi-level aggregation, price impact 고려 가능
- **Fallback 전략:** Provider/Snapshot 없으면 기존 로직 유지 (하위 호환성)

---

## 📋 D84-2 Runner의 조립 방식

### 파일: `scripts/run_d84_2_calibrated_fill_paper.py`

### 조립 흐름

```python
# 1. Calibration JSON 로드
calibration = load_calibration(Path("logs/d84/d84_1_calibration.json"))

# 2. MockMarketDataProvider 생성 (L2 시뮬레이션)
market_data_provider = MockMarketDataProvider()
market_data_provider.start()

# 3. FillEventCollector 생성
fill_event_collector = FillEventCollector(
    events_file=fill_events_path, enabled=True
)

# 4. RiskGuard 생성
risk_guard = RiskGuard(limits=RiskLimits(...))

# 5. CalibratedFillModel 생성
base_model = SimpleFillModel(...)
fill_model = CalibratedFillModel(
    base_model=base_model,
    calibration_table=calibration,
    entry_bps=ENTRY_BPS,
    tp_bps=TP_BPS
)

# 6. PaperExecutor 생성 (ExecutorFactory 통해)
executor = executor_factory.create_paper_executor(
    symbol=symbol,
    portfolio_state=portfolio_state,
    risk_guard=risk_guard,
    fill_model_config=None,  # 직접 주입
    market_data_provider=market_data_provider,  # D83-0
    fill_event_collector=fill_event_collector,  # D83-0.5
)

# 7. Fill Model 수동 주입 (ExecutorFactory가 CalibratedFillModel 미지원)
executor.fill_model = fill_model
executor.enable_fill_model = True

# 8. Trade 루프 실행
for iteration in range(max_iterations):
    trade = generate_mock_trade(...)
    results = executor.execute_trades([trade])
    # Fill Events 자동 기록됨
```

### 핵심 특징
- **Provider 주입:** `create_paper_executor(market_data_provider=...)`
- **Collector 주입:** `create_paper_executor(fill_event_collector=...)`
- **Fill Model 주입:** 수동으로 `executor.fill_model` 설정
- **Executor → FillModel → Collector 체인:** PaperExecutor가 Fill Event 자동 기록

---

## 📋 Real L2 WebSocket Provider 통합 경로

### 후보 경로 분석

#### ✅ 경로 1: `arbitrage/exchanges/upbit_l2_ws_provider.py` (신규 파일)

**장점:**
- 기존 `upbit_ws_adapter.py` 재사용 가능
- `MarketDataProvider` 인터페이스 구현
- ExecutorFactory 수정 불필요 (Provider 주입만)
- 책임 분리 명확

**구조:**
```python
class UpbitL2WebSocketProvider(MarketDataProvider):
    """Real L2 WebSocket Provider (Upbit)"""
    
    def __init__(self, symbols: List[str]):
        self.ws_adapter = UpbitWebSocketAdapter(
            symbols=symbols,
            callback=self._on_snapshot
        )
        self.latest_snapshots: Dict[str, OrderBookSnapshot] = {}
    
    def start(self) -> None:
        """WebSocket 연결 및 구독"""
        asyncio.create_task(self.ws_adapter.connect())
        asyncio.create_task(self.ws_adapter.subscribe(self.symbols))
    
    def stop(self) -> None:
        """WebSocket 종료"""
        asyncio.create_task(self.ws_adapter.disconnect())
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """최신 스냅샷 반환"""
        return self.latest_snapshots.get(symbol)
    
    def _on_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """콜백: 스냅샷 업데이트"""
        self.latest_snapshots[snapshot.symbol] = snapshot
```

#### ❌ 경로 2: 기존 `WebSocketMarketDataProvider` 확장

**단점:**
- 이미 복잡한 구조 (D59 멀티심볼, D63 Queue)
- 실제 구현 미완료 상태
- 수정 시 기존 코드 영향 범위 큼

### ✅ 최종 결론

**경로 1 선택:** 신규 `UpbitL2WebSocketProvider` 클래스 생성

**이유:**
1. 기존 `UpbitWebSocketAdapter` 재사용 (검증된 코드)
2. `MarketDataProvider` 인터페이스 그대로 구현
3. D84-2 Runner에서 Provider만 교체하면 됨 (최소 변경)
4. 테스트 용이 (WebSocket 레이어 주입 가능)
5. DO-NOT-TOUCH 원칙 준수 (기존 코드 영향 최소화)

---

## 📋 통합 지점 요약

### 1. Provider 생성
```python
# Before (D84-2): Mock Provider
market_data_provider = MockMarketDataProvider()

# After (D83-1): Real L2 Provider
market_data_provider = UpbitL2WebSocketProvider(symbols=["KRW-BTC"])
```

### 2. Executor 생성 (동일)
```python
executor = executor_factory.create_paper_executor(
    ...,
    market_data_provider=market_data_provider,  # Provider만 교체
    ...
)
```

### 3. Runner 스크립트 (재사용)
- D84-2 Runner 구조 최대 재사용
- CLI 인자로 `--l2-source=mock|real` 추가
- Provider 생성 로직만 분기

---

## 📋 Next Steps

### STEP 1: Real L2 WebSocket Provider 설계
- `docs/D83/D83-1_REAL_L2_WEBSOCKET_DESIGN.md` 작성
- Provider 상세 설계 (재연결, 에러 처리, 스레딩 모델)

### STEP 2: 코드 구현
- `arbitrage/exchanges/upbit_l2_ws_provider.py` 구현
- `UpbitWebSocketAdapter` 재사용

### STEP 3: Runner 통합
- D84-2 Runner 확장 (`--l2-source` 인자)
- 또는 얇은 래퍼 스크립트 생성

### STEP 4: 테스트 코드
- `tests/test_d83_1_real_l2_provider.py`
- WebSocket 레이어 Mock/Fake로 유닛 테스트

### STEP 5: REAL PAPER 실행
- 5분 스모크 테스트
- 분석 스크립트 재사용 (D84-2 분석 스크립트)

---

**분석 완료 시각:** 2025-12-06

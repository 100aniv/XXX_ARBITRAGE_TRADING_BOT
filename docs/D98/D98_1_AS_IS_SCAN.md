# D98-1 AS-IS 스캔: 주문 함수 진입점 분석

**스캔일**: 2025-12-18  
**목적**: Read-only Preflight Guard 구현을 위한 주문/취소/출금 함수 진입점 식별

---

## 1. Exchange Adapter 구조

### 1.1 Base Interface
**파일**: `arbitrage/exchanges/base.py`

**주문 관련 추상 메서드** (3개):
```python
class BaseExchange(ABC):
    @abstractmethod
    def create_order(
        self, symbol: str, side: OrderSide, qty: float,
        price: Optional[float] = None, order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC
    ) -> OrderResult:
        """주문 생성"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        pass
    
    # 출금 함수는 BaseExchange에 없음 (거래소별 구현)
```

**진입점**:
- `create_order`: 모든 주문 생성 (BUY/SELL)
- `cancel_order`: 주문 취소

---

### 1.2 Paper Exchange 구현
**파일**: `arbitrage/exchanges/paper_exchange.py`

**특징**:
- BaseExchange 상속
- 실제 API 호출 없이 메모리 기반 시뮬레이션
- create_order, cancel_order 구현

**안전성**:
- ✅ Paper 모드는 실주문 0건 (메모리 시뮬레이션)
- ✅ 실제 거래소 API 호출 없음

---

### 1.3 Live Exchange 구현
**파일**:
- `arbitrage/exchanges/upbit_spot.py`
- `arbitrage/exchanges/binance_futures.py`

**특징**:
- BaseExchange 상속
- 실제 거래소 API 호출
- create_order, cancel_order → 실주문 생성/취소

**리스크**:
- ❌ LIVE 모드에서는 실주문 발생
- ❌ 실수로 호출 시 실자금 거래

---

## 2. Executor 레벨

### 2.1 Base Executor
**파일**: `arbitrage/execution/executor.py`

**주문 호출 경로**:
```python
class BaseExecutor(ABC):
    @abstractmethod
    def execute_trades(self, trades: List) -> List[ExecutionResult]:
        """거래 실행 - 내부에서 create_order 호출"""
        pass
```

**Paper Executor**:
- Exchange 객체를 주입받아 create_order 호출
- Paper 모드에서는 PaperExchange 사용

---

## 3. 주문 함수 호출 카운트

### 3.1 place_order 검색 결과
- **36 matches** across 13 files
- 주요 파일:
  - `arbitrage/live_trader.py` (5)
  - `arbitrage/execution_engine.py` (2)
  - `arbitrage/live_api.py` (2)
  - `arbitrage/binance_live.py` (1)
  - `arbitrage/upbit_live.py` (1)

### 3.2 cancel_order 검색 결과
- **70 matches** across 23 files
- 주요 파일:
  - `arbitrage/cross_exchange/executor.py` (2)
  - `arbitrage/exchanges/binance_futures.py` (2)
  - `arbitrage/exchanges/upbit_spot.py` (2)
  - `arbitrage/execution/executor.py` (2)
  - `arbitrage/live_api.py` (2)

---

## 4. Tuning 인프라 확인

**스캔 결과** (이전 D98-0에서 확인):
- ✅ 완전 구현됨 (D23~D41 완료)
- Core 모듈: 8개
- Runner scripts: 44개
- Test coverage: 142개 파일, 1523 매치

**D98-1 범위**: 튜닝 구현 없음 (재사용만)

---

## 5. Read-only Guard 구현 전략

### 5.1 Guard 위치
**최적 위치**: `arbitrage/config/readonly_guard.py` (신규 생성)

**이유**:
- live_safety.py와 동일 계층 (config/)
- BaseExchange 진입점 래핑
- 환경변수 기반 제어 (READ_ONLY_ENFORCED)

---

### 5.2 Guard 메커니즘

**환경변수**: `READ_ONLY_ENFORCED` (기본값: true)

**차단 대상**:
1. `BaseExchange.create_order` → ReadOnlyError 발생
2. `BaseExchange.cancel_order` → ReadOnlyError 발생
3. 출금 함수 (거래소별 구현 시)

**허용 대상**:
- `get_orderbook` (조회)
- `get_balance` (조회)
- `get_open_positions` (조회)
- `get_order_status` (조회)

---

### 5.3 Preflight 스크립트 안전화

**파일**: `scripts/d98_live_preflight.py`

**변경 사항**:
1. READ_ONLY_ENFORCED=true 강제 설정
2. Exchange 객체 생성 시 read_only=True 플래그
3. 주문 생성/취소 메서드 접근 불가능하게 구조적 차단

---

## 6. 테스트 전략

### 6.1 단위 테스트
**파일**: `tests/test_d98_readonly_guard.py` (신규)

**테스트 케이스** (최소 10개):
1. READ_ONLY_ENFORCED=true 시 create_order 차단
2. READ_ONLY_ENFORCED=true 시 cancel_order 차단
3. READ_ONLY_ENFORCED=false 시 정상 동작 (PAPER만)
4. ReadOnlyError 예외 메시지 검증
5. 조회 함수는 정상 동작 (get_orderbook 등)
6. Preflight 스크립트 실행 시 주문 호출 0건
7. Mock/Spy를 통한 호출 카운트 검증
8. Paper 모드에서도 Guard 작동 확인
9. LIVE 모드에서는 이중 차단 (Guard + Safety)
10. Guard 우회 시도 시 FAIL

---

### 6.2 Integration Test
**파일**: `tests/test_d98_preflight_readonly.py` (신규)

**테스트 케이스**:
1. Preflight 스크립트 전체 실행
2. create_order/cancel_order 호출 카운트 = 0 검증
3. 조회 함수만 호출됨 검증
4. 환경변수 READ_ONLY_ENFORCED 강제 적용

---

## 7. 구현 체크리스트

### Phase 1: Guard 구현
- [ ] `arbitrage/config/readonly_guard.py` 생성
- [ ] ReadOnlyError 예외 정의
- [ ] ReadOnlyGuard 클래스 구현
- [ ] BaseExchange wrapper 또는 decorator

### Phase 2: Preflight 안전화
- [ ] `scripts/d98_live_preflight.py` 수정
- [ ] READ_ONLY_ENFORCED=true 강제 설정
- [ ] Exchange 객체를 read-only 모드로만 생성

### Phase 3: 테스트
- [ ] `tests/test_d98_readonly_guard.py` 생성 (10+ tests)
- [ ] `tests/test_d98_preflight_readonly.py` 생성
- [ ] Fast Gate 100% PASS
- [ ] Core Regression 100% PASS

### Phase 4: 문서
- [ ] `docs/D98/D98_1_REPORT.md` 업데이트
- [ ] ROADMAP D98-1 섹션 추가
- [ ] CHECKPOINT 업데이트

---

## 8. FAIL 조건

| Condition | Action |
|-----------|--------|
| create_order 호출 1건 발생 | 즉시 FAIL |
| cancel_order 호출 1건 발생 | 즉시 FAIL |
| 출금 함수 호출 발생 | 즉시 FAIL |
| READ_ONLY_ENFORCED=false | 즉시 FAIL (PAPER 제외) |
| 테스트 100% PASS 실패 | 커밋 금지 |

---

**스캔 완료일**: 2025-12-18  
**다음 단계**: STEP 2 - ReadOnlyGuard 구현

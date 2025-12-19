# D98-3: Executor Layer Order Bypass Path Scan

**Date**: 2025-12-18  
**Objective**: Identify all potential order placement bypass routes at Executor/Router/Strategy layers

---

## 1. Scan Summary

### 1.1 Total Order-Related Functions Found

| Function Pattern | Count | Files |
|-----------------|-------|-------|
| `create_order` | 11 | 9 files |
| `cancel_order` | 11 | 9 files |
| `place_order` | 4 | 3 files |
| **Total** | **23** | **11 files** |

### 1.2 Critical Bypass Risk Paths (3개 발견)

| # | Path | Risk Level | Current Defense | Required Action |
|---|------|------------|-----------------|-----------------|
| **1** | `LiveExecutor._execute_single_trade()` → `upbit_api.create_order()` | 🔴 **HIGH** | ❌ None | Add ReadOnlyGuard check |
| **2** | `LiveExecutor._execute_single_trade()` → `binance_api.create_order()` | 🔴 **HIGH** | ❌ None | Add ReadOnlyGuard check |
| **3** | `upbit_live.UpbitLiveAPI.place_order()` | 🟡 MEDIUM | ❌ None | Add decorator |
| **4** | `binance_live.BinanceLiveAPI.place_order()` | 🟡 MEDIUM | ❌ None | Add decorator |

**Conclusion**: Executor 계층에 ReadOnlyGuard가 없어 Exchange Adapter 레벨 데코레이터를 우회 가능. **D98-3에서 필수 차단 필요**.

---

## 2. Detailed Entry Point Analysis

### 2.1 LiveExecutor (Highest Risk)

**File**: `arbitrage/execution/executor.py`

#### 2.1.1 execute_trades() - Line 796

```python
def execute_trades(self, trades: List) -> List[ExecutionResult]:
    """
    D64: 거래 실행 (Live Mode)
    """
    results = []
    
    for trade in trades:
        # 1. 리스크 체크
        if not self.risk_guard.check_symbol_capital_limit(...):
            # Rejected
            continue
        
        # 2. 거래 실행 ← ★ 여기서 우회 가능
        result = self._execute_single_trade(trade)
        results.append(result)
```

**Risk**: `_execute_single_trade()`가 직접 호출되며 ReadOnlyGuard 체크 없음.

#### 2.1.2 _execute_single_trade() - Line 862

```python
def _execute_single_trade(self, trade: ArbitrageTrade) -> ExecutionResult:
    """단일 거래 실행"""
    try:
        # 1. 매수 주문 (Exchange A)
        if self.dry_run:
            buy_order_id = f"DRY_BUY_{self.symbol}_{self.execution_count}"
        else:
            if trade.buy_exchange == "upbit" and self.upbit_api:
                # ★ 직접 API 호출 (데코레이터 우회 가능)
                order = self.upbit_api.create_order(
                    market=f"KRW-{trade.symbol.split('-')[1]}",
                    side="bid",
                    ord_type="limit",
                    volume=trade.quantity,
                    price=trade.buy_price,
                )
            elif trade.buy_exchange == "binance" and self.binance_api:
                # ★ 직접 API 호출 (데코레이터 우회 가능)
                order = self.binance_api.create_order(
                    symbol=f"{trade.symbol.split('-')[1]}USDT",
                    side="BUY",
                    type="LIMIT",
                    quantity=trade.quantity,
                    price=trade.buy_price,
                )
        
        # 2. 매도 주문 (Exchange B) - 동일 패턴
        ...
```

**Critical Issue**:
- `upbit_api`와 `binance_api`는 `UpbitLiveAPI`, `BinanceLiveAPI` 인스턴스
- 이들의 `create_order()`는 **데코레이터가 없음**
- `UpbitSpotExchange.create_order()`는 `@enforce_readonly` 있지만, `UpbitLiveAPI.place_order()`는 없음
- **우회 경로 확정**: LiveExecutor → UpbitLiveAPI.place_order → 실제 HTTP 요청

**Dry-run vs ReadOnlyGuard**:
- `self.dry_run`: LiveExecutor 내부 플래그 (독립적)
- `READ_ONLY_ENFORCED`: 전역 안전장치 (우선순위 높음)
- **둘은 독립적이므로 ReadOnlyGuard 추가 필수**

---

### 2.2 UpbitLiveAPI (Direct HTTP Layer)

**File**: `arbitrage/upbit_live.py`

#### 2.2.1 place_order() - Line 179

```python
def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
    """주문 실행"""
    if self.mock_mode:
        # Mock order
        return mock_response
    
    # ★ 실제 HTTP POST 요청
    url = f"{self.base_url}/v1/orders"
    headers = self._create_auth_headers(...)
    
    response = requests.post(url, headers=headers, json=params)
    # ... 응답 처리
```

**Risk**: 
- 데코레이터 없음
- LiveExecutor에서 직접 호출됨
- Mock mode 체크만 있음 (READ_ONLY 체크 없음)

#### 2.2.2 cancel_order() - Line 240

```python
def cancel_order(self, order_id: str) -> bool:
    """주문 취소"""
    if self.mock_mode:
        return True
    
    # ★ 실제 HTTP DELETE 요청
    url = f"{self.base_url}/v1/order"
    # ...
```

**Same Risk**: 데코레이터 없음, ReadOnly 체크 없음.

---

### 2.3 BinanceLiveAPI (Direct HTTP Layer)

**File**: `arbitrage/binance_live.py`

#### 2.3.1 place_order() - Line 190

```python
def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
    """주문 실행"""
    if self.mock_mode:
        return mock_response
    
    # ★ 실제 HTTP POST 요청
    url = f"{self.base_url}/api/v3/order"
    # ...
```

#### 2.3.2 cancel_order() - Line 261

```python
def cancel_order(self, order_id: str) -> bool:
    """주문 취소"""
    # ★ 실제 HTTP DELETE 요청
```

**Same Risk**: UpbitLiveAPI와 동일.

---

### 2.4 OrderManager (High-Level Router)

**File**: `arbitrage/order_manager.py`

#### 2.4.1 create_order() - Line 93

```python
def create_order(
    self,
    exchange: str,
    symbol: str,
    side: OrderSide,
    quantity: float,
    price: Optional[float] = None,
) -> Optional[OrderResult]:
    """주문 생성 (고수준 라우터)"""
    # Exchange adapter로 라우팅
    if exchange == "upbit":
        adapter = self.exchanges.get("upbit")
        return adapter.create_order(...)
    elif exchange == "binance":
        adapter = self.exchanges.get("binance")
        return adapter.create_order(...)
```

**Analysis**:
- 고수준 추상화 레이어
- Exchange adapter로 라우팅만 수행
- Adapter가 이미 `@enforce_readonly` 보호 중
- **우회 위험 낮음** (Adapter 레벨에서 차단됨)

---

### 2.5 Exchange Adapters (Already Protected)

#### 2.5.1 UpbitSpotExchange

**File**: `arbitrage/exchanges/upbit_spot.py`

```python
@enforce_readonly  # ✅ D98-2에서 적용 완료
def create_order(self, symbol: str, side: OrderSide, qty: float, ...) -> OrderResult:
    """주문 생성"""
    # ... 실제 HTTP 요청
```

**Status**: ✅ Protected (D98-2)

#### 2.5.2 BinanceFuturesExchange

**File**: `arbitrage/exchanges/binance_futures.py`

```python
@enforce_readonly  # ✅ D98-2에서 적용 완료
def create_order(self, symbol: str, side: OrderSide, qty: float, ...) -> OrderResult:
    """주문 생성"""
    # ... 실제 HTTP 요청
```

**Status**: ✅ Protected (D98-2)

#### 2.5.3 PaperExchange

**File**: `arbitrage/exchanges/paper_exchange.py`

```python
@enforce_readonly  # ✅ D98-1에서 적용 완료
def create_order(self, symbol: str, side: OrderSide, qty: float, ...) -> OrderResult:
    """주문 생성 (가상 체결)"""
    # ... Paper 시뮬레이션
```

**Status**: ✅ Protected (D98-1)

---

## 3. Bypass Path Diagram

```
User Strategy
    ↓
LiveExecutor.execute_trades()              ← ❌ NO GUARD (D98-3 추가 예정)
    ↓
LiveExecutor._execute_single_trade()       ← ❌ NO GUARD (D98-3 추가 예정)
    ↓
    ├─→ upbit_api.create_order()           ← ❌ NO GUARD (D98-3 추가 예정)
    │        ↓
    │   UpbitLiveAPI.place_order()         ← ❌ NO GUARD (D98-3 추가 예정)
    │        ↓
    │   HTTP POST to api.upbit.com         ← 🔴 REAL ORDER
    │
    └─→ binance_api.create_order()         ← ❌ NO GUARD (D98-3 추가 예정)
             ↓
        BinanceLiveAPI.place_order()       ← ❌ NO GUARD (D98-3 추가 예정)
             ↓
        HTTP POST to api.binance.com       ← 🔴 REAL ORDER

Alternative Path (OrderManager):
    OrderManager.create_order()
        ↓
    Exchange Adapter.create_order()        ← ✅ @enforce_readonly (SAFE)
        ↓
    Blocked by ReadOnlyGuard
```

**Critical Gap**: LiveExecutor가 `UpbitLiveAPI`/`BinanceLiveAPI`를 직접 호출하는 경로에서 ReadOnlyGuard 없음.

---

## 4. Defense Layer Analysis

### 4.1 Current Defense (D98-2 기준)

| Layer | Component | Defense Mechanism | Status |
|-------|-----------|-------------------|--------|
| **L1: Exchange Adapter** | UpbitSpotExchange | `@enforce_readonly` | ✅ Protected |
| **L1: Exchange Adapter** | BinanceFuturesExchange | `@enforce_readonly` | ✅ Protected |
| **L1: Exchange Adapter** | PaperExchange | `@enforce_readonly` | ✅ Protected |
| **L2: Executor** | LiveExecutor | ❌ None | 🔴 **VULNERABLE** |
| **L3: Live API** | UpbitLiveAPI | ❌ None | 🔴 **VULNERABLE** |
| **L3: Live API** | BinanceLiveAPI | ❌ None | 🔴 **VULNERABLE** |

### 4.2 Required Defense (D98-3)

**Primary Defense Point**: `LiveExecutor.execute_trades()` 또는 `_execute_single_trade()`

**Option A: execute_trades() 레벨 (권장)**
- **Pros**: 모든 거래 실행 전 단일 체크포인트
- **Cons**: None
- **Implementation**: 함수 시작 시 ReadOnlyGuard 체크 1회

**Option B: _execute_single_trade() 레벨**
- **Pros**: 개별 거래마다 체크 (더 세밀)
- **Cons**: 중복 체크 (성능 오버헤드)
- **Implementation**: 매 거래마다 ReadOnlyGuard 체크

**Decision**: **Option A (execute_trades() 레벨) 채택**
- 성능상 유리 (1회 체크)
- 명확한 단일 게이트
- Defense-in-depth 원칙 준수

**Secondary Defense**: `UpbitLiveAPI.place_order()`, `BinanceLiveAPI.place_order()`에 `@enforce_readonly` 추가
- Defense-in-depth 강화
- LiveExecutor 우회 시 추가 차단

---

## 5. Implementation Plan (D98-3)

### 5.1 Code Changes Required

**Priority 1: LiveExecutor Guard**

`arbitrage/execution/executor.py`:
```python
from arbitrage.config.readonly_guard import get_readonly_guard, ReadOnlyError

class LiveExecutor(BaseExecutor):
    def execute_trades(self, trades: List) -> List[ExecutionResult]:
        """
        D64: 거래 실행 (Live Mode)
        D98-3: ReadOnlyGuard 추가 (Executor 레벨 차단)
        """
        # ★ D98-3: 중앙 차단 게이트
        guard = get_readonly_guard()
        if guard.is_readonly_enabled():
            logger.error("[D98-3_EXECUTOR_GUARD] Live order execution blocked in READ_ONLY mode")
            raise ReadOnlyError(
                "[D98-3_EXECUTOR_GUARD] Cannot execute live trades when READ_ONLY_ENFORCED=true. "
                "Set READ_ONLY_ENFORCED=false to enable live trading (use with extreme caution)."
            )
        
        results = []
        for trade in trades:
            # ... 기존 로직
```

**Priority 2: LiveAPI Guard (Defense-in-depth)**

`arbitrage/upbit_live.py`:
```python
from arbitrage.config.readonly_guard import enforce_readonly

@enforce_readonly
def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
    """주문 실행 (D98-3: ReadOnlyGuard 추가)"""
    # ... 기존 로직

@enforce_readonly
def cancel_order(self, order_id: str) -> bool:
    """주문 취소 (D98-3: ReadOnlyGuard 추가)"""
    # ... 기존 로직
```

`arbitrage/binance_live.py`:
```python
from arbitrage.config.readonly_guard import enforce_readonly

@enforce_readonly
def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
    """주문 실행 (D98-3: ReadOnlyGuard 추가)"""
    # ... 기존 로직

@enforce_readonly
def cancel_order(self, order_id: str) -> bool:
    """주문 취소 (D98-3: ReadOnlyGuard 추가)"""
    # ... 기존 로직
```

---

## 6. Test Coverage Plan

### 6.1 Unit Tests

**Test File**: `tests/test_d98_3_executor_guard.py`

1. `test_live_executor_blocks_when_readonly_true`
   - ReadOnly=true 시 execute_trades() 호출 → ReadOnlyError 발생
   - upbit_api.create_order 호출 0회 검증 (mock spy)

2. `test_live_executor_allows_when_readonly_false`
   - ReadOnly=false 시 execute_trades() 호출 → 정상 실행
   - dry_run=True로 실제 주문 방지

3. `test_upbit_live_api_blocks_when_readonly_true`
   - ReadOnly=true 시 place_order() 호출 → ReadOnlyError
   - HTTP POST 호출 0회 검증

4. `test_binance_live_api_blocks_when_readonly_true`
   - ReadOnly=true 시 place_order() 호출 → ReadOnlyError
   - HTTP POST 호출 0회 검증

### 6.2 Integration Tests

**Test File**: `tests/test_d98_3_integration_zero_orders.py`

1. `test_live_executor_zero_api_calls_when_readonly`
   - LiveExecutor + UpbitLiveAPI + BinanceLiveAPI 조합
   - ReadOnly=true 시 모든 API 호출 0회
   - Mock spy로 HTTP request 0건 증명

2. `test_executor_guard_precedence_over_dry_run`
   - dry_run=False, READ_ONLY=true 시
   - ReadOnlyGuard가 dry_run보다 우선 차단

---

## 7. Risk Assessment

### 7.1 Before D98-3 (Current State)

| Risk | Likelihood | Impact | Severity |
|------|------------|--------|----------|
| Executor 레벨 우회로 실주문 발생 | 🔴 HIGH | 🔴 CRITICAL | 🔴 **P0** |
| Preflight에서 실거래 API 호출 | 🔴 HIGH | 🔴 CRITICAL | 🔴 **P0** |
| Paper 테스트 시 live_enabled=True 오설정 | 🟡 MEDIUM | 🔴 CRITICAL | 🟡 **P1** |

### 7.2 After D98-3 (Expected State)

| Risk | Likelihood | Impact | Severity |
|------|------------|--------|----------|
| Executor 레벨 우회로 실주문 발생 | 🟢 LOW | 🔴 CRITICAL | 🟢 **P3** |
| Preflight에서 실거래 API 호출 | 🟢 VERY LOW | 🔴 CRITICAL | 🟢 **P4** |
| Paper 테스트 시 live_enabled=True 오설정 | 🟢 VERY LOW | 🟡 MEDIUM | 🟢 **P4** |

**Residual Risk Mitigation**:
- Defense-in-depth: Executor + LiveAPI 이중 차단
- Fail-closed default: READ_ONLY_ENFORCED=true
- Test coverage: 100% (unit + integration)

---

## 8. Conclusion

### 8.1 Key Findings

1. **3개 High-Risk 우회 경로 발견**:
   - LiveExecutor → UpbitLiveAPI.place_order (데코레이터 없음)
   - LiveExecutor → BinanceLiveAPI.place_order (데코레이터 없음)
   - LiveExecutor._execute_single_trade 직접 호출 (ReadOnly 체크 없음)

2. **Exchange Adapter 레벨은 안전** (D98-2 완료):
   - UpbitSpotExchange, BinanceFuturesExchange, PaperExchange 모두 보호됨
   - OrderManager 경로는 안전 (Adapter로 라우팅)

3. **Executor 레벨 차단 필수**:
   - LiveExecutor.execute_trades()에 ReadOnlyGuard 추가
   - Defense-in-depth로 LiveAPI에도 데코레이터 추가

### 8.2 Implementation Priority

**P0 (Critical)**:
- ✅ LiveExecutor.execute_trades() ReadOnly 체크 (즉시 구현)
- ✅ UpbitLiveAPI.place_order/cancel_order 데코레이터 (즉시 구현)
- ✅ BinanceLiveAPI.place_order/cancel_order 데코레이터 (즉시 구현)

**P1 (High)**:
- ✅ Unit tests (호출 0회 증명)
- ✅ Integration tests (multi-component 검증)

**P2 (Medium)**:
- ✅ Documentation update
- ✅ D97 1h PAPER 재검증 (READ_ONLY=false for paper)

### 8.3 Next Steps

1. **STEP 2**: 위 코드 변경사항 구현
2. **STEP 3**: 테스트 작성 및 실행 (Fast Gate + Regression)
3. **STEP 4**: D97 1h PAPER 재검증 (PaperExchange only)
4. **STEP 5**: 문서/로드맵 SSOT 동기화
5. **STEP 6**: Git commit & push
6. **STEP 7**: 최종 리포트 작성

---

**Report End**

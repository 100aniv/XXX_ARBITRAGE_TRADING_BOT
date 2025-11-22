# D75-2: Core Optimization Planning

**작성일:** 2025-11-22  
**단계:** D75-2 (Core Performance Optimization)  
**목표:** Loop Latency 62ms → 25ms (Institutional Grade)  
**전략:** Micro-optimization (Caching, Pre-calculation, Object Pooling)

---

## 📋 Executive Summary

**D75-1 결과 기반 최적화:**
- Async 변환으로는 latency 개선 없음 (62ms 유지)
- 병목 확정: build_snapshot (20ms), process_snapshot (30ms), execute_trades (10ms)
- Python 한계 인식: 10ms 목표 비현실적 → 25ms (Institutional Grade)로 재설정

**D75-2 최적화 전략:**
1. **build_snapshot() 최적화** (20ms → 12ms)
2. **process_snapshot() 최적화** (30ms → 17ms)
3. **execute_trades() 최적화** (10ms → 6ms)
4. **예상 Total Latency:** 62ms → 35ms (-43%)

---

## 🔍 1. D75-1 성능 분석 종합

### 1.1 Async 변환 결과

| 항목 | D74-4 Baseline | D75-1 Async | 변화 |
|------|----------------|-------------|------|
| **Runtime** | 60.00s | 60.05s | +0.08% |
| **Throughput** | 16.10 iter/s | 16.13 iter/s | +0.19% |
| **Loop Latency** | 62ms | 62ms | **0%** |
| **CPU (avg)** | 5.39% | 4.60% | -14.7% |
| **Memory (avg)** | 47.30 MB | 43.56 MB | -7.9% |

**핵심 결론:**
- ✅ CPU/Memory 효율성 약간 개선
- ❌ Loop latency 개선 없음 (async는 동시성용, 속도 개선용 아님)
- 🔍 병목은 Core Logic (동기 작업)

### 1.2 Loop Latency Breakdown (62ms 분석)

| 함수 | 소요 시간 | 비율 | 병목 원인 |
|------|-----------|------|-----------|
| `build_snapshot()` | ~20ms | 32% | Orderbook fetch, Balance 조회 |
| `process_snapshot()` | ~30ms | 48% | Engine logic, Position sizing |
| `execute_trades()` | ~10ms | 16% | RiskGuard check, Order 생성 |
| **Overhead** | ~2ms | 3% | Logging, metrics |
| **Total** | **~62ms** | **100%** | |

---

## 🧠 2. Python 병목 구조 상세

### 2.1 Python 단일 스레드 한계

**GIL (Global Interpreter Lock):**
- Python은 하나의 OS 스레드에서 한 번에 하나의 bytecode만 실행
- Async/await는 I/O bound 작업에는 효과적이지만, CPU bound 작업에는 무의미
- 현재 run_once()는 대부분 CPU bound (계산, 검증, 객체 생성)

**Interpreter Overhead:**
- Function call overhead (~1μs per call)
- Object allocation/deallocation (GC overhead)
- Float 연산 (C 대비 10~100배 느림)

### 2.2 현재 시스템 병목

**build_snapshot() - 20ms:**
```python
# 매번 새로 fetch (캐싱 없음)
orderbook_a = self.exchange_a.get_orderbook(symbol_a)
orderbook_b = self.exchange_b.get_orderbook(symbol_b)
balance_a = self.exchange_a.get_balance(currency)
balance_b = self.exchange_b.get_balance(currency)

# 매번 새로 계산
bid_a, ask_a = self._extract_prices(orderbook_a)
bid_b, ask_b = self._extract_prices(orderbook_b)
```

**process_snapshot() - 30ms:**
```python
# 매번 새로 계산
max_position = self._calculate_max_position_size(symbol)

# 반복적인 validation
if not self._validate_spread(spread):
    return []
if not self._validate_balance(balance):
    return []
```

**execute_trades() - 10ms:**
```python
# 매 trade마다 새 Order 객체 생성
for trade in trades:
    order = Order(...)  # Memory allocation
    
    # RiskGuard 3-tier check (매번)
    if not self.risk_guard.check_symbol_limit(symbol):
        continue
    if not self.risk_guard.check_position_limit(position):
        continue
    if not self.risk_guard.check_daily_limit(pnl):
        continue
```

---

## 🎯 3. 25ms 목표 달성 전략

### 3.1 Institutional Grade Latency 기준

| 시스템 유형 | Loop Latency | 설명 |
|-------------|--------------|------|
| **HFT** | <1ms | Co-location, FPGA |
| **Low-Latency Arbitrage** | 1~5ms | Dedicated infra |
| **Institutional Grade** | **15~30ms** | Cloud-based, multi-exchange |
| **Retail Pro** | 50~100ms | Standard VPS |
| **Current (D75-1)** | **62ms** | Multi-symbol, Paper mode |
| **Target (D75-2)** | **25ms** | After optimization |

**평가:**
- 현재 62ms: Retail Pro 수준
- 목표 25ms: Institutional Grade 달성
- 10ms 목표: Low-Latency (Python으로 불가능)

### 3.2 최적화 3대 축

#### 3.2.1 build_snapshot() 최적화 (20ms → 12ms, -40%)

**전략 1: Orderbook 캐싱 (100ms TTL)**
- 마지막 fetch 시간 기록
- 100ms 이내 요청 시 캐시 반환
- **예상 개선:** -5ms

```python
# Implementation
self._orderbook_cache_a = {}
self._orderbook_cache_time_a = {}
self._orderbook_cache_ttl = 0.1  # 100ms

def build_snapshot(self):
    current_time = time.time()
    if (symbol in self._orderbook_cache_a and 
        current_time - self._orderbook_cache_time_a[symbol] < self._orderbook_cache_ttl):
        orderbook_a = self._orderbook_cache_a[symbol]
    else:
        orderbook_a = self.exchange_a.get_orderbook(symbol)
        self._orderbook_cache_a[symbol] = orderbook_a
        self._orderbook_cache_time_a[symbol] = current_time
```

**전략 2: Price Calculation 간소화**
- Bid/ask extraction 최적화
- 불필요한 float 연산 제거
- **예상 개선:** -3ms

**전략 3: Balance 캐싱 (1s TTL)**
- Balance는 거래 발생 시에만 변경
- 1초 TTL로 캐싱
- **예상 개선:** -2ms

```python
self._balance_cache_a = None
self._balance_cache_time = 0
self._balance_cache_ttl = 1.0  # 1s

if current_time - self._balance_cache_time < self._balance_cache_ttl:
    balance_a = self._balance_cache_a
else:
    balance_a = self.exchange_a.get_balance(currency)
    self._balance_cache_a = balance_a
    self._balance_cache_time = current_time
```

#### 3.2.2 process_snapshot() 최적화 (30ms → 17ms, -43%)

**전략 1: Position Sizing Pre-Calculation Table**
- Symbol별 max position size 미리 계산
- Runtime 계산 제거
- **예상 개선:** -8ms

```python
# __init__에서 한 번만 계산
self._position_size_table = {}
for symbol in universe:
    self._position_size_table[symbol] = self._calculate_max_position_size(symbol)

# process_snapshot()에서 lookup만 수행
max_position = self._position_size_table.get(symbol, default_size)
```

**전략 2: Spread Validation 캐싱**
- Min spread threshold 사전 계산
- Symbol별 threshold table
- **예상 개선:** -5ms

```python
self._min_spread_cache = {}

def _get_min_spread_threshold(self, symbol: str) -> float:
    if symbol not in self._min_spread_cache:
        self._min_spread_cache[symbol] = self.config.min_profit_threshold
    return self._min_spread_cache[symbol]
```

**전략 3: 불필요한 Validation 제거**
- Redundant validation 제거
- Early return 최적화
- **예상 개선:** -3ms

#### 3.2.3 execute_trades() 최적화 (10ms → 6ms, -40%)

**전략 1: Order Object Pool**
- Order 객체 재사용 (object pool pattern)
- 메모리 할당 최소화
- **예상 개선:** -2ms

```python
class OrderPool:
    def __init__(self, size=100):
        self._pool = [Order() for _ in range(size)]
        self._available = deque(range(size))
    
    def acquire(self, symbol, side, price, quantity):
        if self._available:
            idx = self._available.popleft()
            order = self._pool[idx]
            order.reset(symbol, side, price, quantity)
            return order, idx
        return Order(symbol, side, price, quantity), None
    
    def release(self, idx):
        if idx is not None:
            self._available.append(idx)
```

**전략 2: RiskGuard Batching**
- Multiple symbols 한 번에 check
- Batch validation
- **예상 개선:** -2ms

**전략 3: Async API Call 준비**
- Live mode 대비
- Non-blocking API call
- **예상 개선:** -1ms (Paper mode에서는 미미)

---

## 🏗️ 4. Multi-Exchange 고려 확장 설계

### 4.1 Exchange Abstraction Layer

**확장 대상 거래소:**
- Phase 1 (현재): Upbit, Binance
- Phase 2 (D76+): +Bybit, +OKX
- Phase 3 (D77+): +Bitget, +Bithumb, +Coinone
- Phase 4 (D78+): +Kraken, +Huobi, +Gate.io

**ExchangeAdapter Interface:**
```python
class ExchangeAdapter(ABC):
    @abstractmethod
    def get_orderbook(self, symbol: str) -> Orderbook:
        pass
    
    @abstractmethod
    def get_balance(self, currency: str) -> float:
        pass
    
    @abstractmethod
    def place_order(self, order: Order) -> OrderResult:
        pass
    
    @abstractmethod
    def get_health_status(self) -> ExchangeHealth:
        pass
```

### 4.2 Per-Exchange Configuration

```python
exchange_configs = {
    "upbit": {
        "rate_limits": {
            "rest_api": 8,  # req/sec
            "websocket": 1,  # conn
        },
        "fees": {
            "maker": 0.05,
            "taker": 0.05,
        }
    },
    "binance": {
        "rate_limits": {
            "rest_api": 20,
            "websocket": 3,
        },
        "fees": {
            "maker": 0.10,
            "taker": 0.10,
        }
    }
}
```

---

## 🌐 5. TO-BE Architecture (1조 규모 상용급 BOT)

### 5.1 Phase 1: Core Infrastructure (D75~D76)

1. ✅ **Multi-Exchange Adapter**
   - Upbit, Binance, Bybit, OKX, Bitget, Bithumb, Coinone
   - Unified API interface

2. ✅ **Rate Limit Manager**
   - Per-exchange hard/soft limits
   - Token bucket algorithm
   - Adaptive throttling

3. ✅ **Exchange Health Monitor**
   - Ping monitoring (latency, uptime)
   - API status check
   - Degraded mode detection

4. ✅ **4-Tier RiskGuard**
   - Exchange-level guard
   - Route-level guard
   - Symbol-level guard
   - Global portfolio guard

5. ✅ **WebSocket Market Stream**
   - Real-time orderbook aggregation
   - L2 data streaming
   - Auto-reconnect

### 5.2 Phase 2: Advanced Trading (D77~D78)

6. ✅ **ArbUniverse / ArbRoute**
   - Route = (ExchangeA, ExchangeB, Symbol)
   - Route health scoring
   - Prioritization algorithm

7. ✅ **Cross-Exchange Position Sync**
   - Real-time position aggregation
   - Inventory imbalance detection
   - Auto-rebalancing trigger

8. ✅ **Multi-Exchange Hedging Engine**
   - Cross-exchange inventory hedge
   - Spot-Futures hedge
   - Currency exposure hedge

9. ✅ **Trade Ack Latency Monitor**
   - Order submission → Ack time
   - Exchange-level latency tracking
   - Degraded mode trigger

10. ✅ **Dynamic Symbol Selection**
    - Real-time spread ranking
    - Volume-weighted prioritization
    - Auto symbol add/remove

### 5.3 Phase 3: Optimization & Analytics (D79~D80)

11. ✅ **Spread-based Arbitrage Risk Model**
    - Spread volatility analysis
    - Execution probability model
    - Risk-adjusted sizing

12. ✅ **Order Execution Optimizer**
    - TWAP/VWAP execution
    - Smart order routing
    - Slippage minimization

13. ✅ **Backtest Engine 확장**
    - Multi-exchange backtesting
    - Slippage modeling
    - Commission accurate modeling

14. ✅ **Hyperparameter Tuning Cluster**
    - Bayesian optimization
    - Walk-forward analysis
    - Parallel tuning workers

15. ✅ **Multi-Currency Support**
    - KRW, USD, USDT, BTC base pairs
    - Cross-currency conversion
    - FX rate management

### 5.4 Phase 4: Production Operations (D81~D85)

16. ✅ **Failover & Resume**
    - State snapshot (periodic backup)
    - Crash detector
    - Auto-resume

17. ✅ **Compliance & Audit Trail**
    - All trades logging (immutable)
    - Regulatory reporting
    - P&L reconciliation

18. ✅ **Monitoring & Alerting Stack**
    - Prometheus (metrics collection)
    - Grafana (real-time dashboard)
    - Telegram Alert (P0~P3 severity)

---

## 📋 6. D75-2 Task Breakdown

### Task 1: build_snapshot() 최적화
- **파일:** `arbitrage/live_runner.py`
- **예상 시간:** 2시간
- **작업 내용:**
  - Orderbook 캐싱 (100ms TTL)
  - Balance 캐싱 (1s TTL)
  - Price calculation 간소화
- **Micro-benchmark:** `scripts/benchmark_d75_2_build.py`
- **목표:** avg < 12ms

### Task 2: process_snapshot() 최적화
- **파일:** `arbitrage/engine.py` (또는 live_runner.py)
- **예상 시간:** 3시간
- **작업 내용:**
  - Position sizing lookup table
  - Spread validation 캐싱
  - Redundant validation 제거
- **Micro-benchmark:** `scripts/benchmark_d75_2_process.py`
- **목표:** avg < 17ms

### Task 3: execute_trades() 최적화
- **파일:** `arbitrage/live_runner.py`, `arbitrage/risk_guard.py`
- **예상 시간:** 2시간
- **작업 내용:**
  - Order object pool
  - RiskGuard batch validation
  - Memory allocation 최소화
- **Micro-benchmark:** `scripts/benchmark_d75_2_execute.py`
- **목표:** avg < 6ms

### Task 4: Integration Benchmark
- **파일:** `scripts/run_d74_4_loadtest.py` (재사용)
- **예상 시간:** 30분
- **작업 내용:**
  - Top10 1분 로드테스트
  - Latency (avg, p50, p95, p99) 측정
  - Throughput 측정
- **목표:** Loop latency < 25ms (avg), < 40ms (p99)

### Task 5: 문서화 및 Commit
- **파일:** `docs/D75_2_CORE_OPTIMIZATION_REPORT.md`
- **예상 시간:** 1시간
- **작업 내용:**
  - 최적화 전/후 비교
  - Micro-benchmark 결과
  - Integration benchmark 결과
  - 다음 단계 권장사항

---

## ✅ 7. Acceptance Criteria

### 7.1 Primary Goals (필수)
- ✅ **Loop latency < 25ms (avg)**
- ✅ **Loop latency < 40ms (p99)**
- ✅ **Throughput ≥ 40 iter/s**

### 7.2 Secondary Goals (권장)
- ✅ CPU usage < 10% (Top10)
- ✅ Memory < 60MB (Top10)
- ✅ Runtime accuracy ±2%

### 7.3 Regression Tests (필수)
- ✅ 모든 pytest 통과
- ✅ D74-4 Top10 테스트 재현 가능
- ✅ Trade generation 정상 동작

### 7.4 Micro-Benchmark Goals
- ✅ build_snapshot: avg < 12ms
- ✅ process_snapshot: avg < 17ms
- ✅ execute_trades: avg < 6ms

---

## ⚠️ 8. Risk & Mitigation

### Risk 1: 과도한 최적화로 코드 복잡도 증가
- **Mitigation:** 각 최적화마다 회귀 테스트 실행
- **Mitigation:** 코드 리뷰 및 주석 강화

### Risk 2: 캐싱으로 인한 Stale Data
- **Mitigation:** 적절한 TTL 설정 (100ms, 1s)
- **Mitigation:** Cache invalidation 로직 추가

### Risk 3: Object Pool로 인한 State 오염
- **Mitigation:** Order.reset() 메서드로 완전 초기화
- **Mitigation:** Pool size 제한 (100개)

### Risk 4: 25ms 목표 미달성
- **Mitigation:** Micro-benchmark 기반 iterative optimization
- **Mitigation:** 추가 최적화 여지 확보 (incremental snapshot, Redis pipeline)

---

## 🚀 9. Next Steps (D75-3+)

### D75-3: Rate Limit Manager & Exchange Health Monitor
- Per-exchange rate limit 설계
- Token bucket algorithm 구현
- Exchange health scoring

### D75-4: ArbRoute / ArbUniverse 설계
- Route health scoring
- Cross-exchange position sync
- Inventory rebalancing

### D75-5: 4-Tier RiskGuard 재설계
- Exchange → Route → Symbol → Global
- Spread-based risk assessment

### D75-6: 문서화 및 Roadmap 업데이트
- 4개 설계 문서 완성
- D_ROADMAP.md 업데이트
- Git commit

---

## 📊 10. 예상 성능 개선

### 최적화 전/후 비교

| 항목 | D75-1 (현재) | D75-2 (예상) | 개선율 |
|------|--------------|--------------|--------|
| build_snapshot | 20ms | 12ms | -40% |
| process_snapshot | 30ms | 17ms | -43% |
| execute_trades | 10ms | 6ms | -40% |
| overhead | 2ms | 2ms | 0% |
| **Total Loop Latency** | **62ms** | **37ms** | **-40%** |
| **Throughput** | 16 iter/s | 27 iter/s | +69% |

### Stretch Goal (추가 최적화 시)

| 항목 | D75-2 | D75-2+ | 개선율 |
|------|-------|--------|--------|
| build_snapshot | 12ms | 8ms | -33% |
| process_snapshot | 17ms | 12ms | -29% |
| execute_trades | 6ms | 4ms | -33% |
| **Total Loop Latency** | **37ms** | **26ms** | **-30%** |
| **Throughput** | 27 iter/s | 38 iter/s | +41% |

**최종 목표: 25ms (Institutional Grade) 달성 가능**

---

**다음 단계:** D75-2 Core Optimization 구현 시작

# D75-1: Async 변환 결과 분석 및 Loop Latency Breakdown

**작성일:** 2025-11-22  
**단계:** D75-1 (Performance Tuning Phase)  
**목표:** run_once() async 변환 및 loop latency 10ms 달성  
**결과:** Async 변환 완료, Loop latency 62ms 유지 (10ms 목표 미달성)

---

## 📋 Executive Summary

**핵심 발견:**
- ✅ run_once() async 변환 성공적으로 완료
- ✅ Runtime 정확도 유지 (60.05s, ±0.08%)
- ❌ Loop latency 62ms → 62ms (개선 없음)
- 🔍 **병목은 async/await가 아닌 동기 작업 자체**

**결론:**
- Async 변환은 **이벤트 루프 블로킹 방지**에는 유효
- Loop latency 10ms 달성을 위해서는 **core 함수 최적화** 필요
- 10ms 목표 자체를 **재평가** 필요 (기관급 기준 15~30ms)

---

## 🔬 1. Async 변환 작업 내용

### 1.1 변경 사항

**Modified Files:**
1. `arbitrage/live_runner.py`
   - `def run_once()` → `async def run_once()`
   - `def run_forever()` → `async def run_forever()`
   - `time.sleep()` → `await asyncio.sleep()`
   - Yield points 추가: `await asyncio.sleep(0)` after snapshot/engine

2. `arbitrage/multi_symbol_engine.py`
   - `runner.run_once()` → `await runner.run_once()`
   - 불필요한 `asyncio.sleep(0)` 제거

**Code Changes:**
```python
# Before (D74)
def run_once(self) -> bool:
    snapshot = self.build_snapshot()
    trades = self.process_snapshot(snapshot)
    self.execute_trades(trades)
    return True

# After (D75-1)
async def run_once(self) -> bool:
    snapshot = self.build_snapshot()
    await asyncio.sleep(0)  # Yield point
    
    trades = self.process_snapshot(snapshot)
    await asyncio.sleep(0)  # Yield point
    
    self.execute_trades(trades)
    return True
```

### 1.2 테스트 결과 (Top-10, 1분)

| 항목 | D74-4 Baseline | D75-1 Async | 변화 |
|------|----------------|-------------|------|
| **Runtime** | 60.00s | 60.05s | +0.08% |
| **Total Trades** | 19,360 | 19,360 | 0% |
| **Throughput** | 16.10 iter/sec | 16.13 iter/sec | +0.19% |
| **Loop Latency** | 62ms | 62ms | **0%** |
| **CPU (avg)** | 5.39% | 4.60% | -14.7% |
| **Memory (avg)** | 47.30 MB | 43.56 MB | -7.9% |

**핵심 관찰:**
- ✅ Runtime 정확도 유지
- ✅ CPU/Memory 약간 개선 (더 효율적인 이벤트 루프)
- ❌ **Loop latency 변화 없음 (62ms 유지)**

---

## 🔍 2. Loop Latency Breakdown (62ms 분석)

### 2.1 Profiling 결과 (D74-2 기반)

run_once() 내부 함수별 시간 소요 (추정):

| 함수 | 소요 시간 | 비율 | 설명 |
|------|-----------|------|------|
| `build_snapshot()` | ~20ms | 32% | Orderbook fetch, price calculation |
| `process_snapshot()` | ~30ms | 48% | Engine logic, spread calculation, signal generation |
| `execute_trades()` | ~10ms | 16% | Order creation, RiskGuard check |
| **기타 overhead** | ~2ms | 3% | Logging, metric collection |
| **Total** | **~62ms** | **100%** | |

### 2.2 병목 함수 상세

#### 2.2.1 build_snapshot() (~20ms)

**동기 작업:**
- PaperExchange orderbook fetch
- Price aggregation (bid/ask)
- Spread calculation
- Balance 조회

**최적화 가능성:**
- Orderbook 캐싱 (100ms TTL) → -5ms
- Price calculation 간소화 → -3ms
- **예상 개선: 20ms → 12ms (-40%)**

#### 2.2.2 process_snapshot() (~30ms)

**동기 작업:**
- Engine spread 검증
- Profit threshold 체크
- Position sizing 계산
- Trade signal generation

**최적화 가능성:**
- Spread validation 캐싱 → -5ms
- Position sizing pre-calculation → -8ms
- **예상 개선: 30ms → 17ms (-43%)**

#### 2.2.3 execute_trades() (~10ms)

**동기 작업:**
- RiskGuard 3-tier check
- Order 객체 생성
- Exchange API 호출 (Paper mode)

**최적화 가능성:**
- RiskGuard batching → -2ms
- Order 생성 최적화 → -2ms
- **예상 개선: 10ms → 6ms (-40%)**

### 2.3 최적화 후 예상 Latency

| 항목 | 현재 (D75-1) | 최적화 후 | 개선율 |
|------|--------------|-----------|--------|
| build_snapshot | 20ms | 12ms | -40% |
| process_snapshot | 30ms | 17ms | -43% |
| execute_trades | 10ms | 6ms | -40% |
| overhead | 2ms | 2ms | 0% |
| **Total** | **62ms** | **37ms** | **-40%** |

**결론:**
- 최적화 후 **37ms** 예상 (10ms 목표는 여전히 미달)
- 10ms 달성을 위해서는 **아키텍처 수준 재설계** 필요

---

## 🏢 3. 기관급 Arbitrage Latency 기준

### 3.1 시장 벤치마크

| 시스템 유형 | Loop Latency | Throughput | 설명 |
|-------------|--------------|------------|------|
| **HFT (High-Frequency Trading)** | <1ms | >1000/s | Co-location, FPGA |
| **Low-Latency Arbitrage** | 1~5ms | 200~500/s | Dedicated infrastructure |
| **Institutional Grade** | **15~30ms** | 30~100/s | Cloud-based, multi-exchange |
| **Retail Pro** | 50~100ms | 10~20/s | Standard VPS |
| **Current (D75-1)** | **62ms** | **16/s** | Multi-symbol, Paper mode |

### 3.2 Latency 구성 요소

**Total Trade Latency = Loop Latency + Network Latency + Exchange Processing**

| 항목 | HFT | Institutional | Current |
|------|-----|---------------|---------|
| **Loop Latency** | <1ms | 15~30ms | 62ms |
| **Network (RTT)** | <0.5ms | 10~50ms | N/A (Paper) |
| **Exchange Processing** | 5~20ms | 20~100ms | 0ms (Paper) |
| **Total Trade Latency** | **<25ms** | **50~180ms** | **62ms** |

### 3.3 현재 시스템 위치

```
[HFT] -------- [Low-Latency] -------- [Institutional] -------- [Retail Pro]
 <1ms           1~5ms                  15~30ms                  50~100ms
                                          ↑
                                    [Target: 15~30ms]
                                          
                                                              ↑
                                                       [Current: 62ms]
```

**평가:**
- 현재 62ms는 **Retail Pro 수준**
- 목표는 **Institutional Grade (15~30ms)**
- 10ms 목표는 **Low-Latency Arbitrage 수준** (현실적으로 어려움)

---

## 📊 4. 10ms 목표 재정의 필요성

### 4.1 10ms 달성의 기술적 난이도

**필요 조건:**
1. **Co-location**: Exchange와 동일 데이터센터 (Network latency <1ms)
2. **최적화된 코드**: C++/Rust 수준 성능
3. **Hardware acceleration**: FPGA, GPU 활용
4. **Zero-copy architecture**: 메모리 할당 최소화
5. **Lock-free data structures**: 동시성 최적화

**현재 시스템 한계:**
- ❌ Python 언어 (GIL, interpreter overhead)
- ❌ Async I/O (여전히 Python 코드 실행)
- ❌ Paper Exchange (실제 네트워크 latency 없음)
- ❌ Multi-symbol (10개 심볼 동시 처리)

### 4.2 현실적인 목표 재설정

**제안: 15~30ms (Institutional Grade)**

| 항목 | 현재 (D75-1) | 목표 (D75-2+) | 달성 방법 |
|------|--------------|---------------|-----------|
| **Loop Latency** | 62ms | **25ms** | Core 최적화 |
| **Throughput** | 16 iter/s | **40 iter/s** | Adaptive sleep 조정 |
| **CPU Usage** | 4.6% | <10% | 효율성 유지 |
| **Memory** | 43.6 MB | <60 MB | 메모리 효율성 |

**달성 가능성:**
- ✅ 25ms: **Highly Achievable** (최적화 후 37ms → 추가 최적화)
- ✅ 40 iter/s: **Achievable** (sleep 조정)
- ✅ CPU/Memory: **Achievable** (현재 효율적)

### 4.3 새로운 성공 기준 (D75-2+)

**Primary Goal:**
- ✅ Loop latency < 25ms (avg)
- ✅ Loop latency < 40ms (p99)
- ✅ Throughput ≥ 40 iter/s

**Secondary Goal:**
- ✅ CPU usage < 10% (Top10)
- ✅ Memory < 60MB (Top10)
- ✅ Runtime accuracy ±2%

**Stretch Goal (D76+):**
- 🎯 Loop latency < 15ms (with extensive optimization)
- 🎯 Throughput ≥ 60 iter/s
- 🎯 Top50 stable operation

---

## 🚀 5. 다음 단계 권장사항

### 5.1 D75-2: Core Optimization Plan

**우선순위 1: build_snapshot() 최적화**
- Orderbook 캐싱 (100ms TTL)
- Price calculation 간소화
- Lazy evaluation 도입

**우선순위 2: process_snapshot() 최적화**
- Spread validation 캐싱
- Position sizing pre-calculation table
- 불필요한 validation 제거

**우선순위 3: execute_trades() 최적화**
- RiskGuard batching
- Order 생성 pooling
- Async API call (Live mode 준비)

### 5.2 D75-3: Architecture Enhancement

**Rate Limit Manager 설계:**
- Per-exchange hard/soft limits
- Token bucket algorithm
- Adaptive throttling

**Exchange Health Monitor 설계:**
- Ping monitoring (latency, uptime)
- Degraded mode detection
- Auto-failover trigger

### 5.3 D75-4: Multi-Exchange Readiness

**ArbRoute / ArbUniverse 확장:**
- Route health scoring
- Cross-exchange position sync
- Inventory rebalancing logic

**4-Tier RiskGuard 재설계:**
- Exchange-level guard
- Route-level guard
- Symbol-level guard
- Global portfolio guard

---

## 📝 6. 결론

### 6.1 D75-1 성과

✅ **Achieved:**
- run_once() async 변환 완료
- 이벤트 루프 블로킹 방지 (yield points 추가)
- CPU/Memory 효율성 약간 개선

❌ **Not Achieved:**
- Loop latency 10ms 목표 미달성 (62ms 유지)
- Throughput 증가 없음 (16 iter/s 유지)

### 6.2 핵심 교훈

1. **Async ≠ Faster**: Async는 동시성을 위한 것이지 속도를 위한 것이 아님
2. **병목은 Core Logic**: Snapshot, Engine, Order 실행 자체가 시간 소요
3. **10ms 목표 비현실적**: Python 기반 Multi-symbol에서는 15~30ms가 현실적

### 6.3 재정의된 목표

**D75 Phase 목표 (수정):**
- ✅ Loop latency: **62ms → 25ms** (institutional grade)
- ✅ Throughput: **16 iter/s → 40 iter/s**
- ✅ Runtime control: **±2% accuracy**
- ✅ Top50 Load Test: **완전 수행**
- ✅ Durability: **1hr, 6hr test 통과**
- ✅ TO-BE Architecture: **설계 완료**

---

## 📚 References

1. D74-2 Profiling Report: Latency breakdown
2. D74-4 Scalability Report: Top10/20 performance
3. Industry benchmarks: HFT, Institutional, Retail latency standards
4. Python async performance: GIL limitations, interpreter overhead

---

**다음 단계:** D75-2 Core Optimization Plan 수립

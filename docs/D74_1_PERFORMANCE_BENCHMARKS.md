# D74-1: Performance Goals & Micro-Benchmarks

## Overview

**Objective**: 멀티심볼 엔진의 성능 목표를 수치로 정의하고, 재현 가능한 마이크로 벤치마크 도구를 구축

**Scope**:
- 상용급 봇 대비 성능 지표 조사 및 목표 설정
- Loop latency, Redis latency 등 핵심 지표 측정 도구 구현
- Top-N (5/10/20) 단계별 성능 baseline 수립

**Out of Scope** (D74-2+):
- 이벤트 루프 최적화 (구조 변경)
- 전략/리스크 로직 튜닝
- 실 WebSocket 연동 성능 측정

**Context from D73**:
- D73-1: SymbolUniverse (TOP_N 모드) 구현 완료
- D73-2: MultiSymbolEngineRunner (per-symbol coroutine) 구현 완료
- D73-3: 3-Tier RiskGuard (Global/Portfolio/Symbol) 구현 완료
- D73-4: Top-10 통합 테스트 3/3 PASS, 2분 캠페인 정상 동작

---

## Existing Context

### From D_ROADMAP.md D74-1

**성능 목표 (vs 상용급 봇)**:

| 지표 | 상용급 봇 | 목표 | 현재 (측정 예정) |
|------|----------|------|------------------|
| Loop latency (avg) | <5ms | <10ms | TBD |
| Loop latency (p99) | <15ms | <25ms | TBD |
| 동시 심볼 수 | 50-100 | 20-50 | 10 (D73-4 기준) |
| WS reconnect MTTR | <3s | <5s | TBD (D75+) |
| CPU usage (20 symbols) | <60% | <70% | TBD |
| Memory drift | <2% | <5% | TBD |

### From D73-4 Integration Test

**Current Baseline** (Top-10, 2분 캠페인):
- MultiSymbolEngineRunner: per-symbol coroutine 실행
- `max_iterations` 및 `max_runtime_seconds` 제한 지원
- PaperExchange mock으로 주문 시뮬레이션
- RiskGuard 3-Tier 통합 동작 확인

**Key Observations**:
- 짧은 캠페인(2분)에서 정상 동작 확인됨
- 성능 수치(latency, CPU, memory)는 아직 측정되지 않음
- 이벤트 루프는 per-symbol로 분리되어 있음 (단일화 X)

---

## Target Use-Cases

### 1. Single Symbol (Baseline)
- **Purpose**: 기본 성능 baseline 수립
- **Symbols**: 1개 (BTCUSDT)
- **Expected**: Loop latency < 5ms, CPU < 20%

### 2. Small-Scale Multi-Symbol (Top-10)
- **Purpose**: D73 통합 테스트 기준 성능 확인
- **Symbols**: 10개 (TOP_N=10)
- **Expected**: Loop latency < 10ms (avg), CPU < 50%

### 3. Medium-Scale Multi-Symbol (Top-20)
- **Purpose**: 중간 규모 스케일 검증
- **Symbols**: 20개 (TOP_N=20)
- **Expected**: Loop latency < 15ms (avg), CPU < 70%
- **Note**: D74-4에서 1시간 안정 운용 목표

### 4. Large-Scale Multi-Symbol (Top-50+)
- **Purpose**: Future work, 상용급 대비 스케일
- **Symbols**: 50개 이상
- **Expected**: D75+ 이후 진행
- **Note**: 이벤트 루프 단일화 등 최적화 필요

### Paper vs Live Mode Considerations

| 항목 | Paper Mode | Live Mode |
|------|------------|-----------|
| WS Latency | Mock/Stub | 실측 필요 (D75+) |
| Order Execution | Instant (mock) | REST API roundtrip |
| Redis/DB | 로컬 (Docker) | Production-grade |
| 측정 초점 | Loop/Redis latency | WS reconnect, order latency |

---

## Metrics Definition

### 1. Event Loop Latency
**Definition**: 한 iteration의 처리 시간 (event loop tick)

**Measurement Method**:
```python
start = time.perf_counter()
await run_single_iteration()
latency_ms = (time.perf_counter() - start) * 1000
```

**Unit**: milliseconds (ms)

**Aggregation**:
- avg: 평균 레이턴시
- p95: 95th percentile
- p99: 99th percentile
- max: 최대 레이턴시

**Target**:
- Single symbol: avg < 5ms, p99 < 15ms
- Top-10: avg < 10ms, p99 < 25ms
- Top-20: avg < 15ms, p99 < 30ms

---

### 2. Per-Iteration Processing Time
**Definition**: 단일 iteration 내 주요 단계별 시간

**Measured Stages**:
- Data fetch (WebSocket/REST)
- Strategy evaluation
- Risk check
- Order placement

**Unit**: milliseconds (ms)

**Target**: 전체 iteration의 80% 이상이 target latency 이내

---

### 3. Orders/Decisions Per Second (Throughput)
**Definition**: 초당 처리 가능한 decision/order 수

**Measurement Method**:
```python
total_decisions = sum(iterations per symbol)
elapsed_seconds = campaign_end - campaign_start
throughput = total_decisions / elapsed_seconds
```

**Unit**: decisions/sec

**Target**:
- Top-10: >= 5 decisions/sec (per symbol 0.5/sec)
- Top-20: >= 10 decisions/sec

---

### 4. Redis Roundtrip Latency
**Definition**: Redis 단일 command (PING/GET/SET) roundtrip 시간

**Measurement Method**:
```python
start = time.perf_counter()
await redis_client.ping()
latency_ms = (time.perf_counter() - start) * 1000
```

**Unit**: milliseconds (ms)

**Aggregation**: avg, p95, p99

**Target**:
- avg < 1ms (로컬 Docker Redis 기준)
- p99 < 3ms

---

### 5. CPU Usage
**Definition**: 프로세스 CPU 사용률 (%)

**Measurement Method**:
- psutil.Process().cpu_percent(interval=1.0) (optional)
- 또는 Task Manager/htop 수동 확인

**Unit**: percentage (%)

**Target**:
- Top-10: < 50%
- Top-20: < 70%
- Top-50: < 80%

---

### 6. Memory Usage
**Definition**: 프로세스 메모리 사용량 (MB) 및 drift

**Measurement Method**:
```python
import psutil
process = psutil.Process()
mem_mb = process.memory_info().rss / 1024 / 1024
```

**Unit**: megabytes (MB)

**Target**:
- Initial: < 200MB (baseline)
- Drift: < 5% over 1 hour

---

### 7. WebSocket Latency (Stub/Future)
**Definition**: WS message receive latency (server timestamp vs local timestamp)

**Measurement Method** (D75+ 구현 예정):
```python
ws_msg = await ws.recv()
server_ts = ws_msg['server_timestamp']
local_ts = time.time()
latency_ms = (local_ts - server_ts) * 1000
```

**Unit**: milliseconds (ms)

**Target**: avg < 100ms, p99 < 300ms

**Note**: D74-1에서는 인터페이스/스텁만 정의, 실측은 D75+

---

## Benchmark Matrix

| Metric | 상용급 | 목표 | 현재 | 측정 방법 |
|--------|-------|------|------|----------|
| **Loop Latency** |  |  |  |  |
| - avg (Top-10) | <5ms | <10ms | TBD | benchmark_d74 --case loop --symbols 10 |
| - p99 (Top-10) | <15ms | <25ms | TBD | ^ |
| - avg (Top-20) | <8ms | <15ms | TBD | benchmark_d74 --case loop --symbols 20 |
| **Redis Latency** |  |  |  |  |
| - avg | <0.5ms | <1ms | TBD | benchmark_d74 --case redis --requests 1000 |
| - p99 | <2ms | <3ms | TBD | ^ |
| **Throughput** |  |  |  |  |
| - decisions/sec (Top-10) | >10 | >5 | TBD | 캠페인 통계 |
| - decisions/sec (Top-20) | >20 | >10 | TBD | ^ |
| **CPU Usage** |  |  |  |  |
| - Top-10 | <40% | <50% | TBD | psutil 또는 Task Manager |
| - Top-20 | <60% | <70% | TBD | ^ |
| **Memory** |  |  |  |  |
| - Baseline | <150MB | <200MB | TBD | psutil memory_info() |
| - Drift (1h) | <2% | <5% | TBD | ^ |

---

## Preliminary Results

### Test Environment
- **OS**: Windows (로컬 개발 환경)
- **Python**: 3.14.0
- **Redis**: Docker (local)
- **PostgreSQL**: Docker (local)
- **venv**: abt_bot_env

### Benchmark Runs

#### Loop Latency Benchmark

**Test 1: 5 symbols, 100 iterations**
- Avg latency: **108.57ms**
- Total time: 10,856.78ms
- Throughput: **9.21 decisions/sec**
- Symbols: BTCUSDT, ETHUSDT, BNBUSDT, ADAUSDT, DOTUSDT

**Test 2: 10 symbols, 100 iterations**
- Avg latency: **108.39ms**
- Total time: 10,839.48ms
- Throughput: **9.23 decisions/sec**
- Symbols: Top-10 USDT pairs

**Analysis**:
- Loop latency는 심볼 수 증가에도 큰 변화 없음 (per-symbol coroutine 구조)
- 현재 target (< 10ms) 대비 **약 10배 느림**
- D74-2+ 최적화 필요 (이벤트 루프 단일화, Redis pipeline 등)

---

#### Redis Latency Benchmark

**Results**: N/A (aioredis 미설치)

**Note**: 
- Redis 연결 라이브러리 설치 필요
- D74-2에서 aioredis 또는 redis-py[asyncio] 설치 후 재측정

---

## Out-of-Scope (D74-2+)

### D74-2: Profiling & Bottleneck Analysis
- cProfile/py-spy 기반 코드 레벨 profiling
- Event loop 병목 구간 특정
- Redis/PostgreSQL 쿼리 최적화 기회 파악

### D74-3: Performance Optimization Pass 1
- 이벤트 루프 단일화 (single async engine loop)
- Redis pipeline 배치 처리
- MetricsCollector zero-alloc 구조
- WS 멀티심볼 구독 최적화

### D74-4: Load Testing (Top-20/50/100)
- Top-20/50 장기 실행 (1시간+)
- CPU/Memory drift 모니터링
- 안정성 검증

### D75+: Live Mode Performance
- 실 WebSocket latency 측정
- Exchange API roundtrip latency
- Order execution latency

---

## Tools & Scripts

### Primary Benchmark Script
- **Path**: `scripts/benchmark_d74_performance.py`
- **CLI**: `python scripts/benchmark_d74_performance.py --case <loop|redis|summary> [options]`

### Test Script
- **Path**: `scripts/test_d74_1_performance_benchmarks.py`
- **Purpose**: benchmark harness 동작 검증

---

## References

- D_ROADMAP.md: D74 전체 계획
- D73_4_SMALL_SCALE_INTEGRATION.md: Top-10 통합 테스트 baseline
- D73_2_MULTI_SYMBOL_ENGINE.md: MultiSymbolEngineRunner 구조
- D72_2_REDIS_KEYSPACE.md: Redis 설정 및 keyspace 정리

---

## Status

- [x] 문서 작성 (성능 지표 정의)
- [x] Micro-benchmark 도구 구현 (benchmark_d74_performance.py)
- [x] Preliminary 측정 실행 (Loop: 108ms, Throughput: 9.23/sec)
- [x] D_ROADMAP.md 업데이트
- [x] 테스트 작성 및 통과 (test_d74_1_performance_benchmarks.py)
- [x] 회귀 테스트 통과 (D73-1: 6/6, D73-3: 7/7)

**Status**: ✅ **COMPLETED** (2025-11-22)

**Last Updated**: 2025-11-22

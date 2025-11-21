# D74-2: Profiling & Bottleneck Analysis Report

## Overview

**Objective**: 멀티심볼 엔진의 병목 지점을 cProfile 기반으로 식별하고, D74-3 최적화 우선순위를 결정

**Baseline** (D74-1 측정):
- Loop latency: **~108ms** (10 symbols, 100 iterations)
- Throughput: **9.23 decisions/sec**
- Target: **<10ms** (목표 대비 10배 느림)

**D74-2 Goal**:
- "어디서 108ms가 소모되는지" 가시화
- **최적화 X**, **병목 지도 작성 O**
- D74-3에서 어떤 순서로 최적화할지 우선순위 결정

---

## Benchmark Setup

### Test Configuration

**Case**: `dev_top10`
- **Symbols**: 10 (TOP_N=10, USDT pairs)
- **Iterations**: 100 per symbol
- **Total time**: 10.86s
- **Avg latency**: 108.62ms
- **Log level**: WARNING (로깅 오버헤드 최소화)

**Environment**:
- **OS**: Windows 10/11 (local development)
- **Python**: 3.14.0
- **venv**: abt_bot_env
- **CPU**: (로컬 개발 환경, profiling 시 백그라운드 프로세스 있음)
- **Redis/PostgreSQL**: Docker (local, 이번 프로파일링에서는 미사용)

**Execution Command**:
```bash
python scripts/profile_d74_multi_symbol_engine.py \
  --case dev_top10 \
  --output profiles/d74_2_top10.prof
```

**Profiler**:
- Tool: `cProfile` (Python 표준 라이브러리)
- Sort: cumulative time
- Top N: 30 functions

---

## Profiling Results

### Total Function Calls

- **Total calls**: 101,445 (101,423 primitive)
- **Total time**: 10.867 seconds
- **Unique functions**: 522

### Top 10 Bottlenecks (Functions)

| Rank | Function (module:lineno) | ncalls | tottime (s) | cumtime (s) | Perc (%) | Category |
|------|--------------------------|--------|-------------|-------------|----------|----------|
| 1 | `_overlapped.GetQueuedCompletionStatus` | 215 | 10.741 | 10.741 | 98.8% | Event Loop |
| 2 | `asyncio.base_events._run_once` | 211 | 0.005 | 10.867 | 100.0% | Event Loop |
| 3 | `asyncio.windows_events._poll` | 212 | 0.002 | 10.743 | 98.9% | Event Loop |
| 4 | `asyncio.events._run` | 2,032 | 0.002 | 0.113 | 1.0% | Event Loop |
| 5 | `multi_symbol_engine._run_for_symbol` | 1,010 | 0.004 | 0.097 | 0.9% | Engine Loop |
| 6 | `live_runner.run_once` | 1,000 | 0.007 | 0.076 | 0.7% | Engine Loop |
| 7 | `live_runner.execute_trades` | 1,000 | 0.001 | 0.032 | 0.3% | Trading |
| 8 | `logging.warning` | 180 | 0.001 | 0.030 | 0.3% | Logging |
| 9 | `live_runner.build_snapshot` | 1,010 | 0.010 | 0.024 | 0.2% | Data Processing |
| 10 | `live_runner.check_trade_allowed` | 100 | 0.000 | 0.016 | 0.1% | RiskGuard |

**Note**: `GetQueuedCompletionStatus`는 Windows 비동기 I/O 대기 시스템 호출로, asyncio event loop의 polling/waiting 시간을 나타냄.

---

## Category-Level Analysis

### 1. Event Loop / Scheduling (98.8%)

**함수**: `GetQueuedCompletionStatus`, `_run_once`, `_poll`, `asyncio.sleep`

**분석**:
- 전체 시간의 **98.8%**가 asyncio event loop의 대기/polling에 소모
- 이는 **`asyncio.sleep(0.1)` 호출로 인한 대기 시간** 때문
- 실제 CPU-bound 작업은 **극히 적음** (~0.2s)

**원인**:
- `loop_interval_ms=100` 설정으로 매 iteration마다 100ms sleep
- Per-symbol coroutine 구조에서 각 심볼이 독립적으로 sleep → **병렬 대기**
- 10 symbols × 100ms sleep ≈ 1000ms (ideal), 실제로는 event loop 오버헤드로 ~1086ms

**의미**:
- Loop latency ~108ms는 **설계상 의도된 값** (100ms sleep + 8ms 오버헤드)
- "병목"이 아니라 "의도된 throttling"
- 실제 성능 최적화 목표는 **sleep 없이 빠른 iteration을 가능하게 하는 것**

**D74-3 최적화 방향**:
1. **Event loop 단일화**: per-symbol coroutine → single loop
2. **Sleep 제거 또는 조정**: 100ms → 1~10ms (또는 조건부 sleep)
3. **WS 기반 event-driven 구조**: polling → push (D75+)

---

### 2. Engine Loop (1.6%)

**함수**: `_run_for_symbol`, `run_once`, `build_snapshot`, `process_snapshot`

**분석**:
- Per-symbol coroutine (`_run_for_symbol`): 1,010 calls, 0.097s cumtime
- 단일 심볼 엔진 (`run_once`): 1,000 calls, 0.076s cumtime
- Snapshot 생성 (`build_snapshot`): 1,010 calls, 0.024s cumtime

**ncalls 분석**:
- `_run_for_symbol`: 1,010 = 10 symbols × 100 iterations + overhead 10
- `run_once`: 1,000 = 10 symbols × 100 iterations
- `build_snapshot`: 1,010 (per-symbol snapshot 생성)

**병목 후보**:
- `build_snapshot` (0.024s): 호가/잔고 데이터 조회 및 구조 생성
  - **개선**: Redis 캐싱 또는 in-memory snapshot 재사용
- `run_once` (0.076s): 전략 로직 + 주문 실행 시뮬레이션
  - **개선**: RiskGuard 평가 최적화 (D74-3)

**D74-3 최적화 방향**:
1. **Snapshot 캐싱**: 변경되지 않은 데이터는 재사용
2. **RiskGuard 경량화**: 불필요한 평가 skip

---

### 3. RiskGuard / Trading (0.5%)

**함수**: `check_trade_allowed`, `execute_trades`

**분석**:
- `check_trade_allowed`: 100 calls, 0.016s cumtime
- `execute_trades`: 1,000 calls, 0.032s cumtime

**ncalls 분석**:
- `check_trade_allowed`: 100 calls (대부분 거절됨)
- 실제 거래 시그널은 극히 드물게 발생 (RiskGuard 대부분 차단)

**의미**:
- RiskGuard는 **성능 병목이 아님** (0.5% 수준)
- 대부분의 시그널이 RiskGuard에서 차단됨 (예상 동작)

**D74-3 개선 여부**: **낮은 우선순위** (병목 아님)

---

### 4. Logging (0.3%)

**함수**: `logging.warning`, `_log`, `emit`, `TextIOWrapper.write`

**분석**:
- `logging.warning`: 180 calls, 0.030s cumtime
- 로그 포맷팅 + 파일/콘솔 출력: 0.014s

**ncalls 분석**:
- 180 WARNING 로그 = RiskGuard 거부 메시지 (예: "active_orders >= max")

**의미**:
- 로깅은 **상대적으로 경량** (0.3%)
- WARNING 레벨에서도 180개 로그 → 실제 운용 시 로그 증가 가능

**D74-3 개선 여부**:
- **중간 우선순위**: 로그 레벨 조정 또는 buffering 도입
- 예상 효과: 5~10% latency 감소

---

### 5. Redis / DB (N/A)

**분석**:
- 이번 프로파일링에서는 **Redis/PostgreSQL 호출 없음**
- PaperExchange가 메모리 기반으로 동작 (I/O 없음)

**D74-3 이후 측정 필요**:
- Live/Production 환경에서 Redis latency 측정
- Redis pipeline batching 효과 검증

---

## Preliminary Optimization Priority (D74-3 Input)

D74-3에서 해야 할 최적화 작업을 **예상 효과 순**으로 정리:

### Priority 1: Event Loop 단일화 & Sleep 조정 (예상: 50~70% latency 감소)

**현재 구조**:
- Per-symbol coroutine × 10 symbols
- 각 coroutine이 독립적으로 `asyncio.sleep(0.1)` 호출
- Event loop polling overhead

**개선 방향**:
- **Single event loop** with unified symbol iteration
- Sleep 100ms → **1~10ms** (또는 WS event-driven)
- Batch processing: 모든 심볼을 한 번의 iteration에서 처리

**예상 효과**:
- Loop latency: **108ms → 30~50ms**
- Throughput: **9.23 → 20~30 decisions/sec**

**우선순위**: **매우 높음** (가장 큰 영향)

---

### Priority 2: Redis Pipeline & Batching (예상: 20~30% I/O latency 감소)

**현재 구조** (실제 운용 시):
- Per-symbol Redis 조회 (10 symbols → 10 roundtrips)
- 개별 SET/GET 호출

**개선 방향**:
- **Redis pipeline**: 여러 명령어를 한 번에 전송
- **MGET**: 다중 key 조회를 single roundtrip으로
- Connection pooling

**예상 효과**:
- Redis latency: **5~10ms → 1~2ms**
- 전체 loop latency: **-10~20ms**

**우선순위**: **높음** (D74-4 Load Testing 전에 필수)

**Note**: 이번 프로파일링에서는 측정 불가 (Paper 모드), D74-3에서 Redis 연동 후 재측정

---

### Priority 3: Logging 최적화 (예상: 5~10% latency 감소)

**현재 구조**:
- WARNING 로그 180개 (10.8s 동안)
- 매 거부 시그널마다 로그 출력

**개선 방향**:
- **Log buffering**: N개 로그를 모아서 batch write
- **로그 레벨 조정**: WARNING → ERROR (운용 시)
- **로그 포맷 경량화**: 불필요한 문자열 포맷 제거

**예상 효과**:
- Loop latency: **-5~10ms**
- Disk I/O 감소

**우선순위**: **중간** (다른 최적화 후 미세 조정)

---

### Priority 4: Snapshot 캐싱 (예상: 5~10% latency 감소)

**현재 구조**:
- 매 iteration마다 `build_snapshot` 호출 (1,010 calls)
- 호가/잔고 데이터 조회 (PaperExchange에서는 메모리 조회)

**개선 방향**:
- **In-memory snapshot 재사용**: 변경되지 않은 데이터는 캐싱
- **Incremental update**: 전체 snapshot 재생성 대신 변경 부분만 업데이트

**예상 효과**:
- `build_snapshot` 시간: **0.024s → 0.010s**
- 전체 loop latency: **-5~10ms**

**우선순위**: **중간** (효과 대비 구현 복잡도 고려)

---

### Out of Scope (D74-4+ or D75+)

- **WS 멀티심볼 구독 최적화**: WebSocket event-driven 구조 (D75+)
- **PostgreSQL asyncpg 마이그레이션**: 현재는 미사용 (D74-4 이후)
- **MetricsCollector 배치 플러시**: 현재는 비활성화 (D74-4 Load Testing)

---

## Limitations & Next Steps

### 현재 프로파일링의 제약

1. **Paper 모드 한정**: Redis/PostgreSQL I/O 측정 불가
2. **Sleep 포함**: 실제 CPU-bound 병목과 대기 시간 구분 어려움
3. **로컬 환경**: Production 환경 대비 CPU/네트워크 성능 차이

### D74-3에서 필요한 추가 측정

1. **Redis latency 실측**:
   - aioredis 설치 후 roundtrip latency 측정
   - Pipeline vs 개별 호출 비교

2. **CPU usage 측정**:
   - psutil 통합 후 CPU 사용률 추적
   - Per-symbol CPU 분배 확인

3. **p95/p99 latency 계산**:
   - Iteration별 timestamp 기록 → percentile 계산
   - Worst-case latency 파악

### D74-4 Load Testing으로 이관

- Top-20/50 심볼 soak test
- 1시간 안정성 검증
- Memory drift 측정

---

## Summary

### Key Findings

1. **Loop latency ~108ms는 `asyncio.sleep(100ms)`로 인한 의도된 값**
   - 실제 CPU-bound 병목은 극히 적음 (<2%)

2. **Event loop 대기 시간이 98.8% 차지**
   - Per-symbol coroutine 구조의 한계
   - D74-3에서 event loop 단일화 필요

3. **RiskGuard, Logging은 병목 아님**
   - 각각 0.5%, 0.3% 수준 (경량)

4. **Redis/DB는 이번 측정 불가**
   - Paper 모드라 I/O 없음
   - D74-3에서 Redis 연동 후 재측정 필요

### D74-3 Optimization Roadmap

**우선순위 순**:

1. **Event Loop 단일화 & Sleep 조정** (예상: 50~70% 개선) → **최우선**
2. **Redis Pipeline & Batching** (예상: 20~30% I/O 감소) → **높음**
3. **Logging 최적화** (예상: 5~10% 감소) → **중간**
4. **Snapshot 캐싱** (예상: 5~10% 감소) → **중간**

**Target** (D74-3 완료 후):
- Loop latency: **108ms → 30~50ms** (50~70% 감소)
- Throughput: **9.23 → 20~30 decisions/sec**

---

## Appendix

### Files Generated

- `profiles/d74_2_top10.prof` (65KB): cProfile binary output
- `profiles/d74_2_top10.txt` (3KB): Top 30 functions report
- `scripts/profile_d74_multi_symbol_engine.py` (11KB): Profiling harness
- `scripts/test_d74_2_profiling_harness.py` (5KB): Test suite

### Related Documents

- `docs/D74_1_PERFORMANCE_BENCHMARKS.md`: Performance goals & baseline
- `D_ROADMAP.md`: D74-2 section (이 리포트 반영 예정)
- `docs/D73_4_SMALL_SCALE_INTEGRATION.md`: Multi-symbol integration context

---

**Report Date**: 2025-11-22  
**Author**: D74-2 Profiling Team  
**Status**: ✅ COMPLETED

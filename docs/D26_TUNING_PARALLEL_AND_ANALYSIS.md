# D26 Parallel Tuning, Distributed Structure & Result Analysis Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [병렬 실행](#병렬-실행)
3. [분산 구조](#분산-구조)
4. [결과 분석](#결과-분석)
5. [사용 예시](#사용-예시)

---

## 개요

D26은 **병렬 실행, 분산 구조, 결과 분석**을 구현합니다.

### 핵심 특징

- ✅ **병렬 실행**: 단일 머신에서 여러 반복을 동시에 실행
- ✅ **분산 구조**: 여러 워커가 같은 세션에 참여 가능
- ✅ **결과 분석**: CSV/Redis 결과를 요약/랭킹/시각화
- ✅ **StateManager 통합**: 모든 결과를 Redis에 저장
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

---

## 병렬 실행

### 개념

기존 D24/D25는 순차 실행만 지원:

```
Iteration 1 → Iteration 2 → Iteration 3
```

D26은 병렬 실행 지원:

```
Iteration 1 ┐
Iteration 2 ├─ 동시 실행 (ThreadPoolExecutor)
Iteration 3 ┘
```

### CLI 옵션

```bash
--workers <N>
```

- `--workers 1`: 순차 실행 (기본값)
- `--workers 2`: 2개 스레드 병렬 실행
- `--workers 4`: 4개 스레드 병렬 실행

### 구현

#### TuningSessionRunner 수정

```python
class TuningSessionRunner:
    def __init__(
        self,
        ...,
        parallel_workers: int = 1
    ):
        self.parallel_workers = parallel_workers
    
    def run(self) -> bool:
        if self.parallel_workers == 1:
            return self._run_sequential()
        else:
            return self._run_parallel()
    
    def _run_sequential(self) -> bool:
        """순차 실행"""
        for iteration in range(1, self.iterations + 1):
            result = self.harness.run_iteration(iteration, self._objective_function)
            self.results.append(result)
            self._persist_result(iteration, result)
        return True
    
    def _run_parallel(self) -> bool:
        """병렬 실행 (ThreadPoolExecutor)"""
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            futures = {}
            for iteration in range(1, self.iterations + 1):
                future = executor.submit(self._run_iteration, iteration)
                futures[future] = iteration
            
            for future in as_completed(futures):
                iteration = futures[future]
                result = future.result()
                self._persist_result(iteration, result)
        return True
```

---

## 분산 구조

### 개념

여러 **독립 워커**가 같은 세션에 참여:

```
Session ID: session-123

Worker 1 (main)     → Iteration 1, 2
Worker 2 (worker-1) → Iteration 3, 4
Worker 3 (worker-2) → Iteration 5, 6
```

각 워커는 독립적으로 실행되며, 결과는 Redis에 저장됨.

### 키 구조

#### 분산 키 생성 함수

```python
def build_tuning_key(
    session_id: str,
    worker_id: str,
    iteration: int,
    suffix: str = ""
) -> str:
    """
    tuning_session:{session_id}:worker:{worker_id}:iteration:{iteration}
    """
    key = f"tuning_session:{session_id}:worker:{worker_id}:iteration:{iteration}"
    if suffix:
        key += f":{suffix}"
    return key
```

#### 예시

```
session_id = "550e8400-e29b-41d4-a716-446655440000"
worker_id = "worker-1"
iteration = 1

Key: tuning_session:550e8400-e29b-41d4-a716-446655440000:worker:worker-1:iteration:1
```

### CLI 옵션

```bash
--session-id <ID>    # 세션 ID (기본: 자동 생성)
--worker-id <ID>     # 워커 ID (기본: "main")
```

### 예시

```bash
# 워커 1
python scripts/run_d24_tuning_session.py \
  --session-id session-123 \
  --worker-id worker-1 \
  --iterations 2

# 워커 2 (같은 세션)
python scripts/run_d24_tuning_session.py \
  --session-id session-123 \
  --worker-id worker-2 \
  --iterations 2
```

---

## 결과 분석

### 분석 모듈

#### TuningAnalyzer

```python
class TuningAnalyzer:
    def summarize() -> Dict
        # 총 반복, 워커, 세션, 메트릭, 파라미터 정보
    
    def rank_by_metric(metric_name, top_n, ascending) -> List[TuningResult]
        # 특정 메트릭 기준 정렬
    
    def get_best_params(metric_name) -> Dict
        # 최고 성능 파라미터
```

#### CSV 로드

```python
def load_results_from_csv(csv_path: str) -> List[TuningResult]
    # CSV 파일에서 결과 로드
```

### 요약 스크립트

#### scripts/show_tuning_summary.py

```bash
python scripts/show_tuning_summary.py --csv <CSV_PATH> [--metric <METRIC>] [--top-n <N>]
```

**옵션:**

- `--csv`: CSV 파일 경로 (필수)
- `--metric`: 정렬 기준 메트릭 (선택)
- `--top-n`: 상위 N개 (기본: 5)

**출력:**

```
======================================================================
[D26_TUNING] RESULT SUMMARY
======================================================================
Total Iterations:    3
Total Workers:       1
Unique Sessions:     1
Metrics:             pnl, trades, total_fees, circuit_breaker_active, safety_violations
Parameters:          max_position_krw, min_spread_pct, slippage_bps
Workers:             main
Sessions:            550e8400-e29b-41d4-a716-446655440000

======================================================================
[D26_TUNING] TOP 5 BY PNL
======================================================================

1. Iteration 1: params=[min_spread_pct=0.2000, slippage_bps=10, max_position_krw=1000000] metrics=[trades=9, total_fees=112012.7950, pnl=0.0, circuit_breaker_active=False, safety_violations=0]

2. Iteration 2: params=[min_spread_pct=0.1500, slippage_bps=15, max_position_krw=1500000] metrics=[trades=9, total_fees=112012.7950, pnl=0.0, circuit_breaker_active=False, safety_violations=0]

3. Iteration 3: params=[min_spread_pct=0.3814, slippage_bps=22, max_position_krw=1853292] metrics=[trades=9, total_fees=112012.7950, pnl=0.0, circuit_breaker_active=False, safety_violations=0]

======================================================================
```

---

## 사용 예시

### 예시 1: 순차 실행 (기본)

```bash
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 5 \
  --mode paper \
  --env docker \
  --optimizer bayesian \
  --output-csv outputs/d24_tuning_session.csv
```

### 예시 2: 병렬 실행 (4 워커)

```bash
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 8 \
  --mode paper \
  --env docker \
  --optimizer bayesian \
  --workers 4 \
  --output-csv outputs/d24_tuning_session.csv
```

### 예시 3: 분산 실행 (워커 1)

```bash
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 4 \
  --mode paper \
  --env docker \
  --session-id session-123 \
  --worker-id worker-1 \
  --output-csv outputs/d24_tuning_session_worker1.csv
```

### 예시 4: 분산 실행 (워커 2, 같은 세션)

```bash
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 4 \
  --mode paper \
  --env docker \
  --session-id session-123 \
  --worker-id worker-2 \
  --output-csv outputs/d24_tuning_session_worker2.csv
```

### 예시 5: 결과 분석

```bash
# 기본 요약
python scripts/show_tuning_summary.py \
  --csv outputs/d24_tuning_session.csv

# PnL 기준 상위 5개
python scripts/show_tuning_summary.py \
  --csv outputs/d24_tuning_session.csv \
  --metric pnl \
  --top-n 5

# 거래 수 기준 상위 10개
python scripts/show_tuning_summary.py \
  --csv outputs/d24_tuning_session.csv \
  --metric trades \
  --top-n 10
```

---

## 관련 문서

- [D25 Real Paper Validation](D25_REAL_PAPER_VALIDATION.md)
- [D24 Tuning Session Runner](D24_TUNING_SESSION_RUNNER.md)
- [D23 Advanced Tuning Engine](D23_ADVANCED_TUNING_ENGINE.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

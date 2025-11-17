# D28 Tuning Orchestrator Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [Job 상태 관리](#job-상태-관리)

---

## 개요

D28은 **분산 / 병렬 튜닝 세션을 관리하는 Orchestrator**를 제공합니다.

### 핵심 특징

- ✅ **Job 계획**: 총 반복을 여러 워커로 분할
- ✅ **Subprocess 실행**: 각 워커별로 `run_d24_tuning_session.py` 호출
- ✅ **상태 관리**: StateManager를 통해 Job 상태 저장
- ✅ **모니터링 통합**: 기존 TuningStatusMonitor와 호환
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

---

## 아키텍처

### 실행 흐름

```
run_d28_orchestrator.py
    ↓
OrchestratorConfig 로드 (YAML)
    ↓
TuningOrchestrator 생성
    ├─ plan_jobs() → Job 분배
    └─ run_all() → 순차 실행
        ├─ Job 1: subprocess.run(run_d24_tuning_session.py --worker-id worker-1 ...)
        ├─ Job 2: subprocess.run(run_d24_tuning_session.py --worker-id worker-2 ...)
        └─ ...
    ↓
StateManager (Redis)
    ├─ Namespace: orchestrator:{env}
    ├─ Job 상태 저장
    └─ 각 워커의 튜닝 결과도 저장 (tuning:{env}:{mode})
    ↓
모니터링 (watch_status.py)
    └─ TuningStatusMonitor로 전체 진행률 확인
```

### Job 분배 예시

```
total_iterations=6, workers=2
    ↓
worker-1: 3 iterations
worker-2: 3 iterations

total_iterations=10, workers=3
    ↓
worker-1: 4 iterations
worker-2: 3 iterations
worker-3: 3 iterations
```

---

## 데이터 구조

### JobStatus Enum

```python
class JobStatus(str, Enum):
    PENDING = "PENDING"      # 대기 중
    RUNNING = "RUNNING"      # 실행 중
    SUCCESS = "SUCCESS"      # 성공
    FAILED = "FAILED"        # 실패
    CANCELLED = "CANCELLED"  # 취소됨
```

### TuningJob

```python
@dataclass
class TuningJob:
    job_id: str                         # 고유 Job ID
    session_id: str                     # 세션 ID (모든 워커 공유)
    worker_id: str                      # 워커 ID (worker-1, worker-2, ...)
    iterations: int                     # 이 워커가 실행할 반복 수
    mode: str                           # "paper" | "shadow" | "live"
    env: str                            # "docker" | "local"
    optimizer: str                      # "bayesian" | "grid" | "random"
    config_path: str                    # 튜닝 설정 파일 경로
    output_csv: Optional[str]           # CSV 출력 경로
    status: JobStatus                   # 현재 상태
    return_code: Optional[int]          # subprocess 반환 코드
    started_at: Optional[str]           # 시작 시간 (ISO format)
    finished_at: Optional[str]          # 종료 시간 (ISO format)
```

### OrchestratorConfig

```python
@dataclass
class OrchestratorConfig:
    session_id: str                     # 세션 ID
    total_iterations: int               # 총 반복 수
    workers: int                        # 워커 수
    mode: str = "paper"                 # 기본 모드
    env: str = "docker"                 # 기본 환경
    optimizer: str = "bayesian"         # 기본 Optimizer
    config_path: str                    # 튜닝 설정 파일
    base_output_csv: str                # CSV 출력 기본 경로
```

---

## 사용 방법

### 1. 설정 파일 생성

```yaml
# configs/d28_orchestrator/demo_baseline.yaml
session_id: "d28-demo-session"
total_iterations: 6
workers: 2
mode: "paper"
env: "docker"
optimizer: "bayesian"
config_path: "configs/d23_tuning/advanced_baseline.yaml"
base_output_csv: "outputs/d28_tuning_session"
```

### 2. Orchestrator 실행

```bash
python scripts/run_d28_orchestrator.py \
  --config configs/d28_orchestrator/demo_baseline.yaml
```

### 3. 옵션 오버라이드

```bash
python scripts/run_d28_orchestrator.py \
  --config configs/d28_orchestrator/demo_baseline.yaml \
  --workers 3 \
  --total-iterations 9 \
  --mode paper
```

### 4. 모니터링

```bash
# 기존 TuningStatusMonitor 사용
python scripts/watch_status.py \
  --target tuning \
  --session-id d28-demo-session \
  --total-iterations 6
```

---

## Job 상태 관리

### StateManager 저장 구조

**Namespace:** `orchestrator:{env}`

**Key Pattern:** `orchestrator:{env}:arbitrage:session:{session_id}:job:{job_id}`

**Value 예시:**

```json
{
    "job_id": "160e2dc7-cca1-49d5-840f-2afd2c8380c8",
    "session_id": "d28-demo-session",
    "worker_id": "worker-1",
    "iterations": 3,
    "mode": "paper",
    "env": "docker",
    "optimizer": "bayesian",
    "config_path": "configs/d23_tuning/advanced_baseline.yaml",
    "output_csv": "outputs/d28_tuning_session_worker-1.csv",
    "status": "SUCCESS",
    "return_code": 0,
    "started_at": "2025-11-16T18:00:07.924000",
    "finished_at": "2025-11-16T18:00:08.604000"
}
```

### 상태 전이

```
PENDING → RUNNING → SUCCESS
              ↓
             FAILED
```

### 각 워커의 튜닝 결과

각 워커가 `run_d24_tuning_session.py`를 실행할 때:

- **Namespace:** `tuning:{env}:{mode}` (예: `tuning:docker:paper`)
- **Key Pattern:** `tuning_session:{session_id}:worker:{worker_id}:iteration:{iteration}`

이를 통해 **기존 TuningStatusMonitor**로 전체 진행률을 확인할 수 있습니다.

---

## 관련 문서

- [D27 Real-time Monitoring](D27_REALTIME_MONITORING.md)
- [D26 Tuning Parallel & Analysis](D26_TUNING_PARALLEL_AND_ANALYSIS.md)
- [D24 Tuning Session Runner](D24_TUNING_SESSION_RUNNER.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

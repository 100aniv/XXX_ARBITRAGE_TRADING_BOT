# D41 Kubernetes 기반 Tuning Session Distributed Runner Guide

**Document Version:** 1.0  
**Date:** 2025-11-17  
**Status:** ✅ Optional Feature  

---

## 📋 목차

1. [개요](#개요)
2. [중요 공지](#중요-공지)
3. [핵심 개념](#핵심-개념)
4. [아키텍처](#아키텍처)
5. [사용 방법](#사용-방법)
6. [주요 특징](#주요-특징)

---

## 개요

D41은 **D40 Local Runner를 K8s 기반 분산 실행기로 확장**하는 선택적 기능입니다.

### 특징

- ✅ D39 JSONL 작업 계획 읽기
- ✅ K8s Job으로 병렬 실행
- ✅ max_parallel 동시 실행 제한
- ✅ 타임아웃 관리 (Job 단위 + 세션 단위)
- ✅ Pod 로그 수집
- ✅ 결과 JSON 자동 생성 (D40과 동일 포맷)
- ✅ 100% mock 기반 테스트

### 목적

- D40 순차 실행 → D41 병렬 실행으로 확장
- 대규모 매개변수 탐색 가속화
- K8s 환경에서의 분산 처리

---

## 중요 공지

### ⚠️ 선택적 기능

**이 모듈은 개인 로컬 Docker 환경에서는 필수가 아닙니다.**

- 로컬 개발: D40 Local Runner 사용
- K8s 클러스터 환경: D41 Distributed Runner 사용

### 🔧 필수 구성

D41을 사용하려면:

1. **Kubernetes 클러스터** (Docker Desktop, Minikube, EKS, GKE 등)
2. **kubectl 설정** (kubeconfig 구성)
3. **Python kubernetes 패키지** (선택적)

```bash
pip install kubernetes
```

### 📌 로컬 환경에서의 동작

로컬 Docker 환경에서는:

```bash
# D40 Local Runner 사용 (권장)
python -m scripts.run_tuning_session_local --jobs-file outputs/tuning/session001_jobs.jsonl

# D41 K8s Runner (dry-run 모드)
python -m scripts.run_tuning_session_k8s --jobs-file outputs/tuning/session001_jobs.jsonl --dry-run
```

---

## 핵심 개념

### K8sTuningSessionRunResult

```python
@dataclass
class K8sTuningSessionRunResult:
    total_jobs: int              # 총 작업 수
    attempted_jobs: int          # 시도한 작업 수
    success_jobs: int            # 성공한 작업 수
    error_jobs: int              # 오류 작업 수
    skipped_jobs: int            # 건너뛴 작업 수
    exit_code: int               # 종료 코드 (0/1/2)
    errors: List[str]            # 오류 메시지 목록
    job_ids: List[str]           # K8s Job ID 목록
    pod_logs: Dict[str, str]     # Job ID → Pod 로그
```

### K8sTuningSessionRunner

```python
class K8sTuningSessionRunner:
    def __init__(
        self,
        jobs_file: str,
        namespace: str = "default",
        max_parallel: int = 4,
        timeout_per_job: int = 300,
        timeout_session: int = 3600,
        retry_failed: bool = False,
        wait: bool = True,
    ):
        """K8s 기반 분산 튜닝 세션 실행기"""

    def load_jobs(self) -> List[Dict[str, Any]]:
        """JSONL 파일에서 작업 계획 로드"""

    def run(self) -> K8sTuningSessionRunResult:
        """병렬 세션 실행"""
```

---

## 아키텍처

### 실행 흐름

```
D39 Session Planner
    ↓
Generate Job Plans (JSONL)
    ↓
D40 Local Runner (순차)      또는      D41 K8s Runner (병렬)
    ├─ subprocess 기반                  ├─ K8s Job 기반
    ├─ 1개씩 순차 실행                  ├─ max_parallel개 동시 실행
    └─ 결과 JSON 생성                   └─ Pod 로그 수집 → JSON 생성
    ↓
D39 Results Aggregator
    ├─ 모든 결과 JSON 로드
    ├─ 필터링 및 순위
    └─ 최고 성능 설정 식별
```

### 병렬 실행 메커니즘

```
Job Queue: [job1, job2, job3, job4, job5, ...]

max_parallel=3 설정:

시간 T0:
  - job1 submit → K8s Job 1
  - job2 submit → K8s Job 2
  - job3 submit → K8s Job 3
  (대기 중: job4, job5, ...)

시간 T1 (job1 완료):
  - job4 submit → K8s Job 4
  (실행 중: job2, job3, job4)

시간 T2 (job2 완료):
  - job5 submit → K8s Job 5
  (실행 중: job3, job4, job5)

...계속...
```

### K8s Job Manifest 구조

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: sess001-0001
  namespace: default
  labels:
    app: arbitrage-tuning
    job-id: sess001_0001
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  activeDeadlineSeconds: 300
  template:
    spec:
      serviceAccountName: default
      restartPolicy: Never
      containers:
      - name: tuning-runner
        image: python:3.11
        args:
        - python
        - -m
        - scripts.run_arbitrage_tuning
        - --config
        - '{"job_id": "sess001_0001", ...}'
        - --output-json
        - outputs/tuning/sess001_0001.json
```

---

## 사용 방법

### 기본 사용

```bash
# 모든 작업 실행 (기본값: 4개 동시)
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl
```

### 고급 옵션

```bash
# 최대 8개 동시 실행
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --max-parallel 8

# 실패 Job 재시도
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --retry-failed

# submit만 하고 완료 대기 안 함
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --no-wait

# 특정 namespace 사용
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --namespace tuning

# 타임아웃 설정
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --timeout-per-job 600 \
  --timeout-session 7200

# Dry-run (실제 K8s API 호출 없음)
python -m scripts.run_tuning_session_k8s \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --dry-run
```

### 출력 형식

```
======================================================================
[D41_K8S_SESSION] KUBERNETES TUNING SESSION SUMMARY
======================================================================

Total Jobs:     50
Attempted:      50
Success:        48
Errors:         2
Skipped:        0

Exit Code:      1  (⚠️  SOME JOBS FAILED)

Errors:
  - Job sess001_0005 timeout exceeded
  - Job sess001_0012 pod crash

Submitted Jobs (50):
  - sess001-0001
  - sess001-0002
  ...

======================================================================
```

### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 모든 작업 성공 |
| 1 | 일부 작업 실패 |
| 2 | 파일 오류 또는 런타임 오류 |

---

## 주요 특징

### 병렬 처리

- max_parallel로 동시 실행 Job 수 제한
- 기본값: 4개
- 대규모 세션에서 성능 향상

### 타임아웃 관리

- **Job 단위**: timeout_per_job (기본 300초)
- **세션 단위**: timeout_session (기본 3600초)
- 타임아웃 시 자동 정리

### 결과 수집

- Pod 로그 자동 수집
- 결과 JSON 생성 (D40과 동일 포맷)
- D39 Aggregator와 호환

### 안전 정책

✅ 준수:
- 네트워크 호출 없음 (K8s API만 사용)
- kubectl 직접 호출 없음 (K8s 클라이언트 사용)
- 100% mock 기반 테스트

### 테스트 가능성

- K8sClient 인터페이스 기반 설계
- Mock 주입 가능
- 실제 클러스터 없이 테스트 가능

---

## D40 vs D41 비교

| 항목 | D40 (Local) | D41 (K8s) |
|------|------------|----------|
| 실행 환경 | 로컬 머신 | K8s 클러스터 |
| 실행 방식 | subprocess (순차) | K8s Job (병렬) |
| 동시 실행 | 1개 | max_parallel개 |
| 타임아웃 | 300초/job | 300초/job + 3600초/session |
| 결과 수집 | stdout/stderr | Pod logs |
| 입력 | JSONL (동일) | JSONL (동일) |
| 출력 | JSON (동일) | JSON (동일) |
| 테스트 | 31개 | 25+개 |
| 필수 여부 | ✅ 필수 | ⚠️ 선택 |

---

## 다음 단계

### D41 이후

1. **실거래 통합** (INFRA 레이어)
2. **실시간 모니터링 & 대시보드**
3. **자동화된 매개변수 탐색**
4. **결과 분석 & 리포팅**

### 관련 모듈

- **D37**: Arbitrage Strategy MVP (Core Engine)
- **D38**: Arbitrage Tuning Job Runner (Single Job)
- **D39**: Arbitrage Tuning Session Planner & Aggregator
- **D40**: Arbitrage Tuning Session Local Runner (순차 실행)
- **D41**: Arbitrage Tuning Session K8s Distributed Runner (병렬 실행, 이 모듈)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-17  
**상태:** ✅ Optional Feature (로컬 필수 아님)

# D32 Kubernetes Job/Pod Monitoring & Log Collection Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [Read-Only 정책](#read-only-정책)
6. [제한사항](#제한사항)

---

## 개요

D32는 **K8s 클러스터에서 실행 중인 Job/Pod의 상태를 모니터링하고 로그를 수집**하는 모듈입니다. 실제 kubectl get/logs 호출로 정보를 수집하며, 수정 작업은 수행하지 않습니다.

### 핵심 특징

- ✅ **Read-Only 모니터링**: kubectl get, kubectl logs만 사용
- ✅ **Job 상태 추적**: 각 Job의 단계(PENDING, RUNNING, SUCCEEDED, FAILED) 추적
- ✅ **Pod 로그 수집**: 각 Pod의 컨테이너 로그 수집
- ✅ **One-shot & Watch 모드**: 한 번만 조회 또는 주기적 갱신
- ✅ **kubeconfig 지원**: 여러 K8s 클러스터 지원
- ✅ **에러 처리**: kubectl 없음, 네트워크 오류 등 안전하게 처리
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

### 중요: 이것은 "Read-Only 모니터링 도구"입니다

```
D29: K8s Job YAML 생성
  ↓
D30: YAML 검증 및 실행 계획 생성
  ↓
D31: 안전한 Apply 실행
  ↓
K8s 클러스터에서 Job 실행
  ↓
D32: Job/Pod 상태 모니터링 (이 단계) ← Read-Only
  ├─ kubectl get jobs
  ├─ kubectl get pods
  └─ kubectl logs
```

---

## 아키텍처

### 데이터 흐름

```
K8s 클러스터
    ↓
K8sJobMonitor
    ├─ _load_jobs()
    │  ├─ kubectl get jobs -o json
    │  └─ Job 상태 파싱
    │
    └─ _load_pod_logs()
       ├─ kubectl get pods -o json
       ├─ 각 Pod 식별
       └─ kubectl logs <pod>
    ↓
K8sMonitorSnapshot
    ├─ jobs: List[K8sJobStatus]
    ├─ pods_logs: List[K8sPodLog]
    └─ errors: List[str]
    ↓
generate_monitor_report_text()
    └─ 포맷된 모니터링 보고서 생성
    ↓
사용자 (또는 CI/CD)
    └─ 상태 확인 및 필요시 조치
```

### Read-Only 메커니즘

```
1. kubectl get 명령만 사용
   ├─ kubectl get jobs -o json
   ├─ kubectl get pods -o json
   └─ kubectl logs <pod>

2. 수정 작업 금지
   ├─ kubectl apply ❌
   ├─ kubectl delete ❌
   ├─ kubectl patch ❌
   └─ kubectl scale ❌

3. 에러 처리
   ├─ kubectl 없음 → 에러 기록
   ├─ 네트워크 오류 → 에러 기록
   └─ 타임아웃 → 에러 기록
```

---

## 데이터 구조

### K8sPodLog

```python
@dataclass
class K8sPodLog:
    pod_name: str                       # Pod 이름
    namespace: str                      # K8s 네임스페이스
    container_name: str                 # 컨테이너 이름
    lines: List[str]                    # 로그 라인
```

### K8sJobStatus

```python
@dataclass
class K8sJobStatus:
    job_name: str                       # Job 이름
    namespace: str                      # K8s 네임스페이스
    labels: Dict[str, str]              # Job 레이블
    completions: Optional[int]          # 완료해야 할 Pod 수
    succeeded: Optional[int]            # 성공한 Pod 수
    failed: Optional[int]               # 실패한 Pod 수
    active: Optional[int]               # 실행 중인 Pod 수
    phase: JobPhase                     # Job 단계
    start_time: Optional[str]           # 시작 시간
    completion_time: Optional[str]      # 완료 시간
```

### K8sMonitorSnapshot

```python
@dataclass
class K8sMonitorSnapshot:
    namespace: str                      # K8s 네임스페이스
    selector: str                       # 레이블 선택자
    jobs: List[K8sJobStatus]            # Job 상태 목록
    pods_logs: List[K8sPodLog]          # Pod 로그 목록
    timestamp: str                      # 타임스탬프
    errors: List[str]                   # 에러 목록
```

### K8sJobMonitor

```python
class K8sJobMonitor:
    def __init__(
        self,
        namespace: str,
        label_selector: str,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        max_log_lines: int = 100
    ):
        """모니터 초기화"""
    
    def load_snapshot(self) -> K8sMonitorSnapshot:
        """K8s Job/Pod 상태 스냅샷 로드"""
```

---

## 사용 방법

### 1. One-shot 모드 (한 번만 조회)

```bash
python scripts/watch_k8s_jobs.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session
```

**출력:**
```
================================================================================
[D32_K8S_MONITOR] KUBERNETES JOB/POD MONITORING SNAPSHOT
================================================================================

[HEADER]
Namespace:               trading-bots
Label Selector:          app=arbitrage-tuning,session_id=d29-k8s-demo-session
Timestamp:               2025-11-16T10:00:00.000000

[JOB STATUS]

  Job: arb-tuning-d29-k8s--worker-1-0
    Namespace:           trading-bots
    Phase:               SUCCEEDED
    Completions:         1
    Succeeded:           1
    Failed:              0
    Active:              0
    Start Time:          2025-11-16T10:00:00Z
    Completion Time:     2025-11-16T10:05:00Z
    Labels:
      app: arbitrage-tuning
      session_id: d29-k8s-demo-session
      worker_id: worker-1

[POD LOGS]

  Pod: arb-tuning-d29-k8s--worker-1-0-abc123 / Container: tuning-container
    Namespace:           trading-bots
    Log Lines (5):
      [2025-11-16 10:00:00] Starting tuning session
      [2025-11-16 10:01:00] Processing data...
      [2025-11-16 10:02:00] Computing metrics...
      [2025-11-16 10:04:00] Saving results...
      [2025-11-16 10:05:00] Tuning session completed

================================================================================
[D32_K8S_MONITOR] END OF SNAPSHOT
================================================================================
```

### 2. Watch 모드 (주기적 갱신)

```bash
python scripts/watch_k8s_jobs.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session \
  --interval 5
```

**동작:**
- 5초마다 상태 갱신
- 각 갱신마다 스냅샷 출력
- Ctrl+C로 중단

### 3. kubeconfig 지정

```bash
python scripts/watch_k8s_jobs.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --kubeconfig ~/.kube/config \
  --context my-cluster \
  --interval 5
```

### 4. 로그 라인 수 조정

```bash
python scripts/watch_k8s_jobs.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --max-log-lines 50 \
  --interval 5
```

---

## Read-Only 정책

### 허용되는 작업

✅ **Read-Only 작업:**
```bash
kubectl get jobs -o json
kubectl get pods -o json
kubectl logs <pod>
kubectl describe job <job>
kubectl describe pod <pod>
```

### 금지되는 작업

❌ **수정 작업:**
```bash
kubectl apply -f ...        # ❌ 금지
kubectl delete job ...      # ❌ 금지
kubectl patch job ...       # ❌ 금지
kubectl scale job ...       # ❌ 금지
kubectl exec pod ...        # ❌ 금지
```

### 에러 처리

D32는 다음 상황에서 안전하게 처리합니다:

```
1. kubectl 없음
   → 에러 기록, 빈 스냅샷 반환

2. 네트워크 오류
   → 에러 기록, 빈 스냅샷 반환

3. 권한 없음
   → 에러 기록, 빈 스냅샷 반환

4. 타임아웃
   → 에러 기록, 빈 스냅샷 반환
```

---

## Job 단계 (Phase)

| 단계 | 의미 | 조건 |
|------|------|------|
| PENDING | 대기 중 | startTime 없음 |
| RUNNING | 실행 중 | active > 0 |
| SUCCEEDED | 성공 | succeeded > 0 |
| FAILED | 실패 | failed > 0 |
| UNKNOWN | 불명 | 기타 |

---

## 제한사항 및 주의

### D32에서 하지 않는 것

❌ **실제 K8s 수정:**
- kubectl apply 실행 금지
- kubectl delete 실행 금지
- kubectl patch 실행 금지
- kubectl scale 실행 금지

❌ **기존 인프라 변경:**
- Docker Compose 설정 수정 금지
- Redis 컨테이너 제어 금지
- 외부 컨테이너 조작 금지

### D32에서 하는 것

✅ **Read-Only 모니터링:**
- Job 상태 조회
- Pod 상태 조회
- 로그 수집
- 에러 기록

---

## 관련 문서

- [D31 Safe K8s Apply Layer](D31_K8S_APPLY_LAYER.md)
- [D30 Kubernetes Executor](D30_K8S_EXECUTOR.md)
- [D29 Kubernetes Orchestrator](D29_K8S_ORCHESTRATOR.md)

---

## 향후 단계

### D33+ (미래 계획)

- **Pod 이벤트 모니터링**: Pod 생성/삭제 이벤트 추적
- **메트릭 수집**: CPU/메모리 사용량 수집
- **자동 알림**: 실패한 Job 알림
- **히스토리 저장**: 모니터링 데이터 저장

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

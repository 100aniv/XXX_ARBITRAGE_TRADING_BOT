# D33 Kubernetes Health Evaluation & CI-friendly Alert Layer Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [건강 상태 규칙](#건강-상태-규칙)
6. [종료 코드](#종료-코드)
7. [CI/CD 통합](#cicd-통합)

---

## 개요

D33는 **D32의 K8s 모니터링 스냅샷을 기반으로 건강 상태를 평가하고 CI/CD 친화적인 종료 코드를 제공**하는 모듈입니다.

### 핵심 특징

- ✅ **건강 상태 분류**: OK, WARN, ERROR
- ✅ **Job 단계 기반 평가**: PENDING, RUNNING, SUCCEEDED, FAILED, UNKNOWN
- ✅ **CI/CD 친화적 종료 코드**: 0 (OK), 1 (WARN), 2 (ERROR)
- ✅ **Strict 모드**: WARN도 에러로 처리
- ✅ **JSON 출력**: 자동화된 처리를 위한 JSON 형식
- ✅ **Read-Only**: 클러스터 수정 작업 없음
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

### 계층 구조

```
D29: K8s Job YAML 생성
  ↓
D30: YAML 검증 및 실행 계획 생성
  ↓
D31: 안전한 Apply 실행
  ↓
K8s 클러스터에서 Job 실행
  ↓
D32: Job/Pod 상태 모니터링 (Read-Only)
  ├─ kubectl get jobs
  ├─ kubectl get pods
  └─ kubectl logs
  ↓
D33: 건강 상태 평가 (이 단계) ← CI/CD 친화적
  ├─ 건강 상태 분류
  ├─ 종료 코드 제공
  └─ JSON 보고서 생성
```

---

## 아키텍처

### 데이터 흐름

```
K8sMonitorSnapshot (from D32)
    ├─ jobs: List[K8sJobStatus]
    ├─ pods_logs: List[K8sPodLog]
    └─ errors: List[str]
    ↓
K8sHealthEvaluator
    ├─ evaluate_job(job_status) → K8sJobHealth
    │  ├─ phase 분석
    │  ├─ 건강 상태 결정
    │  └─ 이유 기록
    │
    └─ compute_overall_health(jobs_health, errors) → HealthLevel
    ↓
K8sHealthSnapshot
    ├─ jobs_health: List[K8sJobHealth]
    ├─ overall_health: HealthLevel
    └─ errors: List[str]
    ↓
generate_health_report_text()
    └─ 포맷된 건강 상태 보고서 생성
    ↓
CI/CD 시스템
    ├─ 종료 코드 확인
    ├─ JSON 보고서 처리
    └─ 필요시 알림 또는 조치
```

### Read-Only 메커니즘

```
D33는 D32의 K8sJobMonitor를 사용합니다:

K8sJobMonitor (D32)
    ├─ kubectl get jobs -o json
    ├─ kubectl get pods -o json
    └─ kubectl logs <pod>
    ↓
K8sMonitorSnapshot
    ↓
K8sHealthEvaluator (D33)
    └─ 수정 작업 없음
```

---

## 데이터 구조

### HealthLevel

```python
HealthLevel = Literal["OK", "WARN", "ERROR"]
```

### K8sJobHealth

```python
@dataclass
class K8sJobHealth:
    job_name: str                       # Job 이름
    namespace: str                      # K8s 네임스페이스
    phase: str                          # Job 단계
    succeeded: Optional[int]            # 성공한 Pod 수
    failed: Optional[int]               # 실패한 Pod 수
    active: Optional[int]               # 실행 중인 Pod 수
    health: HealthLevel                 # 건강 상태
    reasons: List[str]                  # 이유 (예: "job_failed", "pending")
    labels: Dict[str, str]              # Job 레이블
```

### K8sHealthSnapshot

```python
@dataclass
class K8sHealthSnapshot:
    namespace: str                      # K8s 네임스페이스
    selector: str                       # 레이블 선택자
    jobs_health: List[K8sJobHealth]     # Job 건강 상태 목록
    errors: List[str]                   # 모니터링 에러 목록
    overall_health: HealthLevel         # 전체 건강 상태
    timestamp: str                      # 타임스탬프
```

### K8sHealthEvaluator

```python
class K8sHealthEvaluator:
    def __init__(
        self,
        warn_on_pending: bool = True,
        treat_unknown_as_error: bool = True
    ):
        """
        warn_on_pending: True면 PENDING을 WARN으로 분류
        treat_unknown_as_error: True면 UNKNOWN을 ERROR로 분류
        """
    
    def evaluate(self, snapshot: K8sMonitorSnapshot) -> K8sHealthSnapshot:
        """건강 상태 평가"""
```

---

## 사용 방법

### 1. 기본 건강 상태 확인

```bash
python scripts/check_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session
```

**출력:**
```
================================================================================
[D33_K8S_HEALTH] KUBERNETES HEALTH EVALUATION SNAPSHOT
================================================================================

[HEADER]
Namespace:               trading-bots
Label Selector:          app=arbitrage-tuning,session_id=d29-k8s-demo-session
Timestamp:               2025-11-16T10:00:00Z
Overall Health:          OK

[JOBS]

  Job: arb-tuning-d29-k8s--worker-1-0
    Namespace:           trading-bots
    Phase:               SUCCEEDED
    Health:              OK
    Succeeded:           1
    Failed:              0
    Active:              0
    Labels:
      app: arbitrage-tuning
      session_id: d29-k8s-demo-session
      worker_id: worker-1

  Job: arb-tuning-d29-k8s--worker-2-1
    Namespace:           trading-bots
    Phase:               SUCCEEDED
    Health:              OK
    Succeeded:           1
    Failed:              0
    Active:              0
    Labels:
      app: arbitrage-tuning
      session_id: d29-k8s-demo-session
      worker_id: worker-2

================================================================================
[D33_K8S_HEALTH] END OF HEALTH SNAPSHOT
================================================================================
```

**종료 코드:** 0 (OK)

### 2. Strict 모드 (WARN도 에러로 처리)

```bash
python scripts/check_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --strict
```

**동작:**
- WARN 상태 → 종료 코드 1
- ERROR 상태 → 종료 코드 2

### 3. kubeconfig 지정

```bash
python scripts/check_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --kubeconfig ~/.kube/config \
  --context my-cluster
```

### 4. JSON 출력 저장

```bash
python scripts/check_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --output-json health_report.json
```

**health_report.json:**
```json
{
  "namespace": "trading-bots",
  "selector": "app=arbitrage-tuning,session_id=d29-k8s-demo-session",
  "overall_health": "OK",
  "timestamp": "2025-11-16T10:00:00Z",
  "jobs_health": [
    {
      "job_name": "arb-tuning-d29-k8s--worker-1-0",
      "namespace": "trading-bots",
      "phase": "SUCCEEDED",
      "health": "OK",
      "reasons": [],
      "succeeded": 1,
      "failed": 0,
      "active": 0,
      "labels": {
        "app": "arbitrage-tuning",
        "session_id": "d29-k8s-demo-session",
        "worker_id": "worker-1"
      }
    }
  ],
  "errors": []
}
```

---

## 건강 상태 규칙

### Job 단계별 건강 상태

| Phase | 기본 상태 | 조건 | 이유 |
|-------|---------|------|------|
| SUCCEEDED | OK | 성공 완료 | - |
| RUNNING | OK | 실행 중 | - |
| PENDING | WARN* | 대기 중 | "pending" |
| FAILED | ERROR | 실패 | "job_failed" |
| UNKNOWN | ERROR** | 불명 | "unknown_phase" |

*: `warn_on_pending=True`일 때 (기본값)  
**: `treat_unknown_as_error=True`일 때 (기본값)

### 전체 건강 상태 계산

```
1. 어떤 Job이라도 ERROR → 전체 ERROR
2. 어떤 Job이 WARN이거나 모니터링 에러 있음 → 전체 WARN
3. 모두 OK이고 에러 없음 → 전체 OK
```

### 이유 코드 (Reasons)

| 코드 | 의미 |
|------|------|
| "job_failed" | Job이 실패함 |
| "unknown_phase" | Job 단계가 불명 |
| "pending" | Job이 대기 중 |
| "unexpected_phase" | 예상치 못한 단계 |

---

## 종료 코드

### 종료 코드 규칙

```
Overall Health = OK
  → 종료 코드 0 (항상)

Overall Health = WARN
  → --strict 없음: 종료 코드 0
  → --strict 있음: 종료 코드 1

Overall Health = ERROR
  → 종료 코드 2 (항상)
```

### 사용 예

```bash
# 기본 모드
python scripts/check_k8s_health.py ... && echo "OK" || echo "Failed"

# Strict 모드
python scripts/check_k8s_health.py --strict ... || {
  exit_code=$?
  if [ $exit_code -eq 1 ]; then
    echo "Warning detected"
  elif [ $exit_code -eq 2 ]; then
    echo "Error detected"
  fi
}
```

---

## CI/CD 통합

### GitHub Actions 예시

```yaml
name: K8s Health Check

on:
  schedule:
    - cron: '*/5 * * * *'  # 5분마다

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Check K8s Health
        run: |
          python scripts/check_k8s_health.py \
            --namespace trading-bots \
            --label-selector app=arbitrage-tuning \
            --kubeconfig ${{ secrets.KUBECONFIG }} \
            --output-json health_report.json \
            --strict
      
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: health-report
          path: health_report.json
      
      - name: Notify on failure
        if: failure()
        run: |
          echo "K8s health check failed!"
          cat health_report.json
```

### GitLab CI 예시

```yaml
k8s_health_check:
  stage: monitor
  script:
    - python scripts/check_k8s_health.py \
        --namespace trading-bots \
        --label-selector app=arbitrage-tuning \
        --kubeconfig $KUBECONFIG \
        --output-json health_report.json \
        --strict
  artifacts:
    paths:
      - health_report.json
    when: always
  allow_failure: true
```

### Cron Job 예시

```bash
#!/bin/bash
# /usr/local/bin/check_k8s_health.sh

cd /opt/arbitrage-lite

python scripts/check_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --kubeconfig ~/.kube/config \
  --output-json /tmp/health_report.json

exit_code=$?

if [ $exit_code -eq 0 ]; then
  echo "Health check OK"
elif [ $exit_code -eq 1 ]; then
  echo "Warning detected" | mail -s "K8s Health Warning" admin@example.com
elif [ $exit_code -eq 2 ]; then
  echo "Error detected" | mail -s "K8s Health Error" admin@example.com
  exit 1
fi
```

---

## 관련 문서

- [D32 K8s Job/Pod Monitoring](D32_K8S_JOB_MONITORING.md)
- [D31 Safe K8s Apply Layer](D31_K8S_APPLY_LAYER.md)
- [D30 Kubernetes Executor](D30_K8S_EXECUTOR.md)
- [D29 Kubernetes Orchestrator](D29_K8S_ORCHESTRATOR.md)

---

## 향후 단계

### D34+ (미래 계획)

- **Pod 이벤트 모니터링**: Pod 생성/삭제/재시작 이벤트 추적
- **메트릭 수집**: CPU/메모리 사용량 수집
- **자동 알림**: 실패한 Job 자동 알림
- **히스토리 저장**: 건강 상태 변화 추적
- **대시보드**: 웹 기반 모니터링 대시보드

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

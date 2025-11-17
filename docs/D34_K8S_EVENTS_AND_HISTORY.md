# D34 Kubernetes Events Collection & Health History Persistence Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [이벤트 수집](#이벤트-수집)
6. [히스토리 저장](#히스토리-저장)
7. [히스토리 조회](#히스토리-조회)

---

## 개요

D34는 **D33의 건강 상태 스냅샷을 파일 기반 저장소에 저장하고, K8s 이벤트를 수집**하는 모듈입니다.

### 핵심 특징

- ✅ **K8s 이벤트 수집**: Job/Pod 관련 이벤트 수집
- ✅ **건강 상태 히스토리**: JSONL 형식 파일 기반 저장
- ✅ **히스토리 조회**: 최근 레코드 및 요약 조회
- ✅ **Read-Only**: 클러스터 수정 작업 없음
- ✅ **파일 기반**: 외부 DB 없음
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
D33: 건강 상태 평가 (CI/CD 친화적)
  ├─ 건강 상태 분류
  ├─ 종료 코드 제공
  └─ JSON 보고서 생성
  ↓
D34: 이벤트 + 히스토리 저장 (이 단계) ← 파일 기반 저장소
  ├─ K8s 이벤트 수집
  ├─ 건강 상태 히스토리 저장
  └─ 히스토리 조회
```

---

## 아키텍처

### 데이터 흐름

```
K8sEventCollector
    ├─ kubectl get events -o json
    └─ K8sEventSnapshot
    ↓
K8sJobMonitor (D32)
    ├─ kubectl get jobs -o json
    ├─ kubectl get pods -o json
    └─ K8sMonitorSnapshot
    ↓
K8sHealthEvaluator (D33)
    └─ K8sHealthSnapshot
    ↓
K8sHealthHistoryStore (D34)
    ├─ append(snapshot) → K8sHealthHistoryRecord
    ├─ load_recent(limit) → List[K8sHealthHistoryRecord]
    └─ summarize(window) → Dict
    ↓
파일 저장소 (JSONL)
    └─ outputs/k8s_health_history.jsonl
    ↓
CLI 도구
    ├─ record_k8s_health.py (기록)
    └─ show_k8s_health_history.py (조회)
```

### Read-Only 메커니즘

```
D34는 다음 작업만 수행합니다:

K8sEventCollector:
    └─ kubectl get events -o json

K8sHealthHistoryStore:
    ├─ 파일 읽기 (load_recent)
    ├─ 파일 쓰기 (append)
    └─ 파일 분석 (summarize)

금지되는 작업:
    ❌ kubectl apply
    ❌ kubectl delete
    ❌ kubectl patch
    ❌ 클러스터 수정
```

---

## 데이터 구조

### K8sEvent

```python
@dataclass
class K8sEvent:
    type: str                       # Normal, Warning, etc.
    reason: str                     # 이유 (예: "BackoffLimitExceeded")
    message: str                    # 메시지
    involved_kind: Optional[str]    # 관련 객체 종류 (Job, Pod, etc.)
    involved_name: Optional[str]    # 관련 객체 이름
    involved_namespace: Optional[str]  # 관련 객체 네임스페이스
    first_timestamp: Optional[str]  # 첫 발생 시간
    last_timestamp: Optional[str]   # 마지막 발생 시간
    count: Optional[int]            # 발생 횟수
    raw: Dict[str, Any]             # 원본 이벤트 (디버깅용)
```

### K8sEventSnapshot

```python
@dataclass
class K8sEventSnapshot:
    namespace: str                  # K8s 네임스페이스
    selector: str                   # 레이블 선택자
    events: List[K8sEvent]          # 이벤트 목록
    timestamp: str                  # 스냅샷 타임스탬프
    errors: List[str]               # 수집 중 발생한 에러
```

### K8sHealthHistoryRecord

```python
@dataclass
class K8sHealthHistoryRecord:
    timestamp: str                  # 레코드 타임스탬프
    namespace: str                  # K8s 네임스페이스
    selector: str                   # 레이블 선택자
    overall_health: HealthLevel     # 전체 건강 상태
    jobs_ok: int                    # OK 상태 Job 수
    jobs_warn: int                  # WARN 상태 Job 수
    jobs_error: int                 # ERROR 상태 Job 수
    raw_snapshot: Optional[Dict]    # 원본 스냅샷 (선택)
```

### K8sEventCollector

```python
class K8sEventCollector:
    def __init__(
        self,
        namespace: str,
        label_selector: str,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
    ):
        """이벤트 수집기 초기화"""
    
    def load_events(self) -> K8sEventSnapshot:
        """K8s 이벤트 수집"""
```

### K8sHealthHistoryStore

```python
class K8sHealthHistoryStore:
    def __init__(self, path: str):
        """히스토리 저장소 초기화"""
    
    def append(self, snapshot: K8sHealthSnapshot) -> K8sHealthHistoryRecord:
        """건강 상태 스냅샷을 히스토리에 추가"""
    
    def load_recent(self, limit: int = 50) -> List[K8sHealthHistoryRecord]:
        """최근 N개 레코드 로드"""
    
    def summarize(self, window: Optional[int] = None) -> Dict[str, Any]:
        """히스토리 요약"""
```

---

## 사용 방법

### 1. 건강 상태 기록

```bash
python scripts/record_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session \
  --history-file outputs/k8s_health_history.jsonl
```

**출력:**
```
================================================================================
[D34_RECORD] HEALTH RECORD SUMMARY
================================================================================

Namespace:               trading-bots
Label Selector:          app=arbitrage-tuning,session_id=d29-k8s-demo-session
Timestamp:               2025-11-16T10:00:00Z
Overall Health:          OK

Job Counts:
  OK:                    2
  WARN:                  0
  ERROR:                 0

History File:            outputs/k8s_health_history.jsonl
================================================================================
```

**종료 코드:** 0 (OK)

### 2. kubeconfig 지정

```bash
python scripts/record_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --kubeconfig ~/.kube/config \
  --context my-cluster \
  --history-file outputs/k8s_health_history.jsonl
```

### 3. Strict 모드

```bash
python scripts/record_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file outputs/k8s_health_history.jsonl \
  --strict
```

**동작:**
- WARN 상태 → 종료 코드 1
- ERROR 상태 → 종료 코드 2

### 4. 히스토리 조회 - 최근 레코드

```bash
python scripts/show_k8s_health_history.py \
  --history-file outputs/k8s_health_history.jsonl \
  --limit 20
```

**출력:**
```
================================================================================
[D34_SHOW] KUBERNETES HEALTH HISTORY RECORDS
================================================================================

Total Records: 5

#   Timestamp                Timestamp                Health   OK   WARN ERR  Namespace       Selector
--- -------- -------- -------- -------- -------- -------- -------- -------- -------- -------- --------
1   2025-11-16T10:00:00Z       OK       2    0    0   trading-bots    app=arbitrage-tuning,...
2   2025-11-16T10:05:00Z       OK       2    0    0   trading-bots    app=arbitrage-tuning,...
3   2025-11-16T10:10:00Z       WARN     1    1    0   trading-bots    app=arbitrage-tuning,...
4   2025-11-16T10:15:00Z       OK       2    0    0   trading-bots    app=arbitrage-tuning,...
5   2025-11-16T10:20:00Z       OK       2    0    0   trading-bots    app=arbitrage-tuning,...

================================================================================
```

### 5. 히스토리 조회 - 요약만

```bash
python scripts/show_k8s_health_history.py \
  --history-file outputs/k8s_health_history.jsonl \
  --summary-only
```

**출력:**
```
================================================================================
[D34_SHOW] KUBERNETES HEALTH HISTORY SUMMARY
================================================================================

Total Records:           5

Health Status Counts:
  OK:                    4
  WARN:                  1
  ERROR:                 0

Last Record:
  Overall Health:        OK
  Timestamp:             2025-11-16T10:20:00Z
  Jobs OK:               2
  Jobs WARN:             0
  Jobs ERROR:            0

================================================================================
```

---

## 이벤트 수집

### K8sEventCollector 사용

```python
from arbitrage.k8s_events import K8sEventCollector

collector = K8sEventCollector(
    namespace="trading-bots",
    label_selector="app=arbitrage-tuning,session_id=d29-k8s-demo-session"
)

snapshot = collector.load_events()

print(f"Events: {len(snapshot.events)}")
for event in snapshot.events:
    print(f"  {event.reason}: {event.message}")
```

### 이벤트 필터링

이벤트는 다음 조건으로 필터링됩니다:

1. **이름 접두사**: `arb-tuning-`로 시작하는 Job/Pod
2. **레이블 선택자**: 지정된 레이블과 매칭되는 객체

### 이벤트 타입

| Type | 의미 |
|------|------|
| Normal | 정상 이벤트 |
| Warning | 경고 이벤트 |

### 이벤트 이유 (Reason)

| 이유 | 의미 |
|------|------|
| Scheduled | Pod 스케줄됨 |
| Pulled | 이미지 풀됨 |
| Created | 컨테이너 생성됨 |
| Started | 컨테이너 시작됨 |
| BackoffLimitExceeded | 재시도 한계 도달 |
| Failed | Job 실패 |
| Succeeded | Job 성공 |

---

## 히스토리 저장

### K8sHealthHistoryStore 사용

```python
from arbitrage.k8s_health import K8sHealthSnapshot
from arbitrage.k8s_history import K8sHealthHistoryStore

store = K8sHealthHistoryStore("outputs/k8s_health_history.jsonl")

# 스냅샷 추가
record = store.append(snapshot)
print(f"Recorded: {record.overall_health} at {record.timestamp}")

# 최근 레코드 로드
records = store.load_recent(limit=10)
print(f"Loaded {len(records)} records")

# 요약 조회
summary = store.summarize()
print(f"Total: {summary['total_records']}, OK: {summary['ok_count']}")
```

### 파일 형식

JSONL (JSON Lines) 형식:

```json
{"timestamp": "2025-11-16T10:00:00Z", "namespace": "trading-bots", "selector": "app=arbitrage-tuning", "overall_health": "OK", "jobs_ok": 2, "jobs_warn": 0, "jobs_error": 0, "raw_snapshot": null}
{"timestamp": "2025-11-16T10:05:00Z", "namespace": "trading-bots", "selector": "app=arbitrage-tuning", "overall_health": "OK", "jobs_ok": 2, "jobs_warn": 0, "jobs_error": 0, "raw_snapshot": null}
```

### 손상된 라인 처리

손상된 JSON 라인은 자동으로 스킵되고 로그에 기록됩니다.

---

## 히스토리 조회

### 최근 레코드 조회

```python
from arbitrage.k8s_history import K8sHealthHistoryStore

store = K8sHealthHistoryStore("outputs/k8s_health_history.jsonl")

# 최근 50개 레코드
records = store.load_recent(limit=50)

for record in records:
    print(f"{record.timestamp}: {record.overall_health} (OK={record.jobs_ok}, WARN={record.jobs_warn}, ERROR={record.jobs_error})")
```

### 요약 조회

```python
# 전체 요약
summary = store.summarize()
print(f"Total: {summary['total_records']}")
print(f"OK: {summary['ok_count']}, WARN: {summary['warn_count']}, ERROR: {summary['error_count']}")

# 최근 100개 기반 요약
summary = store.summarize(window=100)
print(f"Last 100 records: OK={summary['ok_count']}, WARN={summary['warn_count']}")
```

---

## CI/CD 통합

### Cron Job 예시

```bash
#!/bin/bash
# /usr/local/bin/record_k8s_health.sh

cd /opt/arbitrage-lite

python scripts/record_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --kubeconfig ~/.kube/config \
  --history-file /var/log/k8s_health_history.jsonl \
  --strict

exit_code=$?

if [ $exit_code -eq 0 ]; then
  echo "Health recorded: OK"
elif [ $exit_code -eq 1 ]; then
  echo "Health recorded: WARN" | mail -s "K8s Health Warning" admin@example.com
elif [ $exit_code -eq 2 ]; then
  echo "Health recorded: ERROR" | mail -s "K8s Health Error" admin@example.com
fi

exit $exit_code
```

**Crontab:**
```bash
# 5분마다 건강 상태 기록
*/5 * * * * /usr/local/bin/record_k8s_health.sh

# 매일 자정에 히스토리 요약 출력
0 0 * * * python /opt/arbitrage-lite/scripts/show_k8s_health_history.py --history-file /var/log/k8s_health_history.jsonl --summary-only
```

### GitHub Actions 예시

```yaml
name: K8s Health Recording

on:
  schedule:
    - cron: '*/5 * * * *'  # 5분마다

jobs:
  record-health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Record K8s Health
        run: |
          python scripts/record_k8s_health.py \
            --namespace trading-bots \
            --label-selector app=arbitrage-tuning \
            --kubeconfig ${{ secrets.KUBECONFIG }} \
            --history-file /tmp/k8s_health_history.jsonl
      
      - name: Show History Summary
        if: always()
        run: |
          python scripts/show_k8s_health_history.py \
            --history-file /tmp/k8s_health_history.jsonl \
            --summary-only
      
      - name: Upload history
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: k8s-health-history
          path: /tmp/k8s_health_history.jsonl
```

---

## 관련 문서

- [D33 K8s Health Evaluation](D33_K8S_HEALTH_MONITORING.md)
- [D32 K8s Job/Pod Monitoring](D32_K8S_JOB_MONITORING.md)
- [D31 Safe K8s Apply Layer](D31_K8S_APPLY_LAYER.md)
- [D30 Kubernetes Executor](D30_K8S_EXECUTOR.md)
- [D29 Kubernetes Orchestrator](D29_K8S_ORCHESTRATOR.md)

---

## 향후 단계

### D35+ (미래 계획)

- **알림 통합**: Slack/webhook 알림
- **웹 대시보드**: 히스토리 시각화
- **메트릭 수집**: CPU/메모리 사용량
- **자동 정리**: 오래된 히스토리 삭제
- **데이터베이스**: 장기 저장소 (선택)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

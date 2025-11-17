# D35 Kubernetes Alert & Incident Summary Layer Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [인시던트 감지](#인시던트-감지)
6. [알림 전송](#알림-전송)
7. [채널 설정](#채널-설정)

---

## 개요

D35는 **D34의 건강 상태 히스토리와 이벤트를 분석하여 인시던트를 감지하고, 알림 페이로드를 생성하여 Slack/Webhook으로 전송**하는 모듈입니다.

### 핵심 특징

- ✅ **인시던트 감지**: 건강 상태 변화 추적
- ✅ **알림 페이로드**: Slack/Webhook 호환 형식
- ✅ **Dry-run 기본값**: 안전한 기본 설정
- ✅ **Read-Only**: 클러스터 수정 작업 없음
- ✅ **다중 채널**: Console, Slack, Generic Webhook
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
  ↓
D33: 건강 상태 평가 (CI/CD 친화적)
  ↓
D34: 이벤트 + 히스토리 저장 (파일 기반)
  ↓
D35: 인시던트 감지 + 알림 전송 (이 단계) ← Slack/Webhook
```

---

## 아키텍처

### 데이터 흐름

```
K8sHealthHistoryStore (D34)
    └─ load_recent(limit=20)
    ↓
K8sEventCollector (D34)
    └─ load_events()
    ↓
K8sAlertManager
    ├─ build_incident_from_history()
    │   └─ K8sIncident
    ├─ build_alert_payload()
    │   └─ K8sAlertPayload
    └─ dispatch()
    ↓
채널별 전송
    ├─ Console (stdout)
    ├─ Slack Webhook
    └─ Generic Webhook
```

### 인시던트 생명주기

```
1. 건강 상태 변화 감지
   OK → WARN/ERROR

2. 인시던트 생성
   - 심각도 결정 (INFO/WARN/CRITICAL)
   - 시작 시간 계산
   - 최근 이벤트 수집

3. 알림 페이로드 생성
   - 텍스트 형식화
   - 메타데이터 추가
   - 채널별 형식 변환

4. 알림 전송
   - Console: stdout 출력
   - Webhook: HTTP POST (dry-run 기본값)
```

---

## 데이터 구조

### K8sIncident

```python
@dataclass
class K8sIncident:
    id: str                                    # 고유 ID (해시)
    severity: IncidentSeverity                 # INFO, WARN, CRITICAL
    namespace: str                             # K8s 네임스페이스
    selector: str                              # 레이블 선택자
    current_health: HealthLevel                # OK, WARN, ERROR
    previous_health: Optional[HealthLevel]     # 이전 상태
    started_at: str                            # 시작 시간 (ISO format)
    detected_at: str                           # 감지 시간 (ISO format)
    summary: str                               # 요약 텍스트
    job_counts: Dict[str, int]                 # Job 상태별 개수
    recent_events: List[K8sEvent]              # 최근 이벤트 (최대 3개)
```

### K8sAlertPayload

```python
@dataclass
class K8sAlertPayload:
    title: str                                 # 알림 제목
    text: str                                  # 알림 본문 (Markdown)
    severity: IncidentSeverity                 # 심각도
    namespace: str                             # K8s 네임스페이스
    selector: str                              # 레이블 선택자
    current_health: HealthLevel                # 현재 건강 상태
    metadata: Dict[str, str]                   # 메타데이터
    raw_incident: Dict                         # 원본 인시던트 (JSON)
```

### AlertChannelConfig

```python
@dataclass
class AlertChannelConfig:
    channel_type: Literal["console", "slack_webhook", "generic_webhook"]
    webhook_url: Optional[str] = None          # Webhook URL
    timeout_seconds: int = 5                   # 타임아웃
    dry_run: bool = True                       # 기본값: dry-run (안전)
```

### K8sAlertManager

```python
class K8sAlertManager:
    def __init__(self, channel_config: AlertChannelConfig):
        """알림 관리자 초기화"""
    
    def build_incident_from_history(
        self,
        history: List[K8sHealthHistoryRecord],
        recent_events: List[K8sEvent],
    ) -> Optional[K8sIncident]:
        """히스토리에서 인시던트 생성"""
    
    def build_alert_payload(self, incident: K8sIncident) -> K8sAlertPayload:
        """인시던트를 알림 페이로드로 변환"""
    
    def dispatch(self, payload: K8sAlertPayload) -> bool:
        """알림 전송"""
```

---

## 사용 방법

### 1. Console 알림 (기본값)

```bash
python scripts/send_k8s_alerts.py \
  --history-file outputs/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning
```

**출력:**
```
================================================================================
[D35_ALERT] 🚨 K8s Alert: CRITICAL – trading-bots
================================================================================

**Namespace:** trading-bots
**Selector:** app=arbitrage-tuning
**Severity:** CRITICAL
**Current Health:** ERROR

**Previous Health:** OK

**Job Counts:**
  - OK: 1
  - WARN: 0
  - ERROR: 1

**Recent Events (1):**
  - [Warning] BackoffLimitExceeded: Job has reached backoff limit (arb-tuning-worker-1)

**Started At:** 2025-11-16T10:00:00Z
**Detected At:** 2025-11-16T10:05:00Z
**Summary:** Health transitioned from OK to ERROR. 1 job(s) in ERROR state. Recent warnings: BackoffLimitExceeded.

================================================================================
```

**종료 코드:** 0 (성공)

### 2. Slack Webhook (Dry-run)

```bash
python scripts/send_k8s_alerts.py \
  --history-file outputs/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --channel-type slack_webhook \
  --webhook-url https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  --dry-run
```

**출력:**
```
[D35_ALERT] Webhook (slack) payload:
{
  "text": "🚨 K8s Alert: CRITICAL – trading-bots",
  "attachments": [
    {
      "color": "danger",
      "title": "🚨 K8s Alert: CRITICAL – trading-bots",
      "text": "...",
      "fields": [
        {
          "title": "Namespace",
          "value": "trading-bots",
          "short": true
        },
        ...
      ]
    }
  ]
}

[D35_ALERT] DRY-RUN: Would send to https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**종료 코드:** 0 (dry-run이므로 실제 전송 없음)

### 3. Slack Webhook (실제 전송)

```bash
python scripts/send_k8s_alerts.py \
  --history-file outputs/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --channel-type slack_webhook \
  --webhook-url https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  --no-dry-run
```

**동작:**
- 실제 HTTP POST 요청 전송
- 성공 시 종료 코드 0
- 실패 시 종료 코드 1

### 4. Generic Webhook

```bash
python scripts/send_k8s_alerts.py \
  --history-file outputs/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --channel-type generic_webhook \
  --webhook-url https://example.com/alerts \
  --no-dry-run
```

**페이로드:**
```json
{
  "alert_type": "k8s_health",
  "title": "🚨 K8s Alert: CRITICAL – trading-bots",
  "severity": "CRITICAL",
  "namespace": "trading-bots",
  "selector": "app=arbitrage-tuning",
  "current_health": "ERROR",
  "text": "...",
  "metadata": {
    "incident_id": "abc123def456",
    "started_at": "2025-11-16T10:00:00Z",
    "detected_at": "2025-11-16T10:05:00Z",
    "severity": "CRITICAL",
    "namespace": "trading-bots",
    "selector": "app=arbitrage-tuning"
  },
  "incident": { ... }
}
```

---

## 인시던트 감지

### 심각도 매핑

| 건강 상태 | 심각도 | 의미 |
|---------|--------|------|
| ERROR | CRITICAL | 즉시 조치 필요 |
| WARN | WARN | 주의 필요 |
| OK | (인시던트 없음) | 정상 |

### 인시던트 생성 조건

```python
# 최신 레코드가 OK가 아닐 때만 인시던트 생성
if latest_record.overall_health != "OK":
    incident = K8sIncident(...)
    return incident
else:
    return None  # 인시던트 없음
```

### 시작 시간 계산

```python
# 최근 히스토리에서 첫 번째 non-OK 레코드 찾기
for record in reversed(history):
    if record.overall_health != "OK":
        started_at = record.timestamp
    else:
        break
```

### 이벤트 포함

```python
# 최근 이벤트 중 마지막 3개만 포함
recent_events = events[-3:] if events else []
```

---

## 알림 전송

### Console 채널

```python
config = AlertChannelConfig(channel_type="console")
manager = K8sAlertManager(config)

payload = manager.build_alert_payload(incident)
manager.dispatch(payload)  # stdout에 출력
```

### Slack Webhook 채널

```python
config = AlertChannelConfig(
    channel_type="slack_webhook",
    webhook_url="https://hooks.slack.com/services/...",
    dry_run=False  # 실제 전송
)
manager = K8sAlertManager(config)

payload = manager.build_alert_payload(incident)
manager.dispatch(payload)  # HTTP POST
```

### Generic Webhook 채널

```python
config = AlertChannelConfig(
    channel_type="generic_webhook",
    webhook_url="https://example.com/alerts",
    dry_run=False
)
manager = K8sAlertManager(config)

payload = manager.build_alert_payload(incident)
manager.dispatch(payload)  # HTTP POST
```

---

## 채널 설정

### CLI 옵션

```bash
python scripts/send_k8s_alerts.py \
  --history-file <path>              # 필수: D34 히스토리 파일
  --namespace <ns>                   # 필수: K8s 네임스페이스
  --label-selector <selector>        # 필수: 레이블 선택자
  --channel-type <type>              # 선택: console (기본), slack_webhook, generic_webhook
  --webhook-url <url>                # 선택: Webhook URL (webhook 타입 필수)
  --dry-run                          # 선택: Dry-run 모드 (기본값)
  --no-dry-run                       # 선택: 실제 전송
  --events-limit <n>                 # 선택: 이벤트 개수 (기본값: 10)
  --history-limit <n>                # 선택: 히스토리 레코드 개수 (기본값: 20)
  --kubeconfig <path>                # 선택: kubeconfig 경로
  --context <name>                   # 선택: K8s context 이름
```

### 기본값

| 옵션 | 기본값 |
|------|--------|
| channel-type | console |
| dry-run | True (안전) |
| events-limit | 10 |
| history-limit | 20 |
| timeout-seconds | 5 |

---

## CI/CD 통합

### Cron Job 예시

```bash
#!/bin/bash
# /usr/local/bin/send_k8s_alerts.sh

cd /opt/arbitrage-lite

# 1. 건강 상태 기록 (D34)
python scripts/record_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file /var/log/k8s_health_history.jsonl

# 2. 알림 전송 (D35)
python scripts/send_k8s_alerts.py \
  --history-file /var/log/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --channel-type slack_webhook \
  --webhook-url $SLACK_WEBHOOK_URL \
  --no-dry-run

exit_code=$?

if [ $exit_code -ne 0 ]; then
  echo "Alert dispatch failed" | mail -s "K8s Alert Error" admin@example.com
fi

exit $exit_code
```

**Crontab:**
```bash
# 5분마다 건강 상태 기록 및 알림 전송
*/5 * * * * /usr/local/bin/send_k8s_alerts.sh
```

### GitHub Actions 예시

```yaml
name: K8s Health Alerts

on:
  schedule:
    - cron: '*/5 * * * *'  # 5분마다

jobs:
  send-alerts:
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
      
      - name: Send K8s Alerts
        run: |
          python scripts/send_k8s_alerts.py \
            --history-file /tmp/k8s_health_history.jsonl \
            --namespace trading-bots \
            --label-selector app=arbitrage-tuning \
            --channel-type slack_webhook \
            --webhook-url ${{ secrets.SLACK_WEBHOOK_URL }} \
            --no-dry-run
        continue-on-error: true
```

---

## 안전 정책

### Dry-run 기본값

```python
# 기본값: dry_run=True
config = AlertChannelConfig(
    channel_type="slack_webhook",
    webhook_url="https://hooks.slack.com/services/...",
    dry_run=True  # ← 기본값
)
```

**동작:**
- 페이로드 출력
- HTTP 요청 미전송
- 안전한 기본 설정

### Read-Only 정책

```
✅ 허용:
- 히스토리 읽기
- 이벤트 읽기
- 알림 생성
- HTTP POST (webhook)

❌ 금지:
- kubectl apply
- kubectl delete
- kubectl patch
- kubectl scale
- kubectl exec
```

---

## 관련 문서

- [D34 K8s Events & History](D34_K8S_EVENTS_AND_HISTORY.md)
- [D33 K8s Health Evaluation](D33_K8S_HEALTH_MONITORING.md)
- [D32 K8s Job/Pod Monitoring](D32_K8S_JOB_MONITORING.md)

---

## 향후 단계

### D36+ (미래 계획)

- **웹 대시보드**: 알림 시각화
- **알림 필터링**: 심각도별 필터
- **알림 히스토리**: 전송된 알림 추적
- **재시도 로직**: 실패한 전송 재시도
- **다중 채널**: Email, PagerDuty 등

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

# D36 Kubernetes Tuning Pipeline Orchestrator Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [사용 방법](#사용-방법)
4. [파이프라인 단계](#파이프라인-단계)
5. [안전 정책](#안전-정책)
6. [CI/CD 통합](#cicd-통합)

---

## 개요

D36은 **D29–D35의 모든 스크립트를 하나의 메타-CLI로 통합하여 K8s 튜닝 파이프라인을 자동화**하는 모듈입니다.

### 핵심 특징

- ✅ **원클릭 파이프라인**: 생성 → 검증 → 적용 → 모니터링 → 평가 → 기록 → 알림
- ✅ **안전한 기본값**: Dry-run 기본값, 명시적 플래그로만 실제 적용
- ✅ **모듈식 설계**: 기존 D29–D35 스크립트 재사용
- ✅ **완전한 자동화**: 수동 개입 없음
- ✅ **CI/CD 친화적**: 종료 코드 기반 상태 보고
- ✅ **Read-Only 정책 준수**: 모니터링만 수행

### 파이프라인 흐름

```
D29: Job YAML 생성
  ↓
D30: YAML 검증
  ↓
D31: 안전한 Apply (dry-run 기본값)
  ↓
D32: Job/Pod 모니터링
  ↓
D33: 건강 상태 평가
  ↓
D34: 히스토리 기록
  ↓
D35: 알림 전송 (dry-run 기본값)
  ↓
종료 코드 반환
```

---

## 아키텍처

### 데이터 구조

#### K8sTuningPipelineConfig

```python
@dataclass
class K8sTuningPipelineConfig:
    jobs_dir: str                          # D29 출력 디렉토리
    namespace: str                         # K8s 네임스페이스
    label_selector: str                    # 레이블 선택자
    history_file: str                      # D34 히스토리 파일
    kubeconfig: Optional[str] = None       # kubeconfig 경로
    context: Optional[str] = None          # K8s context
    apply_enabled: bool = False            # 실제 적용 여부
    alerts_enabled: bool = False           # 실제 알림 여부
    strict_health: bool = False            # WARN을 실패로 취급
    events_limit: int = 20                 # 이벤트 개수 제한
    history_limit: int = 20                # 히스토리 레코드 제한
    channel_type: str = "console"          # 알림 채널
    webhook_url: Optional[str] = None      # Webhook URL
```

#### K8sTuningPipelineResult

```python
@dataclass
class K8sTuningPipelineResult:
    mode: PipelineMode                     # "dry_run" | "apply" | "full_alerts"
    generated_jobs: int                    # 생성된 Job 개수
    validated_jobs: int                    # 검증된 Job 개수
    applied_jobs: int                      # 적용된 Job 개수
    health_status: str                     # "OK" | "WARN" | "ERROR"
    incidents_sent: int                    # 전송된 인시던트 개수
    history_appended: bool                 # 히스토리 추가 여부
    exit_code: int                         # 종료 코드
    steps: List[str]                       # 각 단계별 요약
```

### K8sTuningPipelineRunner

```python
class K8sTuningPipelineRunner:
    def __init__(self, config: K8sTuningPipelineConfig):
        """파이프라인 러너 초기화"""
    
    def run(self) -> K8sTuningPipelineResult:
        """
        파이프라인 실행:
        1. 생성 (D29)
        2. 검증 (D30)
        3. 적용 (D31)
        4. 모니터링 (D32)
        5. 평가 (D33)
        6. 기록 (D34)
        7. 알림 (D35)
        """
```

---

## 사용 방법

### 1. Dry-run 모드 (기본값 - 안전)

```bash
python scripts/run_k8s_tuning_pipeline.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file outputs/k8s_health_history.jsonl
```

**동작:**
- 모든 단계가 dry-run 모드로 실행
- 실제 클러스터 변경 없음
- 실제 Webhook 호출 없음
- 안전한 기본 설정

**출력:**
```
================================================================================
[D36_PIPELINE] SUMMARY
================================================================================
Mode: dry_run
Health: OK
Generated Jobs: 5
Validated Jobs: 5
Applied Jobs: 0
Incidents Sent: 0
History Appended: True
Exit Code: 0

Steps:
  - Generate: 5 jobs created
  - Validate: 5 jobs validated
  - Apply: 5 jobs (dry-run)
  - Monitor: snapshot captured
  - Health: OK
  - History: appended to outputs/k8s_health_history.jsonl
  - Alerts: 0 incident(s) sent
================================================================================
```

**종료 코드:** 0 (성공)

### 2. Apply 활성화 (실제 클러스터 변경)

```bash
python scripts/run_k8s_tuning_pipeline.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file outputs/k8s_health_history.jsonl \
  --enable-apply
```

**동작:**
- D31에서 실제 `kubectl apply` 실행
- 클러스터에 Job 생성
- 알림은 여전히 dry-run 모드

**주의:**
- 실제 클러스터 변경 발생
- 신중하게 사용

### 3. 알림 활성화 (실제 Webhook 호출)

```bash
python scripts/run_k8s_tuning_pipeline.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file outputs/k8s_health_history.jsonl \
  --enable-apply \
  --enable-alerts \
  --channel-type slack_webhook \
  --webhook-url https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**동작:**
- D31에서 실제 적용
- D35에서 실제 Slack Webhook 호출
- 완전한 자동화 파이프라인

### 4. Strict 모드 (WARN을 실패로 취급)

```bash
python scripts/run_k8s_tuning_pipeline.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file outputs/k8s_health_history.jsonl \
  --strict-health
```

**동작:**
- 건강 상태가 WARN이면 종료 코드 1
- CI/CD에서 WARN을 실패로 취급 가능

---

## 파이프라인 단계

### 단계 1: 생성 (D29)

```bash
python scripts/gen_d29_k8s_jobs.py \
  --orchestrator-config configs/d29_k8s/orchestrator_k8s_baseline.yaml \
  --output-dir outputs/d29_k8s_jobs
```

**출력:**
- K8s Job YAML 파일들

### 단계 2: 검증 (D30)

```bash
python scripts/validate_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs
```

**검증 항목:**
- YAML 형식
- 필수 필드
- 리소스 제한

### 단계 3: 적용 (D31)

```bash
# Dry-run (기본값)
python scripts/apply_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs

# 실제 적용
python scripts/apply_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --apply
```

### 단계 4: 모니터링 (D32)

```bash
python scripts/watch_k8s_jobs.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --one-shot
```

**수집 정보:**
- Job 상태
- Pod 상태
- 로그

### 단계 5: 평가 (D33)

```bash
python scripts/check_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning
```

**평가 결과:**
- OK (모든 Job 성공)
- WARN (일부 Job 경고)
- ERROR (Job 실패)

### 단계 6: 기록 (D34)

```bash
python scripts/record_k8s_health.py \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file outputs/k8s_health_history.jsonl
```

**기록 내용:**
- 건강 상태 스냅샷
- 이벤트
- 타임스탬프

### 단계 7: 알림 (D35)

```bash
# Console (기본값)
python scripts/send_k8s_alerts.py \
  --history-file outputs/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --dry-run

# Slack (실제)
python scripts/send_k8s_alerts.py \
  --history-file outputs/k8s_health_history.jsonl \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --channel-type slack_webhook \
  --webhook-url https://hooks.slack.com/services/... \
  --no-dry-run
```

---

## 안전 정책

### Dry-run 기본값

```python
# 기본값: apply_enabled=False, alerts_enabled=False
config = K8sTuningPipelineConfig(
    jobs_dir="outputs/jobs",
    namespace="trading-bots",
    label_selector="app=arbitrage-tuning",
    history_file="outputs/history.jsonl",
    apply_enabled=False,  # ← 기본값
    alerts_enabled=False,  # ← 기본값
)
```

**동작:**
- 모든 단계가 dry-run 모드
- 실제 변경 없음
- 안전한 기본 설정

### 종료 코드

| 상태 | 코드 | 의미 |
|------|------|------|
| OK | 0 | 성공 |
| WARN (strict 아님) | 0 | 성공 (경고 무시) |
| WARN (strict) | 1 | 실패 (경고 취급) |
| ERROR | 2 | 실패 (에러) |
| 파이프라인 오류 | 3 | 실패 (시스템 오류) |

---

## CI/CD 통합

### Cron Job 예시

```bash
#!/bin/bash
# /usr/local/bin/run_k8s_tuning_pipeline.sh

cd /opt/arbitrage-lite

python scripts/run_k8s_tuning_pipeline.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --namespace trading-bots \
  --label-selector app=arbitrage-tuning \
  --history-file /var/log/k8s_health_history.jsonl \
  --enable-apply \
  --enable-alerts \
  --channel-type slack_webhook \
  --webhook-url $SLACK_WEBHOOK_URL

exit_code=$?

if [ $exit_code -ne 0 ]; then
  echo "Pipeline failed with exit code $exit_code" | mail -s "K8s Pipeline Error" admin@example.com
fi

exit $exit_code
```

**Crontab:**
```bash
# 매일 자정에 파이프라인 실행
0 0 * * * /usr/local/bin/run_k8s_tuning_pipeline.sh
```

### GitHub Actions 예시

```yaml
name: K8s Tuning Pipeline

on:
  schedule:
    - cron: '0 0 * * *'  # 매일 자정
  workflow_dispatch:     # 수동 실행

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run K8s Tuning Pipeline
        run: |
          python scripts/run_k8s_tuning_pipeline.py \
            --jobs-dir outputs/d29_k8s_jobs \
            --namespace trading-bots \
            --label-selector app=arbitrage-tuning \
            --history-file /tmp/k8s_health_history.jsonl \
            --enable-apply \
            --enable-alerts \
            --channel-type slack_webhook \
            --webhook-url ${{ secrets.SLACK_WEBHOOK_URL }}
        env:
          KUBECONFIG: ${{ secrets.KUBECONFIG }}
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: pipeline-logs
          path: /tmp/k8s_health_history.jsonl
```

### Kubernetes CronJob 예시

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: k8s-tuning-pipeline
  namespace: trading-bots
spec:
  schedule: "0 0 * * *"  # 매일 자정
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: tuning-pipeline
          containers:
          - name: pipeline
            image: arbitrage-lite:latest
            command:
            - python
            - scripts/run_k8s_tuning_pipeline.py
            - --jobs-dir
            - /data/d29_k8s_jobs
            - --namespace
            - trading-bots
            - --label-selector
            - app=arbitrage-tuning
            - --history-file
            - /data/k8s_health_history.jsonl
            - --enable-apply
            - --enable-alerts
            - --channel-type
            - slack_webhook
            - --webhook-url
            - $(SLACK_WEBHOOK_URL)
            env:
            - name: SLACK_WEBHOOK_URL
              valueFrom:
                secretKeyRef:
                  name: pipeline-secrets
                  key: slack-webhook-url
            volumeMounts:
            - name: data
              mountPath: /data
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: pipeline-data
          restartPolicy: OnFailure
```

---

## 관련 문서

- [D35 K8s Alerts](D35_K8S_ALERTS.md)
- [D34 K8s Events & History](D34_K8S_EVENTS_AND_HISTORY.md)
- [D33 K8s Health Evaluation](D33_K8S_HEALTH_MONITORING.md)
- [D32 K8s Job/Pod Monitoring](D32_K8S_JOB_MONITORING.md)
- [D31 K8s Apply Layer](D31_K8S_APPLY_LAYER.md)
- [D30 K8s Executor](D30_K8S_EXECUTOR.md)
- [D29 K8s Orchestrator](D29_K8S_ORCHESTRATOR.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready

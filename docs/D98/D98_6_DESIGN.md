# D98-6: Observability & Alerting Pack v1 설계 문서

**작성일:** 2025-12-21  
**작성자:** Windsurf AI  
**상태:** 📋 DESIGN

---

## Executive Summary

**목표:** D98-5 Preflight Real-Check에 Observability 계층 추가 (Prometheus + Grafana + Telegram)

**핵심 원칙:**
- **기존 인프라 100% 재사용** (D77-1 Prometheus, D80-7 Telegram)
- **최소 추가 구현** (Preflight 메트릭 6개 + 대시보드 4개 패널 + 알림 2개 규칙)
- **상용 운영 기준** (Golden Signals, Runbook, P0~P3 라우팅)

**범위:**
- ✅ Preflight 메트릭 6~10개 (Counter/Gauge/Histogram)
- ✅ Grafana 패널 4~6개 (Last Status, Breakdown, Timeline)
- ✅ Telegram 알림 P0/P1 (Preflight FAIL/WARN)
- ✅ Docker Compose Prometheus/Grafana 추가
- ❌ WebSocket 메트릭 (D83 완료, 인벤토리만)
- ❌ Private API health (D98-5 범위 외)

---

## 1. KPI 10종 정의 (Golden Signals 관점)

### 1.1. Golden Signals 매핑

**4대 Golden Signals (Google SRE):**
1. **Latency** (지연 시간)
2. **Traffic** (트래픽)
3. **Errors** (오류)
4. **Saturation** (포화도)

### 1.2. Preflight KPI → Golden Signals

| # | KPI Name | Type | Golden Signal | Description |
|---|----------|------|---------------|-------------|
| 1 | Preflight Runs Total | Counter | Traffic | Preflight 실행 횟수 (총합) |
| 2 | Preflight Last Success | Gauge (0/1) | Errors | 마지막 실행 성공 여부 |
| 3 | Preflight Duration | Histogram | Latency | Preflight 실행 시간 (분포) |
| 4 | Preflight Checks Total | Counter | Traffic | 체크별 실행 횟수 |
| 5 | Preflight Check Status | Counter | Errors | 체크별 PASS/FAIL/WARN 횟수 |
| 6 | Redis Ping Latency | Histogram | Latency | Redis PING 응답 시간 |
| 7 | Postgres Query Latency | Histogram | Latency | Postgres SELECT 1 응답 시간 |
| 8 | Preflight Ready for LIVE | Gauge (0/1) | Errors | LIVE 실행 준비 완료 여부 |
| 9 | Preflight Fail Count (24h) | Counter | Errors | 24시간 내 실패 횟수 |
| 10 | Preflight Environment | Info | Metadata | 실행 환경 (paper/live) |

### 1.3. 추가 메트릭 (Optional, 향후 확장)

| # | KPI Name | Type | Description |
|---|----------|------|-------------|
| 11 | Exchange Health Check Latency | Histogram | 거래소 Health 체크 시간 |
| 12 | ReadOnly Guard Status | Gauge (0/1) | READ_ONLY_ENFORCED 상태 |

---

## 2. Prometheus 메트릭 네이밍/라벨 정책

### 2.1. 네이밍 컨벤션

**형식:** `{namespace}_{subsystem}_{metric}_{unit}`

**Namespace:** `arbitrage` (전체 시스템)  
**Subsystem:** `preflight` (D98-6)  
**Unit Suffix:**
- `_total` (Counter)
- `_seconds` (Histogram/Summary, 시간)
- `_bytes` (Gauge, 크기)
- 없음 (Gauge, 상태/비율)

**예시:**
- `arbitrage_preflight_runs_total` (Counter)
- `arbitrage_preflight_duration_seconds` (Histogram)
- `arbitrage_preflight_last_success` (Gauge, 0/1)

### 2.2. 라벨 정책

**원칙:**
- **저카디널리티 (Low Cardinality):** 라벨 조합 최대 100개 이하
- **필수 라벨:** `env` (paper/live), `run_id` (optional)
- **체크별 라벨:** `check` (Environment/Secrets/Database 등), `status` (pass/fail/warn)

**금지 라벨:**
- ❌ `timestamp` (타임스탬프는 Prometheus가 자동 추가)
- ❌ `message` (고카디널리티)
- ❌ `user_id` (고카디널리티)

**라벨 예시:**
```
arbitrage_preflight_checks_total{check="Database", status="pass"} 15
arbitrage_preflight_checks_total{check="Database", status="fail"} 2
arbitrage_preflight_checks_total{check="Exchange Health", status="pass"} 12
```

### 2.3. 메트릭 상세 정의

#### 메트릭 1: `arbitrage_preflight_runs_total`
- **Type:** Counter
- **Labels:** `env` (paper/live)
- **Description:** Preflight 실행 총 횟수
- **용도:** Traffic 추적, 실행 빈도 분석

#### 메트릭 2: `arbitrage_preflight_last_success`
- **Type:** Gauge (0 or 1)
- **Labels:** `env`
- **Description:** 마지막 Preflight 실행 성공 여부 (1=success, 0=fail)
- **용도:** 현재 상태 알림, 대시보드 Status 표시

#### 메트릭 3: `arbitrage_preflight_duration_seconds`
- **Type:** Histogram
- **Labels:** `env`
- **Buckets:** 0.1, 0.5, 1.0, 2.0, 5.0, 10.0 (초)
- **Description:** Preflight 실행 시간 분포
- **용도:** 성능 모니터링, P50/P99 계산

#### 메트릭 4: `arbitrage_preflight_checks_total`
- **Type:** Counter
- **Labels:** `env`, `check`, `status`
- **Description:** 체크별 실행 결과 카운트
- **용도:** 실패율 분석, 체크별 성공률

#### 메트릭 5: `arbitrage_preflight_realcheck_redis_latency_seconds`
- **Type:** Histogram
- **Labels:** `env`, `operation` (ping/set/get)
- **Buckets:** 0.001, 0.005, 0.01, 0.05, 0.1, 0.5 (초)
- **Description:** Redis Real-Check 응답 시간
- **용도:** Redis 성능 모니터링

#### 메트릭 6: `arbitrage_preflight_realcheck_postgres_latency_seconds`
- **Type:** Histogram
- **Labels:** `env`
- **Buckets:** 0.01, 0.05, 0.1, 0.5, 1.0 (초)
- **Description:** Postgres SELECT 1 응답 시간
- **용도:** Postgres 성능 모니터링

#### 메트릭 7: `arbitrage_preflight_ready_for_live`
- **Type:** Gauge (0 or 1)
- **Labels:** `env`
- **Description:** LIVE 실행 준비 완료 여부
- **용도:** Production readiness 판단

#### 메트릭 8: `arbitrage_preflight_info`
- **Type:** Info (Gauge=1, labels only)
- **Labels:** `env`, `version`, `hostname`
- **Description:** Preflight 메타데이터
- **용도:** 환경 정보 추적

---

## 3. Preflight 메트릭 수집 방식

### 3.1. 방식 선택: Textfile Collector

**근거:**
- Preflight는 **짧게 실행되는 배치** (5~10초)
- HTTP 서버는 오버헤드 (포트 충돌 위험)
- Textfile collector는 간단하고 안전함

**동작 방식:**
1. Preflight 실행 → 메트릭 계산
2. `.prom` 파일 생성 (`/var/lib/prometheus/node_exporter/preflight.prom`)
3. Prometheus가 주기적으로 scrape (node_exporter textfile collector)

**장점:**
- 포트 충돌 없음
- 별도 HTTP 서버 불필요
- 파일 기반이라 디버깅 쉬움

**단점:**
- 실시간성 낮음 (scrape interval에 의존)
- Node exporter 필요

### 3.2. 대안: Pushgateway

**근거:**
- Batch job에 적합
- Prometheus Pushgateway에 HTTP POST로 메트릭 전송

**장점:**
- 실시간성 높음
- Node exporter 불필요

**단점:**
- Pushgateway 서비스 추가 필요
- HTTP POST 실패 시 메트릭 손실

### 3.3. 최종 선택: **Textfile Collector (1안)**

**이유:**
- 기존 프로젝트가 Node exporter 사용 중인지 확인 필요
- 없다면 Pushgateway보다는 **In-Memory Backend + Periodic Export**

**실제 구현 방식 (최종):**
- `d98_live_preflight.py`에서 `prometheus_backend.py` 재사용
- 실행 시작 시 메트릭 초기화
- 실행 종료 시 `.prom` 파일 저장 (`docs/D98/evidence/d98_6/preflight_metrics.prom`)
- Prometheus는 이 파일을 static file로 읽기 (또는 Pushgateway 사용)

---

## 4. Telegram 알림 정책 (P0~P3)

### 4.1. 알림 우선순위

| Priority | Severity | 조건 | 채널 | Throttling |
|----------|----------|------|------|-----------|
| P0 | Critical | Preflight FAIL | Telegram + PostgreSQL | Never |
| P1 | High | Preflight WARN (중요 체크) | Telegram + PostgreSQL | 5분 |
| P2 | Medium | Preflight WARN (일반 체크) | PostgreSQL only | 30분 |
| P3 | Low | Preflight 성공 (정보) | PostgreSQL only | 1시간 |

### 4.2. P0 알림 (Critical)

**트리거 조건:**
- `preflight_last_success == 0` (FAIL)
- 또는 `ready_for_live == 0` (LIVE 준비 안 됨)

**메시지 포맷:**
```
🚨 P0: Preflight FAIL

Source: D98.PREFLIGHT.FAIL
Time: 2025-12-21 01:30:00
Environment: paper

Preflight 실행 실패 (6/8 PASS, 2 FAIL)

Failed Checks:
  - Database: Redis PING 실패 (Connection refused)
  - Exchange Health: Upbit API 타임아웃

Recommended Actions:
1. docker ps 확인 (arbitrage-redis, arbitrage-postgres 상태)
2. .env.paper 확인 (REDIS_URL, POSTGRES_DSN)
3. python scripts/d98_live_preflight.py --real-check 재실행
4. 실패 지속 시 운영팀 에스컬레이션

Run ID: preflight_20251221_013000
Evidence: docs/D98/evidence/d98_6/preflight_20251221_013000.json
```

**액션:**
- Telegram 즉시 발송 (Never throttled)
- PostgreSQL 저장
- Evidence JSON 파일 링크

### 4.3. P1 알림 (High)

**트리거 조건:**
- Preflight WARN 발생 (중요 체크)
  - Database WARN (테이블 누락 등)
  - Exchange Health WARN (Degraded 상태)
  - ReadOnly Guard WARN (설정 불일치)

**메시지 포맷:**
```
⚠️ P1: Preflight WARN

Source: D98.PREFLIGHT.WARN
Time: 2025-12-21 01:30:00
Environment: paper

Preflight 실행 경고 (7/8 PASS, 1 WARN)

Warning Checks:
  - Open Positions: 오픈 포지션 점검 구현 필요

Recommended Actions:
1. 정상 동작하지만 개선 필요
2. D98-7+에서 Open Positions 실제 조회 구현 예정
3. 지금은 무시 가능 (WARN 누적 시 P0 에스컬레이션)

Run ID: preflight_20251221_013000
Evidence: docs/D98/evidence/d98_6/preflight_20251221_013000.json
```

**액션:**
- Telegram 발송 (5분 throttling)
- PostgreSQL 저장

### 4.4. P2/P3 알림 (Medium/Low)

**P2 (Medium):**
- Preflight 성공 but 성능 저하 (duration > 5초)
- PostgreSQL only (Telegram opt-in via env var)

**P3 (Low):**
- Preflight 성공 (정보성)
- PostgreSQL only

---

## 5. Grafana Dashboard 설계

### 5.1. 대시보드 구성

**옵션 A: 기존 대시보드 수정**
- `monitoring/grafana/dashboards/d77_system_health.json` 수정
- "Preflight Health" 섹션 추가 (Row 추가)

**옵션 B: 신규 대시보드 생성**
- `monitoring/grafana/dashboards/d98_preflight_health.json` 신규
- Preflight 전용 대시보드

**최종 선택:** **옵션 A (기존 수정)**

**이유:**
- Preflight는 System Health의 일부
- 대시보드 분산 방지
- 기존 대시보드에서 한눈에 파악

### 5.2. 패널 구성 (최소 4개)

#### 패널 1: Last Preflight Status (Stat Panel)
- **Type:** Stat (단일 값)
- **Query:** `arbitrage_preflight_last_success{env="$env"}`
- **Thresholds:** 1=green (PASS), 0=red (FAIL)
- **Display:** "✅ PASS" or "❌ FAIL"
- **Refresh:** 30s

#### 패널 2: Preflight Checks Breakdown (Pie Chart)
- **Type:** Pie Chart
- **Query:** `sum by (status) (arbitrage_preflight_checks_total{env="$env"})`
- **Labels:** pass, fail, warn
- **Colors:** green, red, yellow

#### 패널 3: Preflight Execution Time (Graph)
- **Type:** Time Series (Graph)
- **Query:** `histogram_quantile(0.99, arbitrage_preflight_duration_seconds{env="$env"})`
- **Y-Axis:** 시간 (초)
- **Legend:** P50, P95, P99

#### 패널 4: Top Failed Checks (Table)
- **Type:** Table
- **Query:** 
  ```promql
  topk(5, 
    sum by (check) (
      increase(arbitrage_preflight_checks_total{env="$env", status="fail"}[24h])
    )
  )
  ```
- **Columns:** Check Name, Fail Count (24h)
- **Sort:** Fail Count DESC

#### 패널 5: Redis/Postgres Latency (Graph, Optional)
- **Type:** Time Series (Graph)
- **Queries:**
  - Redis: `histogram_quantile(0.99, arbitrage_preflight_realcheck_redis_latency_seconds{env="$env"})`
  - Postgres: `histogram_quantile(0.99, arbitrage_preflight_realcheck_postgres_latency_seconds{env="$env"})`
- **Y-Axis:** 시간 (ms)
- **Legend:** Redis P99, Postgres P99

#### 패널 6: Preflight Run Frequency (Stat, Optional)
- **Type:** Stat
- **Query:** `rate(arbitrage_preflight_runs_total{env="$env"}[5m]) * 60`
- **Display:** "X runs/minute"

### 5.3. Dashboard 변수 (Variables)

**변수 1: `env`**
- **Type:** Query
- **Query:** `label_values(arbitrage_preflight_runs_total, env)`
- **Default:** `paper`
- **Multi-value:** false

**변수 2: `check` (Optional)**
- **Type:** Query
- **Query:** `label_values(arbitrage_preflight_checks_total, check)`
- **Multi-value:** true
- **용도:** 특정 체크만 필터링

---

## 6. 런북 (Runbook) - 운영자 행동

### 6.1. 알림 수신 시 행동 (P0: Preflight FAIL)

**Step 1: 상황 파악 (1분)**
1. Grafana 대시보드 접속 (`http://localhost:3000`)
2. "System Health" → "Preflight Health" 섹션 확인
3. "Last Preflight Status" 패널: ❌ FAIL 확인
4. "Top Failed Checks" 테이블: 실패한 체크 확인

**Step 2: 인프라 확인 (2분)**
```powershell
# Docker 컨테이너 상태
docker ps -a | Select-String "redis|postgres|engine"

# Redis 연결 테스트
docker exec arbitrage-redis redis-cli PING

# Postgres 연결 테스트
docker exec arbitrage-postgres psql -U arbitrage -d arbitrage -c "SELECT 1"
```

**Step 3: Preflight 재실행 (1분)**
```powershell
cd C:\work\XXX_ARBITRAGE_TRADING_BOT
.\abt_bot_env\Scripts\Activate.ps1
python scripts\d98_live_preflight.py --real-check --output "docs\D98\evidence\d98_6\preflight_manual.json"
```

**Step 4: 결과 분석**
- ✅ PASS → 일시적 장애, 모니터링 계속
- ❌ FAIL → 근본 원인 파악 (로그, 설정 파일)

**Step 5: 중단/롤백 판단**
- **FAIL이 지속되면:** 봇 실행 중단, 인프라 복구 후 재시작
- **PASS로 전환되면:** 정상 운영 재개

### 6.2. 알림 수신 시 행동 (P1: Preflight WARN)

**Step 1: WARN 내용 확인**
- Telegram 메시지에서 "Warning Checks" 확인
- 대부분 WARN은 개선 필요하지만 즉시 중단은 아님

**Step 2: WARN 누적 모니터링**
- Grafana "Preflight Checks Breakdown" 패널에서 WARN 비율 확인
- WARN이 50% 이상이면 에스컬레이션

**Step 3: 백로그 등록**
- WARN 항목을 D98-7+ 백로그에 등록
- 우선순위 설정 (High/Medium)

### 6.3. 정기 점검 (Daily)

**매일 오전 9시:**
1. Grafana 대시보드 접속
2. "Last Preflight Status" 확인 (✅ PASS 여부)
3. "Top Failed Checks" (24h) 확인
4. FAIL이 1건 이상이면 근본 원인 분석

**주간 리뷰 (Weekly):**
1. Preflight 성공률 계산 (pass / total)
2. 목표: 99% 이상
3. 99% 미만이면 개선 계획 수립

---

## 7. Acceptance Criteria (AC)

### AC1: Prometheus 메트릭 6개 이상 노출
- [ ] `arbitrage_preflight_runs_total` (Counter)
- [ ] `arbitrage_preflight_last_success` (Gauge 0/1)
- [ ] `arbitrage_preflight_duration_seconds` (Histogram)
- [ ] `arbitrage_preflight_checks_total{check, status}` (Counter)
- [ ] `arbitrage_preflight_realcheck_redis_latency_seconds` (Histogram)
- [ ] `arbitrage_preflight_realcheck_postgres_latency_seconds` (Histogram)
- **증거:** Preflight 실행 후 `.prom` 파일 생성 or Pushgateway에서 확인

### AC2: Grafana 대시보드 패널 4개 이상 추가
- [ ] Last Preflight Status (Stat Panel)
- [ ] Preflight Checks Breakdown (Pie Chart)
- [ ] Preflight Execution Time (Graph)
- [ ] Top Failed Checks (Table)
- **증거:** Grafana 대시보드 JSON 파일, 스크린샷 (optional)

### AC3: Preflight 결과가 Evidence에 저장
- [ ] JSON 파일: `docs/D98/evidence/d98_6/preflight_<timestamp>.json`
- [ ] 메트릭 파일: `docs/D98/evidence/d98_6/preflight_metrics.prom` (optional)
- **증거:** Evidence 파일 존재 확인

### AC4: Telegram 알림 P0/P1 실제 발송 or Dry-run
- [ ] P0 알림 규칙: `D98.PREFLIGHT.FAIL`
- [ ] P1 알림 규칙: `D98.PREFLIGHT.WARN`
- [ ] 메시지 포맷: 체크 항목, 실패 이유, Recommended Actions
- **증거:** Telegram 발송 로그 or Mock 테스트 PASS

### AC5: 테스트 100% PASS
- [ ] Fast Gate PASS (shadowing, compileall, docs)
- [ ] Feature Tests PASS (D98-6 unit tests 10개 이상)
- [ ] Core Regression PASS (기존 176개 + D98-6 추가분)
- **증거:** pytest 출력 로그

### AC6: D_ROADMAP + CHECKPOINT 동기화
- [ ] D_ROADMAP.md에 D98-6 상태/증거 반영
- [ ] CHECKPOINT 문서에 D98-6 완료 기록
- **증거:** 문서 diff

### AC7: Git commit + push
- [ ] 의미 있는 커밋 메시지 (한국어)
- [ ] 대용량 파일 제외 (.gitignore)
- [ ] GitHub 푸시 성공
- **증거:** git log, GitHub commit 해시

---

## 8. 구현 로드맵 (STEP 3 상세)

### 8.1. Phase 1: Preflight 메트릭 추가

**파일 수정:**
- `scripts/d98_live_preflight.py` (~100 lines 추가)

**구현 내용:**
1. `prometheus_backend.py` import
2. 메트릭 정의 (6개)
3. 실행 시작 시 메트릭 초기화
4. 각 체크 완료 시 메트릭 기록
5. 실행 종료 시 `.prom` 파일 저장

**예상 코드:**
```python
from arbitrage.monitoring.prometheus_backend import PrometheusClientBackend

backend = PrometheusClientBackend()

# 메트릭 정의
runs_counter = backend.counter(
    "arbitrage_preflight_runs_total",
    "Total Preflight executions",
    ["env"]
)

# 실행 시작
start_time = time.time()
runs_counter.labels(env=self.settings.env).inc()

# 각 체크 완료
checks_counter.labels(env=self.settings.env, check="Database", status="pass").inc()

# 실행 종료
duration = time.time() - start_time
duration_histogram.labels(env=self.settings.env).observe(duration)

# .prom 파일 저장
with open("docs/D98/evidence/d98_6/preflight_metrics.prom", "w") as f:
    f.write(backend.export_prometheus_text())
```

### 8.2. Phase 2: Grafana 패널 추가

**파일 수정:**
- `monitoring/grafana/dashboards/d77_system_health.json` (~500 lines 추가)

**구현 내용:**
1. "Preflight Health" Row 추가
2. 4개 패널 JSON 생성 (Stat, Pie, Graph, Table)
3. Dashboard 변수 `$env` 연동

### 8.3. Phase 3: Telegram 알림 통합

**파일 수정:**
- `scripts/d98_live_preflight.py` (~50 lines 추가)
- `arbitrage/alerting/rule_engine.py` (~30 lines 추가)

**구현 내용:**
1. `AlertManager` import
2. Preflight FAIL 시 `AlertManager.dispatch()` 호출
3. Alert 규칙 추가: `D98.PREFLIGHT.FAIL` (P0), `D98.PREFLIGHT.WARN` (P1)

### 8.4. Phase 4: Docker Compose 수정

**파일 수정:**
- `docker/docker-compose.yml` (~40 lines 추가)

**구현 내용:**
1. Prometheus 서비스 추가 (포트 9090)
2. Grafana 서비스 추가 (포트 3000)
3. Volume 추가: `prometheus-data`, `grafana-data`

---

## 9. 테스트 전략

### 9.1. Unit Tests (최소 10개)

1. `test_preflight_metrics_counter_increment()`
2. `test_preflight_metrics_gauge_set()`
3. `test_preflight_metrics_histogram_observe()`
4. `test_preflight_metrics_export_prometheus_text()`
5. `test_preflight_telegram_alert_p0_fail()`
6. `test_preflight_telegram_alert_p1_warn()`
7. `test_preflight_telegram_message_format()`
8. `test_preflight_prom_file_output()`
9. `test_preflight_metrics_labels()`
10. `test_preflight_golden_signals_coverage()`

### 9.2. Integration Tests (최소 3개)

1. `test_preflight_full_pipeline()`: Real-Check → Metrics → Alert
2. `test_preflight_grafana_query_validation()`: PromQL 쿼리 실행 가능 여부
3. `test_preflight_telegram_delivery()`: Mock send_message 호출 확인

### 9.3. Regression Tests

- 기존 176개 테스트 100% PASS 유지
- D98-6 추가분 포함 총 ~190개 예상

---

## 10. 리스크 및 완화 전략

### 리스크 1: Prometheus/Grafana Docker 컨테이너 추가 시 포트 충돌
**완화:**
- 포트 9090 (Prometheus), 3000 (Grafana) 사용 전 확인
- `docker ps` 출력에서 포트 충돌 확인

### 리스크 2: Textfile Collector 방식이 실시간성 부족
**완화:**
- Preflight는 주기적 실행 (10분마다) 가정
- Scrape interval 30s면 충분

### 리스크 3: Telegram 알림 과다 발송 (P0 Never throttled)
**완화:**
- P0는 Preflight FAIL만 (1일 1~2건 예상)
- Aggregator로 5분 윈도우 내 중복 제거

### 리스크 4: 테스트 실패로 AC5 미달성
**완화:**
- Mock 기반 테스트 우선 (네트워크 의존성 제거)
- Preflight dry-run 모드 활용

---

## 11. 다음 단계 (D98-7+)

**D98-7: Open Positions 실제 조회**
- 현재 WARN 상태인 "Open Positions" 체크를 실제 구현
- Exchange Private API 호출

**D98-8: DB 마이그레이션 자동화**
- Preflight 실행 시 필수 테이블 자동 생성
- Alembic 통합

**D99: LIVE 점진 확대**
- 소액 LIVE 실행 (Live-0)
- Preflight를 LIVE 실행 전 필수 단계로 고정

---

**설계 완료:** 2025-12-21 01:45 KST  
**다음 단계:** STEP 3 (구현)

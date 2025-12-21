# D98-6 GAP LIST - 미완 항목 체크리스트

**작성일:** 2025-12-21  
**목적:** D98-6 ONE-TURN ENDGAME에서 완결할 미완 항목 명세

---

## 현재 상태 (AS-IS)

### ✅ 완료된 항목
1. **Prometheus 메트릭 7개 구현** (`scripts/d98_live_preflight.py`)
   - `arbitrage_preflight_runs_total`
   - `arbitrage_preflight_last_success`
   - `arbitrage_preflight_duration_seconds`
   - `arbitrage_preflight_checks_total`
   - `arbitrage_preflight_realcheck_redis_latency_seconds`
   - `arbitrage_preflight_realcheck_postgres_latency_seconds`
   - `arbitrage_preflight_ready_for_live`

2. **Telegram 알림 P0/P1 구현**
   - FAIL → P0 (Never throttled)
   - WARN → P1 (5분 throttling)

3. **기존 인프라 스캔 완료**
   - Grafana 대시보드 JSON: 6개 존재 (`monitoring/grafana/dashboards/`)
   - Prometheus 설정 샘플: `monitoring/prometheus/prometheus.yml.sample`
   - Grafana provisioning: `monitoring/grafana/provisioning/`

### ❌ 미완 항목 (TO-BE)

#### GAP-1: Docker Compose Prometheus/Grafana/Node-Exporter 추가
**현재 상태:**
- `docker/docker-compose.yml`에 Redis, Postgres, Engine만 존재
- Prometheus/Grafana 서비스 없음

**요구사항:**
- Prometheus 서비스 추가 (포트 9090)
- Grafana 서비스 추가 (포트 3000)
- Node-Exporter 서비스 추가 (textfile collector 활성화)
- Volume: `prometheus-data`, `grafana-data`, `textfile-collector-data`
- Network: 기존 `arbitrage-network` 재사용
- Prometheus가 다음을 scrape:
  1. 기존 arbitrage exporter (localhost:9100)
  2. node-exporter textfile collector (localhost:9101)

**산출물:**
- `docker/docker-compose.yml` (수정)
- `monitoring/prometheus/prometheus.yml` (신규, yml.sample 기반)

---

#### GAP-2: Preflight 메트릭 → Prometheus E2E 연결
**현재 상태:**
- Preflight는 `.prom` 파일만 생성 (`docs/D98/evidence/d98_6/preflight_*.prom`)
- Prometheus가 이를 읽지 못함 (수동 import만 가능)

**요구사항:**
- Node-Exporter textfile collector 설정
- Preflight가 textfile collector 디렉토리에 `.prom` 파일을 atomic write (임시 파일 → rename)
- Prometheus가 주기적으로 scrape하여 메트릭 수집
- 검증: `curl http://localhost:9090/api/v1/query?query=arbitrage_preflight_runs_total`로 메트릭 조회 가능

**산출물:**
- `scripts/d98_live_preflight.py` (수정: textfile collector 경로로 export)
- 실행 명령어 문서화 (README 또는 REPORT)

---

#### GAP-3: Grafana 패널 4개 이상 실제 구현 (AC-2 PASS)
**현재 상태:**
- D98_6_DESIGN.md에 패널 설계만 존재
- AC-2가 "⚠️ DEFERRED" 상태

**요구사항:**
- 기존 대시보드 JSON 수정: `monitoring/grafana/dashboards/d77_system_health.json`
- 최소 4개 패널 추가:
  1. **Preflight Last Success** (Stat 패널, 0/1)
  2. **Preflight Duration P95** (Graph 패널, Histogram quantile)
  3. **Check Status Breakdown** (Pie 패널, PASS/FAIL/WARN)
  4. **Redis/Postgres Latency** (Graph 패널, 2개 시계열)
- Grafana provisioning 설정 확인:
  - `monitoring/grafana/provisioning/dashboards/` 에 자동 로딩 설정
  - `monitoring/grafana/provisioning/datasources/` 에 Prometheus datasource 설정

**산출물:**
- `monitoring/grafana/dashboards/d77_system_health.json` (수정)
- Grafana API 검증 로그 (`curl http://localhost:3000/api/dashboards/...`)

---

## 완결 조건 (Definition of Done)

### 기능 검증
1. ✅ `docker compose up -d` 실행 시 Prometheus/Grafana/Node-Exporter가 정상 기동
2. ✅ Preflight 실행 → `.prom` 파일 생성 → Prometheus가 메트릭 수집
3. ✅ Prometheus query로 7개 메트릭 조회 가능
4. ✅ Grafana 대시보드에서 Preflight 패널 4개 확인 가능

### 테스트 검증
1. ✅ Fast Gate PASS (프로젝트 SSOT Fast Gate 스크립트)
2. ✅ Core Regression 100% PASS (전체 테스트, `-k test_d98` 금지)
3. ✅ Preflight Real-Check E2E PASS

### 문서 검증
1. ✅ D98_6_REPORT.md 업데이트 (AC-2를 ✅ PASS로)
2. ✅ D_ROADMAP.md 업데이트 (D98-6 완결 상태)
3. ✅ CHECKPOINT 업데이트 (D98-6 섹션)

### Git 검증
1. ✅ 커밋 메시지 한국어 (핵심 포함)
2. ✅ Push 성공 (대용량 파일 제외)
3. ✅ 변경 파일 Raw URL 확인 가능

---

## 실행 순서 (STEP 2~5)

### STEP 2-A: Docker Compose 확장
1. `docker/docker-compose.yml`에 Prometheus/Grafana/Node-Exporter 서비스 추가
2. `monitoring/prometheus/prometheus.yml` 생성 (yml.sample 기반)
3. Textfile collector 디렉토리 마운트 설정
4. `docker compose up -d` 검증

### STEP 2-B: Preflight → Prometheus 연결
1. `scripts/d98_live_preflight.py` 수정: textfile collector 경로로 export
2. Atomic write 구현 (임시 파일 → rename)
3. Preflight 실행 검증
4. Prometheus query 검증 (`curl`)

### STEP 2-C: Grafana 패널 구현
1. `d77_system_health.json` 읽기
2. "Preflight Health" Row 추가 (4개 패널)
3. PromQL 쿼리 작성 (Last Success, Duration P95, Check Breakdown, Latency)
4. JSON 저장 및 Grafana 재시작
5. Grafana API 검증 (`curl`)

### STEP 3: 테스트 Gate 3단
1. Fast Gate 실행
2. Full Core Regression 실행 (전체 테스트)
3. Preflight E2E 검증

### STEP 4: 문서 동기화
1. D98_6_REPORT.md 업데이트
2. D_ROADMAP.md 업데이트
3. CHECKPOINT 업데이트

### STEP 5: Git Commit + Push
1. `git status` / `git diff --stat`
2. Commit (한국어 메시지)
3. Push

---

## 증거 파일 경로

### STEP 0 (환경 정리)
- `docs/D98/evidence/d98_6/step0/docker_status.txt`

### STEP 2 (구현)
- `docker/docker-compose.yml` (수정)
- `monitoring/prometheus/prometheus.yml` (신규)
- `monitoring/grafana/dashboards/d77_system_health.json` (수정)
- `scripts/d98_live_preflight.py` (수정)

### STEP 3 (테스트)
- `docs/D98/evidence/d98_6/fast_gate.log`
- `docs/D98/evidence/d98_6/full_regression.log`
- `docs/D98/evidence/d98_6/prometheus_query_result.json`
- `docs/D98/evidence/d98_6/grafana_api_result.json`

### STEP 4 (문서)
- `docs/D98/D98_6_REPORT.md` (업데이트)
- `D_ROADMAP.md` (업데이트)

---

## 금지 사항

1. ❌ 선택/보류/스킵 금지 (AC-2 DEFERRED 금지)
2. ❌ 부분 테스트 (`-k test_d98`) 금지 (Full Regression 필수)
3. ❌ 대용량 파일 커밋 금지 (`.gitignore` 확인)
4. ❌ 중복 구현 금지 (기존 인프라 100% 재사용)

---

**체크리스트 완료 시점:** 모든 GAP-1~3 완료 + 테스트 PASS + 문서 동기화 + Git Push

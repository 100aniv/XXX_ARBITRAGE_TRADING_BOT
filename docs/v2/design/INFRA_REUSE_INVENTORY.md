# V2 인프라 재사용 인벤토리

**작성일:** 2025-12-29  
**목적:** V1에서 구축된 인프라 자산 중 V2에서 재사용할 항목을 KEEP/DROP/DEFER로 분류

---

## 📋 분류 기준

- **KEEP**: V2에서 즉시 재사용 (설정만 조정)
- **DROP**: V2에서 사용하지 않음 (삭제 또는 보관)
- **DEFER**: V2 Phase 2+ 이후 재검토 (현재는 보류)

---

## 🐳 Docker 인프라

### ✅ KEEP: 즉시 재사용

#### 1. PostgreSQL + TimescaleDB
- **위치:** `docker/docker-compose.yml` (line 38-59), `infra/docker-compose.yml` (line 40-78)
- **상태:** 2개 파일 중복 (통합 필요)
- **V2 활용:**
  - PnL 데이터 저장 (daily/weekly/monthly aggregation)
  - Trade history 저장
  - TimescaleDB로 시계열 분석
- **조치:**
  - `infra/docker-compose.yml` 버전 유지 (더 상세한 주석)
  - V2 migration SQL 작성 (`db/migrations/v2_schema.sql`)
  - **SSOT:** `infra/docker-compose.yml`

#### 2. Redis
- **위치:** `docker/docker-compose.yml` (line 12-33), `infra/docker-compose.yml` (line 83-115)
- **상태:** 2개 파일 중복 (포트 설정 다름)
- **V2 활용:**
  - Real-time market data cache
  - Session state 저장
  - Rate limiting 카운터
- **조치:**
  - 포트 통일: 6380 (호스트), 6379 (컨테이너 내부)
  - **SSOT:** `infra/docker-compose.yml`

#### 3. Prometheus
- **위치:** `docker/docker-compose.yml` (line 64-87), `infra/docker-compose.yml` (line 412-435)
- **상태:** 2개 파일 중복
- **V2 활용:**
  - Engine cycle latency 모니터링
  - Adapter execution time 추적
  - PnL metrics 수집
- **조치:**
  - 설정 파일 통합: `monitoring/prometheus/prometheus.v2.yml` 생성
  - V2 metrics exporter 추가 필요
  - **SSOT:** `monitoring/prometheus/prometheus.v2.yml` (신규 생성 예정)

#### 4. Grafana
- **위치:** `docker/docker-compose.yml` (line 109-132), `infra/docker-compose.yml` (line 437-467)
- **상태:** 2개 파일 중복
- **V2 활용:**
  - V2 대시보드 (D205-2)
  - PnL 시각화
  - Real-time order flow
- **조치:**
  - V2 전용 대시보드 생성: `monitoring/grafana/dashboards/v2_overview.json`
  - **SSOT:** `infra/docker-compose.yml`

#### 5. Node Exporter
- **위치:** `docker/docker-compose.yml` (line 92-104)
- **상태:** 단일 파일
- **V2 활용:**
  - Textfile collector로 preflight metrics 수집
  - System metrics 모니터링
- **조치:**
  - V2 preflight 결과를 `/textfile-collector/v2_preflight.prom`에 저장
  - **SSOT:** `docker/docker-compose.yml`

---

### ❌ DROP: V2에서 사용하지 않음

#### 1. Arbitrage Engine Service (V1 레거시)
- **위치:** `docker/docker-compose.yml` (line 137-193)
- **사유:** V1 live_loop 전용, V2는 harness 기반 실행
- **조치:**
  - 서비스 비활성화 (주석 처리)
  - V2에서는 `arbitrage.v2.harness.smoke_runner` 사용

#### 2. Arbitrage Core (D15 고성능 버전)
- **위치:** `infra/docker-compose.yml` (line 154-223)
- **사유:** V1 아키텍처 의존성, V2와 호환 불가
- **조치:**
  - 서비스 보관 (docs/v1/ 참조용)
  - V2는 Engine-Centric 구조로 재작성

#### 3. Paper Trader (D18)
- **위치:** `infra/docker-compose.yml` (line 239-292)
- **사유:** V1 paper_trader 모듈, V2는 harness 통합
- **조치:**
  - 서비스 보관
  - V2 paper mode는 SmokeRunner + MockAdapter로 대체

#### 4. Dashboard (FastAPI + WebSocket)
- **위치:** `infra/docker-compose.yml` (line 305-357)
- **사유:** V1 전용, V2는 D205-2에서 재설계
- **조치:**
  - 현재 서비스 보관
  - V2 대시보드는 Grafana 우선 (FastAPI는 DEFER)

#### 5. Adminer (DB 관리 UI)
- **위치:** `infra/docker-compose.yml` (line 120-136)
- **사유:** 개발 편의용, 프로덕션 불필요
- **조치:**
  - 로컬 개발 시에만 사용 (docker-compose.dev.yml 분리)

---

### 🔄 DEFER: V2 Phase 2+ 재검토

#### 1. Redis Exporter
- **위치:** `infra/docker-compose.yml` (line 363-383)
- **검토 시기:** D206-1 (Ops/Deploy)
- **사유:** 모니터링 인프라 최적화 시 필요

#### 2. Postgres Exporter
- **위치:** `infra/docker-compose.yml` (line 385-406)
- **검토 시기:** D206-1 (Ops/Deploy)
- **사유:** DB 성능 모니터링 필요 시 활성화

---

## 📂 Config 인프라

### ✅ KEEP

#### 1. 환경 변수 파일 구조
- **위치:** `.env.example`, `.env.paper`, `.env.live`
- **V2 활용:**
  - API Keys (UPBIT_ACCESS_KEY, BINANCE_API_KEY)
  - DB/Redis 접속 정보
  - Safety limits
- **조치:**
  - `.env.v2.example` 신규 생성 (V2 전용 템플릿)
  - Secrets는 절대 config.yml에 넣지 않음 (SSOT 원칙)

#### 2. YAML 설정 구조
- **위치:** `config/base.yml`, `configs/*.yaml`
- **V2 활용:**
  - V2 설정 스켈레톤 참조
- **조치:**
  - `config/v2/config.yml` 신규 생성 (이번 턴)
  - V1 config는 참조만 (직접 재사용 안 함)

---

### ❌ DROP

#### 1. Zone Profiles (D95)
- **위치:** `config/arbitrage/zone_profiles*.yaml`
- **사유:** V1 전용 로직, V2는 단순화
- **조치:** 보관 (docs/v1/ 참조)

---

## 🛠️ 모니터링 인프라

### ✅ KEEP

#### 1. Prometheus 설정
- **위치:** `monitoring/prometheus/prometheus.yml`, `prometheus.fx.yml`
- **상태:** 2개 파일 (multi-source용 .fx 버전 존재)
- **V2 활용:**
  - V2 metrics scraping 설정
- **조치:**
  - `prometheus.v2.yml` 신규 생성 (V2 전용 scrape config)

#### 2. Grafana Dashboards
- **위치:** `monitoring/grafana/dashboards/`
- **V2 활용:**
  - V2 dashboard 참조용
- **조치:**
  - `v2_overview.json` 신규 대시보드 생성 (D205-2)

#### 3. Grafana Provisioning
- **위치:** `monitoring/grafana/provisioning/`
- **V2 활용:**
  - Datasource 자동 설정
- **조치:**
  - V2 datasource 추가 (변경 없이 재사용)

---

### 🔄 DEFER

#### 1. Textfile Collector
- **위치:** `monitoring/textfile-collector/preflight.prom`
- **검토 시기:** D200-2 (Harness 표준화)
- **사유:** V2 preflight 결과 포맷 확정 후 재사용

---

## 🗄️ DB 인프라

### ✅ KEEP

#### 1. PostgreSQL Alert Storage
- **위치:** `arbitrage/alerting/storage/postgres_storage.py`
- **V2 활용:**
  - Alert history 저장 (D202-2에서 재사용)
  - UTC-naive timestamp 정규화 (FIX-0)
- **조치:**
  - 그대로 재사용 (UTC-naive 정규화 완료)
  - **SSOT:** `arbitrage/alerting/storage/postgres_storage.py`
  - **검증:** `tests/test_postgres_storage.py` (12/12 PASS)

#### 2. Migration Scripts
- **위치:** `db/migrations/*.sql`
- **V2 활용:**
  - V1 스키마 참조
- **조치:**
  - `db/migrations/v2_schema.sql` 신규 생성
  - V1 테이블과 분리 (v2_trades, v2_pnl 등)

---

## 📊 통합 요약

| 카테고리 | KEEP | DROP | DEFER | 총계 |
|----------|------|------|-------|------|
| Docker 서비스 | 5 | 5 | 2 | 12 |
| Config | 2 | 1 | 0 | 3 |
| 모니터링 | 3 | 0 | 1 | 4 |
| DB | 1 | 0 | 0 | 1 |
| **총계** | **11** | **6** | **3** | **20** |

---

## 🎯 다음 단계 (D200-1)

1. **즉시 조치 (이번 턴):**
   - `config/v2/config.yml` 생성
   - `infra/docker-compose.yml` SSOT 확정
   - V2 전용 .env.v2.example 템플릿 생성

2. **D200-2:**
   - Prometheus `prometheus.v2.yml` 생성
   - Grafana `v2_overview.json` 대시보드 생성
   - Textfile collector v2 포맷 정의

3. **D206-1 (Ops/Deploy):**
   - Exporter 활성화 결정
   - Production 배포 가이드 작성
   - 리소스 제한 설정

---

## 📚 참조 문서

- **Docker 설정:** `docker/docker-compose.yml`, `infra/docker-compose.yml`
- **V1 문서:** `docs/v1/README.md`
- **V2 규칙:** `docs/v2/SSOT_RULES.md`
- **V2 아키텍처:** `docs/v2/V2_ARCHITECTURE.md`

---

**결론:** V1 인프라의 55% (11/20)를 V2에서 즉시 재사용 가능. 나머지는 DROP(30%) 또는 DEFER(15%).

# D98-6: Repository Inventory - Observability & Alerting 기존 인프라

**작성일:** 2025-12-21  
**목적:** D98-6 구현 전 기존 모듈/인프라 재사용 가능 여부 파악

---

## 1. Executive Summary

**발견 사항:**
- ✅ Prometheus Exporter 인프라 **완전 구현됨** (D77-1, D80-6)
- ✅ Grafana Dashboard **6개 존재** (Trading KPIs, System Health, Risk Guard 등)
- ✅ Telegram 알림 시스템 **완전 구현됨** (D80-7~13)
- ✅ Alert 라우팅 엔진 **완전 구현됨** (P0~P3 우선순위, 다중 채널)
- ⚠️ Preflight 메트릭은 **미구현** (D98-5까지는 Real-Check만 완료)
- ⚠️ Docker Compose에 Prometheus/Grafana 컨테이너 **미추가**

**D98-6 전략:**
- **재사용 우선:** 기존 Prometheus/Telegram 인프라 100% 활용
- **최소 추가:** Preflight 메트릭 + 대시보드 패널만 추가
- **No 중복:** 새 exporter/notifier 생성 금지

---

## 2. 기존 인프라 상세 (AS-IS)

### 2.1. Prometheus Exporter (D77-1, D80-6)

#### (A) 구현 완료
**파일:**
- `arbitrage/monitoring/prometheus_exporter.py` (191 lines)
- `arbitrage/monitoring/prometheus_backend.py` (5261 bytes)
- `arbitrage/monitoring/metrics.py` (11736 bytes)
- `scripts/run_prometheus_exporter.py`

**기능:**
- HTTP 서버 (`/metrics` endpoint, `/health` endpoint)
- Background thread (non-blocking)
- Graceful shutdown
- PrometheusClientBackend (prometheus_client 라이브러리 기반)

**메트릭 (기존 11개):**
1. `arbitrage_total_pnl_usd` (Gauge) - 총 손익
2. `arbitrage_win_rate_pct` (Gauge) - 승률
3. `arbitrage_round_trips_total` (Counter) - 완료된 라운드 트립
4. `arbitrage_loop_latency_avg_ms` (Gauge) - 평균 루프 레이턴시
5. `arbitrage_loop_latency_p99_ms` (Gauge) - P99 루프 레이턴시
6. `arbitrage_memory_usage_mb` (Gauge) - 메모리 사용량
7. `arbitrage_cpu_usage_pct` (Gauge) - CPU 사용률
8. `arbitrage_guard_triggers_total` (Counter) - RiskGuard 트리거
9. `arbitrage_alert_count_total{severity="P0/P1/P2/P3"}` (Counter) - 알림 수
10. `arbitrage_exchange_health{exchange="upbit/binance"}` (Gauge) - 거래소 상태
11. `arbitrage_spread_opportunity_count_total` (Counter) - 스프레드 기회

**포트:** 9100 (기본)

**상태:** ✅ **PRODUCTION READY**

#### (B) 미구현 영역
- ❌ Preflight 관련 메트릭 (D98-5까지는 JSON 출력만)
- ❌ Textfile collector (.prom 파일) 방식 (Preflight는 짧게 실행되므로 필요 시 추가)

**증거:**
- `docs/D77_1_PROMETHEUS_EXPORTER_DESIGN.md` (513 lines)
- `tests/test_d77_1_prometheus_exporter.py` (139 matches)

---

### 2.2. Grafana Dashboard (D77-2)

#### (A) 구현 완료
**파일:**
- `monitoring/grafana/dashboards/topn_arbitrage_core.json` (27141 bytes)
- `monitoring/grafana/dashboards/d77_topn_trading_kpis.json` (5957 bytes)
- `monitoring/grafana/dashboards/d77_system_health.json` (7170 bytes)
- `monitoring/grafana/dashboards/d77_risk_guard.json` (9595 bytes)
- `monitoring/grafana/dashboards/alerting_overview.json` (25536 bytes)
- `monitoring/grafana/dashboards/fx_multi_source.json` (12995 bytes)

**대시보드 (6개):**
1. **Trading KPIs** (7 panels): PnL, Win Rate, Round Trips, Throughput, Latency
2. **System Health** (7 panels): CPU, Memory, Loop Latency, Uptime
3. **Risk Guard** (7 panels): Guard Triggers, Block Events, Exchange Health
4. **Alerting Overview** (복합): Alert 통계, 우선순위별 분포, 채널별 전송 현황
5. **FX Multi-Source** (복합): 환율 데이터 (TopN 확장용)
6. **TopN Arbitrage Core** (복합): 종합 대시보드

**Provisioning:**
- `monitoring/grafana/provisioning/` 디렉토리 존재

**상태:** ✅ **PRODUCTION READY**

#### (B) 미구현 영역
- ❌ Preflight 전용 패널 (체크별 PASS/FAIL/WARN, 실행 시간, Last Success 등)

**증거:**
- `docs/D77_2_GRAFANA_DASHBOARD_DESIGN.md` (771 lines)
- `tests/test_d77_2_grafana_dashboards.py` (76 matches)

---

### 2.3. Telegram Alerting (D80-7~13)

#### (A) 구현 완료
**파일:**
- `arbitrage/alerting/notifiers/telegram_notifier.py` (139 lines)
- `arbitrage/alerting/config.py` (TelegramConfig, 305 lines)
- `arbitrage/alerting/manager.py` (9125 bytes)
- `arbitrage/alerting/dispatcher.py` (17319 bytes)
- `arbitrage/alerting/routing.py` (16066 bytes)
- `arbitrage/alerting/rule_engine.py` (18670 bytes)

**기능:**
- **Severity 기반 Emoji:** P0=🚨, P1=⚠️, P2=⚡, P3=ℹ️
- **환경별 라우팅:** PROD (Telegram + PostgreSQL), DEV (Telegram + Slack + Email)
- **Throttling:** 5분 윈도우, Redis 기반 (메모리 fallback)
- **Aggregation:** 5분 타임 윈도우 내 중복 알림 집계
- **Retry:** 최대 3회 재시도, Exponential backoff
- **Failsafe:** Telegram 실패 시 PostgreSQL에 저장 보장

**설정:**
- `TELEGRAM_BOT_TOKEN` (env var)
- `TELEGRAM_CHAT_ID` (env var)
- `TELEGRAM_ENABLED` (기본: true)

**Alert Rules (기존 10개):**
1. `D75.SYSTEM.REDIS_CONNECTION_LOST` (P0)
2. `D75.SYSTEM.ENGINE_LATENCY` (P1)
3. `D75.RISK_GUARD.GLOBAL_BLOCK` (P0, Never throttled)
4. `D75.SYSTEM.WS_RECONNECT_STORM` (P1)
5. `D75.RATE_LIMITER.LOW_REMAINING` (P2)
6. `D75.RATE_LIMITER.HTTP_429` (P1)
7. `D75.HEALTH.DOWN` (P1)
8. `D75.ARB_UNIVERSE.ALL_SKIP` (P1)
9. `D75.CROSS_SYNC.HIGH_IMBALANCE` (P2)
10. `D75.WATCHDOG.ENGINE_STUCK` (P0)

**상태:** ✅ **PRODUCTION READY**

#### (B) 미구현 영역
- ❌ Preflight 실패 알림 규칙 (P0/P1)
- ❌ Preflight WARN 알림 규칙 (P2, 조건부)

**증거:**
- `tests/test_d80_13_alert_routing.py` (162 matches)
- `tests/test_d80_9_alert_reliability.py` (149 matches)
- `arbitrage/alerting/simulation/incidents.py` (142 matches)

---

### 2.4. Preflight (D98-0~5)

#### (A) 구현 완료
**파일:**
- `scripts/d98_live_preflight.py` (28 matches)
- `arbitrage/config/preflight.py` (PreflightError, 10 lines)
- `tests/test_d98_5_preflight_realcheck.py` (26 matches)

**기능:**
- **7개 체크:**
  1. Environment (ARBITRAGE_ENV)
  2. Secrets (6개 필수 시크릿)
  3. ReadOnly Guard (READ_ONLY_ENFORCED)
  4. Live Safety (LiveSafetyValidator, LIVE 모드만)
  5. Database (Redis PING+SET/GET, Postgres SELECT 1)
  6. Exchange Health (env별 분기)
  7. Git Safety (.env.live 누락 확인)
- **Real-Check:** `--real-check` 플래그로 실제 연결 검증
- **Fail-Closed:** PreflightError 발생 시 즉시 종료
- **Evidence:** JSON 출력 (`--output` 플래그)

**출력 포맷 (JSON):**
```json
{
  "summary": {
    "total_checks": 8,
    "passed": 7,
    "failed": 0,
    "warnings": 1,
    "ready_for_live": true
  },
  "checks": [
    {
      "name": "Database",
      "status": "PASS",
      "message": "...",
      "details": {...},
      "timestamp": "..."
    }
  ]
}
```

**상태:** ✅ **FUNCTIONAL** (D98-5 완료)

#### (B) 미구현 영역
- ❌ Prometheus 메트릭 노출
- ❌ Grafana 대시보드 통합
- ❌ Telegram 알림 통합

---

### 2.5. Docker Compose (AS-IS)

**파일:** `docker/docker-compose.yml`

**현재 서비스 (3개):**
1. `arbitrage-redis` (Redis 7-alpine, 포트 6380)
2. `arbitrage-postgres` (TimescaleDB, 포트 5432)
3. `arbitrage-engine` (Python 봇, 포트 8080)

**누락 서비스:**
- ❌ Prometheus (scrape target)
- ❌ Grafana (visualization)

**상태:** ⚠️ **PARTIAL** (모니터링 스택 미포함)

---

## 3. D98-6 스코프 확정

### 3.1. 이번 단계에서 다룰 대상

#### (A) Preflight 메트릭 추가
**목표:** Preflight 실행 결과를 Prometheus 메트릭으로 노출

**추가할 메트릭 (최소 6개):**
1. `preflight_runs_total` (Counter) - Preflight 실행 횟수
2. `preflight_last_success` (Gauge, 0/1) - 마지막 실행 성공 여부
3. `preflight_checks_total{check, status}` (Counter) - 체크별 상태 (pass/fail/warn)
4. `preflight_duration_seconds` (Histogram) - 실행 시간
5. `preflight_realcheck_redis_latency_seconds` (Histogram, optional) - Redis 응답 시간
6. `preflight_realcheck_postgres_latency_seconds` (Histogram, optional) - Postgres 응답 시간

**구현 방법:**
- 기존 `prometheus_backend.py` 재사용
- `d98_live_preflight.py`에서 메트릭 기록
- 또는 textfile collector (.prom 파일) 방식 (Preflight는 짧게 실행되므로)

#### (B) Grafana Preflight 패널 추가
**목표:** 기존 대시보드에 Preflight 섹션 추가

**추가할 패널 (최소 4개):**
1. **Last Preflight Status** (Stat panel) - 마지막 실행 결과 (PASS/FAIL)
2. **Preflight Checks Breakdown** (Pie chart) - 체크별 PASS/FAIL/WARN 분포
3. **Preflight Execution Time** (Graph) - 실행 시간 히스토리
4. **Top Failed Checks** (Table) - 최근 실패한 체크 목록

**대상 대시보드:**
- `monitoring/grafana/dashboards/d77_system_health.json` 수정 (Preflight 섹션 추가)
- 또는 `monitoring/grafana/dashboards/d98_preflight_health.json` 신규 생성

#### (C) Telegram Preflight 알림 통합
**목표:** Preflight 실패/WARN 시 Telegram 발송

**추가할 Alert Rules (최소 2개):**
1. `D98.PREFLIGHT.FAIL` (P0) - Preflight 실패 즉시 발송
2. `D98.PREFLIGHT.WARN` (P1 or P2) - WARN 발생 시 발송 (정책 확정 필요)

**메시지 포맷:**
```
🚨 P0: Preflight FAIL

Source: D98.PREFLIGHT
Time: 2025-12-21 01:30:00

Preflight 실행 실패 (7/8 PASS, 1 FAIL)

Failed Checks:
  - Database: DB Real-Check 실패 (Postgres 연결 거부)

Recommended Actions:
1. docker ps 확인 (arbitrage-postgres 상태)
2. .env.paper 확인 (POSTGRES_DSN 정확성)
3. python scripts/d98_live_preflight.py --real-check 재실행

Run ID: preflight_20251221_013000
```

**구현 방법:**
- `d98_live_preflight.py`에서 `AlertManager.dispatch()` 호출
- 기존 `arbitrage/alerting/manager.py` 재사용
- `arbitrage/alerting/rule_engine.py`에 D98.PREFLIGHT 규칙 추가

#### (D) Docker Compose Prometheus/Grafana 추가
**목표:** 로컬 개발 환경에서 Prometheus + Grafana 자동 실행

**추가할 서비스 (2개):**
1. `prometheus` (prom/prometheus:latest)
   - 포트: 9090
   - 설정: `monitoring/prometheus/prometheus.yml`
   - Scrape target: `arbitrage-engine:8080/metrics` (또는 Preflight textfile)
2. `grafana` (grafana/grafana:latest)
   - 포트: 3000
   - Provisioning: `monitoring/grafana/provisioning/`
   - Dashboard: `monitoring/grafana/dashboards/`

**주의사항:**
- Docker network: `arbitrage-network` (기존 재사용)
- Volume: `prometheus-data`, `grafana-data` (persistence)

---

### 3.2. 보류 대상 (이번 단계에서 다루지 않음)

#### (A) D83-1 Real L2 WebSocket
**상태:** 완료 (D83-1), 기본 디폴트는 Mock 유지

**이번 단계:**
- ✅ 3~5분 스모크 테스트 (기존 스크립트 사용)
- ✅ Evidence 저장 (성공/실패 여부만)
- ❌ Real L2를 디폴트로 변경 (스코프 확장 금지)
- ❌ WebSocket 관련 메트릭 추가 (D83에서 이미 구현되었을 가능성, 확인만)

#### (B) Private Endpoint Health Check
**이유:** Preflight는 Public endpoint만 호출 (D98-5 설계 원칙)

**이번 단계:**
- ❌ 잔고 조회 (Private API)
- ❌ 주문 조회 (Private API)
- ❌ 포지션 조회 (Private API)

#### (C) DB 마이그레이션 자동화
**이유:** Preflight는 연결 검증만 (D98-5 설계 원칙)

**이번 단계:**
- ❌ 테이블 자동 생성
- ❌ 스키마 마이그레이션

#### (D) 성능 최적화
**이유:** D98-6은 Observability 추가, 성능은 D99+

**이번 단계:**
- ❌ 메트릭 병렬 수집
- ❌ 메트릭 캐싱
- ❌ Dashboard 쿼리 최적화

---

## 4. 미사용/조건부 구현 목록

### 4.1. 미사용 (구현은 있으나 entrypoint에서 사용 안 함)

**발견 항목:**
1. `arbitrage/alerting/notifiers/slack_notifier.py` (5345 bytes)
   - **상태:** 구현 완료, 테스트 존재
   - **사용 여부:** DEV 환경에서만 사용 (SLACK_ENABLED=false 기본)
   - **D98-6 판단:** 보류 (Telegram만으로 충분)

2. `arbitrage/alerting/notifiers/email_notifier.py` (10489 bytes)
   - **상태:** 구현 완료, 테스트 존재
   - **사용 여부:** P2 알림에서 선택적 사용
   - **D98-6 판단:** 보류 (Telegram만으로 충분)

3. `arbitrage/monitoring/longrun_analyzer.py` (21496 bytes)
   - **상태:** 구현 완료
   - **사용 여부:** D77-0-RM (Real Market) 1h/12h 검증 시 사용
   - **D98-6 판단:** 재사용 (Preflight 장기 통계 분석 시 활용 가능, 단 이번 단계에서는 미사용)

### 4.2. 조건부 구현 (환경/플래그에 따라 활성화)

**발견 항목:**
1. `arbitrage/alerting/throttler.py` (8549 bytes)
   - **조건:** `ALERT_THROTTLE_ENABLED=true` (기본)
   - **D98-6 판단:** 재사용 (Preflight P2 WARN 알림에 throttling 적용)

2. `arbitrage/alerting/aggregator.py` (10643 bytes)
   - **조건:** 5분 윈도우 내 중복 알림 집계
   - **D98-6 판단:** 재사용 (Preflight 반복 실패 시 집계)

3. `arbitrage/config/live_safety.py` (LiveSafetyValidator)
   - **조건:** `ARBITRAGE_ENV=live`
   - **D98-6 판단:** 재사용 (Preflight Exchange Health 체크에서 이미 사용 중)

---

## 5. 테스트 커버리지 (AS-IS)

### 5.1. 기존 테스트

**Prometheus/Grafana:**
- `tests/test_d77_1_prometheus_exporter.py` (139 matches)
- `tests/test_d77_2_grafana_dashboards.py` (76 matches)
- `tests/test_d77_1_metrics.py` (68 matches)

**Telegram/Alerting:**
- `tests/test_d80_13_alert_routing.py` (162 matches)
- `tests/test_d80_9_alert_reliability.py` (149 matches)
- `tests/test_d80_8_full_alert_integration.py` (122 matches)

**Preflight:**
- `tests/test_d98_5_preflight_realcheck.py` (26 matches)
- `tests/test_d98_preflight.py` (34 matches)
- `tests/test_d98_preflight_readonly.py` (31 matches)

**총 테스트 카운트 (추정):**
- Prometheus/Grafana: ~150개
- Alerting: ~500개
- Preflight: ~50개

### 5.2. D98-6 추가 테스트 (예정)

**Unit Tests (최소 10개):**
1. test_preflight_metrics_counter_increment
2. test_preflight_metrics_gauge_set
3. test_preflight_metrics_histogram_observe
4. test_preflight_telegram_alert_p0_fail
5. test_preflight_telegram_alert_p1_warn
6. test_preflight_telegram_message_format
7. test_preflight_metrics_export_prometheus_text
8. test_preflight_dashboard_panel_query
9. test_preflight_throttler_integration
10. test_preflight_aggregator_integration

**Integration Tests (최소 3개):**
1. test_preflight_full_pipeline (Real-Check → Metrics → Alert)
2. test_preflight_grafana_query_validation (PromQL 쿼리 검증)
3. test_preflight_telegram_delivery (Mock send_message)

---

## 6. 결론 및 D98-6 실행 가이드

### 6.1. 재사용 가능 모듈 (100% 활용)

| 모듈 | 파일 | 재사용 방법 |
|------|------|----------|
| Prometheus Exporter | `prometheus_backend.py` | Preflight 메트릭 등록 |
| Telegram Notifier | `telegram_notifier.py` | Preflight 알림 전송 |
| Alert Manager | `alerting/manager.py` | Preflight 규칙 추가 |
| Grafana Dashboard | `grafana/dashboards/*.json` | Preflight 패널 추가 |

### 6.2. 최소 추가 구현 (D98-6)

**신규 코드 (최소화):**
1. `scripts/d98_live_preflight.py` 수정 (메트릭 기록 + 알림 호출, ~50 lines)
2. `arbitrage/alerting/rule_engine.py` 수정 (D98.PREFLIGHT 규칙 추가, ~30 lines)
3. `monitoring/grafana/dashboards/d98_preflight_health.json` 신규 (또는 기존 수정, ~500 lines)
4. `docker/docker-compose.yml` 수정 (Prometheus + Grafana 추가, ~40 lines)
5. `tests/test_d98_6_preflight_observability.py` 신규 (~300 lines)

**총 추가 예상:** ~920 lines (기존 인프라 재사용으로 최소화)

### 6.3. No Side-track 보장

**금지 사항:**
- ❌ 새 Prometheus backend 작성
- ❌ 새 Telegram notifier 작성
- ❌ Slack/Email 통합 (이번 단계 불필요)
- ❌ WebSocket 메트릭 추가 (D83 완료, 인벤토리만)
- ❌ Private API health check (D98-5 설계 범위 외)
- ❌ DB 마이그레이션 자동화 (D98-5 설계 범위 외)
- ❌ 성능 최적화 (D99+)

**허용 사항:**
- ✅ Preflight 메트릭 6~10개 추가
- ✅ Grafana 패널 4~6개 추가
- ✅ Telegram 알림 규칙 2개 추가
- ✅ Docker Compose 서비스 2개 추가
- ✅ 테스트 10~15개 추가

---

**Inventory 작성 완료:** 2025-12-21  
**다음 단계:** D98-6 DESIGN 작성 (STEP 2)

# D77-0-RM-EXT: Real Market 1h+ Extended PAPER Validation - Execution Plan

**작성일:** 2025-12-03 | **버전:** v1.0  
**범위:** TopN Real Market PAPER 1시간+ 장기 실행 검증  
**기반:** D77-0-RM (10분 검증) 확장

---

## 🎯 Executive Summary

### 목적 (Goal)
D77-0-RM의 10분 검증을 확장하여, **Upbit/Binance Real Market TopN PAPER 모드를 최소 1시간 이상** 연속 실행하면서:
- **장기 안정성** 검증 (메모리 누수, CPU 안정성, Rate Limit 핸들링)
- **스프레드/라우팅 패턴** 분석 (실시간 시장 데이터 기반)
- **모니터링/알림 스택** 통합 검증 (D77-1/2/5 + D76)
- **상용급 운영 준비도** 평가

### 핵심 차별점
| 검증 단계 | 실행 시간 | 주요 목적 |
|-----------|----------|-----------|
| D77-0 (Mock) | 5분 | 기술적 구조 검증 |
| D77-0-RM | 10분 | Real Market 통합 검증 |
| **D77-0-RM-EXT** | **1h+** | **장기 안정성 + 운영 준비도** |
| D77-4 | 1h+ | Mock → Real + 모니터링 스택 종합 검증 |

### 제약 사항 (DO-NOT-TOUCH)
- ✅ **엔진/전략/도메인 레이어**: 절대 수정 금지
- ✅ **모니터링/알림 인프라**: D77-1/2/5 + D76 + D80-7/8 기준선 그대로 사용
- ✅ **변경 범위**: 실행 하네스, 검증 플로우, 리포트, 설정 레벨만 허용

---

## 📋 1. 실행 시나리오

### Universe 전략 (TopN)

- **Primary: Top20** (필수)
  - 목적: 실전 운영에 가장 가까운 조건에서 1시간 장기 안정성 및 성능 검증
  - 유동성/거래량 상위 심볼 기준, 실전 수익 기여 핵심

- **Extended: Top50** (선택, 환경 여유 시)
  - 목적: 상위 알트까지 포함한 부하/안정성 Stress Test
  - Rate Limit 핸들링 강도 검증

- **Top100+ 확장**
  - 현재 D77 단계에서는 범위 밖
  - 향후 D80+ Multi-Symbol Performance 단계에서
    - TopN(20/50/100) 별 Load Test
    - Rate Limit 튜닝
    - API 비용/수익 기여도 분석
    과 함께 재검토 예정

### 1.1 Primary Scenario (기본)
```bash
# Top20, 1시간, Real Market PAPER
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top20 \
  --duration-minutes 60 \
  --data-source real \
  --monitoring-enabled \
  --kpi-output-path logs/d77-0-rm-ext/1h_top20_kpi.json
```

**목표:**
- Universe: Top20 (Upbit/Binance 상위 20개 심볼)
- Duration: 60분 (3600초)
- Round Trips: 목표 100+ (실제 시장 조건에 따라 변동)
- Data Source: Real (Upbit/Binance Public API)

### 1.2 Extended Scenario (필수)
```bash
# Top50, 1시간, Real Market PAPER
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top50 \
  --duration-minutes 60 \
  --data-source real \
  --monitoring-enabled \
  --kpi-output-path logs/d77-0-rm-ext/1h_top50_kpi.json
```

**목표:**
- Universe: Top50 (더 많은 라우트, 더 복잡한 부하)
- Rate Limit 핸들링 강도 테스트 (Upbit 429 에러)
- 스프레드 분포 패턴 분석
- **D77-0-RM-EXT Done Criteria 충족을 위해 Top20 + Top50 모두 필수 완료**

### 1.3 Smoke Test (사전 검증)
```bash
# 3분 스모크 테스트 (환경 확인)
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top20 \
  --duration-minutes 3 \
  --data-source real \
  --monitoring-enabled \
  --kpi-output-path logs/d77-0-rm-ext/smoke_3m_kpi.json
```

**목적:**
- Upbit/Binance Public API 접근성 확인
- Docker 스택 (Redis/Postgres/Prometheus/Grafana) 정상 동작 확인
- 429 Rate Limit 핸들링 동작 확인 (D77-5)
- 기본 Round Trip 발생 여부 확인 (최소 1개 이상)

---

## 🔧 2. 환경 전제 조건

### 2.1 Docker Infrastructure
**필수 컨테이너:**
- ✅ Redis (키-값 캐싱, 심볼 상태)
- ✅ PostgreSQL (Alert 로그, Trade 히스토리)
- ✅ Prometheus (메트릭 수집, 포트 9090)
- ✅ Grafana (대시보드, 포트 3000)
- ⚠️ Alertmanager (알림 라우팅, 선택적)

**확인 명령:**
```powershell
docker ps --filter "name=redis|postgres|prometheus|grafana" --format "table {{.Names}}\t{{.Status}}"
```

### 2.2 API Rate Limits (중요)
**Upbit Public API:**
- Rate Limit: **초당 10회, 분당 600회** (추정)
- D77-5 구현: 429 에러 시 exponential backoff (0.5s → 1.0s → 2.0s)
- Top50 로딩 시 429 발생 가능 → 자동 재시도 확인 필요

**Binance Public API:**
- Rate Limit: **초당 1200회** (상대적으로 여유)
- 에러 핸들링: 일반 RequestException 처리

### 2.3 Python Environment
- Virtual Environment: `abt_bot_env` (또는 프로젝트 표준)
- Python: 3.10+ 권장
- 필수 패키지: `psutil`, `requests`, `prometheus-client`, `redis`, `psycopg2`

**확인 명령:**
```powershell
.\abt_bot_env\Scripts\python.exe --version
.\abt_bot_env\Scripts\python.exe -m pip list | Select-String "prometheus|redis|psycopg2"
```

---

## 📊 3. 모니터링 항목

### 3.1 Core KPI 10종 (D77-2 기준)
| # | KPI | Prometheus 메트릭 | 목표 |
|---|-----|------------------|------|
| 1 | Total PnL | `arb_topn_pnl_total` | 플러스 권장 |
| 2 | Win Rate | `arb_topn_win_rate` | 50~80% |
| 3 | Round Trips | `arb_topn_round_trips_total` | 100+ (1h) |
| 4 | Loop Latency (avg) | `arb_loop_latency_seconds{quantile="0.5"}` | < 25ms |
| 5 | Loop Latency (p99) | `arb_loop_latency_seconds{quantile="0.99"}` | < 80ms |
| 6 | CPU Usage | `process_cpu_usage_percent` | < 70% |
| 7 | Memory Usage | `process_memory_usage_mb` | < 200MB, 증가율 < 10%/h |
| 8 | Open Positions | `arb_open_positions_total` | 스냅샷 시점 확인 |
| 9 | Guard Triggers | `arb_guard_triggers_total` | < 50/h |
| 10 | Snapshot Save Rate | `arb_snapshot_save_success_rate` | 100% |

### 3.2 Arbitrage-Specific KPI (추가)
| # | KPI | 데이터 소스 | 분석 목적 |
|---|-----|------------|-----------|
| A1 | 평균 스프레드 | 로그 분석 | 실시간 시장 기회 평가 |
| A2 | 스프레드 분포 (p50/p95) | 로그 분석 | 수익성 분포 |
| A3 | Route 분포 | 로그 분석 | Upbit ↔ Binance 패턴 |
| A4 | Rate Limit 히트 | 로그: `429` 패턴 | Upbit API 안정성 |
| A5 | TopN Symbol 변화 | TopNProvider 로그 | 심볼 순위 변동성 |

### 3.3 실시간 모니터링 체크리스트 (수동)
**Grafana Dashboard 확인 (매 10분, 총 6회):**
- URL: `http://localhost:3000/d/d77-topn-core/topn-arbitrage-core`
- Panel 1: PnL Over Time (상승 추세 확인)
- Panel 2: Win Rate (50~80% 범위)
- Panel 3: Loop Latency (p99 < 80ms)
- Panel 4: CPU/Memory (안정성)
- Panel 5: Guard Triggers (급증 없음)

**콘솔 로그 감시:**
- `ERROR`, `CRITICAL`, `Traceback` 패턴 → 즉시 조사
- `[UPBIT_PUBLIC] Rate limit (429)` → 재시도 성공 확인
- `DLQ` (Dead Letter Queue) → 0건 유지

---

## 📁 4. 로그/리포트 산출물

### 4.1 자동 생성 파일
**실행 중:**
- `logs/d77-0-rm-ext/<run_id>/console.log` (콘솔 로그)
- `logs/d77-0-rm-ext/<run_id>/kpi.json` (Core KPI 10종)

**실행 후:**
- `logs/d77-0-rm-ext/<run_id>/prometheus_metrics.prom` (D77-5 스냅샷)
- `logs/d77-0-rm-ext/<run_id>/analysis_result.json` (분석 결과, 선택적)

### 4.2 수동 작성 문서
- `docs/D77_0_RM_EXT_REPORT.md` (최종 검증 리포트)
  - Template: `docs/D77_0_RM_EXT_REPORT_TEMPLATE.md`
  - 작성자: 실행 후 결과 기반으로 수동 작성

---

## ⚠️ 5. 위험/에러 핸들링 플로우

### 5.1 Upbit 429 Rate Limit
**발생 조건:**
- Top50 심볼 로딩 시 초당 10회 제한 초과

**자동 대응 (D77-5 구현):**
1. 429 에러 감지
2. Exponential backoff: 0.5s → 1.0s → 2.0s
3. 최대 3회 재시도
4. 성공 시 정상 진행, 실패 시 해당 심볼 스킵

**모니터링:**
- 로그에서 `[UPBIT_PUBLIC] Rate limit (429)` 패턴 확인
- `rate_limit_hits` 카운터 증가 확인

### 5.2 WebSocket 장애 (해당 시)
**발생 조건:**
- Binance WS 연결 끊김, Upbit WS 지연

**대응:**
- 현재는 Public REST API만 사용 → WS 장애 영향 없음
- 향후 WS 통합 시: Reconnection 로직 필요 (TODO)

### 5.3 데이터 Stale (오래된 데이터)
**발생 조건:**
- Redis 캐시 TTL 초과, API 응답 지연

**대응:**
- `fetch_ticker()`, `fetch_orderbook()` 호출 시 타임스탬프 검증
- Stale 데이터 감지 시 해당 심볼 거래 스킵

### 5.4 메모리 누수 의심
**발생 조건:**
- `memory_usage_mb`가 1시간 동안 20% 이상 증가

**대응:**
1. 실행 즉시 중단
2. 메모리 프로파일링 수행 (`memory_profiler`)
3. 로그에서 객체 생성 패턴 분석

### 5.5 CPU 과부하
**발생 조건:**
- `cpu_usage_pct` > 80% 지속 (5분 이상)

**대응:**
1. Grafana 대시보드에서 Loop Latency 확인
2. 병목 구간 식별 (프로파일링 필요 시)
3. Universe 크기 축소 (Top50 → Top20) 고려

---

## 🚀 6. 실행 플로우 (7단계)

### Step 1: 환경 준비
```powershell
# 1.1 가상환경 활성화
.\abt_bot_env\Scripts\Activate.ps1

# 1.2 Docker 스택 확인
docker-compose up -d redis postgres prometheus grafana

# 1.3 기존 PAPER 프로세스 종료 (충돌 방지)
Get-Process python | Where-Object {$_.CommandLine -like "*run_d77_0*"} | Stop-Process -Force
```

### Step 2: 스모크 테스트 (3분)
```powershell
# 2.1 실행
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top20 \
  --duration-minutes 3 \
  --data-source real \
  --monitoring-enabled \
  --kpi-output-path logs/d77-0-rm-ext/smoke_3m_kpi.json

# 2.2 결과 확인
cat logs/d77-0-rm-ext/smoke_3m_kpi.json | Select-String "round_trips_completed"
# 기대: round_trips_completed >= 1
```

### Step 3: 1시간 본 실행 (Primary)
```powershell
# 3.1 실행 (새 터미널 권장)
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top20 \
  --duration-minutes 60 \
  --data-source real \
  --monitoring-enabled \
  --kpi-output-path logs/d77-0-rm-ext/1h_top20_kpi.json

# 3.2 실시간 모니터링 (별도 터미널)
# - Grafana: http://localhost:3000
# - Prometheus: http://localhost:9090
# - 로그: tail -f logs/d77-0-rm-ext/<latest>/console.log
```

### Step 4: 사후 분석
```powershell
# 4.1 KPI 파일 확인
cat logs/d77-0-rm-ext/1h_top20_kpi.json

# 4.2 Prometheus 스냅샷 확인 (D77-5)
ls logs/d77-0-rm-ext/<run_id>/prometheus_metrics.prom

# 4.3 로그 분석 (에러, 429, 스프레드 등)
Select-String -Path logs/d77-0-rm-ext/<run_id>/console.log -Pattern "ERROR|429|spread"
```

### Step 5: 리포트 작성
```bash
# Template 기반 수동 작성
# 파일: docs/D77_0_RM_EXT_REPORT.md
# 내용: 실행 결과, KPI, 스프레드 분석, 이슈/개선점
```

### Step 6: Extended Scenario (선택적)
```powershell
# Top50, 1시간 (환경 여유 시만)
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top50 \
  --duration-minutes 60 \
  --data-source real \
  --monitoring-enabled \
  --kpi-output-path logs/d77-0-rm-ext/1h_top50_kpi.json
```

### Step 7: D_ROADMAP 업데이트
```bash
# D77-0-RM-EXT 섹션에 상태 갱신:
# - Status: PLANNED → IMPLEMENTATION → VALIDATION → COMPLETE
# - 실행 결과 요약, 판단 (GO/CONDITIONAL GO/NO-GO)
```

---

## ✅ 7. Done Criteria

### Implementation Phase
- [x] ✅ 문서 작성 (Execution Plan, Report Template)
- [x] ✅ 실행 하네스/래퍼 스크립트 (기존 러너 재사용 확인)
- [x] ✅ 테스트 코드 (CLI 파싱, 옵션 전달, Dry-run)
- [x] ✅ 스모크 테스트 (3분) 성공

### Validation Phase
- [ ] ⏳ 1시간 본 실행 (Top20) 성공
- [ ] ⏳ KPI 10종 수집 완료
- [ ] ⏳ Prometheus 스냅샷 저장 (D77-5)
- [ ] ⏳ 장기 안정성 확인 (메모리/CPU 안정)
- [ ] ⏳ Rate Limit 핸들링 검증 (429 재시도)
- [ ] ⏳ 최종 리포트 작성

### Acceptance Criteria

**적용 범위:**
- **Top20 (Primary)** 및 **Top50 (Extended)** 각각 독립 평가
- 최종 판단: Top20 + Top50 결과를 종합

**Critical (필수) - 각 Universe별로 평가:**
- C1: 1h 연속 실행 (Crash = 0)
- C2: Round Trips ≥ 50 (실제 시장 조건)
- C3: Memory 증가율 ≤ 10%/h
- C4: CPU ≤ 70% (평균)
- C5: Prometheus 스냅샷 저장 성공

**High Priority (권장) - 각 Universe별로 평가:**
- H1: Loop Latency p99 ≤ 80ms
- H2: Win Rate 30~80% (실시간 시장)
- H3: Rate Limit 429 자동 복구 100%

**최종 판단 기준:**
- **GO**: Top20 + Top50 모두 Critical 5/5 충족
- **CONDITIONAL GO**: 둘 중 하나가 Critical 4/5 (어느 Universe에서 어떤 항목 미달인지 명시)
- **NO-GO**: 어느 Universe든 Critical < 4/5 (재검증 필요)

---

## 📌 Important Notes

1. **엔진 코드 변경 금지**: 모든 작업은 실행 레벨/문서에만 국한
2. **기존 인프라 재사용**: D77-4 오케스트레이터, D77-5 스냅샷, D76 알림 그대로 활용
3. **PnL 수치 해석 주의**: Real Market PAPER 결과는 "엔진 검증용"이며 실거래 수익 보장 아님
4. **Rate Limit 중요**: Upbit 429 에러는 예상된 동작, 재시도 로직 검증이 핵심
5. **스프레드 분석**: 실시간 시장의 스프레드 패턴은 Mock과 다름 → 별도 분석 필요

---

**작성자:** Windsurf AI  
**검토 필요:** 실행 전 환경 설정 재확인, Docker 스택 정상 동작 확인  
**참고 문서:** D77-4 Validation Execution Plan, D77-0-RM Report

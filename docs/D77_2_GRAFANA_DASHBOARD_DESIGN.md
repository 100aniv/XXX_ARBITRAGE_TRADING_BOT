# D77-2: Grafana Dashboard Suite Design Document

**Phase:** D77-2 (Monitoring Infrastructure)  
**Status:** ✅ COMPLETE  
**Date:** 2025-12-01  
**Author:** AI Assistant (Windsurf Cascade)

---

## 📋 목차

1. [개요](#개요)
2. [Dashboard 구성](#dashboard-구성)
3. [Panel 상세 설명](#panel-상세-설명)
4. [PromQL 쿼리 목록](#promql-쿼리-목록)
5. [System Architecture](#system-architecture)
6. [Dashboard → KPI Mapping](#dashboard--kpi-mapping)
7. [Operational Guidelines](#operational-guidelines)
8. [Setup Instructions](#setup-instructions)
9. [Troubleshooting](#troubleshooting)

---

## 📊 개요

### 목적
TopN Arbitrage PAPER Baseline 실행 환경에 대한 **실시간 모니터링 인프라** 제공.  
D77-1에서 구현한 Prometheus Exporter (11 metrics)를 Grafana 대시보드로 시각화.

### 범위
- **3개의 Grafana 대시보드** (21 panels 총)
- **Trading KPIs, System Health, Risk & Guard** 3개 도메인 분리
- Prometheus 데이터소스 연동
- Alert rules 포함 (High Latency, High CPU, Guard Triggers)

### Target Users
- **개발자:** 시스템 성능 및 안정성 모니터링
- **운영팀:** 실시간 트레이딩 KPI 및 리스크 관리
- **QA팀:** 테스트 결과 검증 및 이상 탐지

---

## 🎯 Dashboard 구성

### Dashboard 1: Trading KPIs (7 panels)
**목적:** 트레이딩 성과 지표 실시간 모니터링

| Panel # | Title | Type | Purpose |
|---------|-------|------|---------|
| 1 | Total PnL (USD) | Graph | 누적 PnL 타임라인 |
| 2 | Win Rate (%) | Gauge | 승률 게이지 (0-100%) |
| 3 | Round Trips Completed | Stat | 라운드 트립 총 횟수 |
| 4 | Trades Total (Entry vs Exit) | Graph | Entry/Exit 거래 rate 비교 |
| 5 | Exit Reasons Breakdown | Pie Chart | Exit 이유별 분포 |
| 6 | Active Positions | Stat | 현재 활성 포지션 수 |
| 7 | Trade Rate (1min rolling) | Graph | 1분 롤링 거래 rate |

**Key Features:**
- PnL 추세 파악 (증가/감소)
- 승률 threshold 모니터링 (50% 미만 시 yellow, 70% 이상 green)
- Entry/Exit 불균형 탐지
- Exit 이유 패턴 분석 (TP/SL/Time-based/Spread reversal)

---

### Dashboard 2: System Health & Performance (7 panels)
**목적:** 시스템 성능 및 안정성 모니터링

| Panel # | Title | Type | Purpose |
|---------|-------|------|---------|
| 1 | Loop Latency - Average | Graph | 평균 루프 레이턴시 (ms) |
| 2 | Loop Latency - p99 | Graph | p99 루프 레이턴시 (ms) |
| 3 | CPU Usage (%) | Graph | CPU 사용률 타임라인 |
| 4 | Memory Usage (MB) | Graph | 메모리 사용량 타임라인 |
| 5 | Iteration Rate (iter/s) | Stat | 초당 iteration 수 |
| 6 | Total Iterations | Stat | 누적 iteration 수 |
| 7 | System Status | Stat | 시스템 UP/DOWN 상태 |

**Key Features:**
- Loop latency alert (avg > 50ms, p99 > 80ms)
- CPU usage alert (> 80%)
- 메모리 누수 탐지 (증가 추세)
- Iteration rate 저하 탐지 (< 5 iter/s)

---

### Dashboard 3: Risk & Guard Monitoring (7 panels)
**목적:** 리스크 관리 및 Guard 트리거 모니터링

| Panel # | Title | Type | Purpose |
|---------|-------|------|---------|
| 1 | Guard Triggers Timeline | Graph | Guard 트리거 rate 타임라인 |
| 2 | Alerts by Severity | Graph | Severity별 alert rate |
| 3 | Active Positions (Risk Exposure) | Gauge | 활성 포지션 수 (리스크 노출) |
| 4 | Total Alerts (All Severities) | Stat | 전체 alert 총 횟수 |
| 5 | Guard Trigger Types | Pie Chart | Guard 타입별 분포 |
| 6 | Total Guard Triggers | Stat | Guard 트리거 총 횟수 |
| 7 | Risk Status Overview | Table | 종합 리스크 상태 (Universe별) |

**Key Features:**
- Guard trigger alert (> 10/min)
- Active position threshold (> 10: warning, > 20: critical)
- Alert severity 분포 (P0/P1/P2/P3)
- Guard type 분석 (exchange/route/symbol/global)

---

## 📜 Panel 상세 설명

### Dashboard 1: Trading KPIs

#### Panel 1: Total PnL (USD)
**Type:** Graph  
**Metric:** `arb_topn_pnl_total{env="paper"}`  
**Description:** 누적 PnL을 시간에 따라 표시. Universe별로 legend 분리.  
**Alert:** None (정보성)  
**Format:** USD currency

**Screenshot Placeholder:**
```
[Graph: PnL increasing from $0 to $3,375 over 1 minute]
```

---

#### Panel 2: Win Rate (%)
**Type:** Gauge  
**Metric:** `arb_topn_win_rate{env="paper"}`  
**Description:** 승률 게이지 (0-100%). Threshold: < 50% red, 50-70% yellow, >= 70% green.  
**Alert:** None (시각적 feedback)  
**Format:** Percentage

**Screenshot Placeholder:**
```
[Gauge: 100% (green)]
```

---

#### Panel 3: Round Trips Completed
**Type:** Stat  
**Metric:** `arb_topn_round_trips_total{env="paper"}`  
**Description:** 완료된 라운드 트립 총 횟수. 증가 추세 그래프 포함.  
**Alert:** None  
**Format:** Short (integer)

**Screenshot Placeholder:**
```
[Stat: 27 Round Trips]
```

---

#### Panel 4: Trades Total (Entry vs Exit)
**Type:** Graph  
**Metrics:**  
- `rate(arb_topn_trades_total{env="paper",trade_type="entry"}[1m])`
- `rate(arb_topn_trades_total{env="paper",trade_type="exit"}[1m])`

**Description:** Entry와 Exit 거래의 rate를 비교. 불균형 시 문제 탐지.  
**Alert:** None (시각적 비교)  
**Format:** Trades/sec

**Screenshot Placeholder:**
```
[Graph: Two lines (Entry/Exit) overlapping, both ~0.45 trades/sec]
```

---

#### Panel 5: Exit Reasons Breakdown
**Type:** Pie Chart  
**Metric:** `arb_topn_exit_reasons_total{env="paper"}`  
**Description:** Exit 이유별 분포 (take_profit, stop_loss, time_limit, spread_reversal).  
**Alert:** None  
**Format:** Percentage

**Screenshot Placeholder:**
```
[Pie Chart: 100% Take Profit (green)]
```

---

#### Panel 6: Active Positions
**Type:** Stat  
**Metric:** `arb_topn_active_positions{env="paper"}`  
**Description:** 현재 활성 포지션 수. Threshold: 0-5 green, 5-10 yellow, > 10 red.  
**Alert:** None  
**Format:** Short (integer)

**Screenshot Placeholder:**
```
[Stat: 0 Active Positions (green)]
```

---

#### Panel 7: Trade Rate (1min rolling)
**Type:** Graph  
**Metric:** `rate(arb_topn_trades_total{env="paper"}[1m]) * 60`  
**Description:** 1분 롤링 윈도우로 거래 rate 계산 (trades/min).  
**Alert:** None  
**Format:** Trades/min

**Screenshot Placeholder:**
```
[Graph: Spikes at trade events, ~27 trades/min average]
```

---

### Dashboard 2: System Health & Performance

#### Panel 1: Loop Latency - Average
**Type:** Graph  
**Metric:** `rate(arb_topn_loop_latency_seconds_sum{env="paper"}[1m]) / rate(arb_topn_loop_latency_seconds_count{env="paper"}[1m]) * 1000`  
**Description:** 평균 루프 레이턴시 (ms). 1분 rate 기반 계산.  
**Alert:** avg > 50ms for 5min  
**Format:** Milliseconds

**Screenshot Placeholder:**
```
[Graph: Flat line at ~0.05ms]
```

---

#### Panel 2: Loop Latency - p99
**Type:** Graph  
**Metric:** `histogram_quantile(0.99, rate(arb_topn_loop_latency_seconds_bucket{env="paper"}[1m])) * 1000`  
**Description:** p99 루프 레이턴시 (ms). Histogram quantile 계산.  
**Alert:** None (monitoring only)  
**Format:** Milliseconds

**Screenshot Placeholder:**
```
[Graph: Flat line at ~0.1ms]
```

---

#### Panel 3: CPU Usage (%)
**Type:** Graph  
**Metric:** `arb_topn_cpu_usage_percent{env="paper"}`  
**Description:** CPU 사용률 타임라인. Fill 2 (면적 그래프).  
**Alert:** avg > 80% for 5min  
**Format:** Percentage (0-100)

**Screenshot Placeholder:**
```
[Graph: Fluctuating around 35% (yellow)]
```

---

#### Panel 4: Memory Usage (MB)
**Type:** Graph  
**Metric:** `arb_topn_memory_usage_bytes{env="paper"} / 1024 / 1024`  
**Description:** 메모리 사용량 (MB). Fill 2 (면적 그래프).  
**Alert:** None (메모리 누수 시각적 탐지)  
**Format:** Megabytes

**Screenshot Placeholder:**
```
[Graph: Stable at ~150MB]
```

---

#### Panel 5: Iteration Rate (iter/s)
**Type:** Stat  
**Metric:** `rate(arb_topn_loop_latency_seconds_count{env="paper"}[1m])`  
**Description:** 초당 iteration 수. Threshold: < 5 red, 5-10 yellow, >= 10 green.  
**Alert:** None  
**Format:** Operations per second

**Screenshot Placeholder:**
```
[Stat: 10.2 iter/s (green)]
```

---

#### Panel 6: Total Iterations
**Type:** Stat  
**Metric:** `arb_topn_loop_latency_seconds_count{env="paper"}`  
**Description:** 누적 iteration 수.  
**Alert:** None  
**Format:** Short (integer)

**Screenshot Placeholder:**
```
[Stat: 545 iterations]
```

---

#### Panel 7: System Status
**Type:** Stat  
**Metric:** `up{job="arb_topn_paper"}`  
**Description:** 시스템 UP/DOWN 상태. Mapping: 0 = DOWN (red), 1 = UP (green).  
**Alert:** None (immediate visual feedback)  
**Format:** Text

**Screenshot Placeholder:**
```
[Stat: UP (green)]
```

---

### Dashboard 3: Risk & Guard Monitoring

#### Panel 1: Guard Triggers Timeline
**Type:** Graph  
**Metric:** `rate(arb_topn_guard_triggers_total{env="paper"}[1m]) * 60`  
**Description:** Guard 트리거 rate (triggers/min). Guard type별 stacked graph.  
**Alert:** avg > 10/min for 5min  
**Format:** Triggers/min

**Screenshot Placeholder:**
```
[Graph: Stacked area (exchange/route/symbol/global)]
```

---

#### Panel 2: Alerts by Severity
**Type:** Graph  
**Metric:** `rate(arb_topn_alerts_total{env="paper"}[1m]) * 60`  
**Description:** Alert rate (alerts/min). Severity와 source별 legend.  
**Alert:** None  
**Format:** Alerts/min

**Screenshot Placeholder:**
```
[Graph: Multiple lines (P0/P1/P2/P3 by source)]
```

---

#### Panel 3: Active Positions (Risk Exposure)
**Type:** Gauge  
**Metric:** `arb_topn_active_positions{env="paper"}`  
**Description:** 활성 포지션 수 (리스크 노출 지표). Threshold: 0-5 green, 5-10 yellow, 10-20 orange, > 20 red.  
**Alert:** None  
**Format:** Short (0-50 range)

**Screenshot Placeholder:**
```
[Gauge: 0 (green)]
```

---

#### Panel 4: Total Alerts (All Severities)
**Type:** Stat  
**Metric:** `sum(arb_topn_alerts_total{env="paper"})`  
**Description:** 전체 alert 총 횟수. Threshold: < 10 green, 10-50 yellow, > 50 red.  
**Alert:** None  
**Format:** Short (integer)

**Screenshot Placeholder:**
```
[Stat: 0 Alerts (green)]
```

---

#### Panel 5: Guard Trigger Types
**Type:** Pie Chart (Donut)  
**Metric:** `arb_topn_guard_triggers_total{env="paper"}`  
**Description:** Guard type별 분포 (exchange/route/symbol/global).  
**Alert:** None  
**Format:** Percentage + Name

**Screenshot Placeholder:**
```
[Donut Chart: 4 segments (exchange 40%, route 30%, symbol 20%, global 10%)]
```

---

#### Panel 6: Total Guard Triggers
**Type:** Stat  
**Metric:** `sum(arb_topn_guard_triggers_total{env="paper"})`  
**Description:** Guard 트리거 총 횟수. Threshold: < 100 green, 100-500 yellow, > 500 red.  
**Alert:** None  
**Format:** Short (integer)

**Screenshot Placeholder:**
```
[Stat: 0 Guard Triggers (green)]
```

---

#### Panel 7: Risk Status Overview
**Type:** Table  
**Metrics:**  
- `arb_topn_active_positions{env="paper"}` (Active Positions)
- `arb_topn_pnl_total{env="paper"}` (Total PnL)
- `arb_topn_win_rate{env="paper"}` (Win Rate)
- `sum by (universe) (arb_topn_guard_triggers_total{env="paper"})` (Guard Triggers)

**Description:** Universe별 종합 리스크 상태 테이블.  
**Alert:** None  
**Format:** Table with color-coded cells

**Screenshot Placeholder:**
```
[Table:
| Universe | Active Positions | Total PnL | Win Rate (%) | Guard Triggers |
|----------|------------------|-----------|--------------|----------------|
| top_20   | 0 (green)        | $3,375    | 100% (green) | 0              |
]
```

---

## 🔍 PromQL 쿼리 목록

### Trading KPIs
```promql
# Panel 1: Total PnL
arb_topn_pnl_total{env="paper"}

# Panel 2: Win Rate
arb_topn_win_rate{env="paper"}

# Panel 3: Round Trips
arb_topn_round_trips_total{env="paper"}

# Panel 4: Entry Rate
rate(arb_topn_trades_total{env="paper",trade_type="entry"}[1m])

# Panel 4: Exit Rate
rate(arb_topn_trades_total{env="paper",trade_type="exit"}[1m])

# Panel 5: Exit Reasons
arb_topn_exit_reasons_total{env="paper"}

# Panel 6: Active Positions
arb_topn_active_positions{env="paper"}

# Panel 7: Trade Rate
rate(arb_topn_trades_total{env="paper"}[1m]) * 60
```

### System Health & Performance
```promql
# Panel 1: Loop Latency Average
rate(arb_topn_loop_latency_seconds_sum{env="paper"}[1m]) / rate(arb_topn_loop_latency_seconds_count{env="paper"}[1m]) * 1000

# Panel 2: Loop Latency p99
histogram_quantile(0.99, rate(arb_topn_loop_latency_seconds_bucket{env="paper"}[1m])) * 1000

# Panel 3: CPU Usage
arb_topn_cpu_usage_percent{env="paper"}

# Panel 4: Memory Usage
arb_topn_memory_usage_bytes{env="paper"} / 1024 / 1024

# Panel 5: Iteration Rate
rate(arb_topn_loop_latency_seconds_count{env="paper"}[1m])

# Panel 6: Total Iterations
arb_topn_loop_latency_seconds_count{env="paper"}

# Panel 7: System Status
up{job="arb_topn_paper"}
```

### Risk & Guard Monitoring
```promql
# Panel 1: Guard Triggers Rate
rate(arb_topn_guard_triggers_total{env="paper"}[1m]) * 60

# Panel 2: Alerts Rate
rate(arb_topn_alerts_total{env="paper"}[1m]) * 60

# Panel 3: Active Positions
arb_topn_active_positions{env="paper"}

# Panel 4: Total Alerts
sum(arb_topn_alerts_total{env="paper"})

# Panel 5: Guard Trigger Types
arb_topn_guard_triggers_total{env="paper"}

# Panel 6: Total Guard Triggers
sum(arb_topn_guard_triggers_total{env="paper"})

# Panel 7 (Table): Multiple queries merged
arb_topn_active_positions{env="paper"}
arb_topn_pnl_total{env="paper"}
arb_topn_win_rate{env="paper"}
sum by (universe) (arb_topn_guard_triggers_total{env="paper"})
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   D77 Monitoring Stack                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  TopN PAPER      │       │   Prometheus     │       │    Grafana       │
│  Runner          │──────▶│   Server         │──────▶│   Dashboards     │
│                  │ HTTP  │   (Port 9090)    │ Query │   (Port 3000)    │
│  (Metrics Port   │       │                  │       │                  │
│   9100)          │       │  - Scrape every  │       │  - Dashboard 1:  │
│                  │       │    5 seconds     │       │    Trading KPIs  │
│  - 11 metrics    │       │  - Retention:    │       │  - Dashboard 2:  │
│  - Summary       │       │    15 days       │       │    System Health │
│  - Counter       │       │  - Storage:      │       │  - Dashboard 3:  │
│  - Gauge         │       │    Local disk    │       │    Risk & Guard  │
└──────────────────┘       └──────────────────┘       └──────────────────┘
         │                          │                          │
         │                          │                          │
         └──────────────────────────┴──────────────────────────┘
                        Monitoring Flow
                        (Pull-based scraping)
```

### Data Flow
1. **TopN PAPER Runner:** 메트릭 생성 및 `/metrics` 엔드포인트 노출 (port 9100)
2. **Prometheus Server:** 5초마다 metrics scraping (prometheus.yml 설정)
3. **Grafana Dashboards:** PromQL 쿼리로 Prometheus에서 데이터 가져와 시각화
4. **Alerts:** Grafana built-in alerting (High Latency, High CPU, Guard Triggers)

---

## 🎯 Dashboard → KPI Mapping

### Core KPI 10종 (D99 Done Criteria)

| # | KPI Name | Dashboard | Panel | Metric |
|---|----------|-----------|-------|--------|
| 1 | Total PnL | Trading KPIs | Panel 1 | `arb_topn_pnl_total` |
| 2 | Win Rate | Trading KPIs | Panel 2 | `arb_topn_win_rate` |
| 3 | Trades per Hour | Trading KPIs | Panel 7 | `rate(arb_topn_trades_total[1m]) * 60` |
| 4 | Loop Latency (avg) | System Health | Panel 1 | `rate(arb_topn_loop_latency_seconds_sum[1m]) / rate(...count[1m])` |
| 5 | Loop Latency (p99) | System Health | Panel 2 | `histogram_quantile(0.99, ...)` |
| 6 | CPU Usage | System Health | Panel 3 | `arb_topn_cpu_usage_percent` |
| 7 | Memory Usage | System Health | Panel 4 | `arb_topn_memory_usage_bytes / 1024 / 1024` |
| 8 | Open Positions Count | Risk & Guard | Panel 3 | `arb_topn_active_positions` |
| 9 | Guard Triggers per Hour | Risk & Guard | Panel 1 | `rate(arb_topn_guard_triggers_total[1m]) * 60` |
| 10 | Round Trips | Trading KPIs | Panel 3 | `arb_topn_round_trips_total` |

**Result:** ✅ **10/10 Core KPIs 모두 대시보드에 노출**

---

## 📖 Operational Guidelines

### 일일 모니터링 체크리스트

#### Trading KPIs (Dashboard 1)
- [ ] **PnL 추세:** 증가 중인가? (목표: 긍정적 slope)
- [ ] **Win Rate:** >= 50%? (목표: >= 70%)
- [ ] **Round Trips:** 정상 증가 중? (목표: > 5 round trips/hour)
- [ ] **Entry/Exit 균형:** Entry rate ≈ Exit rate? (불균형 시 조사 필요)
- [ ] **Exit Reasons:** Take Profit 비율? (목표: >= 70%)
- [ ] **Active Positions:** < 10? (리스크 노출 제한)

#### System Health (Dashboard 2)
- [ ] **Loop Latency avg:** < 50ms? (목표: < 25ms)
- [ ] **Loop Latency p99:** < 80ms? (목표: < 40ms)
- [ ] **CPU Usage:** < 80%? (목표: < 60%)
- [ ] **Memory Usage:** 안정적? (누수 없음, drift < 5%)
- [ ] **Iteration Rate:** >= 10 iter/s? (목표: >= 40 iter/s)
- [ ] **System Status:** UP?

#### Risk & Guard (Dashboard 3)
- [ ] **Guard Triggers:** < 10/min? (목표: 0/min)
- [ ] **Alerts:** P0/P1 없음? (P2/P3 허용)
- [ ] **Active Positions:** < 5? (yellow), < 10? (orange)
- [ ] **Guard Type 분포:** 고르게 분산? (특정 타입 과다 발생 시 조사)

---

### Alert Response Procedures

#### Alert 1: High Loop Latency (avg > 50ms for 5min)
**Severity:** P1 (Warning)  
**Action:**
1. System Health Dashboard → Panel 1/2 확인
2. CPU/Memory usage 체크 (병목 가능성)
3. Iteration rate 확인 (< 5 iter/s 시 긴급)
4. 로그 파일 검토 (`logs/d77-0/`)
5. 필요 시 프로세스 재시작

#### Alert 2: High CPU Usage (> 80% for 5min)
**Severity:** P2 (Caution)  
**Action:**
1. System Health Dashboard → Panel 3 확인
2. Memory usage 동시 체크 (메모리 부족 가능성)
3. Iteration rate 확인 (성능 저하 여부)
4. 프로세스 리소스 제한 검토
5. Universe 크기 축소 고려 (top50 → top20)

#### Alert 3: Guard Triggers High (> 10/min for 5min)
**Severity:** P1 (Warning)  
**Action:**
1. Risk & Guard Dashboard → Panel 1/5 확인
2. Guard type 분석 (어느 guard가 주로 발생?)
3. Active positions 확인 (과도한 노출?)
4. 로그 파일에서 guard trigger 상세 확인
5. Risk 파라미터 조정 고려 (threshold 완화/강화)

---

## 🛠️ Setup Instructions

### Prerequisites
- ✅ D77-1 완료 (Prometheus Exporter 구현)
- ✅ Prometheus 서버 설치 (v2.40+)
- ✅ Grafana 서버 설치 (v9.0+)
- ✅ TopN PAPER Runner 실행 가능

### Step 1: Prometheus 설정
```bash
# Prometheus 설정 파일 복사
cp monitoring/prometheus/prometheus.yml.sample monitoring/prometheus/prometheus.yml

# Prometheus 실행
cd <prometheus_dir>
./prometheus --config.file=<project_root>/monitoring/prometheus/prometheus.yml
```

**Verify:**
- Prometheus UI: http://localhost:9090
- Targets 페이지에서 `arb_topn_paper` job status 확인 (UP)

### Step 2: TopN PAPER Runner 실행 (Monitoring 활성화)
```bash
python -m scripts.run_d77_0_topn_arbitrage_paper \
  --universe top20 \
  --duration-minutes 60 \
  --monitoring-enabled \
  --monitoring-port 9100
```

**Verify:**
- Metrics endpoint: http://localhost:9100/metrics
- Prometheus Targets 페이지에서 UP 확인

### Step 3: Grafana 설정
```bash
# Grafana 실행
cd <grafana_dir>
./bin/grafana-server
```

**Grafana UI:** http://localhost:3000 (admin/admin)

#### 3.1 Data Source 추가
1. Configuration → Data Sources → Add data source
2. Select: Prometheus
3. URL: `http://localhost:9090`
4. Save & Test

#### 3.2 Dashboard Import
1. Dashboards → Import
2. Upload JSON file:
   - `monitoring/grafana/dashboards/d77_topn_trading_kpis.json`
   - `monitoring/grafana/dashboards/d77_system_health.json`
   - `monitoring/grafana/dashboards/d77_risk_guard.json`
3. Select Data Source: Prometheus
4. Import

### Step 4: Dashboard 확인
- Dashboard 1: http://localhost:3000/d/d77-topn-trading-kpis
- Dashboard 2: http://localhost:3000/d/d77-system-health
- Dashboard 3: http://localhost:3000/d/d77-risk-guard

**Expected Result:**
- 모든 패널 데이터 정상 표시
- No "No Data" errors
- Alert rules 정상 로드

---

## 🐛 Troubleshooting

### Issue 1: Panel shows "No Data"
**Symptom:** Grafana 패널에 "No Data" 표시

**Root Causes:**
1. TopN PAPER Runner가 실행 중이 아님
2. Prometheus가 metrics를 scraping하지 못함
3. PromQL 쿼리 오류

**Solutions:**
1. TopN PAPER Runner 실행 확인:
   ```bash
   curl http://localhost:9100/metrics
   ```
2. Prometheus Targets 확인:
   - http://localhost:9090/targets
   - `arb_topn_paper` job이 UP인지 확인
3. PromQL 쿼리 테스트:
   - Prometheus UI → Graph 탭에서 쿼리 직접 실행
   - 오류 메시지 확인

### Issue 2: Alert not firing
**Symptom:** Alert 조건 충족되었지만 alert이 발생하지 않음

**Root Causes:**
1. Grafana alerting이 활성화되지 않음
2. Alert rule 설정 오류
3. Notification channel 미설정

**Solutions:**
1. Grafana alerting 활성화:
   - `grafana.ini` → `[alerting]` → `enabled = true`
2. Alert rule 재확인:
   - Dashboard → Panel → Edit → Alert 탭
   - Condition threshold 확인
3. Notification channel 설정:
   - Alerting → Notification channels → Add channel
   - Telegram/Slack 연동 (D76 통합)

### Issue 3: High query load (Prometheus)
**Symptom:** Prometheus 쿼리가 느리거나 타임아웃

**Root Causes:**
1. Retention period가 너무 길음
2. 많은 시계열 데이터 (high cardinality)
3. 리소스 부족 (CPU/Memory)

**Solutions:**
1. Retention 축소:
   - `prometheus.yml` → `--storage.tsdb.retention.time=15d`
2. Label 정리:
   - 불필요한 label 제거 (고유성 감소)
3. Prometheus 리소스 증설:
   - Memory: 최소 4GB
   - CPU: 2 cores

---

## 📚 References

### External Documentation
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Prometheus Query Functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)

### Internal Documentation
- [D77-1: Prometheus Exporter Design](./D77_1_PROMETHEUS_EXPORTER_DESIGN.md)
- [D77-0: TopN Arbitrage PAPER Report](./D77_0_TOPN_ARBITRAGE_PAPER_REPORT.md)
- [D76: Alert Rule Engine Design](./D76_ALERT_RULE_ENGINE_DESIGN.md)

---

## 📝 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-01 | AI Assistant | Initial design document |

---

**End of Document**

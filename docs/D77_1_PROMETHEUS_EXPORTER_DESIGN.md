# D77-1: Prometheus Exporter Design Document

**Phase:** D77-1 Prometheus Exporter Implementation  
**Status:** ✅ DESIGN COMPLETE  
**작성일:** 2025-12-01  
**Target:** TopN Arbitrage PAPER Baseline 모니터링 인프라 구축

---

## 1. Executive Summary

### 1.1. 목표
- D77-0에서 검증된 TopN Arbitrage PAPER Baseline의 **Core KPI 10종**을 Prometheus 메트릭으로 노출
- `/metrics` 엔드포인트를 통해 실시간 스크래핑 가능한 인프라 구축
- D77-0-RM(Real Market Validation) 및 D77-2(Grafana Dashboard) 단계를 위한 관측 파이프라인 확립

### 1.2. Scope
**In Scope:**
- Prometheus Exporter 모듈 (`arbitrage/monitoring/metrics.py`)
- Core KPI 10종 → Prometheus 메트릭 맵핑
- TopN PAPER Runner에 메트릭 Hook 통합
- HTTP 서버 (`/metrics` endpoint)
- Prometheus `prometheus.yml` 샘플 설정
- Unit Tests + 5분 Mock PAPER 통합 테스트

**Out of Scope:**
- Grafana Dashboard 생성 (D77-2)
- Alertmanager 통합 (D77-3)
- 1h/12h 실제 시장 검증 (D77-0-RM)
- 복잡한 메트릭 aggregation 로직

---

## 2. Core KPI 10종 → Prometheus Metrics 맵핑

### 2.1. KPI List (from D77-0 Report)

| # | KPI Name | D77-0 Key | Type | Description |
|---|----------|-----------|------|-------------|
| 1 | Total PnL | `total_pnl_usd` | Gauge | 누적 손익 (USD) |
| 2 | Win Rate | `win_rate_pct` | Gauge | 승률 (%) |
| 3 | Round Trips | `round_trips_completed` | Counter | 완료된 라운드 트립 수 |
| 4 | Loop Latency (avg) | `loop_latency_avg_ms` | Gauge | 평균 루프 레이턴시 (ms) |
| 5 | Loop Latency (p99) | `loop_latency_p99_ms` | Gauge | P99 루프 레이턴시 (ms) |
| 6 | Memory Usage | `memory_usage_mb` | Gauge | 메모리 사용량 (MB) |
| 7 | CPU Usage | `cpu_usage_pct` | Gauge | CPU 사용률 (%) |
| 8 | Guard Triggers | `guard_triggers` | Counter | RiskGuard 트리거 총 횟수 |
| 9 | Alert Count (P0) | `alert_count.P0` | Counter | P0 알림 총 횟수 |
| 10 | Alert Count (P1-P3) | `alert_count.P1/P2/P3` | Counter | P1~P3 알림 총 횟수 |

### 2.2. Prometheus Metric Design

**Namespace:** `arb_topn_`

| Prometheus Metric Name | Type | Labels | Description |
|------------------------|------|--------|-------------|
| `arb_topn_pnl_total` | Gauge | `env`, `universe`, `strategy` | 누적 PnL (USD) |
| `arb_topn_win_rate` | Gauge | `env`, `universe`, `strategy` | 승률 (0.0 ~ 100.0) |
| `arb_topn_round_trips_total` | Counter | `env`, `universe`, `strategy` | 라운드 트립 총 횟수 |
| `arb_topn_trades_total` | Counter | `env`, `universe`, `strategy`, `trade_type` | 거래 총 횟수 (`entry`, `exit`) |
| `arb_topn_loop_latency_seconds` | Summary | `env`, `universe`, `strategy` | 루프 레이턴시 (초 단위, quantiles: 0.5, 0.9, 0.99) |
| `arb_topn_memory_usage_bytes` | Gauge | `env`, `universe`, `strategy` | 메모리 사용량 (bytes) |
| `arb_topn_cpu_usage_percent` | Gauge | `env`, `universe`, `strategy` | CPU 사용률 (%) |
| `arb_topn_guard_triggers_total` | Counter | `env`, `universe`, `strategy`, `guard_type` | Guard 트리거 총 횟수 |
| `arb_topn_alerts_total` | Counter | `env`, `universe`, `strategy`, `severity`, `source` | 알림 총 횟수 |
| `arb_topn_exit_reasons_total` | Counter | `env`, `universe`, `strategy`, `reason` | Exit 이유별 총 횟수 (`take_profit`, `stop_loss`, `time_limit`, `spread_reversal`) |
| `arb_topn_active_positions` | Gauge | `env`, `universe`, `strategy` | 현재 활성 포지션 수 |

**Total:** 11 Metrics (Core KPI 10종 + 추가 메트릭 1종)

### 2.3. Label Schema

**공통 Label:**
- `env`: 환경 (`paper`, `live`, `test`)
- `universe`: 유니버스 모드 (`top20`, `top50`, `custom`)
- `strategy`: 전략 이름 (`topn_arb` 고정, 확장 고려)

**메트릭별 추가 Label:**
- `trade_type`: 거래 타입 (`entry`, `exit`) - `arb_topn_trades_total`
- `guard_type`: Guard 타입 (`exchange`, `route`, `symbol`, `global`) - `arb_topn_guard_triggers_total`
- `severity`: 알림 심각도 (`P0`, `P1`, `P2`, `P3`) - `arb_topn_alerts_total`
- `source`: 알림 소스 (예: `rate_limiter`, `health_monitor`) - `arb_topn_alerts_total`
- `reason`: Exit 이유 (`take_profit`, `stop_loss`, `time_limit`, `spread_reversal`) - `arb_topn_exit_reasons_total`

---

## 3. Exporter Architecture

### 3.1. Module Structure

```
arbitrage/monitoring/
├── __init__.py
└── metrics.py          # Prometheus Exporter 핵심 모듈
```

### 3.2. metrics.py Design

#### 3.2.1. Imports
```python
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Summary,
    start_http_server,
    generate_latest,
)
from typing import Dict, Optional
import logging
```

#### 3.2.2. Global State
```python
# 전역 레지스트리 (테스트 시 교체 가능)
_registry: Optional[CollectorRegistry] = None

# 메트릭 객체 캐시
_metrics: Dict[str, any] = {}

# HTTP 서버 상태
_http_server_started: bool = False

# 공통 Label 값
_common_labels: Dict[str, str] = {}
```

#### 3.2.3. Core Functions

**1. `init_metrics(env: str, universe: str, strategy: str, registry: Optional[CollectorRegistry] = None) -> None`**
- 메트릭 객체 초기화
- 공통 Label 셋 설정
- Registry 등록
- 중복 호출 시 재초기화 (idempotent)

**2. `start_metrics_server(port: int) -> None`**
- Prometheus HTTP 서버 시작 (`/metrics` endpoint)
- 기본 포트: 9100
- 중복 호출 시 무시 (이미 시작된 경우)

**3. KPI 업데이트 함수**
- `record_pnl(delta: float) -> None`: PnL 업데이트 (Gauge)
- `record_trade(trade_type: str) -> None`: 거래 기록 (Counter, `entry` or `exit`)
- `record_round_trip() -> None`: 라운드 트립 완료 (Counter)
- `record_win_rate(wins: int, losses: int) -> None`: 승률 계산 및 업데이트 (Gauge)
- `record_loop_latency(seconds: float) -> None`: 루프 레이턴시 (Summary)
- `record_memory_usage(bytes: float) -> None`: 메모리 사용량 (Gauge)
- `record_cpu_usage(percent: float) -> None`: CPU 사용률 (Gauge)
- `record_guard_trigger(guard_type: str) -> None`: Guard 트리거 (Counter)
- `record_alert(severity: str, source: str) -> None`: 알림 (Counter)
- `record_exit_reason(reason: str) -> None`: Exit 이유 (Counter)
- `set_active_positions(count: int) -> None`: 활성 포지션 수 (Gauge)

**4. Utility Functions**
- `get_metrics_text() -> str`: `/metrics` 텍스트 반환 (테스트용)
- `reset_metrics() -> None`: 메트릭 초기화 (테스트용)

### 3.3. Threading & Safety
- Prometheus client는 기본적으로 thread-safe
- 동시 호출을 위한 추가 락 불필요
- HTTP 서버는 별도 스레드에서 실행 (`start_http_server` 내부)

---

## 4. Integration with TopN PAPER Runner

### 4.1. Config Extension

`configs/paper/topn_arb_baseline.yaml`에 추가:

```yaml
monitoring:
  enabled: true
  port: 9100
  # 추가 설정 (향후 확장)
  scrape_interval_seconds: 5
  export_interval_seconds: 1
```

### 4.2. Runner Modification Points

**File:** `scripts/run_d77_0_topn_arbitrage_paper.py`

**Hook Points:**

1. **Initialization (before loop):**
```python
from arbitrage.monitoring.metrics import init_metrics, start_metrics_server

if config.monitoring.enabled:
    init_metrics(
        env="paper",
        universe=universe_mode.name.lower(),
        strategy="topn_arb",
    )
    start_metrics_server(port=config.monitoring.port)
    logger.info(f"[D77-1] Metrics server started on port {config.monitoring.port}")
```

2. **Trade Recording (inside loop):**
```python
from arbitrage.monitoring.metrics import record_trade, record_round_trip, record_pnl

# Entry trade
if entry_condition:
    record_trade("entry")
    self.metrics["entry_trades"] += 1

# Exit trade
if exit_condition:
    record_trade("exit")
    record_round_trip()
    record_pnl(pnl_delta)
    self.metrics["exit_trades"] += 1
```

3. **Loop Latency (every iteration):**
```python
from arbitrage.monitoring.metrics import record_loop_latency

loop_latency_seconds = (time.time() - loop_start)
record_loop_latency(loop_latency_seconds)
```

4. **Periodic Updates (every 10s):**
```python
from arbitrage.monitoring.metrics import (
    record_win_rate,
    record_memory_usage,
    record_cpu_usage,
    set_active_positions,
)

if iteration % 100 == 0:  # ~10초마다
    record_win_rate(self.metrics["wins"], self.metrics["losses"])
    record_memory_usage(psutil.Process().memory_info().rss)  # bytes
    record_cpu_usage(psutil.Process().cpu_percent())
    set_active_positions(len(self.exit_strategy.positions))
```

5. **Guard/Alert (when triggered):**
```python
from arbitrage.monitoring.metrics import record_guard_trigger, record_alert

# Guard
if guard_triggered:
    record_guard_trigger("exchange")  # or "route", "symbol", "global"

# Alert
if alert_fired:
    record_alert("P1", "rate_limiter")
```

### 4.3. Minimal Code Pollution
- 모든 `record_*()` 호출은 one-liner로 side-effect만 수행
- 코어 로직 변경 없이 관측 가능
- `if config.monitoring.enabled` 조건으로 선택적 활성화

---

## 5. Prometheus Configuration

### 5.1. Sample prometheus.yml

**File:** `monitoring/prometheus/prometheus.yml.sample`

```yaml
# Prometheus Configuration for TopN Arbitrage PAPER Monitoring

global:
  scrape_interval: 5s      # 5초마다 스크래핑
  evaluation_interval: 5s  # Rule 평가 주기
  
  # 외부 Label (선택사항, Alertmanager/Grafana 연동 시 유용)
  external_labels:
    environment: 'paper'
    cluster: 'arbitrage-lite'
    project: 'd77-topn-arb'

scrape_configs:
  # Job 1: TopN Arbitrage PAPER Runner
  - job_name: 'arb_topn_paper'
    static_configs:
      - targets: ['localhost:9100']  # Windows localhost
        labels:
          service: 'topn_paper_runner'
          
    # 타임아웃 설정
    scrape_timeout: 3s
    
    # Relabeling (선택사항)
    # relabel_configs:
    #   - source_labels: [__address__]
    #     target_label: instance
    #     replacement: 'topn-paper-primary'

# 향후 확장: AlertManager 연동 (D77-3)
# alerting:
#   alertmanagers:
#     - static_configs:
#         - targets: ['localhost:9093']

# 향후 확장: Recording Rules (집계 메트릭)
# rule_files:
#   - "rules/*.yml"
```

### 5.2. Running Prometheus (Reference)

```powershell
# Prometheus 다운로드 및 실행 (Windows 기준)
# https://prometheus.io/download/

# 1. prometheus.yml 복사
cp monitoring/prometheus/prometheus.yml.sample monitoring/prometheus/prometheus.yml

# 2. Prometheus 실행
.\prometheus.exe --config.file=monitoring\prometheus\prometheus.yml

# 3. UI 접속
# http://localhost:9090
```

---

## 6. Testing Strategy

### 6.1. Unit Tests

**File:** `tests/test_d77_1_metrics.py`

**Test Cases:**
1. `test_init_metrics()`: 메트릭 초기화 검증
2. `test_record_pnl()`: PnL 업데이트 검증
3. `test_record_trades()`: Entry/Exit 거래 카운터 검증
4. `test_record_round_trip()`: 라운드 트립 카운터 검증
5. `test_record_win_rate()`: 승률 계산 검증
6. `test_record_loop_latency()`: Summary 메트릭 검증
7. `test_record_guard_trigger()`: Guard 트리거 라벨 검증
8. `test_record_alert()`: Alert 카운터 + 라벨 검증
9. `test_metrics_text_output()`: `/metrics` 텍스트 포맷 검증
10. `test_reset_metrics()`: 메트릭 리셋 검증

**검증 방법:**
```python
from arbitrage.monitoring.metrics import init_metrics, record_pnl, get_metrics_text
from prometheus_client import CollectorRegistry

def test_record_pnl():
    registry = CollectorRegistry()
    init_metrics("paper", "top20", "topn_arb", registry=registry)
    
    record_pnl(100.0)
    record_pnl(50.0)
    
    text = get_metrics_text()
    assert 'arb_topn_pnl_total{env="paper",strategy="topn_arb",universe="top20"} 150.0' in text
```

### 6.2. Integration Test (5분 Mock PAPER)

**Script:** `scripts/test_d77_1_metrics_smoke.py`

**Flow:**
1. TopN PAPER Runner 실행 (5분, monitoring.enabled=true, port=9100)
2. 3초 대기 (메트릭 수집 시작)
3. `curl http://localhost:9100/metrics` 호출
4. 응답 텍스트에 다음 포함 여부 확인:
   - `arb_topn_round_trips_total`
   - `arb_topn_pnl_total`
   - `arb_topn_loop_latency_seconds`
   - `arb_topn_win_rate`
5. Runner 종료
6. 결과 출력

**자동화 Bash (PowerShell 버전):**
```powershell
# scripts/test_d77_1_metrics_smoke.ps1
$runner = Start-Process python -ArgumentList "-m scripts.run_d77_0_topn_arbitrage_paper --universe top20 --duration-minutes 5 --monitoring-enabled" -PassThru -NoNewWindow

Start-Sleep -Seconds 5

$metrics = Invoke-WebRequest -Uri "http://localhost:9100/metrics" -UseBasicParsing

if ($metrics.Content -match "arb_topn_round_trips_total") {
    Write-Host "[PASS] Metrics endpoint operational"
} else {
    Write-Host "[FAIL] Metrics not found"
}

Stop-Process -Id $runner.Id -Force
```

---

## 7. Performance Considerations

### 7.1. Overhead Analysis

**Expected Overhead per Iteration:**
- `record_loop_latency()`: ~0.001ms (Summary.observe())
- `record_trade()`: ~0.0005ms (Counter.inc())
- Total per iteration: < 0.01ms
- **Target:** < 1% of 100ms loop interval

**Validation:**
- D77-0 Mock loop latency: 0.008ms avg, 0.043ms p99
- With Prometheus: Target < 0.05ms avg, < 0.1ms p99
- Acceptable degradation: < 20% latency increase

### 7.2. Memory Footprint

**Prometheus Client:**
- Registry + 11 Metrics: ~5MB (estimated)
- HTTP Server Thread: ~2MB
- Total: < 10MB additional memory

**Target:** < 5% memory overhead (D77-0 baseline: 150MB)

### 7.3. Scalability

**Current Design:**
- Single process, single runner
- ~100 iter/s (10ms interval)
- 11 metrics updated every iteration

**Future Considerations (Multi-Symbol):**
- Top50 symbols → 11 metrics × 50 = 550 metrics
- Prometheus handles 10,000+ metrics easily
- Label cardinality must be managed (avoid dynamic labels)

---

## 8. Deployment Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ TopN PAPER Runner (scripts/run_d77_0_topn_arbitrage_paper) │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ (1) init_metrics(env, universe, strategy)
                     ▼
         ┌───────────────────────────┐
         │ arbitrage/monitoring/     │
         │ metrics.py                │
         │ - CollectorRegistry       │
         │ - 11 Prometheus Metrics   │
         └───────────┬───────────────┘
                     │
                     │ (2) start_metrics_server(port=9100)
                     ▼
         ┌───────────────────────────┐
         │ HTTP Server (Thread)      │
         │ GET /metrics              │
         └───────────┬───────────────┘
                     │
                     │ (3) Scrape every 5s
                     ▼
         ┌───────────────────────────┐
         │ Prometheus                │
         │ - Time Series DB          │
         │ - Query Engine (PromQL)   │
         └───────────┬───────────────┘
                     │
                     │ (4) Visualize (D77-2)
                     ▼
         ┌───────────────────────────┐
         │ Grafana Dashboard         │
         │ - Real-time Panels        │
         │ - Core KPI 10종 노출      │
         └───────────────────────────┘
```

---

## 9. Done Criteria (D77-1)

- [x] ✅ **설계 문서 완성** (이 문서)
- [ ] ⏳ `arbitrage/monitoring/metrics.py` 구현
- [ ] ⏳ TopN PAPER Runner에 Metrics Hook 통합
- [ ] ⏳ `monitoring/prometheus/prometheus.yml.sample` 추가
- [ ] ⏳ Unit Tests 10개 작성 및 PASS
- [ ] ⏳ 5분 Mock PAPER 통합 테스트 PASS
- [ ] ⏳ `/metrics` 엔드포인트에서 Core KPI 10종 노출 확인
- [ ] ⏳ `D_ROADMAP.md` 업데이트 (D77-1 → ✅ COMPLETED)
- [ ] ⏳ Git Commit: `[D77-1] Prometheus Exporter for TopN Arbitrage PAPER`

---

## 10. Next Steps (Post D77-1)

### D77-0-RM: Real Market Validation (권장)
- 실제 Exchange API 연동
- 1h Top20 + 12h Top50 PAPER 실행
- Prometheus로 실시간 모니터링하면서 검증
- Critical Gaps 완전 해소

### D77-2: Grafana Dashboard
- 3개 대시보드 생성 (System Health, Trading KPIs, Risk & Guard)
- PromQL 쿼리 작성
- Panel 설계 및 시각화

### D77-3: Alertmanager Integration
- Alert rules 작성 (YAML)
- Telegram 연동 (D76 통합)
- Incident response 자동화

---

**Document Version:** 1.0  
**Last Updated:** 2025-12-01  
**Status:** ✅ DESIGN COMPLETE, READY FOR IMPLEMENTATION

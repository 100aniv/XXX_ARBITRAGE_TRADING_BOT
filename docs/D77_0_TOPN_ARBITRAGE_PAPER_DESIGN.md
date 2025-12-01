# D77-0: TopN Arbitrage PAPER Baseline - Design Document

**Status:** 🔴 **CRITICAL** (UI/UX 개발 전 필수)  
**작성일:** 2025-12-01  
**작성자:** Windsurf AI (D77-0 Meta-Design Session)

---

## 1. Executive Summary

### 배경

D74~D76 Phase 완료 후 메타 분석 결과, **상용급(1조+) 기준 Critical Gaps** 발견:

**Critical Gaps (Q1~Q4 모두 NO):**
- **Q1:** Top50+ 심볼 PAPER 테스트 미실행
- **Q2:** Entry/Exit 완전한 arbitrage cycle 미검증  
- **Q3:** 정량 지표 부재
- **Q4:** 상용급 판단 문서 부재

**근거 문서:** `docs/PHASE_STATUS_SNAPSHOT_D76.md` (Section 7.5)

### 목표

UI/UX/Dashboard(D77) 개발 전에, **실제 시장 데이터 + TopN(최소 Top50) 심볼**에 대해 **아비트라지 엔진 Full Cycle (Entry → Exit → PnL)**을 PAPER 모드로 최소 1h(이상적으로 12h) 실행하고, 그 결과를 리포트/정량 지표로 남긴다.

### 왜 D77-0인가?

**Dashboard 개발 전에 필수:**
- Dashboard는 "실제 동작하는 arbitrage 엔진"의 metrics를 시각화하는 도구
- **검증되지 않은 엔진에 대해 Dashboard를 먼저 만드는 것은 순서가 잘못됨**
- D77-0 실행 중 발생하는 Core KPI 10종을 D77 Dashboard에서 실시간 표시

**상용급(1조+) 기준 필수:**
- Q1~Q4 모두 NO → Critical Gap → **UI/UX 개발 불가**
- D77-0 완료 후에만 "상용급 준비 완료" 판단 가능

---

## 2. Universe Selection Strategy

### 2.1. Universe 정의

**TopN 선정 기준 (3가지 Metrics 조합):**

1. **24h Trading Volume (거래량)**
   - Weight: 40%
   - Source: Upbit/Binance API (`/api/v1/ticker/24hr`)
   - Threshold: Top 100 by volume

2. **Liquidity Depth (유동성)**
   - Weight: 30%
   - Metric: Bid/Ask depth at ±1% price level
   - Source: L2 Orderbook snapshot
   - Threshold: Min $50,000 on each side

3. **Spread Quality (스프레드)**
   - Weight: 30%
   - Metric: Avg spread (ask - bid) / mid-price over 1h
   - Threshold: < 0.5% (50 bps)

**Composite Score:**
```python
score = (volume_rank * 0.4) + (liquidity_rank * 0.3) + (spread_rank * 0.3)
```

### 2.2. Universe Modes

| Mode | N | Target Scenario | Validation Level |
|------|---|-----------------|------------------|
| **TOP_20** | 20 | 1h Smoke Test | Quick validation |
| **TOP_50** | 50 | 12h Soak Test | Production baseline |
| **TOP_100** | 100 | 24h Endurance | Scale verification |

### 2.3. Dynamic Universe Update

- **Refresh Interval:** 1h (during PAPER run)
- **Ranking Update:** Re-compute TopN every 1h based on live metrics
- **Symbol Addition/Removal:** Max 10% churn per update (to avoid excessive turnover)

---

## 3. Target Exchanges & Route Structure

### 3.1. Exchange Pairs

**Primary Routes (Phase 1):**
1. **Upbit KRW ↔ Binance USDT** (Cross-currency arbitrage)
   - FX Rate: KRW/USD real-time (e.g., 1,300 KRW/USD)
   - Example: BTC/KRW (Upbit) vs BTC/USDT (Binance)

**Future Routes (Phase 2+):**
2. Upbit ↔ Bybit
3. Binance ↔ OKX
4. Multi-exchange triangular arbitrage

### 3.2. Route Template

```yaml
route:
  id: "UPBIT_BTC_KRW__BINANCE_BTC_USDT"
  buy_exchange: "upbit"
  buy_symbol: "BTC/KRW"
  sell_exchange: "binance"
  sell_symbol: "BTC/USDT"
  fx_rate: 1300.0  # KRW/USD
  fee_model:
    upbit_maker: 0.0005  # 0.05%
    upbit_taker: 0.0005
    binance_maker: 0.0001  # 0.01%
    binance_taker: 0.0001
```

---

## 4. PAPER Mode Execution Flow

### 4.1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    D77-0 PAPER Runner                       │
│                                                             │
│  Config (YAML) → Engine → Exchange Adapters → Risk/Guard   │
│                     ↓                                       │
│                D75 Infrastructure                           │
│  ┌─────────────┬────────────┬─────────────┬─────────────┐  │
│  │ ArbRoute    │ ArbUniverse│ CrossSync   │ RiskGuard   │  │
│  │ (scoring)   │ (ranking)  │ (rebalance) │ (4-Tier)    │  │
│  └─────────────┴────────────┴─────────────┴─────────────┘  │
│                     ↓                                       │
│                Alert Manager (D76)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Telegram + PostgreSQL (실제 alert 발생 검증)       │   │
│  └─────────────────────────────────────────────────────┘   │
│                     ↓                                       │
│            Core KPI 10+ Metrics Collection                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.2. Execution Steps

**Startup (0-5 min):**
1. Load config (`configs/paper/topn_arb_baseline.yaml`)
2. Initialize D75 Infrastructure (RateLimiter, HealthMonitor, etc.)
3. Initialize D76 AlertManager (Telegram/PostgreSQL)
4. Fetch TopN universe (20/50/100 symbols)
5. Warm up: Fetch initial orderbook/balance snapshots

**Main Loop (5 min ~ 1h/12h):**
1. **Per-iteration (target: < 50ms latency):**
   - Fetch real-time orderbook (via Exchange Adapters)
   - Compute spread for each route (ArbRoute scoring)
   - Apply RiskGuard (4-Tier: Exchange/Route/Symbol/Global)
   - If profitable route found:
     - **Entry:** Place PAPER buy/sell orders
     - Track position open time
   - For open positions:
     - Check **Exit conditions:**
       - TP/SL (Take Profit / Stop Loss)
       - Time-based (max hold time: 30s~2min)
       - Spread reversal (spread < -threshold)
     - **Exit:** Close PAPER position
     - Calculate PnL, update Winrate

2. **Per-hour:**
   - Update TopN universe (re-ranking)
   - Log Core KPI 10종 to JSON/CSV
   - Check Alert triggers (rate limit, health, risk guard)

**Shutdown (final 1 min):**
1. Close all open positions (forced exit)
2. Generate final summary report (JSON/CSV)
3. Save detailed logs (orderbook snapshots, trade history, alert history)

---

## 5. Exit Strategy (Full Cycle 검증)

### 5.1. Exit Conditions

**3가지 Exit Trigger (OR 조건):**

1. **Take Profit (TP)**
   - Condition: `current_pnl >= tp_threshold`
   - Default: `tp_threshold = +1%` (position value)

2. **Stop Loss (SL)**
   - Condition: `current_pnl <= -sl_threshold`
   - Default: `sl_threshold = -0.5%` (position value)

3. **Time-based Exit**
   - Condition: `time_since_open >= max_hold_time`
   - Default: `max_hold_time = 60s`

4. **Spread Reversal Exit**
   - Condition: `current_spread < -spread_threshold`
   - Default: `spread_threshold = -10 bps` (spread turned negative)

### 5.2. Exit Logic Flow

```python
def check_exit_conditions(position, current_market):
    # 1. TP/SL
    current_pnl_pct = calculate_pnl_percent(position, current_market)
    if current_pnl_pct >= tp_threshold:
        return ExitReason.TAKE_PROFIT
    if current_pnl_pct <= -sl_threshold:
        return ExitReason.STOP_LOSS
    
    # 2. Time-based
    time_held = time.time() - position.open_time
    if time_held >= max_hold_time:
        return ExitReason.TIME_LIMIT
    
    # 3. Spread reversal
    current_spread = calculate_spread(current_market)
    if current_spread < -spread_threshold:
        return ExitReason.SPREAD_REVERSAL
    
    return None  # Hold position
```

### 5.3. D64 Trade Lifecycle Fix 통합

**D64에서 구현된 Entry/Exit 로직 재사용:**
- `arbitrage/live_runner.py` (Lines 446-450, 556-655, 812-832)
- `_inject_paper_prices()`: Dynamic spread injection (Entry → Exit)
- `_position_open_times`: Position tracking
- **D77-0에서 강화:** TP/SL/Spread reversal 추가

---

## 6. D75 Infrastructure Integration

### 6.1. ArbRoute (Route Scoring)

**실시간 로그 요구사항:**
```python
# Example log output
[ArbRoute] Symbol: BTC/KRW-BTC/USDT
  Spread Score: 0.45 (45%)
  Health Score: 0.30 (Upbit: 1.0, Binance: 0.8)
  Fee Score: 0.20 (net fee: 0.06%)
  Inventory Score: 0.10 (imbalance: 5%)
  → Total RouteScore: 0.72 (RANK 3/50)
```

**검증 항목:**
- RouteScore 계산이 실제 시장 spread/fee/health/inventory와 정합하는지
- Top routes가 실제로 높은 수익률을 보이는지

### 6.2. ArbUniverse (Universe Ranking)

**실시간 로그 요구사항:**
```python
# Example log output
[ArbUniverse] TOP_50 Ranking Update (2025-12-01 14:00:00)
  #1: BTC/KRW (volume: $500M, liquidity: $1M, spread: 0.05%)
  #2: ETH/KRW (volume: $300M, liquidity: $800K, spread: 0.08%)
  ...
  #50: DOGE/KRW (volume: $10M, liquidity: $50K, spread: 0.25%)
  → Churn: 3 symbols removed, 3 added (6% turnover)
```

**검증 항목:**
- TOP_N mode가 실제 거래량/유동성 기준으로 올바른 심볼을 선정하는지
- Ranking update가 시장 변화를 적절히 반영하는지

### 6.3. CrossSync (Inventory Rebalance)

**실시간 로그 요구사항:**
```python
# Example log output
[CrossSync] Position Sync (2025-12-01 14:05:00)
  Upbit BTC: 0.5 BTC ($25,000)
  Binance BTC: 0.3 BTC ($15,000)
  → Imbalance: 0.2 BTC ($10,000) = 25% of total
  → Exposure: $40,000 (Global limit: $100,000 = 40%)
  → Rebalance decision: HOLD (imbalance < 30% threshold)
```

**검증 항목:**
- Inventory tracking이 실제 거래소 API와 정합하는지
- Imbalance/Exposure 계산이 정확한지
- Rebalance 판단 로직이 합리적인지

### 6.4. RiskGuard (4-Tier Aggregation)

**실시간 로그 요구사항:**
```python
# Example log output
[RiskGuard] 4-Tier Check (Symbol: BTC/KRW-BTC/USDT)
  Exchange Tier: Upbit (HEALTHY), Binance (HEALTHY) → ALLOW
  Route Tier: RouteScore 0.72 > 0.5 threshold → ALLOW
  Symbol Tier: Position count 2 < 5 limit → ALLOW
  Global Tier: Total exposure $40K < $100K limit → ALLOW
  → Final Decision: ALLOW TRADE
```

**검증 항목:**
- 4-Tier aggregation이 실제 환경에서 정상 동작하는지
- Over-blocking (too conservative) vs Under-blocking (too risky) balance

---

## 7. Alert Manager Integration (D76)

### 7.1. 실제 Alert 발생 검증

**목표:** PAPER 실행 중 최소 1회 이상 각 severity alert 발생 확인

**Expected Alerts (PAPER 1h 기준):**

| Alert Rule ID | Severity | Expected Frequency | Validation |
|---------------|----------|--------------------|--------------|
| RATE_LIMITER_LOW_REMAINING | P2 | 1-2 times/h | Upbit/Binance rate limit 소진 시 |
| ENGINE_LATENCY | P1 | 0-1 times (if spike) | Loop latency > 50ms |
| EXCHANGE_HEALTH_DEGRADED | P2 | 0-1 times | REST/WS latency spike |
| ARB_ROUTE_LOW_SCORE | P2 | 5-10 times/h | Low-quality routes filtered |
| CROSS_SYNC_HIGH_IMBALANCE | P2 | 1-2 times/h | Inventory imbalance > 30% |

**실제 Telegram 전송 검증:**
- Mock mode ❌ OFF → **Real Telegram bot 사용**
- 실제 Telegram 메시지 스크린샷 캡처 → 리포트에 첨부

---

## 8. Core KPI 10종 정의

### 8.1. KPI List

| # | KPI Name | Unit | Collection Interval | Target/Threshold |
|---|----------|------|---------------------|------------------|
| 1 | **Total PnL** | USD | Real-time | > $0 (positive) |
| 2 | **Win Rate** | % | Real-time | > 50% |
| 3 | **Trades per Hour** | count/h | Hourly | >= 10 trades/h |
| 4 | **Round Trips** | count | Real-time | >= 10 (Entry → Exit complete) |
| 5 | **Loop Latency (avg)** | ms | Per-iteration | < 50ms |
| 6 | **Loop Latency (p99)** | ms | Per-iteration | < 100ms |
| 7 | **Guard Triggers per Hour** | count/h | Hourly | < 50 (not over-blocking) |
| 8 | **Alert Count (by severity)** | count | Hourly | P0: 0, P1: < 5, P2: < 20 |
| 9 | **Memory Usage** | MB | Every 5 min | < 200MB |
| 10 | **CPU Usage** | % | Every 5 min | < 50% |

### 8.2. Output Format

**JSON Example:**
```json
{
  "timestamp": "2025-12-01T14:00:00Z",
  "session_id": "d77-0-top50-paper-20251201-140000",
  "duration_minutes": 60,
  "kpis": {
    "total_pnl_usd": 234.56,
    "win_rate_pct": 62.5,
    "trades_per_hour": 15.3,
    "round_trips_completed": 23,
    "loop_latency_avg_ms": 42.3,
    "loop_latency_p99_ms": 87.1,
    "guard_triggers_per_hour": 12.5,
    "alert_count": {"P0": 0, "P1": 2, "P2": 8, "P3": 5},
    "memory_usage_mb": 145.2,
    "cpu_usage_pct": 38.7
  }
}
```

**CSV Example:**
```csv
timestamp,session_id,duration_min,total_pnl_usd,win_rate_pct,trades_per_hour,round_trips,loop_latency_avg_ms,loop_latency_p99_ms,guard_triggers_per_hour,alert_p0,alert_p1,alert_p2,alert_p3,memory_mb,cpu_pct
2025-12-01T14:00:00Z,d77-0-top50-paper-20251201-140000,60,234.56,62.5,15.3,23,42.3,87.1,12.5,0,2,8,5,145.2,38.7
```

---

## 9. Long-Run (12h+) Strategy

### 9.1. Log/Data Retention

**로그 파일 구조:**
```
logs/d77-0/
├── paper_session_20251201_140000/
│   ├── main.log (전체 실행 로그)
│   ├── kpi_summary.json (Core KPI 10종)
│   ├── kpi_timeseries.csv (매 5분 KPI snapshot)
│   ├── trades.csv (모든 Entry/Exit 거래 내역)
│   ├── alerts.csv (모든 alert 발생 이력)
│   ├── orderbook_snapshots/ (선택: 디버깅용)
│   └── final_report.md (자동 생성된 요약 리포트)
```

### 9.2. Monitoring During Long-Run

**실시간 모니터링 (개발자 확인용):**
- `tail -f logs/d77-0/paper_session_*/main.log`
- `watch -n 5 cat logs/d77-0/paper_session_*/kpi_summary.json`

**Auto-stop Conditions (12h 전 중단 필요 시):**
1. **Critical Error:** Engine crash, unhandled exception
2. **Resource Exhaustion:** Memory > 500MB, CPU > 90% for 5+ min
3. **Alert Storm:** P0/P1 alerts > 10 in 10 min

---

## 10. Test Plan

### 10.1. Unit Tests

**파일:** `tests/test_d77_0_topn_arbitrage_paper.py`

**테스트 범위:**
1. **Universe Provider:**
   - `test_topn_provider_returns_correct_count`: TOP_20 → 20 symbols
   - `test_topn_provider_ranking_logic`: Volume/Liquidity/Spread 조합 검증
   - `test_topn_provider_dynamic_update`: 1h 후 ranking 변화 검증

2. **Exit Strategy:**
   - `test_exit_tp_sl`: TP/SL 조건 정확히 트리거되는지
   - `test_exit_time_based`: Max hold time 초과 시 exit
   - `test_exit_spread_reversal`: Spread < -threshold 시 exit

3. **Integration Hooks:**
   - `test_alert_manager_integration`: Alert 발생 시 Telegram/PostgreSQL 정상 동작
   - `test_riskguard_integration`: 4-Tier RiskGuard 예외 없이 동작
   - `test_kpi_collection`: Core KPI 10종 모두 수집되는지

### 10.2. Smoke Test (1h Top20)

**실행 명령:**
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top20 \
  --duration-minutes 60 \
  --config configs/paper/topn_arb_baseline.yaml \
  --env PAPER
```

**Acceptance Criteria:**
- [ ] 에러 없이 1h 완주
- [ ] Round trips >= 5 (최소 5개 Entry → Exit 완료)
- [ ] Core KPI 10종 모두 수집됨
- [ ] Alert 최소 1개 발생 (Telegram 전송 확인)

### 10.3. Soak Test (12h Top50)

**실행 명령:**
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top50 \
  --duration-minutes 720 \  # 12h
  --config configs/paper/topn_arb_baseline.yaml \
  --env PAPER
```

**Acceptance Criteria:**
- [ ] 에러 없이 12h 완주
- [ ] Round trips >= 50
- [ ] Win rate >= 50%
- [ ] Core KPI 10종 모두 수집됨
- [ ] Memory leak 없음 (메모리 drift < 10%)
- [ ] Alert 발생 이력 (P0: 0, P1: < 10, P2: < 50)

---

## 11. Done Criteria (상용급 기준)

### 11.1. Critical (필수)

- [ ] **Top50 전체 PAPER 엔진 정상 루프 수행** (에러로 멈추지 않음)
- [ ] **Entry → Exit → PnL Full Cycle 검증** (최소 10+ 완전한 arbitrage round trips)
- [ ] **Core KPI 10종 이상 수집**
- [ ] **Alert/RiskGuard/RateLimiter/HealthMonitor 정상 동작** (과도한 오탐/알람 스톰 없음)
- [ ] **D75 Infrastructure 실제 시장 통합 검증**
  - ArbRoute scoring 실제 동작
  - Universe ranking 실시간 업데이트
  - CrossSync rebalance 판단 로그
  - RiskGuard 4-Tier aggregation 실제 환경 동작
- [ ] **결과 리포트 문서화:** `docs/D77_0_TOPN_ARBITRAGE_PAPER_REPORT.md`
- [ ] **Full regression + 신규 테스트 모두 PASS**

### 11.2. High Priority (권장)

- [ ] **1h Smoke Test:** Top20, 1시간 PAPER 실행 성공
- [ ] **12h Soak Test:** Top50, 12시간 PAPER 실행 성공
- [ ] **Alert 실제 발생 검증:** PAPER 실행 중 rate limit/health/risk alert 발생 → Telegram 전송 확인

---

## 12. 다음 단계 (D77-0 → D77)

D77-0 완료 후:
1. **D77-1:** Prometheus exporter 구현 (Core KPI 10종 metrics endpoint)
2. **D77-2:** Grafana 3개 대시보드 (System Health, Trading KPIs, Risk & Guard)
3. **D77-3:** Alertmanager integration (D76 연동)
4. **D77-4:** Core KPI 10종 대시보드 노출 (D99 Done Criteria 충족)

---

**문서 버전:** 1.0  
**최종 업데이트:** 2025-12-01  
**작성자:** Windsurf AI (D77-0 Meta-Design Session)

**Status:** ⏳ **TODO** (설계 완료, 구현 대기)

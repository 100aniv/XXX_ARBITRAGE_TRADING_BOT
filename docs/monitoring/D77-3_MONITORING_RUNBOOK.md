# D77-3 Monitoring Runbook (TopN Arbitrage & Alerting)

**Version:** 1.0  
**Last Updated:** 2025-12-02  
**Audience:** Operations Team, SRE, DevOps  
**Related Documents:**
- [D77-1 Prometheus Exporter Design](../D77_1_PROMETHEUS_EXPORTER_DESIGN.md)
- [D77-2 Grafana Dashboard Design](../D77_2_GRAFANA_DASHBOARD_DESIGN.md)
- [D77-3 Alerting Playbook](./D77-3_ALERTING_PLAYBOOK.md)
- [D80-7 Alerting System Design](../D80_7_ALERTING_SYSTEM_DESIGN.md)

---

## 1. Overview

### 1.1 System Architecture

This runbook covers the operational monitoring of the **TopN Arbitrage Trading System** with integrated **CrossExchange** and **Alerting** capabilities.

**Key Components:**
1. **Trading Engine**
   - TopN Arbitrage Engine (Paper/Live modes)
   - CrossExchange Strategy & Position Manager
   - 4-Tier RiskGuard (Exchange → Route → Symbol → Global + CrossExchange)

2. **Metrics Collection**
   - `CrossExchangeMetrics` (PnL, trades, latency, resources, guards)
   - `AlertMetrics` (sent, failed, fallback, retry, DLQ, latency, availability)
   - Prometheus Exporter: `/metrics` endpoint (port 9100)

3. **Alerting Pipeline**
   - AlertManager + RuleEngine (D76, D80-7~13)
   - Dispatcher + Routing (priority-based, env-aware)
   - Notifiers: Telegram, Slack, Email, Local Log
   - Fail-safe: Retry, Fallback, DLQ, Chaos Testing

4. **Visualization**
   - **Grafana Dashboards:**
     - `topn_arbitrage_core.json` (11 panels: Trading, Performance, Risk)
     - `alerting_overview.json` (10 panels: Alert Pipeline Health)
   - **Prometheus:** Time-series database for metrics storage

---

### 1.2 Monitoring Objectives

| Objective | Description | Primary Dashboard |
|-----------|-------------|-------------------|
| **Profitability** | Track PnL, win rate, trade volume | TopN Arbitrage Core |
| **Performance** | Monitor loop latency, CPU, memory | TopN Arbitrage Core |
| **Risk Management** | Guard triggers, active positions | TopN Arbitrage Core |
| **Alert Health** | Alert delivery, notifier availability | Alerting Overview |
| **System Stability** | Error rates, DLQ, fallback patterns | Alerting Overview |

---

## 2. Dashboards & Metrics Map

### 2.1 TopN Arbitrage Core Dashboard

**File:** `monitoring/grafana/dashboards/topn_arbitrage_core.json`  
**Panels:** 11  
**Template Variables:** `$env`, `$universe`, `$strategy`

| Panel # | Panel Name | Metric(s) | Purpose |
|---------|------------|-----------|---------|
| 1 | **Total PnL (USD)** | `arb_topn_pnl_total{env, universe, strategy}` | Track cumulative profit/loss over time |
| 2 | **Current PnL** | `arb_topn_pnl_total` (gauge) | Real-time PnL status (green ≥ $1000, yellow ≥ $0, red < $0) |
| 3 | **Trade Rate** | `arb_topn_trades_total{trade_type="entry\|exit"}` | Entry/Exit trades per minute |
| 4 | **Win Rate (%)** | `arb_topn_win_rate{env, universe, strategy}` | Win rate gauge (green ≥ 70%, yellow 50-70%, red < 50%) |
| 5 | **Active Positions** | `arb_topn_active_positions{env, universe, strategy}` | Current open positions count |
| 6 | **Loop Latency (p95/p99)** | `arb_topn_loop_latency_seconds{quantile="0.95\|0.99"}` | Engine loop performance (histogram) |
| 7 | **CPU Usage (%)** | `arb_topn_cpu_usage_percent{env, universe, strategy}` | System CPU utilization |
| 8 | **Memory Usage (bytes)** | `arb_topn_memory_usage_bytes{env, universe, strategy}` | Memory consumption tracking |
| 9 | **Guard Triggers** | `arb_topn_guard_triggers_total{guard_type}` | RiskGuard activation frequency (per 5min) |
| 10 | **Alert Count** | `arb_topn_alerts_total{severity, source}` | Alert volume by severity/source (per 5min) |
| 11 | **Total Round Trips** | `arb_topn_round_trips_total{env, universe, strategy}` | Cumulative completed trades |

**Key Metrics Definitions:**
- **PnL:** Realized profit/loss in USD (counter, increases only on trade close)
- **Win Rate:** Percentage of profitable closed positions (gauge, 0-100)
- **Round Trips:** Complete entry → exit cycles (counter)
- **Guard Triggers:** RiskGuard activation events (counter, labeled by `guard_type`: `exchange`, `route`, `symbol`, `global`, `cross_exchange`)
- **Loop Latency:** Time taken for one engine iteration (histogram, p50/p95/p99)

---

### 2.2 Alerting Overview Dashboard

**File:** `monitoring/grafana/dashboards/alerting_overview.json`  
**Panels:** 10  
**Template Variables:** `$env`, `$notifier`

| Panel # | Panel Name | Metric(s) | Purpose |
|---------|------------|-----------|---------|
| 1 | **Alert Volume** | `alert_sent_total`, `alert_failed_total`, `alert_dlq_total` | Sent/Failed/DLQ per minute (time series) |
| 2 | **Alert Success Rate (%)** | `rate(alert_sent_total) / (rate(alert_sent_total) + rate(alert_failed_total))` | Success rate gauge (green ≥ 95%, yellow 90-95%, red < 90%) |
| 3 | **Alert Sent by Notifier** | `alert_sent_total{notifier}` | Top 10 notifiers by volume (stacked bars) |
| 4 | **Alert Failed by Notifier & Reason** | `alert_failed_total{notifier, reason}` | Top 10 failures by reason (stacked bars) |
| 5 | **Notifier Availability** | `notifier_available{notifier, status}` | Notifier status table (1=available, 0.5=degraded, 0=unavailable) |
| 6 | **Alert Delivery Latency (p95/p99)** | `alert_delivery_latency_seconds{notifier, quantile}` | Notifier delivery latency (histogram) |
| 7 | **Alert Fallback** | `alert_fallback_total{from_notifier, to_notifier}` | Fallback pattern (from → to, stacked bars) |
| 8 | **Alert Retry** | `alert_retry_total{rule_id}` | Retry count by rule_id (stacked bars) |
| 9 | **Dead Letter Queue (DLQ)** | `alert_dlq_total{rule_id, reason}` | Critical stat (red alert if > 10) |
| 10 | **Alert Volume by Rule ID** | `alert_sent_total{rule_id}` | Top 15 rules by volume (stacked bars) |

**Key Metrics Definitions:**
- **alert_sent_total:** Successfully delivered alerts (counter, labeled by `rule_id`, `notifier`)
- **alert_failed_total:** Failed delivery attempts (counter, labeled by `rule_id`, `notifier`, `reason`)
- **alert_fallback_total:** Fallback to secondary notifier (counter, labeled by `from_notifier`, `to_notifier`)
- **alert_retry_total:** Retry attempts (counter, labeled by `rule_id`)
- **alert_dlq_total:** Dead Letter Queue entries (counter, labeled by `rule_id`, `reason`)
- **alert_delivery_latency_seconds:** Alert delivery latency (histogram, p50/p95/p99)
- **notifier_available:** Notifier health status (gauge, 1=healthy, 0=down)

---

## 3. Daily Monitoring Checklist

### 3.1 Morning Check (Start of Day)

**Frequency:** Once per day (before market open or at start of business hours)  
**Duration:** 5-10 minutes  
**Dashboard:** TopN Arbitrage Core

- [ ] **Step 1: PnL Health Check**
  - Open `topn_arbitrage_core` dashboard
  - Check **Total PnL (USD)** panel (Panel 1)
    - ✅ **Normal:** Upward trend or stable (depends on market conditions)
    - ⚠️ **Warning:** Sudden drop > 10% from previous day's close
    - 🚨 **Critical:** Drop > 20% or negative PnL (if previously profitable)
  - Check **Current PnL** gauge (Panel 2)
    - ✅ **Green:** PnL ≥ target threshold
    - ⚠️ **Yellow:** PnL positive but below expectations
    - 🚨 **Red:** PnL negative

- [ ] **Step 2: Trading Activity Check**
  - Check **Trade Rate** (Panel 3)
    - Compare current rate to 7-day average
    - ⚠️ **Warning:** < 50% of average (low market activity or system issue)
    - 🚨 **Critical:** 0 trades for > 30 minutes during active hours
  - Check **Win Rate (%)** (Panel 4)
    - ✅ **Green:** ≥ 70% (good strategy performance)
    - ⚠️ **Yellow:** 50-70% (acceptable but monitor)
    - 🚨 **Red:** < 50% (strategy underperforming, review needed)
  - Check **Total Round Trips** (Panel 11)
    - Verify counter is incrementing (no stale data)

- [ ] **Step 3: Risk Check**
  - Check **Active Positions** (Panel 5)
    - ✅ **Normal:** Within expected range (0-20 for top20, 0-50 for top50)
    - ⚠️ **Warning:** Unusually high (> 2x baseline)
    - 🚨 **Critical:** Near system limits or 0 for extended period
  - Check **Guard Triggers** (Panel 9)
    - ✅ **Normal:** Occasional triggers (< 10/hour)
    - ⚠️ **Warning:** Frequent triggers (10-50/hour)
    - 🚨 **Critical:** > 50/hour or continuous blocking

- [ ] **Step 4: System Health Check**
  - Check **Loop Latency (p95/p99)** (Panel 6)
    - ✅ **Normal:** p95 < 30ms, p99 < 50ms
    - ⚠️ **Warning:** p95 30-60ms, p99 50-100ms
    - 🚨 **Critical:** p95 > 60ms, p99 > 100ms
  - Check **CPU Usage (%)** (Panel 7)
    - ✅ **Normal:** < 50%
    - ⚠️ **Warning:** 50-80%
    - 🚨 **Critical:** > 80% sustained
  - Check **Memory Usage (bytes)** (Panel 8)
    - ✅ **Normal:** < 80% of available
    - ⚠️ **Warning:** 80-90%
    - 🚨 **Critical:** > 90% (potential OOM)

- [ ] **Step 5: Alert System Check**
  - Switch to `alerting_overview` dashboard
  - Check **Notifier Availability** (Panel 5)
    - ✅ **All notifiers status = 1 (available)**
    - ⚠️ **Any notifier status = 0.5 (degraded)**
    - 🚨 **Any notifier status = 0 (unavailable)**
  - Check **Dead Letter Queue (DLQ)** (Panel 9)
    - ✅ **Normal:** DLQ count = 0
    - 🚨 **Critical:** DLQ count > 0 (immediate investigation needed)
  - Check **Alert Success Rate (%)** (Panel 2)
    - ✅ **Green:** ≥ 95%
    - ⚠️ **Yellow:** 90-95%
    - 🚨 **Red:** < 90%

---

### 3.2 Real-time Monitoring (During Trading Hours)

**Frequency:** Continuous (dashboard on display) or every 15-30 minutes  
**Dashboard:** TopN Arbitrage Core (primary), Alerting Overview (secondary)

**Primary View: TopN Arbitrage Core**
1. **Top Row (PnL, Trades):** Monitor for sudden changes
   - PnL should increase gradually (or remain stable in low-volatility periods)
   - Trade rate should be consistent with market activity
2. **Middle Row (Risk, Positions):** Watch for anomalies
   - Guard triggers should be occasional, not constant
   - Active positions should fluctuate within normal range
3. **Bottom Row (Performance):** Ensure system health
   - Latency should remain within baseline (p99 < 50ms)
   - CPU/Memory should be stable

**Secondary View: Alerting Overview**
- Keep **Alert Volume** (Panel 1) in peripheral vision
- If sudden spike in `alert_failed_total` or `alert_dlq_total`, switch to full alert investigation (see Section 5)

**Trigger for Immediate Action:**
- 🚨 **PnL drop > 5% in 5 minutes:** Check Guard Triggers + Market conditions
- 🚨 **Win Rate drops below 40%:** Review strategy parameters
- 🚨 **Loop Latency p99 > 100ms:** Check system resources + logs
- 🚨 **DLQ count > 0:** Investigate alert pipeline (see Alerting Playbook)
- 🚨 **Notifier unavailable:** Check notifier service + network

---

### 3.3 End-of-Day Review

**Frequency:** Once per day (after market close)  
**Duration:** 10-15 minutes  
**Dashboard:** Both (Core + Alerting)

- [ ] **Step 1: Performance Summary**
  - Record daily PnL, win rate, round trips
  - Compare to historical baseline (7-day, 30-day)
  - Note any significant deviations

- [ ] **Step 2: Incident Review**
  - Review **Alert Count** (Panel 10, Core Dashboard)
  - Check **Alert Volume by Rule ID** (Panel 10, Alerting Dashboard)
  - Identify top 5 most frequent alerts
  - Determine if alerts are legitimate or false positives

- [ ] **Step 3: Resource Trends**
  - Review **CPU Usage** and **Memory Usage** trends
  - Check for gradual increases (potential memory leaks)
  - Plan capacity upgrades if sustained > 70%

- [ ] **Step 4: Guard Analysis**
  - Review **Guard Triggers** breakdown by `guard_type`
  - Determine if triggers are appropriate or overly conservative
  - Log any patterns for strategy tuning

- [ ] **Step 5: Alert System Health**
  - Verify **Alert Success Rate** remained ≥ 95% throughout the day
  - Check for any **Fallback** or **Retry** patterns (Panels 7, 8)
  - Confirm **DLQ** remained at 0

- [ ] **Step 6: Documentation**
  - Update operational log with daily summary
  - Note any manual interventions performed
  - Flag items for follow-up investigation

---

## 4. Real-time Monitoring Flow (Normal Operation)

### 4.1 Dashboard Layout Strategy

**Primary Monitor:** `topn_arbitrage_core` dashboard (full screen)
- **Top Row:** Always visible (PnL, Trades, Win Rate)
- **Middle Row:** Peripheral vision (Risk, Alerts)
- **Bottom Row:** Occasional glance (Performance)

**Secondary Monitor (if available):** `alerting_overview` dashboard
- Focus on **Alert Volume** (Panel 1) and **Notifier Availability** (Panel 5)

**Laptop/Tablet:** Prometheus Alertmanager UI (for alert rule status)

---

### 4.2 Normal Operation Flow

```
START: Open topn_arbitrage_core dashboard
  │
  ├─> Check PnL (Panel 1, 2): Upward/stable trend ✅
  ├─> Check Trades (Panel 3): Consistent rate ✅
  ├─> Check Win Rate (Panel 4): Green zone (≥70%) ✅
  ├─> Check Positions (Panel 5): Within range ✅
  ├─> Check Guards (Panel 9): Occasional triggers ✅
  ├─> Check Latency (Panel 6): p99 < 50ms ✅
  ├─> Check CPU/Memory (Panel 7, 8): < 50% ✅
  │
  └─> CONTINUE NORMAL OPERATION
       │
       └─> Repeat every 15-30 minutes
```

---

### 4.3 Anomaly Detection Flow

```
ANOMALY DETECTED (any ⚠️ or 🚨 condition)
  │
  ├─> STEP 1: Identify Anomaly Type
  │   ├─> PnL Drop → Section 5.1 (PnL Investigation)
  │   ├─> Guard Spike → Section 5.2 (Risk Investigation)
  │   ├─> Latency Spike → Section 5.3 (Performance Investigation)
  │   ├─> Alert Failure → Section 5.4 (Alert Investigation)
  │   └─> Notifier Down → Section 5.5 (Notifier Investigation)
  │
  ├─> STEP 2: Drill Down
  │   ├─> Switch to relevant dashboard panel
  │   ├─> Check Prometheus metrics (raw PromQL)
  │   └─> Review application logs
  │
  ├─> STEP 3: Triage (see Alerting Playbook)
  │   ├─> Determine severity (P1/P2/P3)
  │   ├─> Assess impact (trading stopped? reduced? degraded?)
  │   └─> Decide action (immediate fix / workaround / escalate)
  │
  └─> STEP 4: Document & Follow Up
      ├─> Log incident in ops log
      ├─> Create ticket/task for root cause analysis
      └─> Update thresholds/alerts if needed
```

---

## 5. Threshold & Baseline Guidelines

### 5.1 PnL & Trading Thresholds

| Metric | Green ✅ | Yellow ⚠️ | Red 🚨 | Notes |
|--------|---------|-----------|--------|-------|
| **PnL Trend** | Upward or stable | Drop 5-10% from baseline | Drop > 10% or negative | Baseline = 7-day average |
| **Win Rate** | ≥ 70% | 50-69% | < 50% | Strategy-dependent; adjust after initial testing |
| **Trade Rate** | ≥ 80% of 7-day avg | 50-79% of avg | < 50% of avg | Market activity affects this |
| **Round Trips** | Incrementing | Slow increment | Stale (no change) | Check WebSocket + engine health |

**Baseline Learning Period:**
- **Initial Deployment:** First 1-2 weeks
- **After Major Changes:** 3-5 days
- **Method:** Use Prometheus `avg_over_time()` or Grafana stats panel to calculate baseline
- **Update Frequency:** Weekly review, monthly adjustment

---

### 5.2 Performance Thresholds

| Metric | Green ✅ | Yellow ⚠️ | Red 🚨 | Notes |
|--------|---------|-----------|--------|-------|
| **Loop Latency (p95)** | < 30ms | 30-60ms | > 60ms | Target: < 25ms avg, < 40ms p99 |
| **Loop Latency (p99)** | < 50ms | 50-100ms | > 100ms | Spikes acceptable, sustained is critical |
| **CPU Usage** | < 50% | 50-80% | > 80% | Target: < 10% (Phase 4 goal) |
| **Memory Usage** | < 60% | 60-80% | > 80% | Target: < 60MB (Phase 4 goal) |
| **Throughput** | ≥ 40 iter/s | 30-39 iter/s | < 30 iter/s | Depends on universe size |

**Performance Degradation Patterns:**
- **Gradual Increase:** Likely memory leak or cache bloat → Review logs + profiling
- **Sudden Spike:** Likely external API latency or network issue → Check exchange health
- **Oscillation:** Likely GC pauses or resource contention → Tune runtime settings

---

### 5.3 Risk & Guard Thresholds

| Metric | Green ✅ | Yellow ⚠️ | Red 🚨 | Notes |
|--------|---------|-----------|--------|-------|
| **Guard Triggers (hourly)** | < 10 | 10-50 | > 50 | Baseline depends on market volatility |
| **Guard Trigger Rate** | < 3x baseline | 3-5x baseline | > 5x baseline | Baseline = 7-day average |
| **Active Positions** | Within 2σ of mean | 2-3σ from mean | > 3σ from mean | σ = standard deviation over 7 days |
| **Alert Count (hourly)** | < 20 | 20-50 | > 50 | Includes P1/P2/P3 alerts |

**Guard Type Analysis:**
- **exchange:** Most common (API errors, health checks)
- **route:** Market-specific (illiquidity, spread collapse)
- **symbol:** Symbol-specific (volume too low, bid-ask spread too wide)
- **global:** Rare (system-wide risk limit reached)
- **cross_exchange:** FX-related (rate unavailable, stale data)

**Action Based on Guard Type:**
- **Frequent `exchange` guards:** Check exchange health dashboard
- **Frequent `route` guards:** Review ArbRoute scoring + market conditions
- **Frequent `symbol` guards:** Consider removing symbol from universe
- **Frequent `global` guards:** Review risk limits (may be too conservative)
- **Frequent `cross_exchange` guards:** Check FX provider status

---

### 5.4 Alert System Thresholds

| Metric | Green ✅ | Yellow ⚠️ | Red 🚨 | Notes |
|--------|---------|-----------|--------|-------|
| **Alert Success Rate** | ≥ 95% | 90-94% | < 90% | Measured over 1 hour rolling window |
| **Alert Delivery Latency (p99)** | < 3s | 3-5s | > 5s | Notifier-specific; Telegram usually < 1s |
| **Notifier Availability** | 1.0 (available) | 0.5 (degraded) | 0.0 (unavailable) | Check notifier service health |
| **DLQ Count** | 0 | N/A | > 0 | ANY DLQ entry is critical |
| **Fallback Rate** | < 5% of total | 5-10% | > 10% | High fallback = primary notifier unreliable |
| **Retry Rate** | < 10% of total | 10-20% | > 20% | High retry = transient failures |

**Alert Volume Patterns:**
- **Constant Low Volume:** Normal operation (5-20 alerts/hour)
- **Burst (< 5min):** Likely legitimate event (market shock, exchange issue)
- **Sustained High Volume:** Likely alert storm or misconfigured rule → Check RuleEngine

---

## 6. Incident Triage Flow (High-Level)

### 6.1 Severity Classification

| Severity | Trading Impact | Response Time | Escalation |
|----------|---------------|---------------|------------|
| **P1 (Critical)** | Trading stopped or high loss risk | Immediate (< 5min) | On-call engineer + team lead |
| **P2 (High)** | Degraded performance or partial failure | < 30min | On-call engineer |
| **P3 (Medium)** | No immediate impact, monitoring needed | < 2 hours | Normal business hours |

---

### 6.2 Incident Triage Decision Tree

```
INCIDENT DETECTED
  │
  ├─> Is trading stopped? (PnL flat, trades = 0)
  │   YES → P1: CRITICAL → Immediate action (see Alerting Playbook Section 3)
  │   NO  → Continue ↓
  │
  ├─> Is PnL dropping rapidly? (> 5%/5min)
  │   YES → P1: CRITICAL → Check Guards + Market conditions
  │   NO  → Continue ↓
  │
  ├─> Is performance degraded? (Latency > 100ms p99)
  │   YES → P2: HIGH → Check CPU/Memory + Logs
  │   NO  → Continue ↓
  │
  ├─> Are alerts failing? (Success rate < 90% or DLQ > 0)
  │   YES → P2: HIGH → Check Notifier + Alert pipeline
  │   NO  → Continue ↓
  │
  └─> Is it a monitoring anomaly? (Metric spike but no functional impact)
      YES → P3: MEDIUM → Review logs + Create ticket
      NO  → False alarm → Update thresholds
```

---

### 6.3 First Response Actions (by Severity)

#### P1 (Critical)
1. **Confirm incident** (< 1min)
   - Check multiple data sources (Grafana + Prometheus + Logs)
   - Verify not a false alarm
2. **Assess impact** (< 2min)
   - Is trading stopped? How much PnL at risk?
   - Which component is failing? (Engine / Exchange / Alert / FX)
3. **Immediate mitigation** (< 5min)
   - If trading stopped: Check exchange health + RiskGuard state
   - If PnL dropping: Consider emergency stop (if risk > reward)
   - If alert failing: Use fallback channel (Local Log always works)
4. **Escalate** (< 5min)
   - Notify on-call engineer + team lead
   - Share Grafana dashboard links + initial findings
5. **Detailed investigation** (see Alerting Playbook for scenario-specific steps)

#### P2 (High)
1. **Confirm incident** (< 5min)
2. **Assess impact** (< 10min)
3. **Investigate root cause** (< 30min)
   - Check logs (application + system)
   - Review recent changes (deployments, config updates)
4. **Implement workaround** (< 30min)
   - Adjust thresholds, restart services, switch to fallback, etc.
5. **Monitor for resolution** (ongoing)
6. **Document** (< 1 hour)

#### P3 (Medium)
1. **Log incident** (< 15min)
2. **Investigate when available** (< 2 hours)
3. **Create ticket** for follow-up
4. **Update monitoring** if false alarm

---

### 6.4 Escalation Channels

| Channel | Purpose | Audience | SLA |
|---------|---------|----------|-----|
| **Telegram (P1/P2 alerts)** | Immediate notification | On-call engineer | < 1min |
| **Slack (P2/P3 alerts)** | Team-wide awareness | Dev team + SRE | < 5min |
| **Email (P3 alerts)** | Daily digest | Management + compliance | < 1 hour |
| **Local Log (all alerts)** | Audit trail | Compliance + postmortem | Always on |

**Escalation Policy (Template):**
- **P1:** Alert → Telegram (on-call) → Phone call (if no ACK in 5min) → Team lead
- **P2:** Alert → Telegram + Slack → Investigate (30min) → Escalate if unresolved
- **P3:** Alert → Email → Review during business hours

**NOTE:** Adjust escalation policy based on actual team structure and on-call rotation.

---

## 7. Runbook Maintenance

### 7.1 When to Update This Runbook

- **New Metrics Added:** Add to Section 2 (Dashboards & Metrics Map)
- **Dashboard Changes:** Update panel descriptions + screenshots
- **Threshold Tuning:** Update Section 5 (Threshold & Baseline Guidelines)
- **New Alert Rules:** Add to Section 3 (Checklist) + Section 6 (Triage)
- **Incident Postmortems:** Update Section 6 (Triage Flow) with lessons learned
- **Team Structure Changes:** Update Section 6.4 (Escalation Channels)

---

### 7.2 Runbook Review Schedule

- **Weekly:** Review incident log + update thresholds if needed
- **Monthly:** Review full runbook + update baselines
- **Quarterly:** Major review + incorporate postmortem findings
- **After Major Release:** Review all sections + test procedures

---

### 7.3 Related Documents to Keep in Sync

- **Alerting Playbook:** Detailed scenario response procedures
- **D77-1 Prometheus Exporter Design:** Metric definitions + labels
- **D77-2 Grafana Dashboard Design:** Panel configurations + queries
- **D80-7 Alerting System Design:** Alert rules + routing logic
- **RUNBOOK.md:** General system operations (broader scope)
- **TROUBLESHOOTING.md:** Debugging guides (deeper technical details)

---

## 8. Quick Reference

### 8.1 Key URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Prometheus** | `http://localhost:9100/metrics` | Raw metrics endpoint |
| **Grafana** | `http://localhost:3000` | Dashboard UI |
| **Core Dashboard** | `/d/topn-arbitrage-core` | Trading + Performance |
| **Alert Dashboard** | `/d/alerting-overview` | Alert Pipeline Health |
| **Prometheus UI** | `http://localhost:9090` | PromQL queries + alerts |
| **Alertmanager** | `http://localhost:9093` | Alert rule management |

---

### 8.2 Emergency Contacts (Template)

| Role | Name | Telegram | Phone | Backup |
|------|------|----------|-------|--------|
| **On-call Engineer** | TBD | @username | +82-XX-XXXX-XXXX | TBD |
| **Team Lead** | TBD | @username | +82-XX-XXXX-XXXX | TBD |
| **SRE Lead** | TBD | @username | +82-XX-XXXX-XXXX | TBD |

**NOTE:** Update this table with actual team members before production deployment.

---

### 8.3 Common PromQL Queries

```promql
# PnL Rate (per minute)
rate(arb_topn_pnl_total{env="live", universe="top50"}[1m])

# Win Rate (current)
arb_topn_win_rate{env="live", universe="top50", strategy="topn_arb"}

# Loop Latency (p99, last 5min)
histogram_quantile(0.99, rate(arb_topn_loop_latency_seconds_bucket{env="live"}[5m]))

# Alert Success Rate (last 1 hour)
sum(rate(alert_sent_total[1h])) / (sum(rate(alert_sent_total[1h])) + sum(rate(alert_failed_total[1h]))) * 100

# DLQ Count (last 24 hours)
increase(alert_dlq_total[24h])

# Guard Trigger Rate (per hour)
rate(arb_topn_guard_triggers_total{guard_type="cross_exchange"}[1h]) * 3600

# CPU Usage (current, per strategy)
arb_topn_cpu_usage_percent{env="live", strategy="topn_arb"}
```

---

### 8.4 Log File Locations

| Component | Log Path | Log Level | Rotation |
|-----------|----------|-----------|----------|
| **Trading Engine** | `logs/topn_arbitrage.log` | INFO | Daily |
| **Alert System** | `logs/alerting.log` | INFO | Daily |
| **Prometheus Exporter** | `logs/prometheus_exporter.log` | INFO | Daily |
| **Local Log Notifier** | `logs/alert_local.log` | ALL | Daily |

---

## 9. Appendix

### 9.1 Glossary

- **PnL (Profit and Loss):** Realized gains/losses from closed trades
- **Win Rate:** Percentage of profitable trades out of total closed trades
- **Round Trip:** Complete cycle of entry → exit for a single position
- **Guard Trigger:** RiskGuard activation event (blocks or throttles trading)
- **DLQ (Dead Letter Queue):** Failed alerts that cannot be retried
- **Fallback:** Secondary notifier used when primary fails
- **Notifier:** Alert delivery channel (Telegram, Slack, Email, etc.)
- **Baseline:** Historical average used for anomaly detection
- **p95/p99:** 95th/99th percentile (performance metric)

---

### 9.2 Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-12-02 | 1.0 | Initial runbook creation (D77-3) | Windsurf AI |

---

**END OF MONITORING RUNBOOK**

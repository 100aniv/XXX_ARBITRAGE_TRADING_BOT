# D76 Alerting Infrastructure – Sketch

**작성일:** 2025-11-22  
**Phase:** D76 (Alerting & Monitoring)  
**상태:** 📝 SKETCH (초안, 향후 D76 프롬프트에서 상세 설계 및 구현)

---

## 📋 목차

1. [목적](#목적)
2. [이벤트 소스](#이벤트-소스)
3. [Alert 채널 후보](#alert-채널-후보)
4. [최소 요구사항 (초안)](#최소-요구사항-초안)
5. [차후 상세 설계 시 TODO](#차후-상세-설계-시-todo)

---

## 목적

D76 Alerting Infrastructure는 **D75 Arbitrage Core v1**에서 발생하는 다양한 이벤트를  
실시간으로 감지하고, 적절한 채널(Telegram/Slack/Email 등)로 알림을 전송하는 시스템입니다.

**핵심 목표:**
- 24/7 무인 운영 시 Critical 이벤트 즉시 인지
- P0~P3 Severity 분류 및 채널별 routing
- Alert history 저장 및 조회 (PostgreSQL)
- Alert storm 방지 (Rate limiting)

---

## 이벤트 소스

D75 Core 모듈에서 발생하는 알림 대상 이벤트:

### 1. Rate Limiter (D75-3)

**파일:** `arbitrage/infrastructure/rate_limiter.py`

**이벤트:**
- Rate limit 임계값 근접 (`remaining_pct < 20%`)
- Rate limit 초과 (HTTP 429 발생)

**Severity:**
- P2 (Medium): Remaining < 20%
- P1 (High): HTTP 429 발생

**Alert 메시지 예시:**
```
⚠️ [P2] Rate Limit Warning
Exchange: Binance
Category: Order
Remaining: 15% (180/1200)
Action: Throttling activated
```

---

### 2. Exchange Health Monitor (D75-3)

**파일:** `arbitrage/infrastructure/exchange_health.py`

**이벤트:**
- Health status 변화 (`HEALTHY → DEGRADED/DOWN/FROZEN`)
- REST latency > 500ms (5분 이상 지속)
- Error rate > 5% (1분 이상 지속)
- Orderbook age > 5s (stale data)

**Severity:**
- P2 (Medium): HEALTHY → DEGRADED
- P1 (High): DEGRADED → DOWN
- P0 (Critical): DOWN → FROZEN

**Alert 메시지 예시:**
```
🔴 [P1] Exchange Health DOWN
Exchange: Upbit
Previous: DEGRADED
Current: DOWN
Metrics:
  - REST latency: 1,250ms
  - Error rate: 12.5%
  - Orderbook age: 8.2s
Action: Failover to Binance
```

---

### 3. ArbRoute / ArbUniverse (D75-4)

**파일:** `arbitrage/domain/arb_route.py`, `arbitrage/domain/arb_universe.py`

**이벤트:**
- RouteScore < 50 (거래 불가 상태)
- Universe에서 모든 route가 SKIP 상태 (거래 기회 소멸)
- Route score급락 (1분 내 -30% 이상)

**Severity:**
- P2 (Medium): RouteScore < 50 (1개 route)
- P1 (High): 모든 route SKIP (5분 이상)

**Alert 메시지 예시:**
```
⚠️ [P2] Route Score Low
Route: Upbit-Binance-BTCKRW
Score: 42 (spread:50, health:30, fee:60, inventory:40)
Reason: Health score low (Exchange B DEGRADED)
Action: Route SKIP
```

---

### 4. Cross-Exchange Sync (D75-4)

**파일:** `arbitrage/domain/cross_sync.py`

**이벤트:**
- Imbalance ratio > 50% (Rebalance 필요)
- Exposure risk > 80% (High exposure)
- Rebalance 실행 실패 (3회 연속)
- Inventory sync 실패 (Balance API timeout)

**Severity:**
- P2 (Medium): Imbalance > 50%
- P1 (High): Exposure > 80% 또는 Rebalance 실패 3회

**Alert 메시지 예시:**
```
⚠️ [P1] High Exposure Risk
Symbol: BTC
Total Exposure: $85,000 (85% of capital)
Imbalance Ratio: 0.65 (Upbit heavy)
Action: Rebalance initiated (BUY Binance, SELL Upbit)
```

---

### 5. 4-Tier RiskGuard (D75-5)

**파일:** `arbitrage/domain/risk_guard.py`

**이벤트:**

#### Tier 1 (ExchangeGuard):
- Exchange daily loss > $10k → BLOCK
- Health status DOWN/FROZEN → BLOCK
- Rate limit < 20% → DEGRADE

**Severity:** P1 (High)

#### Tier 2 (RouteGuard):
- Route streak loss (3회 연속) → COOLDOWN
- RouteScore < 50 → BLOCK
- Abnormal spread (> 500 bps) → DEGRADE

**Severity:** P2 (Medium)

#### Tier 3 (SymbolGuard):
- Symbol exposure > 50% → DEGRADE
- Symbol drawdown > 20% → BLOCK
- Volatility proxy > 10% → DEGRADE

**Severity:** P2 (Medium) ~ P1 (High)

#### Tier 4 (GlobalGuard):
- Global daily loss > $50k → BLOCK
- Total exposure > $100k → BLOCK
- Cross-exchange imbalance > 50% → BLOCK

**Severity:** **P0 (Critical)** (Global loss/exposure) ~ P1 (High)

**Alert 메시지 예시:**
```
🔴 [P0] GlobalGuard BLOCK
Reason: Global Daily Loss Limit
Daily Loss: $55,000 / $50,000 (limit)
Portfolio Value: $945,000 (start: $1,000,000)
Action: Trading HALTED until next day
Manual Review Required: YES
```

---

## Alert 채널 후보

### 1. Telegram Bot (우선순위 1)

**장점:**
- Real-time push notification
- Mobile/Desktop 동시 지원
- API 간단 (python-telegram-bot)

**대상 Severity:** P0, P1, P2

**구현 예정:**
- Bot token, chat ID config
- Message formatting (emoji, severity color)
- Rate limiting (max 10 msg/min)

---

### 2. Slack Webhook (우선순위 2)

**장점:**
- 팀 공유용
- Thread 댓글 지원 (Alert → Response tracking)
- Rich formatting (attachments, buttons)

**대상 Severity:** P1, P2

**구현 예정:**
- Webhook URL config
- Channel routing (P0 → #critical, P1 → #alerts)

---

### 3. Email (우선순위 3)

**장점:**
- Daily summary report 용도
- Attachment 가능 (CSV, PDF)

**대상 Severity:** P3 (Low), Daily summary (ALL)

**구현 예정:**
- SMTP server config
- HTML template

---

### 4. PostgreSQL Alert History (필수)

**목적:**
- 모든 alert 저장 (P0~P3)
- Alert 빈도 분석
- Incident post-mortem

**스키마 (예정):**
```sql
CREATE TABLE alert_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    severity VARCHAR(10) NOT NULL,  -- P0, P1, P2, P3
    source VARCHAR(50) NOT NULL,    -- RateLimiter, HealthMonitor, ...
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP
);
```

---

## 최소 요구사항 (초안)

### 기능 요구사항

1. **Alert Taxonomy:**
   - 4단계 Severity (P0~P3)
   - 20+ Alert Rules (이벤트 소스별)
   - Rule engine (조건 → alert 발생)

2. **Alert Delivery:**
   - Telegram Bot 통합 (P0~P2)
   - Rate limiting (max 10 msg/min, alert storm 방지)
   - Retry logic (전송 실패 시 재시도 3회)

3. **Alert History:**
   - PostgreSQL 저장 (모든 alert)
   - 조회 API (timestamp 범위, severity 필터)
   - Acknowledgement 기능 (alert 확인 표시)

4. **Integration with D75 Core:**
   - Rate Limiter → `alert_manager.send_alert()`
   - Health Monitor → `alert_manager.send_alert()`
   - RiskGuard → `alert_manager.send_alert()`
   - CrossSync → `alert_manager.send_alert()`

### 비기능 요구사항

1. **Latency:**
   - Alert 발생 → 전송 < 1s (Telegram)
   - D75 Core overhead < 0.1ms (alert check)

2. **Reliability:**
   - Alert 전송 성공률 > 99%
   - Alert history 손실 0건 (PostgreSQL commit)

3. **Configuration:**
   - Config file 기반 (Telegram token, chat ID, severity threshold)
   - Environment variable 지원 (PROD/DEV 분리)

---

## 차후 상세 설계 시 TODO

### D76 프롬프트에서 수행할 작업

1. **Alert Rule Engine 설계:**
   - Rule 정의 형식 (YAML/JSON)
   - Rule evaluation logic
   - Threshold 동적 조정 (예: Daily loss limit config)

2. **Telegram Bot 구현:**
   - Bot 생성 및 Token 발급
   - Message formatting (emoji, severity, rich text)
   - Rate limiting 구현 (max 10 msg/min)
   - Thread 기능 (Alert → Ack → Resolve)

3. **Alert Manager 구현:**
   - `AlertManager.send_alert(severity, source, title, message, metadata)`
   - Channel routing (Severity → Telegram/Slack/Email)
   - Retry logic (exponential backoff)
   - History 저장 (PostgreSQL)

4. **D75 Core Integration:**
   - Rate Limiter에 alert hook 추가
   - Health Monitor에 alert hook 추가
   - RiskGuard에 alert hook 추가
   - CrossSync에 alert hook 추가

5. **Testing:**
   - 단위 테스트 (AlertManager, Telegram notifier)
   - Integration test (D75 Core → Alert 발생 시뮬레이션)
   - Alert storm 테스트 (Rate limiting 검증)

6. **Documentation:**
   - `D76_ALERTING_INFRASTRUCTURE_DESIGN.md` (상세 설계)
   - RUNBOOK 업데이트 (Alert 대응 절차)
   - TROUBLESHOOTING 업데이트 (Alert 관련 문제 해결)

---

**문서 버전:** 1.0 (SKETCH)  
**최종 업데이트:** 2025-11-22  
**작성자:** Windsurf AI

**Note:** 본 문서는 초안(Sketch)이며, D76 프롬프트에서 상세 설계 및 구현이 진행됩니다.

# D77-3 알림 플레이북 (TopN Arbitrage & Cross-Exchange)

**버전:** 1.0  
**최종 업데이트:** 2025-12-02  
**대상:** On-call 엔지니어, SRE, DevOps  
**관련 문서:**
- [D77-3 Monitoring Runbook](./D77-3_MONITORING_RUNBOOK.md)
- [D80-7 Alerting System Design](../D80_7_ALERTING_SYSTEM_DESIGN.md)
- [D76 Alert Rule Engine Design](../D76_ALERT_RULE_ENGINE_DESIGN.md)
- [RUNBOOK.md](../RUNBOOK.md)
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)

---

## 1. Alerting Stack 개요

### 1.1 Alert 파이프라인 아키텍처

```
[Alert Sources] → [AlertManager] → [Dispatcher] → [Routing] → [Notifiers]
     ↓                 ↓              ↓             ↓            ↓
  Engine           RuleEngine      PriorityQueue   Rules      Telegram
  RiskGuard        Throttler       Retry/DLQ      Fallback    Slack
  CrossExchange    Aggregator                                 Email
  HealthMonitor                                               LocalLog
```

**주요 구성 요소:**
1. **Alert Sources:** 엔진 이벤트, RiskGuard 발동, 상태 점검, FX 에러
2. **AlertManager:** 중앙 알림 디스패치 (D76, D80-7)
3. **RuleEngine:** 우선순위/라우팅 결정 (P1/P2/P3, 환경별 분기)
4. **Dispatcher:** 비동기 전송 + 재시도 로직 (D80-11~13)
5. **Notifiers:** 전송 채널 (Telegram, Slack, Email, Local Log)
6. **Fail-safe:** Retry (3회), Fallback (주 → 보조), DLQ (실패 알림)

---

### 1.2 Alert 플로우 (정상 운영)

```
알림 발생
  ↓
RuleEngine.evaluate_alert()
  ├─> rule_id 매칭 (예: "FX-001", "RG-005")
  ├─> 우선순위 결정 (P1/P2/P3)
  ├─> Notifier 선택 (환경별: PROD vs DEV)
  ↓
Dispatcher.enqueue()
  ├─> 우선순위 큐에 추가 (P1 → P2 → P3)
  ├─> Worker 스레드가 dequeue
  ↓
Notifier.send()
  ├─> 전송 시도 (타임아웃: 3초)
  ├─> 성공 → 메트릭 기록 (alert_sent_total++)
  ├─> 실패 → Retry (최대 3회)
  │   ├─> 여전히 실패 → Fallback (예: Telegram → Slack)
  │   └─> 모두 실패 → DLQ (alert_dlq_total++)
  ↓
Metrics + Logs
  ├─> alert_sent_total{rule_id, notifier}
  ├─> alert_failed_total{rule_id, notifier, reason}
  ├─> alert_delivery_latency_seconds{notifier}
  └─> Local Log (항상 기록됨)
```

---

### 1.3 Alert 심각도 및 우선순위 모델

| 우선순위 | 심각도 | 사용 사례 | 대응 시간 | Notifier (PROD) | Notifier (DEV) |
|----------|----------|----------|---------------|-----------------|----------------|
| **P1** | Critical | 시스템 다운, 높은 손실 위험, FX 다운 | < 5분 | Telegram + PostgreSQL | Telegram + Slack + PostgreSQL |
| **P2** | High | 성능 저하, Guard 급증 | < 30분 | PostgreSQL (Telegram 선택) | Telegram + Slack + PostgreSQL |
| **P3** | Medium | 정보/경고, 트렌드 알림 | < 2시간 | PostgreSQL | Email + PostgreSQL |

**Telegram-first 정책 (PROD):**
- P1/P2: Telegram 필수 (on-call에게 즉시 알림)
- P3: PostgreSQL만 (노이즈 감소)

**DEV/TEST:**
- 모든 우선순위: 테스트를 위해 다중 notifier

---

## 2. 시나리오 카탈로그

### 시나리오 개요

| 시나리오 # | 이름 | 우선순위 | 빈도 | 섹션 |
|------------|------|----------|-----------|---------|
| 3.1 | FX Provider 다운 / 불안정 | P1 | 드물음 | 높은 영향 |
| 3.2 | Exchange API 에러 / 주문 실패 | P1 | 가끔 | 높은 영향 |
| 3.3 | Guard Trigger 급증 | P2 | 흔함 | 리스크 관련 |
| 3.4 | Notifier 다운 | P2 | 드물음 | Alert 시스템 |
| 3.5 | DLQ 증가 | P2 | 드물음 | Alert 시스템 |
| 3.6 | 레이턴시 / CPU / 메모리 급증 | P2 | 가끔 | 성능 |
| 3.7 | Chaos/Fail-Safe 테스트 이상 | P3 | 테스트 전용 | 운영 |

---

## 3. 상세 시나리오 절차

### 3.1 FX Provider 다운 / 불안정

#### 시나리오: FX Provider 다운 / 불안정

**설명:** FX 환율 제공자 (예: DunanmuAPI, Upbit, Binance)를 사용할 수 없거나 정체/무효한 환율을 반환하여 CrossExchange 아비트라지가 차단됩니다.

---

**발동 신호:**
- **알림:** `alert_sent_total{rule_id="FX-001", severity="P1"}` 증가
- **메트릭:**
  - `cross_exchange_fx_rate_stale{provider}` = 1 (정체 데이터)
  - `cross_exchange_fx_provider_error_total{provider}` 증가
  - `cross_exchange_guard_blocks_total{reason="fx_unavailable"}` 급증
- **Grafana 패널:**
  - Core Dashboard: **Guard Triggers** (패널 9) → `guard_type="cross_exchange"`로 필터
  - (FX 대시보드가 있는 경우): FX Provider Health 패널

---

**초기 점검 (0-5분):**
1. **FX provider 상태 확인**
   ```promql
   cross_exchange_fx_rate_stale{provider="dunamu"} == 1
   ```
   - = 1인 경우: FX 데이터가 정체됨 (임계값 초과, 예: 30초)
   - 마지막 성공적인 FX 업데이트 타임스탬프 확인

2. **CrossExchange 거래 영향 점검**
   - `arb_topn_trades_total{trade_type="entry"}`가 0으로 떨어지는가?
   - `arb_topn_guard_triggers_total{guard_type="cross_exchange"}`가 급증하는가?

3. **네트워크 연결 확인**
   - FX provider API 엔드포인트 ping (접근 가능한 경우)
   - DNS/TLS 에러에 대한 시스템 로그 확인

4. **다른 FX provider 확인 (다중 소스인 경우)**
   - FX aggregator (D80-5) 사용 시, 백업 소스 확인
   - 예: Dunamu 다운 → Upbit/Binance 환율로 fallback

---

**근본 원인 조사 (5-15분):**
1. **Provider 측 문제?**
   - FX provider 상태 페이지 확인 (가능한 경우)
   - 공지사항 확인 (유지보수, API 변경)
   - 샘플 요청으로 API 수동 테스트 (curl/Postman)

2. **Client 측 문제?**
   - 예외에 대한 애플리케이션 로그 확인:
     ```
     grep -i "fx.*error" logs/topn_arbitrage.log | tail -50
     ```
   - 확인 항목: timeout, connection refused, SSL 에러, rate limit (429)

3. **설정 문제?**
   - FX provider API keys/secrets가 유효한지 확인
   - 설정 확인: `configs/fx_provider.yml` 또는 환경 변수
   - 올바른 API 엔드포인트 URL 확인

4. **데이터 품질 문제?**
   - Provider가 응답하지만 환율이 무효한 경우:
     - 0/음수 환율 확인
     - 예상 범위 밖의 환율 확인 (예: USD/KRW < 1000 또는 > 2000)
     - 코드의 FX 검증 로직 검토

---

**완화 / 임시 조치:**
1. **FX provider가 다운된 경우:**
   - **옵션 A (권장):** 백업 FX provider로 전환 (설정된 경우)
     - 설정 업데이트: `fx_provider: "upbit"` ("dunamu"에서)
     - 엔진 재시작 또는 설정 리로드 (hot-reload 지원 시)
   - **옵션 B:** 정적/캐시된 FX 환율 사용 (임시만)
     - 위험: 정체된 환율로 인해 아비트라지 가격 오류 발생 가능
     - 낮은 변동성 기간에 < 5분만 허용
   - **옵션 C:** CrossExchange 거래 일시 중지
     - CrossExchange 전략 비활성화 (단일 거래소 아비트라지는 계속)
     - 명령: `disable-cross-exchange` (CLI 사용 가능 시)

2. **FX provider가 불안정한 경우 (느리지만 작동):**
   - FX fetch 타임아웃 증가 (예: 3초 → 5초)
   - FX 업데이트 빈도 감소 (예: 10초 → 30초) 로드 감소
   - 복구 모니터링

3. **FX 데이터가 무효한 경우:**
   - 데이터 검증 필터 추가 (아직 없는 경우)
   - 예: USD/KRW에 대해 [1000, 2000] 범위 밖 환율 거부
   - 조사를 위해 무효 환율 로깅

---

**에스컬레이션 기준 및 채널:**
- **P1로 즉시 에스컬레이션** 조건:
  - FX provider가 5분 이상 다운 AND 백업 없음
  - 거래 완전 중단 (5분 이상 거래 0건)
- **에스컬레이션 채널:**
  - Telegram: On-call 엔지니어 + 팀 리더에게 알림
  - Slack: #alerts-critical 채널에 게시
  - 인시던트 티켓: 로그 + 메트릭으로 높은 우선순위 티켓 생성

---

**사후 분석 참고사항:**
- **근본 원인:** 실제 원인 문서화 (provider 장애, 설정 오류, 네트워크 문제 등)
- **영향:** 총 다운타임, 놓친 거래, 추정 손실 수익
- **예방:**
  - 다중 소스 FX aggregation (D80-5) 구현 (아직 안 된 경우)
  - FX provider 상태 점검 추가 (거래 전 검증)
  - 외부 모니터링 설정 (매 1분마다 provider API ping)
- **액션 아이템:**
  - FX provider SLA 검토
  - 중복 provider 고려
  - FX 정체 감지 개선 (임계값 30초 → 10초로 감소)

---

### 3.2 Exchange API Errors / Order Failures

#### Scenario: Exchange API Errors / Order Failures

**Description:** Exchange API (Upbit, Binance) is returning errors, timing out, or rejecting orders, causing trading disruption.

---

**Trigger Signals:**
- **Alert:** `alert_sent_total{rule_id="EX-001", severity="P1"}` increases
- **Metrics:**
  - `exchange_health_status{exchange="upbit"}` = 0 (unhealthy)
  - `arb_topn_trades_total{trade_type="entry"}` drops to zero
  - `arb_topn_guard_triggers_total{guard_type="exchange"}` spikes
  - `cross_exchange_orders_total{result="failed"}` increases
- **Grafana Panels:**
  - Core Dashboard: **Trade Rate** (Panel 3) → sudden drop
  - Core Dashboard: **Guard Triggers** (Panel 9) → `guard_type="exchange"`
  - (If exists) Exchange Health Dashboard

---

**First Checks (0-5 minutes):**
1. **Identify affected exchange(s)**
   ```promql
   exchange_health_status{exchange=~"upbit|binance"} == 0
   ```
   - If = 0: Exchange is marked unhealthy by health monitor

2. **Check trade volume impact**
   - Compare current trade rate to baseline (7-day average)
   - If drop > 50%: Significant impact
   - If drop = 100%: Complete outage

3. **Check guard trigger breakdown**
   ```promql
   rate(arb_topn_guard_triggers_total{guard_type="exchange"}[5m])
   ```
   - High rate → Exchange is blocking trades due to health check failures

4. **Check recent orders (if logs available)**
   ```bash
   grep -i "order.*failed" logs/topn_arbitrage.log | tail -20
   ```
   - Look for error codes: 429 (rate limit), 503 (service unavailable), 401 (auth)

---

**Root Cause Narrowing (5-15 minutes):**
1. **Exchange-side issue?**
   - Check exchange status page (e.g., status.upbit.com)
   - Check Twitter/Telegram for user reports
   - Test API manually: `curl -X GET https://api.upbit.com/v1/status/wallet`

2. **Rate limit exceeded?**
   - Check rate limiter metrics:
     ```promql
     rate_limiter_limit_remaining{exchange="upbit", endpoint="order"} < 10
     ```
   - If < 10: Approaching rate limit
   - If = 0: Rate limit hit → Throttling in effect

3. **Authentication issue?**
   - Check for 401/403 errors in logs
   - Verify API keys are valid (not expired, not revoked)
   - Test auth with simple API call (e.g., GET /accounts)

4. **Network/DNS issue?**
   - Ping exchange API endpoint
   - Check for DNS resolution failures
   - Test from different network (mobile hotspot) to rule out ISP issue

5. **Order rejection reason?**
   - Insufficient balance?
   - Order size too small/large?
   - Symbol not tradable (delisted, maintenance)?

---

**Mitigation / Workaround:**
1. **If exchange is down/degraded:**
   - **Option A:** Pause trading on affected exchange
     - Keep other exchanges running (e.g., pause Upbit, continue Binance)
   - **Option B:** Reduce trade frequency
     - Increase loop interval (e.g., 1s → 5s) to reduce API load
   - **Option C:** Use cached orderbook (if < 10s stale)
     - Risk: Stale data may cause bad entries

2. **If rate limit hit:**
   - Wait for rate limit reset (usually 1 minute window)
   - Reduce API call frequency:
     - Disable non-critical calls (e.g., reduce balance checks)
     - Batch multiple requests if API supports

3. **If authentication failed:**
   - Rotate API keys (if backup keys available)
   - Contact exchange support for key verification

4. **If specific symbol issue:**
   - Remove symbol from universe temporarily
   - Example: Disable BTC-KRW if under maintenance

---

**Escalation Criteria & Channel:**
- **Escalate to P1 (immediate)** if:
  - All exchanges down (complete trading stop)
  - Single exchange down for > 10 minutes AND no alternative available
  - Authentication issue affecting all API keys
- **Escalation Channel:**
  - Telegram: Notify on-call + team lead
  - Slack: #alerts-critical + #exchange-status channels
  - Create incident ticket with exchange name + error codes

---

**Postmortem Notes:**
- **Root Cause:** Exchange outage vs client-side issue
- **Impact:** Downtime duration, missed trades, lost opportunities
- **Prevention:**
  - Multi-exchange support (reduce single point of failure)
  - Improved rate limit management (pre-emptive throttling)
  - Health check improvements (faster detection, auto-recovery)
- **Action Items:**
  - Review exchange SLA contracts
  - Implement circuit breaker for failing exchanges
  - Add exchange redundancy (e.g., 3+ exchanges)

---

### 3.3 Guard Trigger Spike (RiskGuard)

#### Scenario: Guard Trigger Spike

**Description:** RiskGuard (Exchange/Route/Symbol/Global/CrossExchange tier) is triggering abnormally frequently, blocking or throttling trades.

---

**Trigger Signals:**
- **Alert:** `alert_sent_total{rule_id="RG-005", severity="P2"}` increases
- **Metrics:**
  - `arb_topn_guard_triggers_total{guard_type=~".*"}` spikes (> 3x baseline)
  - `arb_topn_trades_total{trade_type="entry"}` drops
  - `arb_topn_win_rate` may drop if guards are too conservative
- **Grafana Panels:**
  - Core Dashboard: **Guard Triggers** (Panel 9) → breakdown by `guard_type`
  - Core Dashboard: **Trade Rate** (Panel 3) → compare to baseline

---

**First Checks (0-5 minutes):**
1. **Identify guard type(s) triggering**
   ```promql
   topk(5, rate(arb_topn_guard_triggers_total[5m]))
   ```
   - Which guard_type is most frequent? (exchange, route, symbol, global, cross_exchange)

2. **Check if trading is blocked or just throttled**
   - Blocked: `arb_topn_trades_total` = 0 for > 5 minutes
   - Throttled: Trade rate reduced but not zero

3. **Check PnL impact**
   - Is PnL dropping? (legitimate risk event)
   - Is PnL stable? (false positive, overly conservative guards)

4. **Check market conditions**
   - Are spreads collapsing? (low opportunity → guards rightly blocking)
   - Is volatility spiking? (high risk → guards rightly blocking)

---

**Root Cause Narrowing (5-15 minutes):**
1. **For `guard_type="exchange"`:**
   - Check exchange health: `exchange_health_status{exchange}` = 0?
   - Check API error rate: `exchange_api_error_total` increasing?
   - Likely cause: Exchange degraded (slow API, high error rate)

2. **For `guard_type="route"`:**
   - Check ArbRoute health: `arb_route_health_score{route}` < threshold?
   - Check spread: Is spread too narrow? (< min_spread_bps)
   - Likely cause: Poor market conditions for this route

3. **For `guard_type="symbol"`:**
   - Check symbol-specific metrics: volume, spread, last_trade_time
   - Is symbol illiquid? (volume < min_volume_24h)
   - Likely cause: Symbol-specific issue (low liquidity, delisting)

4. **For `guard_type="global"`:**
   - Check global risk limits: total exposure, position count, daily PnL
   - Are we hitting max_position_count or max_total_exposure?
   - Likely cause: Risk limits reached (may be intentional)

5. **For `guard_type="cross_exchange"`:**
   - Check FX rate: Is FX stale or unavailable?
   - Check inventory imbalance: `cross_exchange_inventory_imbalance` > threshold?
   - Likely cause: FX issue or inventory imbalance

---

**Mitigation / Workaround:**
1. **If guards are CORRECT (legitimate risk):**
   - **NO ACTION NEEDED** → Guards are protecting capital
   - Monitor for market recovery
   - Document event for post-trade analysis

2. **If guards are OVERLY CONSERVATIVE (false positives):**
   - **Option A (Temporary):** Adjust guard thresholds
     - Example: Increase min_spread_bps (100 → 50) if spreads are tight but safe
     - Example: Increase fx_staleness_threshold (10s → 30s) if FX provider is slow
     - **CAUTION:** Only adjust if you understand the risk
   - **Option B:** Disable specific guard temporarily (RISKY)
     - Example: Disable route guard for specific route if confident it's safe
     - **MUST re-enable after incident**
   - **Option C:** Switch to backup strategy
     - Example: Disable CrossExchange, focus on single-exchange arbitrage

3. **If guards are due to CONFIGURATION ERROR:**
   - Review guard config: `configs/risk_guard.yml`
   - Common errors:
     - Threshold too strict (e.g., min_spread_bps = 200 when market norm is 150)
     - Incorrect FX staleness threshold (e.g., 5s when provider updates every 10s)
   - Fix config + restart engine (or hot-reload if supported)

---

**Escalation Criteria & Channel:**
- **Escalate to P2 (< 30min)** if:
  - Guards blocking trades for > 15 minutes
  - Unable to determine if guards are correct or false positives
  - Need risk management approval to adjust thresholds
- **Escalation Channel:**
  - Telegram: Notify on-call + risk manager
  - Slack: #alerts-risk channel
  - Create ticket for guard config review

---

**Postmortem Notes:**
- **Root Cause:** Legitimate risk vs false positive vs config error
- **Impact:** Missed trades, opportunity cost
- **Prevention:**
  - Fine-tune guard thresholds based on historical data
  - Implement adaptive thresholds (ML-based or time-of-day based)
  - Add guard override mechanism (with audit trail)
- **Action Items:**
  - Review guard trigger logs for patterns
  - Backtest guard thresholds against historical market data
  - Add guard effectiveness metrics (how often guards prevent losses)

---

### 3.4 Notifier Down (Telegram/Slack/Email)

#### Scenario: Notifier Down

**Description:** One or more alert notifiers (Telegram, Slack, Email) are unavailable or failing to deliver alerts.

---

**Trigger Signals:**
- **Alert:** `alert_sent_total{rule_id="NT-001", severity="P2"}` (notifier health check)
- **Metrics:**
  - `notifier_available{notifier="telegram"}` = 0 (unavailable)
  - `alert_failed_total{notifier="telegram", reason="timeout"}` increases
  - `alert_fallback_total{from_notifier="telegram", to_notifier="slack"}` increases
- **Grafana Panels:**
  - Alerting Overview: **Notifier Availability** (Panel 5)
  - Alerting Overview: **Alert Failed by Notifier & Reason** (Panel 4)
  - Alerting Overview: **Alert Fallback** (Panel 7)

---

**First Checks (0-5 minutes):**
1. **Confirm which notifier(s) are down**
   ```promql
   notifier_available{notifier=~"telegram|slack|email"} == 0
   ```

2. **Check if alerts are being delivered via fallback**
   - Is `alert_sent_total{notifier="slack"}` increasing? (fallback working)
   - Is `alert_dlq_total` increasing? (fallback also failed)

3. **Check if trading is affected**
   - **KEY POINT:** Notifier failure does NOT stop trading
   - Trading engine continues running
   - Only alert delivery is impacted

4. **Check Local Log notifier (always-on fallback)**
   - Local Log always works (writes to file)
   - Review: `logs/alert_local.log` for recent alerts

---

**Root Cause Narrowing (5-15 minutes):**
1. **For Telegram:**
   - Check Telegram Bot API status: https://status.telegram.org/
   - Test bot manually: Send `/start` to bot, check response
   - Check bot token validity: Use `getMe` API call
   - Check network: Can bot reach `api.telegram.org`?
   - Look for error messages in logs:
     ```bash
     grep -i "telegram.*error" logs/alerting.log | tail -20
     ```
   - Common errors:
     - 401 Unauthorized: Invalid bot token
     - 403 Forbidden: Bot blocked by user
     - 429 Too Many Requests: Rate limit hit
     - Timeout: Network issue or Telegram API slow

2. **For Slack:**
   - Check Slack API status: https://status.slack.com/
   - Test webhook manually: `curl -X POST <webhook_url> -d '{"text":"test"}'`
   - Check webhook URL validity (not expired/revoked)
   - Look for error messages in logs (similar to Telegram)

3. **For Email:**
   - Check SMTP server status (if self-hosted)
   - Test email send manually (use `telnet` or email client)
   - Check credentials (SMTP username/password)
   - Look for error messages: SMTP errors, DNS resolution failures

---

**Mitigation / Workaround:**
1. **If primary notifier is down:**
   - **Option A:** Rely on fallback notifier (already automatic)
     - Example: Telegram down → Slack receives alerts
     - Verify fallback is working: Check `alert_sent_total{notifier="slack"}`
   - **Option B:** Switch primary notifier temporarily
     - Update config: `primary_notifier: "slack"` (from "telegram")
     - Restart alert dispatcher (or hot-reload config)
   - **Option C:** Use Local Log as last resort
     - Monitor `logs/alert_local.log` manually
     - Set up log monitoring tool (e.g., `tail -f logs/alert_local.log`)

2. **If all notifiers are down (DLQ increasing):**
   - **CRITICAL:** Manually monitor Grafana dashboards
   - Set up SMS alerts (if available) as emergency backup
   - Consider paging on-call engineer directly

3. **If rate limit hit (429 errors):**
   - Reduce alert frequency (temporary)
   - Enable alert aggregation (batch multiple alerts)
   - Wait for rate limit reset (usually 1 minute)

---

**Escalation Criteria & Channel:**
- **Escalate to P2 (< 30min)** if:
  - Primary notifier down for > 10 minutes
  - Fallback notifier also failing
  - DLQ count > 5 (multiple alerts lost)
- **Escalation Channel:**
  - Phone call (if notifier is down, can't rely on Telegram/Slack!)
  - Email (if email notifier is still working)
  - Create incident ticket

---

**Postmortem Notes:**
- **Root Cause:** Service outage vs auth issue vs rate limit vs network
- **Impact:** Missed alert notifications (but trading continued)
- **Prevention:**
  - Multi-notifier redundancy (primary + fallback + DLQ)
  - Health check for notifiers (proactive detection)
  - Rate limit management (throttle alerts if approaching limit)
- **Action Items:**
  - Review notifier SLA
  - Add more fallback notifiers (e.g., SMS, PagerDuty)
  - Implement alert batching/aggregation

---

### 3.5 Dead Letter Queue (DLQ) Increase

#### Scenario: DLQ Increase

**Description:** Alerts are failing to deliver even after retry + fallback, and are being sent to DLQ (dead letter queue).

---

**Trigger Signals:**
- **Alert:** `alert_sent_total{rule_id="DLQ-001", severity="P2"}` (DLQ monitor)
- **Metrics:**
  - `alert_dlq_total{rule_id, reason}` > 0 (ANY DLQ entry is critical)
  - `alert_retry_total{rule_id}` high (many retries before DLQ)
  - `alert_fallback_total` high (fallback attempts failed)
- **Grafana Panels:**
  - Alerting Overview: **Dead Letter Queue (DLQ)** (Panel 9) → RED if > 0
  - Alerting Overview: **Alert Retry** (Panel 8)
  - Alerting Overview: **Alert Fallback** (Panel 7)

---

**First Checks (0-5 minutes):**
1. **Check DLQ count and reasons**
   ```promql
   alert_dlq_total{rule_id, reason}
   ```
   - Group by `reason`: What's the most common failure reason?
     - `timeout`: Notifier not responding
     - `connection_refused`: Notifier service down
     - `auth_failed`: Invalid credentials
     - `rate_limit`: Too many requests
     - `invalid_format`: Alert payload malformed

2. **Check which alerts are in DLQ**
   - Which `rule_id` values are in DLQ?
   - Are they critical (P1) or informational (P3)?
   - **P1 alerts in DLQ = CRITICAL** (must investigate immediately)

3. **Check if notifiers are currently down**
   - See Section 3.4 (Notifier Down) for notifier health check

4. **Check DLQ storage**
   - Where are DLQ alerts stored? (Redis, PostgreSQL, file?)
   - Can we manually retrieve and reprocess them?

---

**Root Cause Narrowing (5-15 minutes):**
1. **For `reason="timeout"`:**
   - All notifiers slow/unresponsive
   - Likely: Network issue, notifier API overloaded
   - Check network latency: Ping notifier endpoints

2. **For `reason="auth_failed"`:**
   - Invalid bot token, webhook URL, or SMTP credentials
   - Likely: Credentials expired or revoked
   - Test auth manually (see Section 3.4)

3. **For `reason="rate_limit"`:**
   - Hit rate limit on all notifiers (primary + fallback)
   - Likely: Alert storm (too many alerts in short time)
   - Check alert volume: `rate(alert_sent_total[1m])` > normal?

4. **For `reason="invalid_format"`:**
   - Alert payload is malformed (bug in alert generation)
   - Review alert payload in logs:
     ```bash
     grep -i "dlq" logs/alerting.log | tail -10
     ```
   - Check for JSON encoding errors, missing fields, etc.

5. **For `reason="connection_refused"`:**
   - Notifier service is down or firewall blocking
   - Ping notifier IP, check firewall rules

---

**Mitigation / Workaround:**
1. **If DLQ due to notifier down:**
   - Fix notifier issue first (see Section 3.4)
   - Then manually reprocess DLQ alerts:
     - If using Redis: Retrieve DLQ list, re-enqueue
     - If using PostgreSQL: Query DLQ table, update status to "pending"
     - If using file: Parse DLQ file, re-send manually

2. **If DLQ due to rate limit:**
   - **Option A:** Wait for rate limit reset (usually 1 minute)
   - **Option B:** Reduce alert volume
     - Enable alert throttling (e.g., max 10 alerts/min)
     - Enable alert aggregation (combine similar alerts)
   - **Option C:** Reprocess DLQ after rate limit resets

3. **If DLQ due to auth failure:**
   - Rotate credentials (bot token, webhook URL, SMTP password)
   - Update config with new credentials
   - Restart alert dispatcher
   - Reprocess DLQ with new credentials

4. **If DLQ due to invalid format (BUG):**
   - **CRITICAL:** This is a code bug, not operational issue
   - Capture DLQ payload for debugging
   - Create bug ticket with logs + payload
   - Temporary workaround: Disable problematic alert rule (if non-critical)

---

**Escalation Criteria & Channel:**
- **Escalate to P2 (immediate)** if:
  - ANY P1 alert in DLQ (high-priority notifications lost)
  - DLQ count > 10 (systematic issue, not transient failure)
  - DLQ reason = "invalid_format" (code bug)
- **Escalation Channel:**
  - Telegram: Notify on-call + team lead (if notifier working)
  - Phone call: If Telegram is down (emergency contact)
  - Create incident ticket with DLQ details

---

**Postmortem Notes:**
- **Root Cause:** Notifier failure vs rate limit vs auth vs bug
- **Impact:** Lost alert notifications (severity depends on alert priority)
- **Prevention:**
  - Improve retry logic (exponential backoff, longer retry window)
  - Add more fallback notifiers (reduce single point of failure)
  - Implement alert aggregation (reduce rate limit risk)
  - Add DLQ monitoring + auto-reprocessing
- **Action Items:**
  - Review DLQ logs for patterns
  - Implement DLQ dashboard (Grafana panel for DLQ count)
  - Add DLQ auto-replay (retry DLQ alerts after 5 minutes)

---

### 3.6 Latency / CPU / Memory Spike

#### Scenario: Latency / CPU / Memory Spike

**Description:** System performance degradation (high loop latency, CPU usage, or memory consumption), potentially affecting trading.

---

**Trigger Signals:**
- **Alert:** `alert_sent_total{rule_id="PERF-001", severity="P2"}`
- **Metrics:**
  - `arb_topn_loop_latency_seconds{quantile="0.99"}` > threshold (e.g., > 100ms)
  - `arb_topn_cpu_usage_percent` > 80%
  - `arb_topn_memory_usage_bytes` > 80% of available
- **Grafana Panels:**
  - Core Dashboard: **Loop Latency (p95/p99)** (Panel 6)
  - Core Dashboard: **CPU Usage (%)** (Panel 7)
  - Core Dashboard: **Memory Usage (bytes)** (Panel 8)

---

**First Checks (0-5 minutes):**
1. **Identify which resource is spiking**
   - Latency only? (network/API issue)
   - CPU only? (compute-heavy operation)
   - Memory only? (memory leak or large data structure)
   - All three? (systemic overload)

2. **Check if trading is affected**
   - Is trade rate dropping?
   - Is PnL affected?
   - Are guards triggering due to latency?

3. **Check for recent changes**
   - Recent deployment?
   - Config change?
   - Increased universe size (e.g., top20 → top50)?

4. **Check system load**
   - Use `top` or `htop` to see process list
   - Check for rogue processes consuming resources

---

**Root Cause Narrowing (5-15 minutes):**
1. **For high loop latency:**
   - **Check external API latency:**
     ```bash
     grep -i "api.*latency" logs/topn_arbitrage.log | tail -20
     ```
   - Are exchange APIs slow? (Upbit, Binance)
   - Is FX provider slow?
   - **Check orderbook cache:**
     - Is cache hit rate low? (forcing frequent API calls)
   - **Check WebSocket latency:**
     - Is WS reconnecting frequently?
     - Is WS message queue backed up?

2. **For high CPU usage:**
   - **Check profiling data (if available):**
     - Use `py-spy` or `cProfile` to identify hot spots
   - **Common causes:**
     - Too many symbols in universe (CPU-bound strategy calculation)
     - Inefficient algorithm (O(n²) instead of O(n log n))
     - Excessive logging (debug level in production)
   - **Check for infinite loops or deadlocks:**
     - Thread dump: `kill -SIGQUIT <pid>` (Python)

3. **For high memory usage:**
   - **Check memory growth over time:**
     - Is memory increasing steadily? (memory leak)
     - Is memory spiking then dropping? (large data structure, then GC)
   - **Common causes:**
     - Memory leak (objects not released)
     - Large orderbook cache (not evicting old data)
     - Large trade history (not truncating)
   - **Use memory profiler:**
     - `memory_profiler` or `tracemalloc` to find leaks

---

**Mitigation / Workaround:**
1. **For high loop latency:**
   - **Option A:** Increase loop interval (reduce frequency)
     - Example: 1s → 2s (halves API call rate)
   - **Option B:** Reduce universe size
     - Example: top50 → top20 (fewer symbols to process)
   - **Option C:** Optimize orderbook cache
     - Increase cache TTL (reduce API calls)
     - Use compression (reduce memory)

2. **For high CPU usage:**
   - **Option A:** Reduce universe size (fewer symbols = less compute)
   - **Option B:** Optimize strategy code
     - Profile hot spots, refactor inefficient loops
   - **Option C:** Scale horizontally
     - Run multiple instances (split symbols across instances)

3. **For high memory usage:**
   - **Option A:** Restart engine (temporary fix for memory leak)
   - **Option B:** Reduce cache size
     - Limit orderbook cache to N entries
     - Evict old data more aggressively
   - **Option C:** Increase system memory (if hardware allows)

---

**Escalation Criteria & Channel:**
- **Escalate to P2 (< 30min)** if:
  - Performance degradation for > 10 minutes
  - Trading significantly affected (> 50% trade rate drop)
  - Unable to identify root cause
- **Escalation Channel:**
  - Telegram: Notify on-call + performance engineer
  - Slack: #alerts-performance channel
  - Create ticket for performance investigation

---

**Postmortem Notes:**
- **Root Cause:** External latency vs code inefficiency vs memory leak
- **Impact:** Reduced trading performance, missed opportunities
- **Prevention:**
  - Continuous profiling (identify hot spots proactively)
  - Load testing (simulate high universe size)
  - Memory leak detection (automated tests)
- **Action Items:**
  - Optimize hot path code (O(n²) → O(n log n))
  - Implement circuit breaker for slow APIs
  - Add memory limits + auto-restart on high memory

---

### 3.7 Chaos/Fail-Safe Test Anomalies

#### Scenario: Chaos/Fail-Safe Test Anomalies

**Description:** During chaos testing (D80-12) or fail-safe validation, unexpected alerts or behaviors are detected.

---

**Trigger Signals:**
- **Alert:** `alert_sent_total{rule_id="CHAOS-*", severity="P3"}` (chaos test alerts)
- **Metrics:**
  - Chaos test metrics (if instrumented)
  - Alert pattern anomalies (e.g., fallback not working as expected)
- **Grafana Panels:**
  - Alerting Overview: **Alert Fallback** (Panel 7) → check fallback behavior
  - Alerting Overview: **Alert Retry** (Panel 8) → check retry logic

---

**First Checks (0-5 minutes):**
1. **Confirm this is a test environment**
   - Check `$env` variable: Should be "local_dev" or "test", NOT "live"
   - **If live environment:** ESCALATE IMMEDIATELY (chaos test should NOT run in live)

2. **Identify which chaos scenario is running**
   - Check chaos test script logs
   - Common scenarios:
     - Notifier down simulation
     - Network partition simulation
     - High latency simulation
     - Message drop simulation

3. **Check if fail-safe mechanisms are working**
   - Retry: Are alerts being retried?
   - Fallback: Are alerts falling back to secondary notifier?
   - DLQ: Are failed alerts going to DLQ?

4. **Check if trading is affected**
   - **KEY POINT:** Chaos tests should NOT affect trading logic
   - If trading is affected, STOP TEST immediately

---

**Root Cause Narrowing (5-15 minutes):**
1. **If chaos test is behaving unexpectedly:**
   - Review chaos test design (D80-12 design doc)
   - Check test parameters (e.g., failure rate, duration)
   - Look for test bugs (incorrect fault injection)

2. **If fail-safe mechanisms are NOT working:**
   - **Retry not working:**
     - Check retry count: Are alerts being retried 3x?
     - Check retry backoff: Is backoff exponential?
   - **Fallback not working:**
     - Check fallback chain config: Is fallback notifier configured?
     - Check fallback trigger condition: Is primary notifier marked as down?
   - **DLQ not working:**
     - Check DLQ storage: Are failed alerts being written to DLQ?
     - Check DLQ threshold: Are we hitting max retries before DLQ?

3. **If alerts are missing or duplicated:**
   - Check for race conditions (concurrent alert processing)
   - Check for idempotency issues (alert sent twice)

---

**Mitigation / Workaround:**
1. **If chaos test is in live environment (CRITICAL):**
   - **STOP TEST IMMEDIATELY**
   - Restore normal operation
   - Escalate to P1 (unintended production impact)

2. **If chaos test reveals fail-safe bug:**
   - **Document bug** with logs + metrics
   - Create high-priority bug ticket
   - Continue test to gather more data (if safe)
   - Stop test if bug is critical (e.g., alerts lost)

3. **If chaos test is working as designed:**
   - **NO ACTION NEEDED** (test is successful)
   - Document test results
   - Review test coverage (are we testing all failure modes?)

---

**Escalation Criteria & Channel:**
- **Escalate to P1 (immediate)** if:
  - Chaos test running in live environment (unintended)
  - Chaos test affecting real trading
- **Escalate to P3 (normal hours)** if:
  - Chaos test reveals minor bug (non-critical)
  - Fail-safe mechanism not working as expected (test environment only)
- **Escalation Channel:**
  - Telegram: Notify test coordinator + on-call
  - Create bug ticket with test logs

---

**Postmortem Notes:**
- **Root Cause:** Test bug vs fail-safe bug vs test design issue
- **Impact:** None (test environment) or critical (if live environment affected)
- **Prevention:**
  - Enforce test environment checks (prevent chaos tests in live)
  - Improve test coverage (add more failure scenarios)
  - Automate chaos tests (run regularly, not manually)
- **Action Items:**
  - Fix identified fail-safe bugs
  - Update chaos test suite with new scenarios
  - Document lessons learned in design doc

---

## 4. Escalation Policy

### 4.1 Escalation Matrix

| Alert Priority | Initial Response | 1st Escalation (if unresolved) | 2nd Escalation | 3rd Escalation |
|----------------|------------------|--------------------------------|----------------|----------------|
| **P1 (Critical)** | On-call engineer (< 5min) | Team lead (< 10min) | SRE lead (< 20min) | CTO (< 30min) |
| **P2 (High)** | On-call engineer (< 30min) | Team lead (< 1 hour) | SRE lead (< 2 hours) | - |
| **P3 (Medium)** | On-call engineer (< 2 hours) | Team lead (next business day) | - | - |

---

### 4.2 Escalation Channels (by Priority)

**P1 (Critical):**
1. **Telegram:** Instant notification to on-call engineer
2. **Phone Call:** If no ACK within 5 minutes
3. **Slack:** Post to #alerts-critical channel (team-wide awareness)
4. **Email:** Send to team lead + SRE lead
5. **Incident Ticket:** Create high-priority ticket with all context

**P2 (High):**
1. **Telegram:** Notification to on-call engineer
2. **Slack:** Post to #alerts-high channel
3. **Incident Ticket:** Create normal-priority ticket
4. **Email:** Send daily digest to team (if multiple P2 alerts)

**P3 (Medium):**
1. **Email:** Daily or weekly digest
2. **Slack:** Post to #alerts-info channel (low priority)
3. **Ticket:** Create low-priority ticket for backlog

---

### 4.3 On-call Rotation (Template)

**NOTE:** Update this table with actual team members and schedules.

| Week | Primary On-call | Backup On-call | SRE Lead |
|------|-----------------|----------------|----------|
| Week 1 | Engineer A | Engineer B | SRE Lead X |
| Week 2 | Engineer B | Engineer C | SRE Lead X |
| Week 3 | Engineer C | Engineer A | SRE Lead Y |
| Week 4 | Engineer A | Engineer B | SRE Lead Y |

**On-call Responsibilities:**
- Monitor Grafana dashboards (passive monitoring via alerts)
- Respond to P1/P2 alerts within SLA
- Perform daily checklist (see Monitoring Runbook Section 3.1)
- Escalate when necessary (see Section 4.1)
- Document incidents (see Section 5)

---

## 5. Incident Documentation

### 5.1 Incident Log Template

For every P1/P2 incident, create an incident log using this template:

```markdown
# Incident Log: <Incident Title>

**Incident ID:** INC-YYYY-MM-DD-NNN  
**Date/Time:** YYYY-MM-DD HH:MM:SS UTC  
**Severity:** P1 / P2 / P3  
**Status:** Investigating / Mitigated / Resolved  
**On-call Engineer:** <Name>

---

## Summary
- **What happened:** Brief description (1-2 sentences)
- **Impact:** Trading stopped / Degraded / Alert failure / etc.
- **Duration:** Start time → End time (total: X minutes)

---

## Timeline
- **HH:MM:** Alert triggered (rule_id: XXX)
- **HH:MM:** Incident confirmed by on-call engineer
- **HH:MM:** Root cause identified: <cause>
- **HH:MM:** Mitigation applied: <action>
- **HH:MM:** Incident resolved

---

## Root Cause
- **Immediate Cause:** <technical cause>
- **Contributing Factors:** <environmental, config, code, etc.>

---

## Resolution
- **Mitigation:** <temporary fix applied>
- **Permanent Fix:** <long-term fix, if different from mitigation>

---

## Metrics
- **PnL Impact:** $XXX lost (or no impact)
- **Missed Trades:** N trades
- **Downtime:** X minutes
- **Alert Success Rate:** Y% (during incident)

---

## Action Items
- [ ] Fix root cause (ticket: PROJ-123)
- [ ] Update monitoring thresholds (ticket: PROJ-124)
- [ ] Improve runbook (ticket: PROJ-125)

---

## Lessons Learned
- <what went well>
- <what could be improved>
- <preventive measures>
```

---

### 5.2 Postmortem Process

**When to conduct postmortem:**
- ALL P1 incidents (mandatory)
- P2 incidents with significant impact (>$100 PnL loss, >30min downtime)
- P3 incidents with recurring pattern (3+ times in 7 days)

**Postmortem Steps:**
1. **Schedule meeting** (within 24-48 hours of incident resolution)
2. **Invite attendees:** On-call engineer, team lead, relevant SMEs
3. **Review timeline:** Use incident log as reference
4. **Identify root cause:** Use 5-Whys or fishbone diagram
5. **Create action items:** Assign owners + deadlines
6. **Document lessons learned:** Update runbook + playbook
7. **Follow up:** Track action items to completion

---

## 6. Playbook Maintenance

### 6.1 When to Update This Playbook

- **New Alert Rule:** Add new scenario section (Section 3.X)
- **New Notifier:** Update Section 3.4 (Notifier Down)
- **New Guard Type:** Update Section 3.3 (Guard Trigger Spike)
- **Incident Postmortem:** Add lessons learned to relevant scenario
- **Team Changes:** Update Section 4.3 (On-call Rotation)
- **Threshold Changes:** Update scenario trigger signals

---

### 6.2 Playbook Review Schedule

- **Weekly:** Review recent incidents, update action items
- **Monthly:** Review all scenarios, update thresholds
- **Quarterly:** Major review, incorporate postmortem findings
- **After Major Release:** Review all scenarios, test procedures

---

### 6.3 Related Documents to Keep in Sync

- **Monitoring Runbook:** Daily checklists, thresholds
- **RUNBOOK.md:** General system operations
- **TROUBLESHOOTING.md:** Detailed debugging guides
- **D80-7 Alerting System Design:** Alert rules, routing logic
- **D76 Alert Rule Engine Design:** Rule definitions, priority model

---

## 7. Quick Reference

### 7.1 Common Alert Rules (Rule IDs)

| Rule ID | Description | Severity | Common Cause |
|---------|-------------|----------|--------------|
| **FX-001** | FX Provider Down | P1 | FX API outage, network issue |
| **EX-001** | Exchange API Error | P1 | Exchange outage, rate limit |
| **RG-005** | Guard Trigger Spike | P2 | Market volatility, config issue |
| **NT-001** | Notifier Health Check | P2 | Notifier service down |
| **DLQ-001** | DLQ Count Increase | P2 | Notifier failure, auth issue |
| **PERF-001** | Latency Spike | P2 | API slow, system overload |
| **CHAOS-*** | Chaos Test Alert | P3 | Chaos testing (test env only) |

---

### 7.2 Emergency Commands (if CLI available)

```bash
# Pause trading (emergency stop)
./cli.sh pause-trading

# Resume trading
./cli.sh resume-trading

# Disable specific exchange
./cli.sh disable-exchange --exchange upbit

# Switch FX provider
./cli.sh set-fx-provider --provider upbit

# Restart alert dispatcher
./cli.sh restart-alerting

# Check system health
./cli.sh health-check

# Reprocess DLQ alerts
./cli.sh reprocess-dlq --limit 10
```

**NOTE:** Adjust commands based on actual CLI implementation.

---

### 7.3 Log Analysis Commands

```bash
# Check recent alerts
tail -f logs/alert_local.log

# Search for errors
grep -i "error" logs/topn_arbitrage.log | tail -50

# Count alerts by severity
grep -oP 'severity="\K\w+' logs/alerting.log | sort | uniq -c

# Check FX provider errors
grep -i "fx.*error" logs/topn_arbitrage.log | tail -20

# Check guard triggers
grep -i "guard.*trigger" logs/topn_arbitrage.log | tail -20

# Check notifier failures
grep -i "notifier.*failed" logs/alerting.log | tail -20
```

---

**END OF ALERTING PLAYBOOK**

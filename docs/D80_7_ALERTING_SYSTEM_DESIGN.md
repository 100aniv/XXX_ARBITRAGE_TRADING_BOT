# D80-7: Alerting System Design

**Status:** PLANNED  
**Author:** Arbitrage Bot Team  
**Date:** 2024-12-02  
**Version:** 1.0

---

## 1. Motivation

### 1.1 Background

D80-6에서 Prometheus + Grafana 모니터링 스택을 구축했으나, **실시간 알림(Alerting)** 기능이 없어 다음과 같은 문제가 있습니다:

**현재 문제점:**
- ❌ **FX Source Down**: 거래소 WebSocket 연결 끊김을 즉시 알 수 없음
- ❌ **FX Rate Anomaly**: 환율 이상 감지 시 수동 확인 필요
- ❌ **Executor Error**: 주문 실행 실패를 실시간으로 파악 불가
- ❌ **RiskGuard Trigger**: Circuit breaker 발동 시 알림 없음
- ❌ **WebSocket Staleness**: 오래된 데이터로 거래하는 위험
- ❌ **Manual Monitoring**: Grafana 대시보드를 수동으로 확인해야 함

**필요성:**
1조 원급 시스템에서는 **Institutional-grade Alerting**이 필수입니다:
- **즉각적인 대응**: P1 장애 발생 시 5분 이내 인지 및 대응
- **다채널 알림**: Telegram (주 채널) + Slack (선택)
- **심각도 분류**: P1 (Critical) / P2 (Warning) / P3 (Info)
- **Alert Throttling**: 중복 알림 방지 (동일 알림 5분 내 1회만)
- **Alert Aggregation**: 관련 알림 묶어서 전송 (노이즈 감소)

### 1.2 Goals

**Primary Goals:**
- ✅ Telegram 기반 실시간 알림 시스템 구축
- ✅ FX, Executor, RiskGuard, WebSocket 이상 감지 및 알림
- ✅ 심각도 분류 (P1/P2/P3) 및 알림 throttling
- ✅ Redis 기반 Alert Queue (live 모드용)
- ✅ Slack 연동 (선택적)

**Secondary Goals:**
- ✅ Alert 이력 저장 및 조회 (DB 연동)
- ✅ Alert 대시보드 (Grafana 통합)
- ✅ Alert 테스트 및 시뮬레이션 도구

---

## 2. Requirements

### 2.1 Functional Requirements

#### FR-1: Alert 생성 및 전송
- Alert는 `AlertManager`를 통해 생성되며, severity/source/message를 포함
- Telegram/Slack Notifier를 통해 실시간 전송
- Alert 생성 시 자동으로 timestamp, alert_id 부여

#### FR-2: Severity 분류
- **P1 (Critical)**: 즉시 대응 필요 (예: FX source 모두 down, Circuit breaker 발동)
- **P2 (Warning)**: 주의 필요 (예: FX source 1개 down, Executor error)
- **P3 (Info)**: 정보성 알림 (예: WebSocket reconnect 성공)

#### FR-3: Alert Rules

| Rule ID | Trigger Condition | Severity | Message |
|---------|-------------------|----------|---------|
| **FX-001** | FX source down > 30s | P2 | `[FX] {source} connection lost (>30s)` |
| **FX-002** | All FX sources down | P1 | `[FX] ALL SOURCES DOWN - Critical` |
| **FX-003** | FX median deviation > 5% | P1 | `[FX] Median rate deviation >5%: {details}` |
| **FX-004** | FX rate staleness > 60s | P2 | `[FX] Rate staleness >60s: {source}` |
| **EX-001** | Executor order error | P2 | `[Executor] Order failed: {reason}` |
| **EX-002** | Executor rollback | P2 | `[Executor] Rollback: {reason}` |
| **RG-001** | RiskGuard circuit breaker | P1 | `[RiskGuard] Circuit breaker triggered: {reason}` |
| **RG-002** | RiskGuard exposure limit | P2 | `[RiskGuard] Exposure limit hit: {current}/{limit}` |
| **WS-001** | WebSocket staleness > 60s | P2 | `[WS] Data staleness >60s: {source}` |
| **WS-002** | WebSocket reconnect failed | P2 | `[WS] Reconnect failed: {source}` |

#### FR-4: Alert Throttling
- 동일 `alert_key` (rule_id + source)에 대해 5분 내 1회만 전송
- Redis 기반 throttling state 관리
- Throttling 중인 알림은 카운트만 증가 (배치 전송)

#### FR-5: Alert Aggregation
- 관련 알림을 묶어서 전송 (예: FX source 3개 동시 down → 1개 알림)
- 30초 window 내 동일 카테고리 알림 aggregation
- Aggregated 알림은 summary + detail 포함

#### FR-6: Alert Queue (Redis-backed)
- Live 모드에서는 Redis Queue를 통해 비동기 전송
- Paper 모드에서는 In-memory Queue 사용
- Queue consumer는 별도 스레드에서 실행

#### FR-7: Alert History
- 모든 알림은 DB에 저장 (PostgreSQL `alerts` 테이블)
- Alert 조회 API: `get_alerts(severity, source, start_time, end_time)`
- Alert 통계: 일별/주별 알림 횟수, severity별 분포

### 2.2 Non-Functional Requirements

#### NFR-1: Performance
- Alert 생성 → 전송 latency < 3초 (P1), < 10초 (P2/P3)
- Throttling check latency < 50ms (Redis 조회)
- Queue throughput ≥ 100 alerts/sec

#### NFR-2: Reliability
- Alert 전송 실패 시 재시도 (exponential backoff, max 3회)
- Queue persistence (Redis AOF/RDB)
- Network 장애 시 local buffering (메모리 큐)

#### NFR-3: Maintainability
- Alert rule 추가/수정 용이 (YAML config 기반)
- Test mode (Telegram/Slack dry-run)
- Alert simulation tool (테스트용 alert 생성)

#### NFR-4: Security
- Telegram/Slack bot token은 환경변수/Vault에서 관리
- Alert message에 민감 정보 제외 (API key, password 등)
- Rate limiting (Telegram API 30 msg/sec)

---

## 3. Architecture

### 3.1 System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Arbitrage Bot Core                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ FX Layer │  │ Executor │  │RiskGuard │  │ WS Layer │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │              │         │
│       └─────────────┴──────────────┴──────────────┘         │
│                           │                                 │
│                    ┌──────▼──────┐                         │
│                    │AlertManager │  ← Alert 생성 및 라우팅  │
│                    └──────┬──────┘                         │
│                           │                                 │
│           ┌───────────────┼───────────────┐               │
│           │               │               │               │
│      ┌────▼────┐    ┌─────▼─────┐   ┌────▼────┐         │
│      │Throttler│    │Aggregator │   │  Queue  │         │
│      └────┬────┘    └─────┬─────┘   └────┬────┘         │
│           │               │               │               │
│           └───────────────┴───────────────┘               │
│                           │                                 │
│                   ┌───────▼───────┐                       │
│                   │  Notifiers    │                       │
│                   ├───────────────┤                       │
│                   │ Telegram      │                       │
│                   │ Slack         │                       │
│                   │ (Future: SMS) │                       │
│                   └───────┬───────┘                       │
└───────────────────────────┼───────────────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  External APIs  │
                   ├─────────────────┤
                   │ Telegram Bot    │
                   │ Slack Webhook   │
                   └─────────────────┘
```

### 3.2 Components

#### 3.2.1 AlertManager (Core)
**책임:**
- Alert 생성 및 메타데이터 부여 (alert_id, timestamp, severity)
- Rule-based alert 생성 (rule_id → Alert 객체)
- Notifier 라우팅 (severity에 따라 Telegram/Slack 선택)
- Alert history DB 저장

**인터페이스:**
```python
class AlertManager:
    def __init__(self, notifiers: List[Notifier], config: AlertConfig):
        ...
    
    async def send_alert(
        self,
        rule_id: str,
        severity: AlertSeverity,
        source: str,
        message: str,
        metadata: Optional[Dict] = None
    ) -> Alert:
        """Alert 생성 및 전송"""
        ...
    
    async def send_alert_batch(self, alerts: List[Alert]) -> None:
        """Alert 배치 전송 (aggregation 후)"""
        ...
    
    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        source: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Alert]:
        """Alert 이력 조회"""
        ...
```

#### 3.2.2 Alert (Domain Model)
**필드:**
```python
@dataclass
class Alert:
    alert_id: str               # UUID
    rule_id: str                # "FX-001", "EX-001", etc.
    severity: AlertSeverity     # P1, P2, P3
    source: str                 # "binance_fx", "executor", etc.
    message: str                # Alert message
    metadata: Dict              # Additional context
    timestamp: datetime         # Created at
    sent_at: Optional[datetime] # Sent timestamp
    throttled: bool = False     # Throttling 여부
```

**AlertSeverity Enum:**
```python
class AlertSeverity(Enum):
    P1_CRITICAL = "P1"  # 🔴 Critical (즉시 대응)
    P2_WARNING = "P2"   # 🟠 Warning (주의 필요)
    P3_INFO = "P3"      # 🟢 Info (정보성)
```

#### 3.2.3 Notifier (Interface)
**책임:**
- Alert를 외부 채널로 전송 (Telegram, Slack, etc.)
- 전송 실패 시 재시도 로직
- Rate limiting 준수

**인터페이스:**
```python
class Notifier(ABC):
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Alert 전송 (성공: True, 실패: False)"""
        ...
    
    @abstractmethod
    async def send_batch(self, alerts: List[Alert]) -> List[bool]:
        """Alert 배치 전송"""
        ...
```

**구현체:**
1. **TelegramNotifier**: Telegram Bot API 사용
2. **SlackNotifier**: Slack Webhook 사용
3. **MockNotifier**: 테스트용 (stdout 출력)

#### 3.2.4 AlertThrottler
**책임:**
- 중복 알림 방지 (동일 alert_key 5분 내 1회)
- Redis 기반 throttling state 관리
- Throttling 통계 제공

**인터페이스:**
```python
class AlertThrottler:
    def __init__(self, redis_client: Redis, window_seconds: int = 300):
        ...
    
    async def should_send(self, alert_key: str) -> bool:
        """Alert 전송 여부 판단 (throttling check)"""
        ...
    
    async def mark_sent(self, alert_key: str) -> None:
        """Alert 전송 완료 마킹"""
        ...
    
    def get_stats(self) -> Dict:
        """Throttling 통계 (suppressed count, etc.)"""
        ...
```

#### 3.2.5 AlertAggregator
**책임:**
- 관련 알림 묶어서 전송 (30초 window)
- Aggregation 룰 관리 (category별)
- Summary + Detail 생성

**인터페이스:**
```python
class AlertAggregator:
    def __init__(self, window_seconds: int = 30):
        ...
    
    async def add_alert(self, alert: Alert) -> None:
        """Alert 추가 (aggregation buffer)"""
        ...
    
    async def flush(self) -> List[Alert]:
        """Aggregated alert 반환 (window 만료 시)"""
        ...
```

#### 3.2.6 AlertQueue (Redis-backed)
**책임:**
- Alert 비동기 전송 큐
- Live 모드: Redis Queue, Paper 모드: In-memory Queue
- Consumer 스레드 관리

**인터페이스:**
```python
class AlertQueue:
    def __init__(self, redis_client: Optional[Redis] = None):
        ...
    
    async def enqueue(self, alert: Alert) -> None:
        """Alert를 큐에 추가"""
        ...
    
    async def dequeue(self) -> Optional[Alert]:
        """Alert를 큐에서 꺼내기"""
        ...
    
    async def start_consumer(self, handler: Callable) -> None:
        """Consumer 시작 (별도 스레드)"""
        ...
```

---

## 4. Data Flow

### 4.1 Alert 생성 및 전송 Flow

```
[1] FX Layer detects anomaly
     ↓
[2] FX Layer calls AlertManager.send_alert(rule_id="FX-001", ...)
     ↓
[3] AlertManager creates Alert object (alert_id, timestamp, etc.)
     ↓
[4] AlertThrottler checks if should_send(alert_key)
     ├─ YES → Continue
     └─ NO  → Increment suppressed count, END
     ↓
[5] AlertAggregator adds alert (if aggregation enabled)
     ├─ Window not expired → Buffer
     └─ Window expired → Flush aggregated alerts
     ↓
[6] AlertQueue enqueues Alert
     ↓
[7] Queue consumer dequeues Alert
     ↓
[8] Notifier.send(alert)
     ├─ Success → Mark sent, save to DB
     └─ Fail → Retry (exponential backoff, max 3)
```

### 4.2 Example: FX Source Down Alert

```python
# FX Layer detects Binance WebSocket disconnected for >30s
if websocket_disconnected_duration > 30:
    await alert_manager.send_alert(
        rule_id="FX-001",
        severity=AlertSeverity.P2_WARNING,
        source="binance_fx",
        message="Binance FX WebSocket connection lost (>30s)",
        metadata={
            "disconnected_duration": websocket_disconnected_duration,
            "last_message_time": last_message_time.isoformat(),
        }
    )
```

**Telegram Message:**
```
🟠 [P2] FX Alert
━━━━━━━━━━━━━━━
📍 Source: binance_fx
⚠️ Binance FX WebSocket connection lost (>30s)
⏰ 2024-12-02 15:30:42 KST
━━━━━━━━━━━━━━━
Duration: 35.2s
Last Message: 2024-12-02 15:29:07
```

---

## 5. File Structure

```
arbitrage/
  alerting/
    __init__.py           # Module exports
    alert.py              # Alert dataclass, AlertSeverity enum
    alert_types.py        # Alert rule definitions (FX-001, EX-001, etc.)
    alert_manager.py      # AlertManager core
    notifier.py           # Notifier interface
    telegram_notifier.py  # TelegramNotifier implementation
    slack_notifier.py     # SlackNotifier implementation
    throttler.py          # AlertThrottler
    aggregator.py         # AlertAggregator
    queue.py              # AlertQueue (Redis/In-memory)
    config.py             # AlertConfig (YAML-based)

tests/
  test_d80_7_alert_manager.py        # AlertManager unit tests
  test_d80_7_telegram_notifier.py    # TelegramNotifier tests
  test_d80_7_throttler.py            # Throttler tests
  test_d80_7_aggregator.py           # Aggregator tests
  test_d80_7_integration.py          # End-to-end integration tests

configs/
  alert_rules.yaml      # Alert rule definitions (rule_id, severity, template)

docs/
  D80_7_ALERTING_SYSTEM_DESIGN.md     # This document
  D80_7_ALERTING_OPERATIONAL_GUIDE.md # Operational guide (TBD)
```

---

## 6. Configuration

### 6.1 Alert Rules Config (YAML)

**configs/alert_rules.yaml:**
```yaml
alert_rules:
  # FX Layer Alerts
  - rule_id: FX-001
    name: FX Source Down
    severity: P2
    category: fx
    condition: "source_down_duration > 30s"
    message_template: "{source} connection lost (>{duration}s)"
    metadata:
      - disconnected_duration
      - last_message_time
  
  - rule_id: FX-002
    name: All FX Sources Down
    severity: P1
    category: fx
    condition: "all_sources_down"
    message_template: "ALL FX SOURCES DOWN - Critical"
  
  - rule_id: FX-003
    name: FX Median Deviation
    severity: P1
    category: fx
    condition: "abs(median - expected) / expected > 0.05"
    message_template: "Median rate deviation >{threshold}%: {details}"
  
  # Executor Alerts
  - rule_id: EX-001
    name: Executor Order Error
    severity: P2
    category: executor
    condition: "order_failed"
    message_template: "Order failed: {reason}"
  
  # RiskGuard Alerts
  - rule_id: RG-001
    name: Circuit Breaker Triggered
    severity: P1
    category: risk_guard
    condition: "circuit_breaker_triggered"
    message_template: "Circuit breaker triggered: {reason}"
```

### 6.2 Notifier Config

**Environment Variables:**
```bash
# Telegram
TELEGRAM_BOT_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>

# Slack (Optional)
SLACK_WEBHOOK_URL=<webhook_url>

# Alert Settings
ALERT_THROTTLE_WINDOW_SECONDS=300  # 5분
ALERT_AGGREGATION_WINDOW_SECONDS=30  # 30초
ALERT_QUEUE_MAX_SIZE=10000
```

---

## 7. Integration Points

### 7.1 FX Layer Integration

**arbitrage/common/currency.py (MultiSourceFxRateProvider):**
```python
async def _update_median(self):
    # ... median calculation ...
    
    # Alert: FX source down
    for source, client in self._clients.items():
        if not client.is_connected():
            down_duration = time.time() - client.last_message_time
            if down_duration > 30:
                await self._alert_manager.send_alert(
                    rule_id="FX-001",
                    severity=AlertSeverity.P2_WARNING,
                    source=f"{source}_fx",
                    message=f"{source} connection lost (>{down_duration:.1f}s)",
                    metadata={"disconnected_duration": down_duration}
                )
    
    # Alert: All sources down
    if all(not client.is_connected() for client in self._clients.values()):
        await self._alert_manager.send_alert(
            rule_id="FX-002",
            severity=AlertSeverity.P1_CRITICAL,
            source="multi_source_fx",
            message="ALL FX SOURCES DOWN - Critical"
        )
    
    # Alert: Median deviation
    if abs(median - self._expected_rate) / self._expected_rate > 0.05:
        await self._alert_manager.send_alert(
            rule_id="FX-003",
            severity=AlertSeverity.P1_CRITICAL,
            source="multi_source_fx",
            message=f"Median rate deviation >5%: {median:.2f} (expected: {self._expected_rate:.2f})",
            metadata={"median": median, "expected": self._expected_rate}
        )
```

### 7.2 Executor Integration

**arbitrage/cross_exchange/executor.py:**
```python
async def execute_entry(self, signal: EntrySignal) -> CrossExecutionResult:
    try:
        # ... execution logic ...
    except Exception as e:
        # Alert: Executor error
        await self._alert_manager.send_alert(
            rule_id="EX-001",
            severity=AlertSeverity.P2_WARNING,
            source="executor",
            message=f"Order failed: {str(e)}",
            metadata={"signal": signal.to_dict(), "error": str(e)}
        )
        raise
```

### 7.3 RiskGuard Integration

**arbitrage/cross_exchange/risk_guard.py:**
```python
def check_can_enter(self, signal: EntrySignal) -> RiskDecision:
    # ... risk checks ...
    
    # Alert: Circuit breaker
    if self._circuit_breaker_active:
        await self._alert_manager.send_alert(
            rule_id="RG-001",
            severity=AlertSeverity.P1_CRITICAL,
            source="risk_guard",
            message=f"Circuit breaker triggered: {reason}",
            metadata={"reason": reason, "current_loss": current_loss}
        )
    
    # Alert: Exposure limit
    if decision.action == RiskAction.BLOCK and decision.reason == "exposure_limit":
        await self._alert_manager.send_alert(
            rule_id="RG-002",
            severity=AlertSeverity.P2_WARNING,
            source="risk_guard",
            message=f"Exposure limit hit: {current_exposure}/{limit}",
            metadata={"current_exposure": current_exposure, "limit": limit}
        )
```

---

## 8. Test Strategy

### 8.1 Unit Tests

**tests/test_d80_7_alert_manager.py:**
- `test_create_alert()`: Alert 생성 및 메타데이터 검증
- `test_send_alert_with_throttling()`: Throttling 동작 검증
- `test_send_alert_batch()`: Batch 전송 검증
- `test_get_alerts()`: Alert 이력 조회 검증

**tests/test_d80_7_telegram_notifier.py:**
- `test_send_telegram_alert()`: Telegram API 호출 검증 (mock)
- `test_telegram_retry_on_failure()`: 재시도 로직 검증
- `test_telegram_rate_limiting()`: Rate limiting 검증

**tests/test_d80_7_throttler.py:**
- `test_throttle_duplicate_alerts()`: 중복 알림 차단 검증
- `test_throttle_window_expiry()`: Throttle window 만료 검증
- `test_throttle_stats()`: 통계 수집 검증

**tests/test_d80_7_aggregator.py:**
- `test_aggregate_related_alerts()`: Alert aggregation 검증
- `test_aggregation_window()`: Aggregation window 검증
- `test_aggregation_summary()`: Summary 생성 검증

### 8.2 Integration Tests

**tests/test_d80_7_integration.py:**
- `test_fx_source_down_alert_e2e()`: FX source down → Telegram 전송 (E2E)
- `test_executor_error_alert_e2e()`: Executor error → Telegram 전송 (E2E)
- `test_risk_guard_circuit_breaker_alert_e2e()`: RiskGuard → Telegram 전송 (E2E)
- `test_alert_throttling_integration()`: Throttling 통합 검증
- `test_alert_aggregation_integration()`: Aggregation 통합 검증

### 8.3 Manual Tests

**Telegram Bot Setup:**
1. BotFather로 Telegram Bot 생성
2. Bot token 및 chat_id 획득
3. `.env` 파일에 설정 추가
4. Test script 실행:
   ```bash
   python scripts/test_telegram_alert.py
   ```

**Expected Output:**
```
🟢 [P3] Test Alert
━━━━━━━━━━━━━━━
📍 Source: test
ℹ️ This is a test alert from arbitrage-lite
⏰ 2024-12-02 15:30:00 KST
```

---

## 9. Operational Guide (Preview)

### 9.1 Alert Response Playbook

**P1 (Critical) Alerts:**
1. **FX-002 (All Sources Down)**:
   - 즉시 거래 중단
   - WebSocket 재시작 시도
   - 수동 환율 설정 또는 대기
   - 복구 후 거래 재개

2. **FX-003 (Median Deviation >5%)**:
   - 환율 이상 원인 조사 (Flash crash? API 오류?)
   - 필요 시 거래 중단
   - 환율 정상화 확인 후 재개

3. **RG-001 (Circuit Breaker)**:
   - 손실 원인 분석
   - RiskGuard 설정 검토
   - 수동 리셋 또는 대기 (cooldown)

**P2 (Warning) Alerts:**
1. **FX-001 (Source Down >30s)**:
   - 다른 소스로 fallback 확인
   - 연결 재시도 모니터링
   - 장기 장애 시 소스 제외 고려

2. **EX-001 (Executor Error)**:
   - 주문 실패 원인 확인 (잔액? API 오류?)
   - 재시도 여부 판단
   - 반복 실패 시 거래 중단

**P3 (Info) Alerts:**
- 모니터링만 진행 (즉시 대응 불필요)

### 9.2 Alert Metrics (Prometheus)

**신규 Metrics:**
```prometheus
# Alert 전송 횟수
alert_sent_total{severity="P1|P2|P3", source="fx|executor|risk_guard"}

# Alert throttling 횟수
alert_throttled_total{rule_id="FX-001|..."}

# Alert 전송 latency
alert_send_duration_seconds{severity="P1|P2|P3"}

# Notifier 성공/실패
notifier_success_total{notifier="telegram|slack"}
notifier_failure_total{notifier="telegram|slack"}
```

---

## 10. Future Enhancements (D80-8+)

### 10.1 Advanced Features
- **Alert Escalation**: P2 → P1 자동 escalation (지속 시간 기반)
- **Alert Correlation**: 관련 알림 자동 연결 (예: FX down → Executor error)
- **Alert ML**: 이상 패턴 학습 및 예측 알림
- **SMS/Phone Call**: P1 알림 시 전화 발신

### 10.2 Grafana Integration
- Alert 이력 Grafana 패널
- Alert 대시보드 (severity별 트렌드)
- Alert acknowledgement UI

### 10.3 Alert API
- REST API: `GET /alerts`, `POST /alerts/ack`
- WebSocket API: 실시간 alert stream

---

## 11. Risks & Mitigations

### 11.1 Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Telegram API 장애** | P1 알림 전달 실패 | Medium | Slack fallback, local logging |
| **Alert Storm** | 과도한 알림 발송 | High | Throttling, aggregation |
| **False Positive** | 불필요한 알림 | Medium | Rule tuning, threshold 조정 |
| **Network Latency** | Alert 지연 | Low | Redis queue, async sending |

### 11.2 Rollback Plan
- Alerting 모듈은 core 기능과 분리 → 장애 시 disable 가능
- Feature flag: `ENABLE_ALERTING=false`
- Graceful degradation: Notifier 실패 시 logging만 수행

---

## 12. Acceptance Criteria

**D80-7 완료 조건:**
- ✅ AlertManager 구현 (alert 생성, 전송, 이력 저장)
- ✅ TelegramNotifier 구현 (Telegram Bot API 연동)
- ✅ SlackNotifier 구현 (Slack Webhook 연동)
- ✅ AlertThrottler 구현 (중복 알림 방지)
- ✅ AlertAggregator 구현 (관련 알림 묶기)
- ✅ AlertQueue 구현 (Redis/In-memory)
- ✅ FX Layer integration (FX-001, FX-002, FX-003)
- ✅ Executor integration (EX-001)
- ✅ RiskGuard integration (RG-001, RG-002)
- ✅ Unit tests (80+ tests, 100% PASS)
- ✅ Integration tests (E2E alerting flow 검증)
- ✅ Manual test (실제 Telegram 알림 수신 확인)
- ✅ D_ROADMAP.md 업데이트

**Test Coverage:**
- Unit tests: ≥ 80% coverage
- Integration tests: E2E flow 3개 이상
- Manual test: Telegram 알림 수신 성공

**Performance:**
- Alert latency < 3s (P1), < 10s (P2/P3)
- Throttling check < 50ms
- Queue throughput ≥ 100 alerts/sec

---

## 13. Timeline

**Estimated Effort:** 2~3 days

| Phase | Task | Duration |
|-------|------|----------|
| **Phase 1** | Alert domain model + AlertManager core | 4h |
| **Phase 2** | TelegramNotifier + SlackNotifier | 3h |
| **Phase 3** | Throttler + Aggregator + Queue | 4h |
| **Phase 4** | FX/Executor/RiskGuard integration | 4h |
| **Phase 5** | Unit tests (80+ tests) | 6h |
| **Phase 6** | Integration tests (E2E) | 3h |
| **Phase 7** | Manual test + Documentation | 2h |

**Total:** ~26 hours (3 days)

---

## 14. References

- **D80-6**: Multi-Source FX Monitoring & Grafana Dashboard
- **D79-5**: Cross-Exchange Advanced Risk Management
- **D79-4**: Cross-Exchange Real Order Execution
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Slack Incoming Webhooks**: https://api.slack.com/messaging/webhooks
- **Prometheus Alertmanager**: https://prometheus.io/docs/alerting/latest/alertmanager/

---

## 15. Appendix

### 15.1 Alert Message Format (Telegram)

**P1 (Critical):**
```
🔴 [P1] {Category} Alert
━━━━━━━━━━━━━━━
📍 Source: {source}
🚨 {message}
⏰ {timestamp}
━━━━━━━━━━━━━━━
{metadata}
```

**P2 (Warning):**
```
🟠 [P2] {Category} Alert
━━━━━━━━━━━━━━━
📍 Source: {source}
⚠️ {message}
⏰ {timestamp}
━━━━━━━━━━━━━━━
{metadata}
```

**P3 (Info):**
```
🟢 [P3] {Category} Alert
━━━━━━━━━━━━━━━
📍 Source: {source}
ℹ️ {message}
⏰ {timestamp}
```

### 15.2 Database Schema (PostgreSQL)

**alerts Table:**
```sql
CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY,
    rule_id VARCHAR(20) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    source VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    throttled BOOLEAN DEFAULT FALSE,
    notifier VARCHAR(20),  -- 'telegram', 'slack', etc.
    status VARCHAR(20),    -- 'sent', 'failed', 'pending'
    INDEX idx_alerts_severity (severity),
    INDEX idx_alerts_source (source),
    INDEX idx_alerts_created_at (created_at)
);
```

---

**Document End.**

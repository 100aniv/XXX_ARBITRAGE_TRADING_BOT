# D76: Alerting Infrastructure Design

## Overview

D76 Alerting Infrastructure는 D75 Arbitrage Core v1의 모든 계층에서 발생하는 critical event를 실시간으로 감지하고, 적절한 채널(Telegram, Slack, Email, PostgreSQL)로 알림을 발송하는 시스템입니다.

**Status:** ✅ **v1 Implementation Complete (2025-01-22)**

---

## Architecture

### 1. Alert Severity Classification

| Severity | Level | Examples | Response Time | Channels |
|----------|-------|----------|---------------|----------|
| **P0** | Critical | Exchange FROZEN, Global risk limit breached | Immediate | Telegram (real-time) |
| **P1** | High | Performance degradation, High error rate | < 5 minutes | Telegram, Slack |
| **P2** | Medium | Component failure, Resource exhaustion | < 15 minutes | Telegram, Slack |
| **P3** | Low | Warnings, Informational | Daily | Email (summary) |

### 2. Event Sources

- **RateLimiter**: Rate limit near exhaustion (P2)
- **ExchangeHealth**: Failover required (P0), Degraded status (P1)
- **ArbRoute**: Route score critical low (P2)
- **ArbUniverse**: No profitable routes (P2)
- **CrossSync**: Inventory imbalance critical (P1)
- **RiskGuard**: Global block (P0), Exchange/Route/Symbol blocks (P1-P2)

### 3. Component Structure

```
arbitrage/alerting/
├── __init__.py               # Public API
├── models.py                 # AlertSeverity, AlertSource, AlertRecord
├── manager.py                # AlertManager (central dispatcher)
├── notifiers/
│   ├── __init__.py
│   ├── base.py               # NotifierBase (interface)
│   ├── telegram_notifier.py  # Telegram implementation
│   ├── slack_notifier.py     # Slack (future)
│   └── email_notifier.py     # Email (future)
└── storage/
    ├── __init__.py
    ├── base.py               # StorageBase (interface)
    ├── memory_storage.py     # In-memory implementation
    └── postgres_storage.py   # PostgreSQL (future)
```

---

## Components

### AlertManager

Central alert dispatcher with rate limiting.

**Features:**
- Alert dispatching to multiple channels
- Rate limiting per (severity, source) combination
- In-memory alert history
- Thread-safe operations

**Rate Limits (per minute):**
- P0: 10 alerts/min
- P1: 5 alerts/min
- P2: 3 alerts/min
- P3: 1 alert/min

**Usage:**
```python
from arbitrage.alerting import AlertManager, AlertSeverity, AlertSource

manager = AlertManager()

# Send alert
manager.send_alert(
    severity=AlertSeverity.P0,
    source=AlertSource.HEALTH_MONITOR,
    title="Exchange FROZEN",
    message="UPBIT API not responding",
    metadata={"exchange": "UPBIT", "latency_ms": 2500}
)

# Get recent alerts
recent = manager.get_recent_alerts(minutes=60, severity=AlertSeverity.P0)

# Get statistics
stats = manager.get_alert_stats()
```

### TelegramNotifier

Telegram notifier with mockable network calls.

**Features:**
- Environment-based configuration (BOT_TOKEN, CHAT_ID)
- Mockable send_message for testing
- Severity-based emoji mapping
  - P0: 🚨 (Critical)
  - P1: ⚠️ (High)
  - P2: ⚡ (Medium)
  - P3: ℹ️ (Low)

**Configuration:**
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

**Usage:**
```python
from arbitrage.alerting.notifiers import TelegramNotifier

notifier = TelegramNotifier()
manager.register_notifier(notifier)
```

### InMemoryStorage

In-memory alert storage with automatic cleanup.

**Features:**
- Thread-safe operations
- Time-based retention (default: 7 days)
- Automatic cleanup of old alerts

**Usage:**
```python
from arbitrage.alerting.storage import InMemoryStorage

storage = InMemoryStorage(retention_days=7)
manager.register_storage(storage)
```

---

## D75 Core Integration

### RateLimiter Hook

**Event:** Rate limit near exhaustion  
**Severity:** P2  
**Trigger:** Token bucket exhausted  
**Throttle:** 1 alert per minute

**Implementation:**
```python
# arbitrage/infrastructure/rate_limiter.py
from arbitrage.alerting import AlertManager

class TokenBucketRateLimiter:
    def __init__(self, config, alert_manager=None):
        self._alert_manager = alert_manager
        # ...
    
    def consume(self, weight=1):
        # ...
        if rejected:
            self._send_rate_limit_alert()
```

### ExchangeHealth Hook

**Event:** Failover required  
**Severity:** P0  
**Triggers:**
- FROZEN status (latency > 2000ms or stale orderbook > 10s)
- DOWN status for 5+ minutes
- Error ratio > 10%

**Throttle:** 1 alert per 5 minutes

**Implementation:**
```python
# arbitrage/infrastructure/exchange_health.py
class HealthMonitor:
    def __init__(self, exchange_name, history_size=100, alert_manager=None):
        self._alert_manager = alert_manager
        # ...
    
    def should_failover(self):
        # ...
        if needs_failover:
            self._send_failover_alert(reason)
```

---

## Testing

### Test Coverage

- **test_alert_manager.py**: 9 tests (AlertManager core functionality)
- **test_telegram_notifier.py**: 8 tests (Telegram notifier with mocking)
- **test_alert_storage.py**: 7 tests (In-memory storage)

**Total:** 24 tests, 100% PASS

### Running Tests

```bash
# D76 tests only
python -m pytest tests/test_alert_*.py tests/test_telegram_*.py -v

# D75 + D76 integration
python scripts/run_d75_regression.py
python -m pytest tests/test_alert_*.py tests/test_telegram_*.py -v
```

---

## Performance Characteristics

- **AlertManager dispatch latency:** < 1ms (in-memory only)
- **Rate limit check:** O(N) where N = alerts in current window
- **Storage query:** O(N) where N = total alerts
- **Memory footprint:** ~100 bytes per alert record
- **Thread-safety:** Full (RLock-based)

---

## Future Enhancements (D76-2)

### Planned Features

1. **Slack Notifier**
   - Webhook-based notifications
   - Channel routing by severity
   - Rich formatting with blocks

2. **Email Notifier**
   - SMTP configuration
   - Daily summary for P3 alerts
   - HTML templates

3. **PostgreSQL Storage**
   - Persistent alert history
   - Advanced querying
   - Alert acknowledgment tracking

4. **Additional Hooks**
   - ArbRoute: Route health score drops
   - ArbUniverse: No profitable routes
   - CrossSync: Critical inventory imbalance
   - RiskGuard: Global/Exchange/Route/Symbol blocks

5. **Alert Acknowledgment**
   - Manual acknowledgment via Telegram
   - Auto-acknowledgment rules
   - On-call rotation

6. **Alert Aggregation**
   - Group similar alerts
   - Trend detection
   - Anomaly detection

---

## Implementation Timeline

- **D76-1 (2025-01-22):** ✅ Core AlertManager + Telegram + RateLimiter/ExchangeHealth hooks
- **D76-2 (Future):** Slack/Email notifiers, PostgreSQL storage
- **D76-3 (Future):** Additional D75 hooks (ArbRoute, CrossSync, RiskGuard)
- **D76-4 (Future):** Alert acknowledgment, aggregation, on-call

---

## References

- **D75 Arbitrage Core:** `docs/D75_ARBITRAGE_CORE_OVERVIEW.md`
- **D76 Initial Sketch:** `docs/D76_ALERTING_INFRA_SKETCH.md`
- **Roadmap:** `D_ROADMAP.md`

# Arbitrage Engine - API Reference

**Status:** PRODUCTION READY  
**Author:** Arbitrage Engine Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration API](#configuration-api)
3. [Monitoring CLI API](#monitoring-cli-api)
4. [Health Check API](#health-check-api)
5. [Metrics API](#metrics-api)
6. [Redis Keyspace Reference](#redis-keyspace-reference)
7. [PostgreSQL Schema Reference](#postgresql-schema-reference)
8. [Internal Engine API](#internal-engine-api)
9. [Logging API](#logging-api)
10. [State Management API](#state-management-api)

---

## Overview

이 문서는 Arbitrage Engine의 내부 API, CLI 도구, 데이터 스키마를 정의합니다.

### API Categories

| Category | Purpose | Usage |
|----------|---------|-------|
| Configuration | 설정 관리 | 엔진 시작 시 로드 |
| Monitoring CLI | 운영 모니터링 | 수동 실행 |
| Health Check | 서비스 상태 확인 | 자동/수동 실행 |
| Metrics | 성능 지표 수집 | 실시간 수집 |
| Redis Keyspace | 키 생성 및 관리 | 내부 사용 |
| PostgreSQL Schema | 데이터 저장 | 내부 사용 |
| Engine Internal | 엔진 내부 로직 | 개발 참조 |
| Logging | 로그 기록 | 내부 사용 |
| State Management | 상태 관리 | 내부 사용 |

---

## Configuration API

### Module: `config.loader`

#### `load_config(env: str) -> Config`

환경별 설정을 로드합니다.

**Parameters:**
- `env` (str): Environment name (`development`, `staging`, `production`)

**Returns:**
- `Config`: Loaded configuration object

**Raises:**
- `ConfigValidationError`: Configuration validation failed
- `FileNotFoundError`: Config file not found

**Example:**
```python
from config.loader import load_config

config = load_config('production')
print(config.trading.min_profit_threshold)
```

### Class: `TradingConfig`

**Attributes:**
- `min_profit_threshold` (float): Minimum profit threshold (e.g., 0.002 = 0.2%)
- `max_position_size` (float): Maximum position size in USDT
- `binance_fee` (float): Binance trading fee (e.g., 0.001 = 0.1%)
- `upbit_fee` (float): Upbit trading fee (e.g., 0.0005 = 0.05%)
- `paper_mode` (bool): Paper trading mode (True) or live trading (False)
- `symbols` (List[str]): Trading symbols (e.g., `["BTC/USDT"]`)
- `log_level` (str): Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

**Example:**
```python
from config.base import TradingConfig

trading_config = TradingConfig(
    min_profit_threshold=0.002,
    max_position_size=1000.0,
    binance_fee=0.001,
    upbit_fee=0.0005,
    paper_mode=False,
    symbols=["BTC/USDT"],
    log_level="INFO"
)
```

### Class: `RiskLimits`

**Attributes:**
- `max_daily_loss` (float): Maximum daily loss in USDT
- `max_open_positions` (int): Maximum number of concurrent positions
- `max_position_size` (float): Maximum position size in USDT
- `min_profit_threshold` (float): Minimum profit threshold

**Example:**
```python
from config.base import RiskLimits

risk_limits = RiskLimits(
    max_daily_loss=500.0,
    max_open_positions=5,
    max_position_size=1000.0,
    min_profit_threshold=0.002
)
```

### Validation Rules

#### Spread Profitability
```python
# min_profit_threshold > (binance_fee + upbit_fee)
# Example: 0.002 > (0.001 + 0.0005) = True ✓
```

#### Risk Constraints
```python
# max_position_size > 0
# max_daily_loss > 0
# max_open_positions > 0
```

---

## Monitoring CLI API

### Command: `python tools/monitor.py`

운영 모니터링 CLI 도구입니다.

### Usage

#### 1. Metrics Dashboard

```bash
python tools/monitor.py --metrics
```

**Output:**
```
=== Arbitrage Engine Metrics ===
Session: prod-20251121-143022
Uptime: 2h 15m

Trading:
  Trades/min:        2.3
  Errors/min:        0.1
  PnL (1min):        $1.23

Performance:
  WS Latency:        12.3ms
  Loop Latency:      8.7ms
  
Risk:
  Guard Triggers:    0.2/min
  Open Positions:    3/5
```

**Options:**
- `--duration <period>`: Time period (default: 1m, options: 1m, 5m, 1h, 24h)
- `--refresh <seconds>`: Auto-refresh interval (default: 5)

#### 2. Tail Logs

```bash
python tools/monitor.py --tail [--lines N]
```

**Options:**
- `--lines N`: Number of recent lines (default: 100)
- `--follow`: Follow mode (like `tail -f`)

#### 3. Error Logs

```bash
python tools/monitor.py --errors [--since <period>]
```

**Options:**
- `--since <period>`: Time period (default: 1h, options: 1h, 6h, 24h)

**Output:**
```
=== Recent Errors ===
[2025-11-21 14:30:22] ERROR - WebSocket connection lost
[2025-11-21 14:25:15] ERROR - Redis timeout
```

#### 4. Search Logs

```bash
python tools/monitor.py --search "pattern" [--since <period>]
```

**Example:**
```bash
python tools/monitor.py --search "trade execution" --since 1h
```

---

## Health Check API

### Command: `python healthcheck.py`

시스템 health check를 수행합니다.

### Exit Codes

- `0`: All checks passed (healthy)
- `1`: One or more checks failed (unhealthy)

### Checks Performed

#### 1. Redis Check

**Test:** Ping and latency measurement

**Threshold:** Latency < 30ms

**Output:**
```
✓ Redis: Redis OK (latency: 12.34ms)
```

**Failure:**
```
✗ Redis: Redis latency too high: 45.67ms
```

#### 2. PostgreSQL Check

**Test:** Connection and query

**Output:**
```
✓ PostgreSQL: PostgreSQL OK
```

**Failure:**
```
✗ PostgreSQL: PostgreSQL connection failed: connection refused
```

#### 3. Log Volume Check

**Test:** Log file exists and recently updated

**Threshold:** Updated within 5 minutes

**Output:**
```
✓ Logs: Log file OK (updated 30s ago, size: 12345 bytes)
```

**Failure:**
```
✗ Logs: Log file not updated in 360s
```

#### 4. Engine Metrics Check

**Test:** Loop latency from Redis metrics

**Threshold:** Latency < 100ms

**Output:**
```
✓ Metrics: Engine metrics OK
```

**Failure:**
```
✗ Metrics: Loop latency too high: 150.23ms
```

### Integration

#### Docker HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python healthcheck.py || exit 1
```

#### systemd (future)

```ini
[Service]
WatchdogSec=60
```

---

## Metrics API

### Module: `arbitrage.metrics_collector`

### Class: `MetricsCollector`

실시간 메트릭을 수집하고 Redis에 저장합니다.

#### Constructor

```python
from arbitrage.metrics_collector import MetricsCollector

collector = MetricsCollector(
    redis_client=redis_client,
    window_seconds=60  # Rolling window
)
```

#### Methods

##### `record_trade(symbol: str, pnl: float)`

트레이드를 기록합니다.

**Parameters:**
- `symbol` (str): Trading symbol (e.g., "BTC/USDT")
- `pnl` (float): Profit/loss in USDT

**Example:**
```python
collector.record_trade("BTC/USDT", 1.23)
```

##### `record_error(error_type: str)`

에러를 기록합니다.

**Parameters:**
- `error_type` (str): Error type

**Example:**
```python
collector.record_error("WebSocketDisconnected")
```

##### `record_ws_latency(latency_ms: float)`

WebSocket 레이턴시를 기록합니다.

**Parameters:**
- `latency_ms` (float): Latency in milliseconds

**Example:**
```python
collector.record_ws_latency(12.34)
```

##### `record_loop_latency(latency_ms: float)`

엔진 루프 레이턴시를 기록합니다.

**Parameters:**
- `latency_ms` (float): Latency in milliseconds

**Example:**
```python
collector.record_loop_latency(8.76)
```

##### `record_guard_trigger(reason: str)`

RiskGuard 트리거를 기록합니다.

**Parameters:**
- `reason` (str): Trigger reason

**Example:**
```python
collector.record_guard_trigger("max_daily_loss_exceeded")
```

##### `get_metrics() -> Dict[str, float]`

현재 메트릭을 조회합니다.

**Returns:**
- `Dict[str, float]`: Metrics dictionary

**Example:**
```python
metrics = collector.get_metrics()
print(metrics)
# {
#   'trades_per_minute': 2.3,
#   'errors_per_minute': 0.1,
#   'avg_ws_latency_ms': 12.34,
#   'avg_loop_latency_ms': 8.76,
#   'guard_triggers_per_minute': 0.2,
#   'pnl_change_1min': 1.23
# }
```

##### `save_to_redis(session_id: str, env: str)`

메트릭을 Redis에 저장합니다.

**Parameters:**
- `session_id` (str): Session ID
- `env` (str): Environment

**Example:**
```python
collector.save_to_redis("prod-20251121-143022", "production")
```

---

## Redis Keyspace Reference

### Module: `arbitrage.redis_keyspace`

### Class: `KeyBuilder`

Redis 키를 생성하고 관리합니다.

#### Methods

##### `state_key(session_id: str, symbol: str, field: str) -> str`

상태 키를 생성합니다.

**Parameters:**
- `session_id` (str): Session ID
- `symbol` (str): Symbol (e.g., "BTC/USDT")
- `field` (str): Field name

**Returns:**
- `str`: Redis key

**Example:**
```python
from arbitrage.redis_keyspace import KeyBuilder

kb = KeyBuilder(env="production")
key = kb.state_key("prod-20251121-143022", "BTC/USDT", "position")
# "arbitrage:production:prod-20251121-143022:STATE:BTC/USDT:position"
```

##### `metrics_key(session_id: str) -> str`

메트릭 키를 생성합니다.

**Example:**
```python
key = kb.metrics_key("prod-20251121-143022")
# "arbitrage:production:prod-20251121-143022:METRICS"
```

##### `snapshot_key(session_id: str) -> str`

스냅샷 키를 생성합니다.

**Example:**
```python
key = kb.snapshot_key("prod-20251121-143022")
# "arbitrage:production:prod-20251121-143022:SNAPSHOT"
```

##### `guard_key(session_id: str, guard_type: str) -> str`

가드 키를 생성합니다.

**Example:**
```python
key = kb.guard_key("prod-20251121-143022", "daily_loss")
# "arbitrage:production:prod-20251121-143022:GUARD:daily_loss"
```

### Key Format

**Pattern:**
```
arbitrage:{env}:{session_id}:{domain}:{symbol}:{field}
```

**Components:**
- `env`: Environment (development, staging, production)
- `session_id`: Unique session identifier
- `domain`: Domain (STATE, METRICS, GUARD, SNAPSHOT, WS, etc.)
- `symbol`: Trading symbol (optional)
- `field`: Field name (optional)

### Domain Types

| Domain | Purpose | TTL | Example |
|--------|---------|-----|---------|
| STATE | Position/balance state | 7 days | `arbitrage:production:session1:STATE:BTC/USDT:position` |
| METRICS | Performance metrics | 1 day | `arbitrage:production:session1:METRICS` |
| GUARD | RiskGuard state | 1 day | `arbitrage:production:session1:GUARD:daily_loss` |
| SNAPSHOT | Session snapshot | 30 days | `arbitrage:production:session1:SNAPSHOT` |
| WS | WebSocket state | 1 hour | `arbitrage:production:session1:WS:binance:status` |
| COOLDOWN | Trade cooldown | 5 minutes | `arbitrage:production:session1:COOLDOWN:BTC/USDT` |
| PORTFOLIO | Portfolio summary | 7 days | `arbitrage:production:session1:PORTFOLIO:summary` |

### TTL Policy

**Class:** `TTLPolicy`

```python
from arbitrage.redis_keyspace import TTLPolicy

ttl = TTLPolicy.get_ttl("METRICS")  # 86400 seconds (1 day)
```

**TTL Values:**

| Domain | TTL (seconds) | Duration |
|--------|---------------|----------|
| STATE | 604800 | 7 days |
| METRICS | 86400 | 1 day |
| GUARD | 86400 | 1 day |
| SNAPSHOT | 2592000 | 30 days |
| WS | 3600 | 1 hour |
| COOLDOWN | 300 | 5 minutes |
| PORTFOLIO | 604800 | 7 days |

---

## PostgreSQL Schema Reference

### Tables

#### 1. `session_snapshots`

세션 스냅샷을 저장합니다.

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| session_id | VARCHAR(100) | Unique session ID |
| env | VARCHAR(20) | Environment |
| status | VARCHAR(20) | Status (running, stopped, crashed) |
| started_at | TIMESTAMP | Session start time |
| stopped_at | TIMESTAMP | Session stop time (nullable) |
| created_at | TIMESTAMP | Snapshot creation time |
| updated_at | TIMESTAMP | Snapshot update time |

**Indexes:**
- `idx_session_snapshots_session_id` (session_id)
- `idx_session_snapshots_status` (status)
- `idx_session_snapshots_created_at_desc` (created_at DESC)
- `idx_session_snapshots_session_created` (session_id, created_at)

**Example Query:**
```sql
SELECT * FROM session_snapshots 
WHERE status = 'running' 
ORDER BY created_at DESC 
LIMIT 1;
```

#### 2. `position_snapshots`

포지션 스냅샷을 저장합니다.

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| session_id | VARCHAR(100) | Foreign key to session_snapshots |
| symbol | VARCHAR(20) | Trading symbol |
| entry_price | NUMERIC(20,8) | Entry price |
| quantity | NUMERIC(20,8) | Position quantity |
| side | VARCHAR(10) | Side (long/short) |
| unrealized_pnl | NUMERIC(20,8) | Unrealized PnL |
| created_at | TIMESTAMP | Creation time |

**Indexes:**
- `idx_position_snapshots_session_id` (session_id)
- `idx_position_snapshots_symbol` (symbol)
- `idx_position_snapshots_created_at_desc` (created_at DESC)

**Example Query:**
```sql
SELECT * FROM position_snapshots 
WHERE session_id = 'prod-20251121-143022' 
ORDER BY created_at DESC;
```

#### 3. `metrics_snapshots`

메트릭 스냅샷을 저장합니다.

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| session_id | VARCHAR(100) | Foreign key to session_snapshots |
| per_symbol_pnl | JSONB | Per-symbol PnL |
| per_symbol_trades | JSONB | Per-symbol trade count |
| created_at | TIMESTAMP | Creation time |

**Indexes:**
- `idx_metrics_snapshots_session_id` (session_id)
- `idx_metrics_snapshots_created_at_desc` (created_at DESC)
- `idx_metrics_snapshots_per_symbol_pnl` (per_symbol_pnl) GIN

**Example Query:**
```sql
SELECT per_symbol_pnl->>'BTC/USDT' as btc_pnl
FROM metrics_snapshots 
WHERE session_id = 'prod-20251121-143022' 
ORDER BY created_at DESC 
LIMIT 1;
```

#### 4. `risk_guard_snapshots`

RiskGuard 스냅샷을 저장합니다.

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| session_id | VARCHAR(100) | Foreign key to session_snapshots |
| daily_loss | NUMERIC(20,8) | Daily loss |
| open_positions_count | INTEGER | Open positions count |
| guard_triggered | BOOLEAN | Guard triggered flag |
| created_at | TIMESTAMP | Creation time |

**Indexes:**
- `idx_risk_guard_snapshots_session_id` (session_id)
- `idx_risk_guard_snapshots_created_at_desc` (created_at DESC)

#### 5. `system_logs`

시스템 로그를 저장합니다 (WARNING 이상).

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| session_id | VARCHAR(100) | Session ID |
| level | VARCHAR(20) | Log level |
| message | TEXT | Log message |
| context | JSONB | Additional context |
| created_at | TIMESTAMP | Creation time |

**Indexes:**
- `idx_system_logs_session_id` (session_id)
- `idx_system_logs_level` (level)
- `idx_system_logs_created_at_desc` (created_at DESC)
- `idx_system_logs_context` (context) GIN

**Example Query:**
```sql
SELECT level, message, created_at 
FROM system_logs 
WHERE level = 'ERROR' 
ORDER BY created_at DESC 
LIMIT 50;
```

### Views

#### 1. `v_latest_snapshot_details`

최신 스냅샷 상세 정보를 제공합니다.

**Definition:**
```sql
CREATE VIEW v_latest_snapshot_details AS
SELECT 
    ss.session_id,
    ss.env,
    ss.status,
    ss.started_at,
    COUNT(ps.id) as position_count,
    SUM(ps.unrealized_pnl) as total_unrealized_pnl
FROM session_snapshots ss
LEFT JOIN position_snapshots ps ON ss.session_id = ps.session_id
GROUP BY ss.session_id, ss.env, ss.status, ss.started_at
ORDER BY ss.created_at DESC;
```

**Usage:**
```sql
SELECT * FROM v_latest_snapshot_details WHERE status = 'running';
```

#### 2. `v_session_history`

세션 히스토리를 제공합니다.

**Definition:**
```sql
CREATE VIEW v_session_history AS
SELECT 
    session_id,
    env,
    status,
    started_at,
    stopped_at,
    EXTRACT(EPOCH FROM (COALESCE(stopped_at, NOW()) - started_at)) as duration_seconds
FROM session_snapshots
ORDER BY started_at DESC;
```

#### 3. `v_index_usage_stats`

인덱스 사용 통계를 제공합니다.

**Definition:**
```sql
CREATE VIEW v_index_usage_stats AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### Functions

#### 1. `cleanup_old_snapshots_30d()`

30일 이상 지난 stopped/crashed 세션의 스냅샷을 삭제합니다.

**Usage:**
```sql
SELECT cleanup_old_snapshots_30d();
```

**Returns:** Number of deleted sessions

#### 2. `vacuum_snapshot_tables()`

스냅샷 테이블들을 VACUUM ANALYZE 합니다.

**Usage:**
```sql
SELECT vacuum_snapshot_tables();
```

#### 3. `get_snapshot_table_stats()`

스냅샷 테이블 통계를 조회합니다.

**Usage:**
```sql
SELECT * FROM get_snapshot_table_stats();
```

**Returns:**

| Column | Type | Description |
|--------|------|-------------|
| table_name | TEXT | Table name |
| row_count | BIGINT | Row count |
| total_size | TEXT | Total size (human-readable) |
| indexes_size | TEXT | Indexes size |

---

## Internal Engine API

### Module: `arbitrage.live_runner`

### Class: `LiveRunner`

메인 엔진 클래스입니다.

#### Constructor

```python
from arbitrage.live_runner import LiveRunner

runner = LiveRunner(
    config=config,
    mode='paper'  # or 'live'
)
```

#### Methods

##### `run()`

엔진을 시작합니다.

**Example:**
```python
runner.run()
```

##### `stop()`

엔진을 중지합니다.

**Example:**
```python
runner.stop()
```

---

## Logging API

### Module: `arbitrage.logging_manager`

### Class: `LoggingManager`

로깅을 관리합니다.

#### Constructor

```python
from arbitrage.logging_manager import LoggingManager

logger_mgr = LoggingManager(
    env='production',
    session_id='prod-20251121-143022',
    log_level='INFO'
)
```

#### Methods

##### `get_logger(name: str) -> logging.Logger`

로거를 가져옵니다.

**Example:**
```python
logger = logger_mgr.get_logger(__name__)
logger.info("Engine started")
```

##### `log(level: str, message: str, **context)`

로그를 기록합니다 (4개 백엔드: File, Console, Redis, PostgreSQL).

**Parameters:**
- `level` (str): Log level
- `message` (str): Log message
- `**context`: Additional context

**Example:**
```python
logger_mgr.log('INFO', 'Trade executed', symbol='BTC/USDT', pnl=1.23)
```

### Log Backends

#### 1. File Backend

**Location:** `logs/arbitrage_{env}.log`

**Format:** `[TIMESTAMP] LEVEL - MESSAGE`

#### 2. Console Backend

**Output:** stdout (captured by Docker)

**Format:** Color-coded

#### 3. Redis Backend

**Key:** `arbitrage:logs:{env}`

**Type:** Stream (XADD)

**Max Length:** 1000 messages

#### 4. PostgreSQL Backend

**Table:** `system_logs`

**Filter:** WARNING and above only

---

## State Management API

### Module: `arbitrage.state_store`

### Class: `StateStore`

상태를 관리합니다 (Redis primary, PostgreSQL backup).

#### Methods

##### `save_snapshot(session_id: str, state: Dict)`

스냅샷을 저장합니다.

**Parameters:**
- `session_id` (str): Session ID
- `state` (Dict): State dictionary

**Example:**
```python
state = {
    'positions': [...],
    'balances': {...},
    'metrics': {...}
}
store.save_snapshot('prod-20251121-143022', state)
```

##### `restore_snapshot(session_id: str) -> Optional[Dict]`

스냅샷을 복원합니다.

**Returns:**
- `Dict`: Restored state or None

**Example:**
```python
state = store.restore_snapshot('prod-20251121-143022')
if state:
    print("Snapshot restored")
```

---

## Appendix

### A. Common Data Types

#### SessionID Format

```
{env}-{date}-{time}
Example: prod-20251121-143022
```

#### Symbol Format

```
{base}/{quote}
Example: BTC/USDT
```

#### Timestamp Format

```
ISO 8601: 2025-11-21T14:30:22+09:00
```

### B. Configuration File Paths

| File | Path |
|------|------|
| Base Config | `config/base.py` |
| Development | `config/environments/development.py` |
| Staging | `config/environments/staging.py` |
| Production | `config/environments/production.py` |
| Secrets | `config/secrets.yaml` |
| Env Vars | `/etc/arbitrage/arbitrage.env` |

### C. Log File Paths

| Environment | Path |
|-------------|------|
| Development | `logs/arbitrage_development.log` |
| Staging | `logs/arbitrage_staging.log` |
| Production | `logs/arbitrage_production.log` |

### D. Default Port Reference

| Service | Container Port | Host Port |
|---------|----------------|-----------|
| Redis | 6379 | 6380 |
| PostgreSQL | 5432 | 5432 |
| Engine Metrics | 8080 | 8080 |

### E. Environment Variables

See [DEPLOYMENT_GUIDE.md - Secrets Management](DEPLOYMENT_GUIDE.md#secrets-management) for complete list.

---

**End of API_REFERENCE.md**

For deployment procedures, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).  
For operational procedures, see [RUNBOOK.md](RUNBOOK.md).  
For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

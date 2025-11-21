# Redis Keyspace Specification

**Version:** 1.0  
**Last Updated:** 2025-11-21  
**Status:** PRODUCTION

---

## 📋 Keyspace Overview

arbitrage 시스템은 Redis를 실시간 상태 저장소로 사용합니다.

**Redis Instance:**
- Host: `localhost` (production: dedicated host)
- Port: `6380`
- DB: `0`

---

## 🗝️ Key Naming Convention

### Standard Format

```
arbitrage:state:{env}:{session_id}:{category}
```

**Components:**
- `arbitrage`: Application namespace
- `state`: Data type (state, metrics, cache)
- `{env}`: Environment (`paper`, `live`, `backtest`, `test`)
- `{session_id}`: Unique session identifier (e.g., `session_20251121_100000`)
- `{category}`: Data category (`session`, `positions`, `metrics`, `risk_guard`)

---

## 📚 Key Categories

### 1. State Keys

**Purpose:** 세션 실시간 상태 저장

**Pattern:**
```
arbitrage:state:{env}:{session_id}:{category}
```

**Categories:**

| Category | Type | Description | Example Value |
|----------|------|-------------|---------------|
| `session` | Hash | 세션 메타데이터 | `{session_id, start_time, mode, ...}` |
| `positions` | Hash | 활성 포지션 상태 | `{active_orders: {...}, ...}` |
| `metrics` | Hash | 거래 메트릭 | `{total_trades_opened, pnl, ...}` |
| `risk_guard` | Hash | 리스크 가드 상태 | `{daily_loss_usd, ...}` |

**TTL:** 
- 기본: No TTL (세션 종료 시 명시적 삭제)
- 권장: 24시간 (장기 미사용 세션 정리)

**Example:**
```
arbitrage:state:paper:session_20251121_100000:session
arbitrage:state:paper:session_20251121_100000:positions
arbitrage:state:paper:session_20251121_100000:metrics
arbitrage:state:paper:session_20251121_100000:risk_guard
```

---

### 2. Future: Metrics Keys (D73+)

**Pattern:**
```
arbitrage:metrics:{env}:{symbol}:{metric_type}
```

**Metric Types:**
- `pnl_realtime`: 실시간 PnL
- `trade_count`: 거래 수
- `winrate`: 승률
- `latency`: 루프 지연 시간

**TTL:** 7 days

---

### 3. Future: Cache Keys (D73+)

**Pattern:**
```
arbitrage:cache:{env}:{cache_key}
```

**Cache Types:**
- `orderbook_snapshot`: 호가창 스냅샷
- `spread_history`: 스프레드 히스토리

**TTL:** 1 hour

---

## 🔄 Key Lifecycle

### Creation
```python
# StateStore.save_state_to_redis()
key = f"arbitrage:state:{env}:{session_id}:{category}"
redis_client.hset(key, mapping=data)
```

### Retrieval
```python
# StateStore.load_state_from_redis()
pattern = f"arbitrage:state:{env}:{session_id}:*"
keys = redis_client.scan_iter(match=pattern)
data = {cat: redis_client.hgetall(key) for key in keys}
```

### Deletion
```python
# StateStore.delete_state_from_redis()
pattern = f"arbitrage:state:{env}:{session_id}:*"
keys = list(redis_client.scan_iter(match=pattern))
if keys:
    redis_client.delete(*keys)
```

---

## 🛡️ Best Practices

### 1. Key Naming
- ✅ **DO**: 일관된 delimiter 사용 (`:`)
- ✅ **DO**: 환경 명시 (`paper`, `live`)
- ❌ **DON'T**: 동적 환경 없이 키 생성
- ❌ **DON'T**: 특수문자 사용 (`:` 제외)

### 2. TTL Management
- ✅ **DO**: 임시 데이터에 TTL 설정
- ✅ **DO**: 세션 종료 시 명시적 삭제
- ❌ **DON'T**: 영구 데이터에 TTL 설정
- ❌ **DON'T**: 삭제 없이 키 누적

### 3. Data Size
- ✅ **DO**: Hash 필드 수 < 1000 유지
- ✅ **DO**: 큰 데이터는 PostgreSQL 저장
- ❌ **DON'T**: 대용량 JSON 저장 (> 1MB)

---

## 📊 Monitoring

### Key Metrics

**Redis Server:**
- Memory usage
- Hit rate
- Eviction count

**Application:**
- Key count by pattern
- Average key size
- Expired key count

**Query:**
```bash
# 전체 키 수
redis-cli -p 6380 DBSIZE

# 패턴별 키 수
redis-cli -p 6380 --scan --pattern "arbitrage:state:*" | wc -l

# 메모리 사용량
redis-cli -p 6380 INFO memory
```

---

## 🧹 Cleanup Strategy

### Manual Cleanup (Development)

```bash
# 테스트 환경 키 삭제
redis-cli -p 6380 --scan --pattern "arbitrage:state:test:*" | xargs redis-cli -p 6380 DEL

# 특정 세션 삭제
redis-cli -p 6380 --scan --pattern "arbitrage:state:*:session_20251121_100000:*" | xargs redis-cli -p 6380 DEL
```

### Automated Cleanup (Production)

**Script:** `scripts/redis_cleanup.py`

```python
# 24시간 이상 된 세션 키 삭제
# 또는 TTL 기반 자동 만료
```

---

## 🔐 Security

### Access Control

**Development:**
- No password (localhost only)

**Production:**
- Password required: `REDIS_PASSWORD` 환경변수
- Network isolation: VPC 내부만 접근
- TLS encryption (선택)

### Data Sensitivity

- ✅ 민감 정보 없음 (PII, secrets)
- ✅ 세션 상태, 메트릭만 저장
- ⚠️ Production: API keys는 Redis에 저장 금지

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-21 | Initial specification (D71 완료 기준) |

---

## 🔗 Related Documents

- **D70_STATE_PERSISTENCE_DESIGN.md**: State 저장 설계
- **D71_REPORT.md**: Failure injection & recovery
- **D72_START.md**: Production deployment 준비

---

**Maintainer:** Arbitrage Dev Team  
**Review Cycle:** Quarterly

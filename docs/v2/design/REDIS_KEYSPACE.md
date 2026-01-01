# V2 Redis Keyspace 규칙

**작성일:** 2025-12-29  
**목적:** Redis key 네이밍 규칙 및 TTL 정책 SSOT 확정

---

## 🎯 Redis의 역할 (왜 필수인가?)

Redis는 DB와 달리 **Truth(최종 원천)가 아니지만**, Paper/Live 런타임에서 다음 역할로 **Required(필수)**:

1. **Rate Limit Counter**: 거래소별 API 요청 제한 관리
   - 없으면: Rate Limit 우회 → 주문 실패 또는 계정 차단
   
2. **Dedup Key**: 중복 주문 방지 (멱등성 보장)
   - 없으면: 네트워크 재시도 시 중복 주문 → 손실 위험
   
3. **Hot-state**: 엔진 상태 저장 (메모리 기반)
   - 없으면: 상태 손실 → 포지션 추적 불가

따라서 **DB(Cold Path) + Redis(Hot Path) 모두 필수**.

---

## 📜 핵심 원칙

1. **네이밍 규칙 강제**: 모든 V2 key는 `v2:` prefix 필수
2. **환경 격리**: dev/prod 환경별 key 충돌 방지
3. **TTL 필수**: 모든 캐시는 TTL 설정 (메모리 누수 방지)
4. **타입 명시**: key 이름에 타입 힌트 포함 (권장)

---

## 🗝️ Key 네이밍 규칙

### 1. 기본 포맷

```
v2:{env}:{run_id}:{domain}:{key}
```

**예시:**
```
v2:prod:d204_2_20251229_1630:market:BTC/KRW
v2:dev:test_run_001:config:threshold
v2:prod:paper_20251229:ratelimit:upbit:orders
```

### 2. 환경 (env)

- `dev`: 로컬 개발 환경
- `test`: 테스트 환경 (pytest 등)
- `prod`: 운영 환경 (Paper/LIVE)

**격리 규칙:**
- 환경별 Redis DB 분리 (권장): dev=0, test=1, prod=2
- 또는 key prefix로 격리 (현재 방식)

### 3. Run ID (run_id)

- Paper/LIVE 실행 세션 ID
- 포맷: `{task}_{YYYYMMDD}_{HHMM}` 또는 `{task}_{uuid}`
- 예시: `d204_2_20251229_1630`, `paper_20251229_1630`

**규칙:**
- 동일 run_id의 key는 실행 종료 후 일괄 삭제 가능
- Run 종료 시 cleanup: `DEL v2:{env}:{run_id}:*`

### 4. Domain (도메인)

| Domain | 설명 | 예시 |
|--------|------|------|
| `market` | 시장 데이터 (호가, 체결, 티커) | `v2:prod:run_001:market:BTC/KRW` |
| `config` | 런타임 설정 (동적 변경) | `v2:prod:run_001:config:threshold` |
| `ratelimit` | Rate limit counter | `v2:prod:run_001:ratelimit:upbit:orders` |
| `lock` | 분산 락 | `v2:prod:run_001:lock:symbol:BTC/KRW` |
| `state` | Engine 상태 저장 | `v2:prod:run_001:state:engine` |
| `cache` | 일반 캐시 | `v2:prod:run_001:cache:spread:BTC/KRW` |

---

## ⏱️ TTL 정책

### 1. TTL 기본값

| Domain | TTL | 근거 |
|--------|-----|------|
| `market` | **100ms** | 실시간 데이터, 빠른 갱신 필요 |
| `config` | **1h (3600s)** | 자주 변경되지 않음 |
| `ratelimit` | **1s ~ 1m** | Rate limit window에 따름 |
| `lock` | **10s** | 분산 락, 짧게 유지 |
| `state` | **1h** | Engine 상태, 주기적 저장 |
| `cache` | **5m (300s)** | 일반 캐시, 적당한 TTL |

### 2. TTL 설정 명령

**Python:**
```python
import redis

r = redis.Redis(host='localhost', port=6380, db=0)

# Market data (100ms TTL)
r.setex('v2:prod:run_001:market:BTC/KRW', 0.1, '{"bid": 50000, "ask": 50100}')

# Config (1h TTL)
r.setex('v2:prod:run_001:config:threshold', 3600, '24')

# Rate limit counter (1s TTL)
r.setex('v2:prod:run_001:ratelimit:upbit:orders', 1, '5')
```

### 3. TTL 없는 key 금지

**검증 스크립트:**
```bash
# TTL 없는 V2 key 찾기
redis-cli --scan --pattern "v2:*" | while read key; do
    ttl=$(redis-cli ttl "$key")
    if [ "$ttl" = "-1" ]; then
        echo "WARNING: No TTL for key: $key"
    fi
done
```

---

## 🔐 Lock (분산 락)

### 1. Lock Key 포맷

```
v2:{env}:{run_id}:lock:{resource}
```

**예시:**
```
v2:prod:run_001:lock:symbol:BTC/KRW
v2:prod:run_001:lock:route:upbit_binance:BTC/KRW
```

### 2. Lock 획득/해제

**Python (redis-py):**
```python
import redis
import uuid
import time

r = redis.Redis(host='localhost', port=6380, db=0)

def acquire_lock(resource: str, timeout: int = 10):
    """분산 락 획득"""
    lock_key = f"v2:prod:run_001:lock:{resource}"
    lock_value = str(uuid.uuid4())
    
    # SET NX EX: Not eXists, EXpire
    acquired = r.set(lock_key, lock_value, nx=True, ex=timeout)
    return lock_value if acquired else None

def release_lock(resource: str, lock_value: str):
    """분산 락 해제"""
    lock_key = f"v2:prod:run_001:lock:{resource}"
    
    # Lua script로 원자적 삭제
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    return r.eval(script, 1, lock_key, lock_value)
```

---

## 📊 Rate Limit Counter

### 1. Counter Key 포맷

```
v2:{env}:{run_id}:ratelimit:{exchange}:{endpoint}
```

**예시:**
```
v2:prod:run_001:ratelimit:upbit:orders
v2:prod:run_001:ratelimit:binance:market_data
```

### 2. Counter 구현 (Token Bucket)

**Python:**
```python
import redis
import time

r = redis.Redis(host='localhost', port=6380, db=0)

def check_rate_limit(exchange: str, endpoint: str, limit: int = 30, window: int = 1):
    """
    Rate limit 체크 (Token Bucket)
    
    Args:
        exchange: 거래소 이름
        endpoint: API endpoint
        limit: 허용 요청 수
        window: 시간 윈도우 (초)
    
    Returns:
        bool: True (허용), False (차단)
    """
    key = f"v2:prod:run_001:ratelimit:{exchange}:{endpoint}"
    
    # INCR + EXPIRE
    current = r.incr(key)
    if current == 1:
        r.expire(key, window)
    
    return current <= limit
```

**예시:**
```python
# Upbit: 30 req/s
if check_rate_limit('upbit', 'orders', limit=30, window=1):
    # 주문 실행
    pass
else:
    # 대기 또는 에러
    print("Rate limit exceeded")
```

---

## 💾 Market Data 캐시

### 1. Market Data Key 포맷

```
v2:{env}:{run_id}:market:{exchange}:{symbol}:{data_type}
```

**예시:**
```
v2:prod:run_001:market:upbit:BTC/KRW:ticker
v2:prod:run_001:market:binance:BTC/USDT:orderbook
v2:prod:run_001:market:upbit:BTC/KRW:trades
```

### 2. 데이터 구조

**JSON 형식 (권장):**
```python
import redis
import json

r = redis.Redis(host='localhost', port=6380, db=0)

# Ticker 저장
ticker_key = "v2:prod:run_001:market:upbit:BTC/KRW:ticker"
ticker_data = {
    "timestamp": "2025-12-29T01:56:00Z",
    "bid": 50000000,
    "ask": 50100000,
    "last": 50050000,
    "volume": 123.45
}
r.setex(ticker_key, 0.1, json.dumps(ticker_data))  # 100ms TTL

# Orderbook 저장 (L2)
orderbook_key = "v2:prod:run_001:market:upbit:BTC/KRW:orderbook"
orderbook_data = {
    "timestamp": "2025-12-29T01:56:00Z",
    "bids": [[50000000, 0.5], [49990000, 1.2]],
    "asks": [[50100000, 0.3], [50110000, 0.8]]
}
r.setex(orderbook_key, 0.1, json.dumps(orderbook_data))
```

---

## 🧹 Cleanup (정리)

### 1. Run 종료 시 일괄 삭제

```bash
# 특정 run_id의 모든 key 삭제
redis-cli --scan --pattern "v2:prod:d204_2_20251229_1630:*" | xargs redis-cli del
```

**Python:**
```python
def cleanup_run(run_id: str):
    """Run 종료 시 Redis key 정리"""
    pattern = f"v2:prod:{run_id}:*"
    
    for key in r.scan_iter(match=pattern, count=100):
        r.delete(key)
    
    print(f"Cleaned up keys for run_id: {run_id}")
```

### 2. 오래된 key 자동 정리 (Cron)

```bash
# 24시간 이상 된 v2 key 삭제
redis-cli --scan --pattern "v2:*" | while read key; do
    ttl=$(redis-cli ttl "$key")
    if [ "$ttl" = "-1" ]; then
        # TTL 없는 key는 삭제 (또는 로그)
        redis-cli del "$key"
        echo "Deleted key without TTL: $key"
    fi
done
```

---

## 🚨 금지 사항

### ❌ 1. v2 prefix 없는 key
```python
# 금지
r.set('market_data:BTC/KRW', '...')  # ❌

# 허용
r.set('v2:prod:run_001:market:BTC/KRW', '...')  # ✅
```

### ❌ 2. TTL 없는 캐시
```python
# 금지
r.set('v2:prod:run_001:cache:spread', '...')  # ❌ TTL 없음

# 허용
r.setex('v2:prod:run_001:cache:spread', 300, '...')  # ✅ 5분 TTL
```

### ❌ 3. 환경 격리 무시
```python
# 금지
r.set('v2:market:BTC/KRW', '...')  # ❌ env 누락

# 허용
r.set('v2:prod:run_001:market:BTC/KRW', '...')  # ✅ env 포함
```

---

## 📊 모니터링

### 1. Redis 메모리 사용량

```bash
# 메모리 정보
redis-cli info memory

# V2 key 개수
redis-cli --scan --pattern "v2:*" | wc -l

# V2 key 메모리 사용량 (추정)
redis-cli --bigkeys --pattern "v2:*"
```

### 2. Prometheus Exporter

**Redis Exporter 설정:**
```yaml
# monitoring/prometheus/prometheus.v2.yml
scrape_configs:
  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']
```

**Grafana Dashboard:**
- Panel: Redis Memory Usage (v2 keys)
- Panel: Redis Key Count (v2:*)
- Panel: Redis Eviction Rate

---

## 📝 다음 단계

이 문서는 **SSOT**입니다. Redis key 추가 시 반드시 이 문서를 업데이트하세요.

**업데이트 규칙:**
1. 새 domain 추가 시 → Domain 섹션 업데이트 + 예시 추가
2. TTL 변경 시 → TTL 정책 섹션 업데이트 + 근거 문서화
3. 변경 시 커밋 메시지에 `[REDIS]` 태그

**참조:**
- SSOT_MAP: `docs/v2/design/SSOT_MAP.md` (Redis SSOT 섹션)
- Config: `config/v2/config.yml` (cache.ttl_seconds)
- 구현: `arbitrage/v2/core/cache_provider.py` (미래 구현)

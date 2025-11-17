# DB Schema Design (PHASE D – Persistence & Infra)

## 개요

이 문서는 PHASE D에서 구현할 PostgreSQL/TimescaleDB 기반 데이터베이스 스키마와 Redis 캐시 구조를 설계합니다.

**현재 상태 (PHASE C4)**:
- CSV 파일 기반 저장소 사용 (SimpleStorage/CsvStorage)
- 이 문서는 "설계 및 계획" 수준
- 실제 구현은 PHASE D에서 진행

**목표**:
- 확장 가능한 시계열 데이터 저장소 (TimescaleDB)
- 실시간 캐시 및 헬스 상태 관리 (Redis)
- 기존 CSV 로그와의 호환성 유지

---

## 1. PostgreSQL/TimescaleDB 테이블 설계

### 1.1 positions 테이블

포지션의 진입/청산 정보를 저장합니다.

```sql
CREATE TABLE positions (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(50) NOT NULL,  -- "upbit_short_binance_long" 등
    size NUMERIC(18, 8) NOT NULL,
    
    entry_upbit_price NUMERIC(18, 2) NOT NULL,
    entry_binance_price NUMERIC(18, 8) NOT NULL,
    entry_spread_pct NUMERIC(8, 4) NOT NULL,
    
    exit_upbit_price NUMERIC(18, 2),
    exit_binance_price NUMERIC(18, 8),
    exit_spread_pct NUMERIC(8, 4),
    
    pnl_krw NUMERIC(18, 2),
    pnl_pct NUMERIC(8, 4),
    
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',  -- "OPEN", "CLOSED"
    
    timestamp_open TIMESTAMPTZ NOT NULL,
    timestamp_close TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- TimescaleDB hypertable 설정 (선택)
-- SELECT create_hypertable('positions', 'timestamp_open', if_not_exists => TRUE);

CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_timestamp_open ON positions(timestamp_open DESC);
```

**매핑**:
- CSV: positions.csv
- Python: `Position` 모델

---

### 1.2 orders 테이블

주문 레그(Order Routing & Slippage Model) 정보를 저장합니다.

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    position_id BIGINT REFERENCES positions(id) ON DELETE CASCADE,
    
    symbol VARCHAR(10) NOT NULL,
    venue VARCHAR(50) NOT NULL,  -- "upbit", "binance_futures"
    side VARCHAR(20) NOT NULL,   -- "buy", "sell", "long", "short"
    qty NUMERIC(18, 8) NOT NULL,
    
    price_theoretical NUMERIC(18, 8) NOT NULL,
    price_effective NUMERIC(18, 8),
    slippage_bps NUMERIC(8, 2),
    
    leg_id VARCHAR(100) NOT NULL,  -- "pos_001_leg_0" 등
    order_id VARCHAR(100),         -- 거래소 주문 ID (Live 모드)
    
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- TimescaleDB hypertable 설정 (선택)
-- SELECT create_hypertable('orders', 'timestamp', if_not_exists => TRUE);

CREATE INDEX idx_orders_position_id ON orders(position_id);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_venue ON orders(venue);
CREATE INDEX idx_orders_timestamp ON orders(timestamp DESC);
```

**매핑**:
- CSV: orders.csv
- Python: `OrderLeg` 모델

---

### 1.3 spreads 테이블

스프레드 기회 스냅샷을 저장합니다.

```sql
CREATE TABLE spreads (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    
    upbit_price NUMERIC(18, 2) NOT NULL,
    binance_price NUMERIC(18, 8) NOT NULL,
    binance_price_krw NUMERIC(18, 2) NOT NULL,
    
    spread_pct NUMERIC(8, 4) NOT NULL,
    net_spread_pct NUMERIC(8, 4) NOT NULL,
    is_opportunity BOOLEAN NOT NULL DEFAULT FALSE,
    
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- TimescaleDB hypertable 설정 (권장)
-- SELECT create_hypertable('spreads', 'timestamp', if_not_exists => TRUE);

CREATE INDEX idx_spreads_symbol ON spreads(symbol);
CREATE INDEX idx_spreads_is_opportunity ON spreads(is_opportunity);
CREATE INDEX idx_spreads_timestamp ON spreads(timestamp DESC);
```

**매핑**:
- CSV: spreads.csv
- Python: `SpreadOpportunity` 모델

---

### 1.4 fx_rates 테이블

환율(FX) 정보를 저장합니다.

```sql
CREATE TABLE fx_rates (
    id BIGSERIAL PRIMARY KEY,
    pair VARCHAR(20) NOT NULL,  -- "USDKRW", "EURKRW" 등
    rate NUMERIC(18, 8) NOT NULL,
    source VARCHAR(50),         -- "static", "upbit", "api", "db" 등
    
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- TimescaleDB hypertable 설정 (권장)
-- SELECT create_hypertable('fx_rates', 'timestamp', if_not_exists => TRUE);

CREATE INDEX idx_fx_rates_pair ON fx_rates(pair);
CREATE INDEX idx_fx_rates_timestamp ON fx_rates(timestamp DESC);
```

**매핑**:
- 현재 CSV 저장 없음 (향후 추가)
- Python: `arbitrage/fx.py` 모듈

---

### 1.5 trades 테이블 (선택)

체결 기록을 저장합니다. (positions 테이블의 진입/청산 정보로도 충분할 수 있음)

```sql
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    position_id BIGINT REFERENCES positions(id) ON DELETE CASCADE,
    
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    size NUMERIC(18, 8) NOT NULL,
    
    side VARCHAR(20) NOT NULL,  -- "OPEN", "CLOSE"
    price_upbit NUMERIC(18, 2),
    price_binance NUMERIC(18, 8),
    
    pnl_krw NUMERIC(18, 2),
    pnl_pct NUMERIC(8, 4),
    
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- TimescaleDB hypertable 설정 (선택)
-- SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);

CREATE INDEX idx_trades_position_id ON trades(position_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_timestamp ON trades(timestamp DESC);
```

**매핑**:
- CSV: trades.csv
- Python: 현재 `Position` 모델에서 파생

---

## 2. TimescaleDB 확장 (선택)

TimescaleDB는 PostgreSQL의 시계열 데이터 최적화 확장입니다.

### 2.1 Hypertable 설정

다음 테이블을 hypertable로 설정하면 시계열 쿼리 성능이 향상됩니다:

```sql
-- positions 테이블 (시간 기준 분할)
SELECT create_hypertable('positions', 'timestamp_open', if_not_exists => TRUE);

-- orders 테이블 (시간 기준 분할)
SELECT create_hypertable('orders', 'timestamp', if_not_exists => TRUE);

-- spreads 테이블 (시간 기준 분할, 권장)
SELECT create_hypertable('spreads', 'timestamp', if_not_exists => TRUE);

-- fx_rates 테이블 (시간 기준 분할, 권장)
SELECT create_hypertable('fx_rates', 'timestamp', if_not_exists => TRUE);

-- trades 테이블 (시간 기준 분할)
SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
```

### 2.2 Retention Policy (선택)

오래된 데이터 자동 삭제:

```sql
-- spreads: 90일 이상 데이터 삭제
SELECT add_retention_policy('spreads', INTERVAL '90 days', if_not_exists => TRUE);

-- fx_rates: 180일 이상 데이터 삭제
SELECT add_retention_policy('fx_rates', INTERVAL '180 days', if_not_exists => TRUE);

-- orders: 365일 이상 데이터 삭제
SELECT add_retention_policy('orders', INTERVAL '365 days', if_not_exists => TRUE);
```

### 2.3 Continuous Aggregates (선택)

실시간 집계 뷰:

```sql
-- 일일 PnL 요약
CREATE MATERIALIZED VIEW daily_pnl_summary AS
SELECT
    DATE(timestamp_close) as trade_date,
    symbol,
    COUNT(*) as trade_count,
    SUM(pnl_krw) as total_pnl_krw,
    AVG(pnl_pct) as avg_pnl_pct,
    MAX(pnl_krw) as max_pnl_krw,
    MIN(pnl_krw) as min_pnl_krw
FROM positions
WHERE status = 'CLOSED'
GROUP BY DATE(timestamp_close), symbol;

-- 시간별 스프레드 평균
CREATE MATERIALIZED VIEW hourly_spread_avg AS
SELECT
    TIME_BUCKET('1 hour', timestamp) as hour,
    symbol,
    AVG(spread_pct) as avg_spread_pct,
    AVG(net_spread_pct) as avg_net_spread_pct,
    MAX(spread_pct) as max_spread_pct,
    MIN(spread_pct) as min_spread_pct
FROM spreads
GROUP BY TIME_BUCKET('1 hour', timestamp), symbol;
```

---

## 3. Redis 캐시 구조

Redis는 실시간 캐시 및 헬스 상태 관리에 사용됩니다.

### 3.1 키 설계

```
# FX 환율 캐시
fx:usdkrw                    → float (예: 1350.0)
fx:eurkrw                    → float (예: 1500.0)

# 스프레드 스냅샷 (JSON)
spreads:BTC:last             → JSON (최근 SpreadOpportunity)
spreads:ETH:last             → JSON (최근 SpreadOpportunity)

# 포지션 스냅샷
positions:BTC:open_count     → int (열린 포지션 수)
positions:ETH:open_count     → int (열린 포지션 수)

# 헬스 상태 (heartbeat timestamp)
health:collector             → timestamp (마지막 수집 시간)
health:paper                 → timestamp (마지막 Paper Trading 시간)
health:live                  → timestamp (마지막 Live Trading 시간)

# 메트릭 집계 (향후)
metrics:daily_pnl:2025-11-15 → JSON (일일 PnL 요약)
metrics:hourly_spread:2025-11-15-03 → JSON (시간별 스프레드)
```

### 3.2 TTL (Time-To-Live) 설정

```python
# FX 환율: 3초 (config.fx.ttl_seconds)
SET fx:usdkrw 1350.0 EX 3

# 스프레드 스냅샷: 60초
SET spreads:BTC:last "{...}" EX 60

# 헬스 상태: 10초 (heartbeat 주기)
SET health:collector "2025-11-15T03:40:15Z" EX 10

# 메트릭: 1일
SET metrics:daily_pnl:2025-11-15 "{...}" EX 86400
```

### 3.3 Python 인터페이스 (PHASE D)

```python
from arbitrage.storage import RedisCacheStorage

redis_cache = RedisCacheStorage(config.get("storage", {}).get("redis", {}))

# FX 환율 저장/조회
redis_cache.set_fx_rate("USDKRW", 1350.0, ttl=3)
rate = redis_cache.get_fx_rate("USDKRW")

# 스프레드 스냅샷 저장/조회
redis_cache.set_spread_snapshot("BTC", {"spread_pct": 0.8, "net_spread_pct": 0.5})
snapshot = redis_cache.get_spread_snapshot("BTC")

# 헬스 상태 기록
redis_cache.set_health_heartbeat("collector")
redis_cache.set_health_heartbeat("paper")
redis_cache.set_health_heartbeat("live")
```

---

## 4. 마이그레이션 전략 (CSV → PostgreSQL)

### 4.1 단계별 마이그레이션

**PHASE D – Step 1: 기본 구조**
- PostgreSQL 테이블 생성
- CsvStorage 읽기 → PostgresStorage 쓰기 (dual-write)

**PHASE D – Step 2: 검증**
- CSV와 PostgreSQL 데이터 비교
- 성능 테스트

**PHASE D – Step 3: 전환**
- 기본 backend를 PostgreSQL로 변경
- CSV 로그는 백업용으로 유지

### 4.2 마이그레이션 스크립트 예시

```python
# scripts/migrate_csv_to_postgres.py (PHASE D)
import csv
from pathlib import Path
from arbitrage.storage import PostgresStorage
from arbitrage.models import Position, SpreadOpportunity, OrderLeg

def migrate_positions(csv_file, storage):
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pos = Position(...)  # CSV 행 → Position 객체
            storage.log_position_open(pos)
            if row.get("status") == "CLOSED":
                storage.log_position_close(pos)

def migrate_spreads(csv_file, storage):
    # 유사하게 spreads.csv 마이그레이션

def migrate_orders(csv_file, storage):
    # 유사하게 orders.csv 마이그레이션
```

---

## 5. 성능 고려사항

### 5.1 인덱싱 전략

- **positions**: symbol, status, timestamp_open (자주 조회)
- **orders**: position_id, symbol, venue, timestamp (조인 및 필터링)
- **spreads**: symbol, is_opportunity, timestamp (실시간 조회)
- **fx_rates**: pair, timestamp (최근값 조회)

### 5.2 쿼리 최적화

```sql
-- 최근 BTC 포지션 조회 (빠름)
SELECT * FROM positions 
WHERE symbol = 'BTC' AND status = 'CLOSED'
ORDER BY timestamp_close DESC 
LIMIT 100;

-- 일일 PnL 계산 (TimescaleDB 집계)
SELECT 
    DATE(timestamp_close) as trade_date,
    SUM(pnl_krw) as daily_pnl,
    COUNT(*) as trade_count
FROM positions
WHERE status = 'CLOSED'
GROUP BY DATE(timestamp_close)
ORDER BY trade_date DESC;

-- 최근 스프레드 평균 (시간별)
SELECT 
    TIME_BUCKET('1 hour', timestamp) as hour,
    AVG(net_spread_pct) as avg_spread
FROM spreads
WHERE symbol = 'BTC'
GROUP BY TIME_BUCKET('1 hour', timestamp)
ORDER BY hour DESC
LIMIT 24;
```

### 5.3 연결 풀링

```python
# PHASE D: psycopg2 또는 asyncpg 사용
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
    min_size=5,
    max_size=20
)
```

---

## 6. 보안 고려사항

### 6.1 데이터베이스 접근 제어

```sql
-- 전용 사용자 생성
CREATE USER arbitrage WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE arbitrage TO arbitrage;
GRANT USAGE ON SCHEMA public TO arbitrage;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO arbitrage;
```

### 6.2 환경 변수 관리

```python
# config/base.yml (또는 환경 변수)
storage:
  postgres:
    dsn: ${DATABASE_URL}  # 환경 변수에서 읽기
```

### 6.3 SSL/TLS 연결

```python
# PHASE D: SSL 연결 설정
dsn = "postgresql://user:password@host:5432/db?sslmode=require"
```

---

## 7. 모니터링 및 관리

### 7.1 데이터베이스 상태 확인

```sql
-- 테이블 크기
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 느린 쿼리 로그
SELECT query, calls, mean_time FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### 7.2 Redis 모니터링

```bash
# Redis CLI
redis-cli INFO stats
redis-cli KEYS "arbitrage:*"
redis-cli MONITOR  # 실시간 명령 모니터링
```

---

## 8. 향후 확장 계획

### 8.1 PHASE E – Dashboard & Monitoring
- Grafana 대시보드 (PostgreSQL 데이터 시각화)
- Prometheus 메트릭 수집

### 8.2 PHASE F – ML/Analytics
- 시계열 데이터 분석
- 머신러닝 기반 스프레드 예측

### 8.3 PHASE G – Multi-Region
- 여러 거래소/지역 데이터 통합
- 분산 데이터베이스 구조

---

## 참고

- **PostgreSQL 공식 문서**: https://www.postgresql.org/docs/
- **TimescaleDB 공식 문서**: https://docs.timescale.com/
- **Redis 공식 문서**: https://redis.io/documentation
- **Python psycopg2**: https://www.psycopg.org/
- **Python redis-py**: https://github.com/redis/redis-py

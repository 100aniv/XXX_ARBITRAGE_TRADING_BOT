# SYSTEM DESIGN - Arbitrage Trading System

**Version:** 2.0  
**Last Updated:** 2025-11-21  
**Status:** Production Infrastructure Complete (D72-4)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Core Components](#core-components)
4. [State Management](#state-management)
5. [Logging & Monitoring](#logging--monitoring)
6. [Multi-Symbol Architecture](#multi-symbol-architecture)
7. [Paper vs Live Mode](#paper-vs-live-mode)
8. [Performance Optimization](#performance-optimization)
9. [Deployment Strategy](#deployment-strategy)

---

## System Overview

### Mission Statement
본 시스템은 **다중 거래소 간 차익거래(Arbitrage)**를 자동으로 수행하는 **Production-grade** 트레이딩 엔진입니다.

### Key Characteristics
- **Single Engine Core:** Backtest/Paper/Live 모두 동일한 엔진 코드 공유
- **Multi-Symbol Support:** Top-N (20~100개) 심볼 동시 처리 (PHASE18 이후)
- **State Persistence:** Redis + PostgreSQL 기반 장애 복구
- **Real-time Monitoring:** 4-backend logging + 60s rolling metrics
- **DO-NOT-TOUCH CORE:** 핵심 로직은 불변, 확장은 wrapper 기반

### Technology Stack
- **Language:** Python 3.9+
- **Async Framework:** asyncio (향후 uvloop)
- **State Store:** Redis 6.0+ (Stream support)
- **Database:** PostgreSQL 12+ (JSONB GIN indexes)
- **Monitoring:** LoggingManager (File/Console/Redis/PostgreSQL)
- **Deployment:** Docker Compose (향후 K8s)

---

## Architecture Principles

### 1. Single Source of Truth (SSOT)
- **Config:** `config/` 모듈 기반 중앙 집중식 (D72-1)
- **Redis Keyspace:** KeyBuilder 기반 도메인 표준화 (D72-2)
- **State:** StateStore 단일 인터페이스

### 2. Immutability
- **Config objects:** frozen dataclass
- **Core engine logic:** 수정 금지, 확장만 허용

### 3. Fail-Safe Design
- **Graceful degradation:** Redis 실패 시 PostgreSQL fallback
- **Auto-recovery:** WebSocket reconnect (exponential backoff)
- **State resume:** Snapshot 기반 중단없는 복구

### 4. Observable System
- **Structured logging:** JSON 기반, 4 backends
- **Metrics collection:** 60s rolling window
- **Real-time monitoring:** CLI tool + Dashboard ready

---

## Core Components

### Engine Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 ArbitrageEngine (Core)                  │
│                  DO-NOT-TOUCH CORE                      │
└──────────┬──────────────────────────────────────────────┘
           │
           ├──► MarketDataSubscriber (WS + REST)
           ├──► OpportunityDetector (Spread calculation)
           ├──► ExecutionManager (Order placement)
           ├──► PositionManager (Multi-symbol aware)
           ├──► RiskGuard (Portfolio + Symbol level)
           └──► StateStore (Redis + PostgreSQL)
```

### Component Details

#### 1. MarketDataSubscriber
- **Role:** 실시간 시장 데이터 수집
- **Sources:** Binance WS, Upbit WS (REST fallback)
- **Multi-symbol:** Per-symbol subscription queue
- **Latency tracking:** ws_latency metric 수집

**현재 상태:**
- Single symbol support (D65-D71)
- **향후 확장 (D80-D89):** Top-20/50/100 멀티심볼

#### 2. OpportunityDetector
- **Role:** 차익거래 기회 탐지
- **Algorithm:** Spread = (sell_price - buy_price) - (fees + slippage)
- **Threshold:** Config 기반 min_profit_threshold

#### 3. ExecutionManager
- **Role:** 주문 실행 및 상태 관리
- **Order types:** LIMIT, MARKET (향후 STOP_LOSS, TAKE_PROFIT)
- **State machine:** PENDING → FILLED → CLOSED

**Paper vs Live 차별화:**
| 기능 | Paper Mode | Live Mode |
|------|------------|-----------|
| 체결 | 시뮬레이션 fill engine | 거래소 fill event |
| order_id | internal UUID | 거래소 order_id |
| Slippage | 시뮬레이션 | 실측 기반 adaptive |
| TP/SL | 엔진 기반 가상 | 엔진 + 거래소 native(OCO) 병행 |

#### 4. PositionManager
- **Role:** 포지션 추적 및 PnL 계산
- **Multi-symbol:** Symbol-level position tracking
- **Metrics:** per_symbol_pnl, total_portfolio_pnl

**현재 상태:**
- Single symbol focus
- **향후 확장:** Symbol bucket, exposure cap

#### 5. RiskGuard
- **Role:** 리스크 한도 관리
- **Levels:**
  - Symbol level: 심볼별 노출 한도
  - Portfolio level: 전체 위험 한도
  - Daily level: 일일 손실 한도

**Guard Types:**
- `MAX_POSITION_SIZE`: 최대 포지션 크기
- `MAX_DAILY_LOSS`: 일일 최대 손실
- `MAX_DRAWDOWN`: 최대 낙폭
- `COOLDOWN`: 거래 쿨다운

#### 6. StateStore
- **Role:** 상태 영속화 및 복구
- **Backends:** Redis (primary), PostgreSQL (snapshot)
- **Integration:** KeyBuilder 기반 표준화된 키 생성

**State Categories:**
- `SESSION`: 세션 메타데이터
- `POSITION`: 포지션 상태
- `METRICS`: 실시간 메트릭
- `GUARD`: RiskGuard 상태

---

## State Management

### Redis Keyspace (D72-2)

**Standard Format:**
```
arbitrage:{env}:{session_id}:{domain}:{symbol}:{field}
```

**Domains:**
- `STATE`: 엔진 상태
- `METRICS`: 실시간 메트릭
- `GUARD`: RiskGuard 상태
- `COOLDOWN`: 쿨다운 타이머
- `PORTFOLIO`: 포트폴리오 집계
- `SNAPSHOT`: 스냅샷 메타
- `WS`: WebSocket 상태

**TTL Policy:**
| Domain | TTL | Rationale |
|--------|-----|-----------|
| STATE | 3600s (1h) | 세션 활성 중 유지 |
| METRICS | 120s (2min) | 실시간 모니터링용 |
| GUARD | 7200s (2h) | 장시간 쿨다운 대응 |
| COOLDOWN | 3600s (1h) | 쿨다운 만료 자동 삭제 |
| SNAPSHOT | 86400s (24h) | 복구 가능 기간 |

### PostgreSQL Schema (D70, D72-3)

#### snapshot_tables (4개)
1. **session_snapshots:** 세션 메타데이터
2. **position_snapshots:** 포지션 상태 (JSONB)
3. **metrics_snapshots:** 메트릭 스냅샷 (JSONB)
4. **risk_guard_snapshots:** RiskGuard 상태 (JSONB)

**Indexes (19개):**
- 복합 인덱스: (session_id, created_at)
- JSONB GIN 인덱스: trade_data, per_symbol_*
- 시계열 인덱스: created_at DESC

**Retention Policy (D72-3):**
- Default: 30일 자동 cleanup
- Target: stopped/crashed 세션만 삭제
- Active 세션: 보존

---

## Logging & Monitoring

### LoggingManager Architecture (D72-4)

```
┌─────────────────────────────────────────────────────────┐
│                   LoggingManager                        │
│                    (Singleton)                          │
└──────────┬──────────┬──────────┬──────────┬────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
    ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
    │  File    │ │ Console │ │  Redis   │ │Postgres  │
    │ Logger   │ │ Logger  │ │ Logger   │ │ Logger   │
    └──────────┘ └─────────┘ └──────────┘ └──────────┘
         │            │           │            │
         ▼            ▼           ▼            ▼
    logs/       stdout       Stream       system_logs
  arbitrage_                 maxlen=      (WARNING+)
  {env}.log                  1000
```

### Log Levels & Filtering

| Environment | Min Level | File | Console | Redis | PostgreSQL |
|-------------|-----------|------|---------|-------|------------|
| development | DEBUG | ✅ | ✅ | ✅ | WARNING+ |
| staging | INFO | ✅ | ✅ | ✅ | WARNING+ |
| production | WARNING | ✅ | ❌ | ✅ | WARNING+ |

### Log Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `ENGINE` | 엔진 이벤트 | Start, stop, state changes |
| `TRADE` | 거래 실행 | Order placed, filled, cancelled |
| `GUARD` | 리스크 가드 | Limit hit, cooldown activated |
| `RISK` | 리스크 관리 | Exposure check, rebalance |
| `EXCHANGE` | 거래소 작업 | API calls, rate limits |
| `POSITION` | 포지션 관리 | Open, close, modify |
| `SYNC` | 상태 동기화 | Redis/DB save, load |
| `WEBSOCKET` | WS 이벤트 | Connect, disconnect, message |
| `METRICS` | 메트릭 업데이트 | Performance data |
| `SYSTEM` | 시스템 이벤트 | Startup, shutdown, config |

### MetricsCollector (D72-4)

**60-second Rolling Window:**
- `trades_per_minute`: 분당 거래 수
- `errors_per_minute`: 분당 에러 수
- `avg_ws_latency_ms`: 평균 WS 지연
- `avg_loop_latency_ms`: 평균 루프 지연
- `guard_triggers_per_minute`: 분당 가드 발동
- `pnl_change_1min`: 1분 PnL 변화

**Flush Strategy:**
- Per-second flush to Redis
- Aggregation over 60 samples
- TTL: 120s (2 minutes)

### CLI Monitoring Tool

**Commands:**
```bash
# Tail logs in real-time
python tools/monitor.py --tail

# Watch metrics dashboard
python tools/monitor.py --metrics

# Monitor errors only
python tools/monitor.py --errors

# Search logs
python tools/monitor.py --search "trade execution"
```

---

## Multi-Symbol Architecture

### Current State (D65-D71)
- **Single symbol focus:** BTCUSDT hardcoded
- **Position tracking:** Single position object
- **RiskGuard:** Global limits only

### Target State (D80-D89 PHASE18+)

#### Symbol Expansion Roadmap
1. **Top-20:** 상위 20개 심볼 (D80-D82)
2. **Top-50:** 상위 50개 심볼 (D83-D85)
3. **Top-100:** 상위 100개 심볼 (D86-D89)

#### Multi-Symbol Engine Loop

```python
async def run_multi_symbol_engine():
    """Per-symbol coroutine with shared scheduler"""
    symbols = select_top_n_symbols(N=20)
    
    tasks = []
    for symbol in symbols:
        task = asyncio.create_task(
            run_symbol_engine(symbol, shared_portfolio, shared_guard)
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)
```

#### Portfolio Manager

```python
class PortfolioManager:
    """Multi-symbol portfolio management"""
    
    def __init__(self, max_total_exposure: float):
        self.symbol_buckets: Dict[str, SymbolBucket] = {}
        self.max_total_exposure = max_total_exposure
    
    def allocate_exposure(self, symbol: str) -> float:
        """Allocate exposure per symbol"""
        # Symbol weight based on volume, volatility
        weight = self.calculate_symbol_weight(symbol)
        return self.max_total_exposure * weight
    
    def check_portfolio_risk(self) -> bool:
        """Check total portfolio risk"""
        total_exposure = sum(
            bucket.current_exposure 
            for bucket in self.symbol_buckets.values()
        )
        return total_exposure <= self.max_total_exposure
```

#### RiskGuard Extension

**Hierarchy:**
```
GlobalGuard
├── PortfolioGuard (전체 노출 한도)
├── SymbolGuard[BTCUSDT] (심볼별 한도)
├── SymbolGuard[ETHUSDT]
└── ...
```

**Symbol-level Guards:**
- `MAX_SYMBOL_POSITION`: 심볼별 최대 포지션
- `MAX_SYMBOL_DAILY_LOSS`: 심볼별 일일 손실
- `SYMBOL_COOLDOWN`: 심볼별 쿨다운

#### KeyBuilder Multi-Symbol Support

**Already implemented (D72-2):**
```python
KeyBuilder(Domain.STATE, symbol="BTCUSDT", field="position")
# → arbitrage:dev:session_123:STATE:BTCUSDT:position

KeyBuilder(Domain.METRICS, symbol="ETHUSDT")
# → arbitrage:dev:session_123:METRICS:ETHUSDT
```

**모든 모듈은 기본적으로 `symbol=None` → multi-symbol aware로 설계됨**

---

## Paper vs Live Mode

### Execution Mode Comparison

| 영역 | Paper Mode | Live Mode |
|------|------------|-----------|
| **TP/SL** | 엔진 기반 가상 TP/SL | 엔진 + 거래소 native TP/SL(OCO) 병행 |
| **체결** | 시뮬레이션 fill engine | 거래소 fill event 기반 |
| **Slippage** | 시뮬레이션 (config 기반) | 실측 슬리피지 기반 adaptive SL |
| **order_id** | internal UUID | 실제 거래소 order_id |
| **WebSocket** | 실시간 데이터 (동일) | 실시간 데이터 (동일) |
| **State persistence** | 동일 (Redis + PostgreSQL) | 동일 (Redis + PostgreSQL) |
| **RiskGuard** | 동일 (논리적 차단) | 동일 + 거래소 한도 체크 |
| **PnL calculation** | 동일 (수수료 포함) | 동일 (실제 수수료) |

### Paper Mode Implementation

**Fill Engine Simulation:**
```python
def _inject_paper_prices(self):
    """Dynamic spread injection for Entry/Exit"""
    if self.has_open_position():
        # Generate negative spread for Exit
        spread = -0.0005
    else:
        # Generate positive spread for Entry
        spread = 0.0015
    
    return spread
```

**Trade Lifecycle (D64 Fix):**
- Entry: spread > threshold → open position
- Exit: spread < 0 (after 10s) → close position
- PnL: (exit_price - entry_price) - fees

### Live Mode Extensions

**Native TP/SL Integration:**
```python
class LiveExecutionManager(ExecutionManager):
    """Live mode with native TP/SL"""
    
    async def place_order_with_tp_sl(
        self, 
        symbol: str,
        side: str,
        quantity: float,
        take_profit: float,
        stop_loss: float
    ):
        # Engine-level TP/SL (backup)
        self.register_engine_tp_sl(take_profit, stop_loss)
        
        # Native exchange TP/SL (primary)
        order_result = await self.exchange.place_oco_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        
        return order_result
```

---

## Performance Optimization

### 상용급 성능 최적화 10대 항목 (D75-D79)

#### 1. 이벤트 루프 단일화
**Current:** Multiple event loops per component  
**Target:** Single async engine loop + multi-exchange fan-out  
**Benefit:** Reduced context switching, <5ms loop latency

#### 2. Redis 단일 커넥션 풀 + Pipeline/MGET
**Current:** Per-operation connection  
**Target:** Connection pool + batched operations  
**Benefit:** 50% Redis latency reduction

#### 3. Postgres 비동기화(AIO) + COPY 기반 고속 insert
**Current:** Synchronous psycopg2  
**Target:** asyncpg + COPY for bulk inserts  
**Benefit:** 10x insert throughput

#### 4. In-Memory snapshot 가중치 캐싱
**Current:** Redis round-trip per snapshot load  
**Target:** In-memory LRU cache  
**Benefit:** <1ms snapshot access

#### 5. MetricsCollector 배치 플러시 + zero-alloc 구조
**Current:** Per-second individual flush  
**Target:** Batched flush + reusable buffers  
**Benefit:** Reduced GC pressure

#### 6. Live 시 네이티브 TP/SL (OCO 등) 병행 구조
**Current:** Engine-only TP/SL  
**Target:** Hybrid (engine + exchange native)  
**Benefit:** Faster execution, reduced slippage

#### 7. MarketDataSubscriber 멀티심볼 구독 최적화
**Current:** Per-symbol WS connection  
**Target:** Single WS with multiplexed subscriptions  
**Benefit:** Reduced WS overhead

#### 8. SymbolSelector AI 기반 자산 우선순위 선정
**Current:** Fixed symbol list  
**Target:** Dynamic symbol selection (volume, volatility, spread)  
**Benefit:** Higher quality opportunities

#### 9. Config hot-reload
**Current:** Restart required for config changes  
**Target:** Runtime config reload with validation  
**Benefit:** Zero-downtime parameter tuning

#### 10. 분산 튜닝 클러스터 (Random → Bayesian → LocalGrid)
**Current:** Sequential tuning  
**Target:** Distributed workers with Bayesian optimization  
**Benefit:** 10x faster hyperparameter search

### Performance Targets (D75-D79)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Loop latency (avg) | ~15ms | <10ms | 🎯 Target |
| Loop latency (p99) | ~50ms | <25ms | 🎯 Target |
| Redis latency | ~2ms | <1ms | 🎯 Target |
| CPU usage | ~60% | <70% | ✅ OK |
| Memory (RSS) | Stable | Drift <5% | 🎯 Target |
| WS reconnect MTTR | ~20s | <5s | 🎯 Target |

---

## Deployment Strategy

### Current State (D72)
- **Docker Compose:** Redis + PostgreSQL
- **Local execution:** Windows CMD
- **Environment:** development/staging/production config

### Target State (D97-D98)

#### Docker/K8s Deployment
```yaml
# docker-compose.prod.yml
services:
  arbitrage-engine:
    image: arbitrage:latest
    environment:
      - ENV=production
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres-data:/var/lib/postgresql/data
```

#### systemd Service
```ini
[Unit]
Description=Arbitrage Trading Engine
After=network.target redis.service postgres.service

[Service]
Type=simple
User=arbitrage
WorkingDirectory=/opt/arbitrage
ExecStart=/opt/arbitrage/venv/bin/python main.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

#### Health Check
```python
@app.route('/health')
def health_check():
    """Health check endpoint"""
    checks = {
        "redis": check_redis_connection(),
        "postgres": check_postgres_connection(),
        "ws_binance": check_ws_connection("binance"),
        "ws_upbit": check_ws_connection("upbit"),
        "engine_status": get_engine_status()
    }
    
    if all(checks.values()):
        return {"status": "healthy", "checks": checks}, 200
    else:
        return {"status": "unhealthy", "checks": checks}, 503
```

---

## Appendix

### File Structure

```
arbitrage-lite/
├── arbitrage/
│   ├── engine.py                 # Core engine (DO-NOT-TOUCH)
│   ├── market_data.py            # MarketDataSubscriber
│   ├── execution.py              # ExecutionManager
│   ├── position.py               # PositionManager
│   ├── risk_guard.py             # RiskGuard
│   ├── state_store.py            # StateStore (D70)
│   ├── redis_keyspace.py         # KeyBuilder (D72-2)
│   ├── logging_manager.py        # LoggingManager (D72-4)
│   └── metrics_collector.py      # MetricsCollector (D72-4)
├── config/
│   ├── base.py                   # Config models (D72-1)
│   ├── loader.py                 # Config loader
│   └── environments/
│       ├── development.py
│       ├── staging.py
│       └── production.py
├── db/migrations/
│   ├── d70_state_persistence.sql
│   ├── d72_postgres_optimize.sql (D72-3)
│   └── d72_4_logging_monitoring.sql (D72-4)
├── tools/
│   └── monitor.py                # CLI monitoring tool (D72-4)
├── scripts/
│   ├── apply_d72_migration.py
│   ├── apply_d72_4_migration.py
│   ├── backup_postgres.py
│   └── test_d72_4_logging.py
└── docs/
    ├── SYSTEM_DESIGN.md          # This file
    ├── D72_1_CONFIG_DESIGN.md
    ├── D72_2_REDIS_KEYSPACE_REPORT.md
    ├── D72_3_POSTGRES_PRODUCTIONIZATION.md
    └── D72_4_LOGGING_MONITORING_MVP.md
```

### Integration Flow

```
Startup
  ↓
LoadConfig (D72-1)
  ↓
InitLoggingManager (D72-4)
  ↓
ConnectRedis (KeyBuilder ready, D72-2)
  ↓
ConnectPostgreSQL (Optimized schema, D72-3)
  ↓
InitStateStore (Redis + PostgreSQL)
  ↓
ResumeFromSnapshot? (D70)
  │
  ├─ Yes → LoadState → Continue
  └─ No  → CleanStart
       ↓
  StartEngine
       ↓
  MainLoop (Async)
    ├─ FetchMarketData (WS)
    ├─ DetectOpportunity
    ├─ CheckRiskGuard
    ├─ ExecuteTrade
    ├─ UpdatePosition
    ├─ SaveSnapshot
    ├─ FlushMetrics (every 1s)
    └─ Log Events (4 backends)
```

---

**End of SYSTEM_DESIGN.md**

**Next Steps:**
- D72-5: Docker deployment infrastructure
- D72-6: Operational documentation
- D73: Prometheus/Grafana monitoring dashboard
- D75-D79: Performance optimization (10대 항목)
- D80-D89: Multi-symbol expansion (Top-20/50/100)

# PHASE C – Multi-Symbol & FX Normalization & Risk Tiering

## 목표
- Multi-symbol 지원 (BTC, ETH 우선)
- Symbol-level config override
- 실시간 환율(FX) 업데이트
- Tier-based Risk System 도입

## 작업 범위
- config/base.yml → symbols.* 설정 확장
- arbitrage/normalizer.py → FX 모듈 강화
- arbitrage/engine.py → 심볼별 net_spread 계산 분리
- arbitrage/risk.py → 심볼별 리스크 한도 적용
- storage/logging은 PHASE D로 미루고 이번 PHASE에서는 최소 수정만

## 제외 범위
- DB, GUI, 모니터링 → PHASE D
- ML/ALGO 개선 → PHASE E

## 산출물
- 코드 패치
- config schema 확장
- 테스트 로그
- CHANGELOG 업데이트

---

## C1 – Multi-Symbol 구조 개편 (상세 분석)

### 현재 코드 흐름 (BTC 단일 심볼 전제)
```
scripts/run_paper.py
  ├─ for symbol in symbols:  # 현재: ["BTC"]만 지원
  │   ├─ collector.get_tickers(symbol)
  │   │   └─ Ticker(symbol="BTC", price=...)
  │   ├─ engine.compute_spread_opportunity(upbit_ticker, binance_ticker, config)
  │   │   └─ SpreadOpportunity(symbol="BTC", spread_pct=..., net_spread_pct=...)
  │   ├─ risk.can_open_new_position(config, self.positions, opp)
  │   │   └─ (bool, reason)
  │   └─ executor.on_opportunity(opp, now)
  │       ├─ risk.should_close_position(position, opp, now)
  │       ├─ executor.execute_exit(position, signal, config)
  │       ├─ executor.execute_entry(signal, size, config)
  │       └─ Position(symbol="BTC", ...)
```

### 변경 필요 포인트

#### 1. config/base.yml
**현재:**
```yaml
symbols:
  - BTC
sizing:
  max_notional_krw: 100000
  max_open_positions: 1
```

**변경 후:**
```yaml
symbols:
  - name: BTC
    sizing:
      max_notional_krw: 100000
    spread:
      min_net_spread_pct: 0.5
  - name: ETH
    sizing:
      max_notional_krw: 50000
    spread:
      min_net_spread_pct: 0.5

sizing:
  max_total_notional_krw: 500000
  max_open_positions: 2  # 전체 포지션
```

#### 2. scripts/run_paper.py
**현재:**
```python
for symbol in symbols:
    opportunity = engine.compute_spread_opportunity(upbit_ticker, binance_ticker, config)
    signals = executor.on_opportunity(opportunity, now)
```

**변경 후:**
```python
for symbol in symbols:
    upbit_ticker = collector.get_ticker(symbol, "upbit")
    binance_ticker = collector.get_ticker(symbol, "binance")
    symbol_config = config_manager.get_symbol_config(symbol, config)
    opportunity = engine.compute_spread_opportunity(upbit_ticker, binance_ticker, symbol_config)
    signals = executor.on_opportunity(opportunity, now, symbol)
```

#### 3. arbitrage/engine.py
**현재:**
```python
def compute_spread_opportunity(upbit_ticker, binance_ticker, config):
    binance_price_krw = to_krw_price(binance_ticker, config)
    # ...
    return SpreadOpportunity(symbol=upbit_ticker.symbol, ...)
```

**변경 후:**
```python
def compute_spread_opportunity(upbit_ticker, binance_ticker, config, symbol=None):
    symbol = symbol or upbit_ticker.symbol
    symbol_config = config.get("symbols", {}).get(symbol, config)
    binance_price_krw = to_krw_price(binance_ticker, symbol_config)
    # ...
    return SpreadOpportunity(symbol=symbol, ...)
```

#### 4. arbitrage/risk.py
**현재:**
```python
def can_open_new_position(config, current_positions, opp):
    max_positions = config.get("sizing", {}).get("max_open_positions", 1)
    open_positions = [p for p in current_positions if p.status == "OPEN"]
    return len(open_positions) < max_positions, "ENTRY_OK"
```

**변경 후:**
```python
def can_open_new_position(config, current_positions, opp, symbol=None):
    symbol = symbol or opp.symbol
    symbol_config = config.get("symbols", {}).get(symbol, config)
    
    # 심볼별 최대 포지션 체크
    max_positions = symbol_config.get("sizing", {}).get("max_open_positions", 1)
    symbol_open = [p for p in current_positions if p.status == "OPEN" and p.symbol == symbol]
    if len(symbol_open) >= max_positions:
        return False, "MAX_POSITIONS_SYMBOL"
    
    # 포트폴리오 전체 최대 포지션 체크
    total_max = config.get("sizing", {}).get("max_open_positions", 2)
    all_open = [p for p in current_positions if p.status == "OPEN"]
    if len(all_open) >= total_max:
        return False, "MAX_POSITIONS_PORTFOLIO"
    
    return True, "ENTRY_OK"
```

#### 5. arbitrage/executor.py
**현재:**
```python
class PaperExecutor:
    def __init__(self, config, storage, ...):
        self.positions = []  # 모든 포지션 (BTC만)
    
    def on_opportunity(self, opp, now):
        # opp.symbol은 항상 "BTC"
```

**변경 후:**
```python
class PaperExecutor:
    def __init__(self, config, storage, ...):
        self.positions = {}  # {symbol: [Position, ...]}
    
    def on_opportunity(self, opp, now, symbol=None):
        symbol = symbol or opp.symbol
        if symbol not in self.positions:
            self.positions[symbol] = []
        # symbol별 포지션 관리
```

### 영향 범위 요약
| 파일 | 변경 유형 | 영향도 |
|------|---------|--------|
| config/base.yml | 스키마 확장 | 높음 |
| scripts/run_paper.py | 루프 로직 추가 | 중간 |
| arbitrage/engine.py | 파라미터 추가 | 중간 |
| arbitrage/risk.py | 로직 확장 | 높음 |
| arbitrage/executor.py | 데이터 구조 변경 | 높음 |
| arbitrage/normalizer.py | 최소 수정 | 낮음 |
| arbitrage/storage.py | 최소 수정 | 낮음 |

---

## C2 – FX Normalization & TTL Caching

### 목표
- 정적 환율 기반 USDT → KRW 변환
- TTL 기반 캐싱으로 API 호출 과도 방지
- Failsafe: 환율 0 또는 급등락 시 최근 값 유지
- 향후 API/DB 연동 가능한 구조 설계

### 구현 내용
- **arbitrage/fx.py**: 신규 모듈, TTL 캐싱 포함
- **config/base.yml**: fx.ttl_seconds, fx.mode, fx.source_prefer 추가
- **arbitrage/normalizer.py**: to_krw_price()가 fx.get_usdkrw() 호출
- **arbitrage/engine.py**: 로깅 추가 (FX 변환 명시)
- **scripts/run_paper.py**: FX 정보 콘솔 출력

### 향후 확장 (PHASE D)
- fetch_usdkrw_from_upbit(): 업비트 USDT-KRW 시세 조회
- fetch_usdkrw_from_api(): 외부 API 연동
- fetch_usdkrw_from_db(): DB 기반 환율 조회

---

## C3 – Order Routing & Slippage Model

### 목표
- 포지션을 "2개의 OrderLeg"로 명확히 표현 (Upbit + Binance)
- Per-venue 슬리피지 모델 (bps 기반)
- Storage 계층 확장 (logs/orders.csv)
- 향후 DB/Redis backend로 쉽게 전환 가능한 구조

### 구현 내용

#### 1. 데이터 모델 (arbitrage/models.py)
- **OrderLeg**: 주문 레그 모델 추가
  - symbol, venue, side, qty
  - price_theoretical, price_effective
  - slippage_bps, leg_id, order_id
  - timestamp (UTC timezone aware)

#### 2. Order Routing (arbitrage/executor.py)
- **_create_order_legs()**: Position → 2개의 OrderLeg 생성
  - Direction 파싱: "upbit_short_binance_long" 등
  - ENTRY: Upbit sell/buy + Binance long/short
  - EXIT: Upbit buy/sell + Binance short/long

#### 3. Slippage Model (arbitrage/executor.py)
- **_get_slippage_bps()**: 거래소별 슬리피지 조회 (bps)
- **_apply_slippage()**: 이론가 → 실제 체결가 변환
  - Buy/Long: 가격 상승 (불리함)
  - Sell/Short: 가격 하락 (불리함)

#### 4. Storage 확장 (arbitrage/storage.py)
- **log_order()**: OrderLeg를 logs/orders.csv에 기록
  - Headers: timestamp, symbol, venue, side, qty, price_theoretical, price_effective, slippage_bps, order_id, leg_id
  - CSV append 방식 (기존 _append_csv 재사용)

#### 5. Config 확장 (config/base.yml)
```yaml
slippage:
  upbit:
    base_bps: 10
    volatility_factor: 1.0
  binance_futures:
    base_bps: 5
    volatility_factor: 1.0
```

### Flow 다이어그램
```
SpreadOpportunity
  ├─ TradeSignal (OPEN/CLOSE)
  │   └─ Position (symbol, direction, size, ...)
  │       └─ OrderLeg x2 (Upbit leg + Binance leg)
  │           ├─ price_theoretical
  │           ├─ slippage_bps 적용
  │           └─ price_effective
  │               └─ storage.log_order() → logs/orders.csv
```

### 향후 확장 (PHASE D – Persistence & Infra)
- **DB Backend**: Postgres/TimescaleDB로 orders 테이블 저장
- **Redis Cache**: 최근 OrderLeg 조회 캐싱
- **Docker-compose**: DB + Redis + App 통합 배포
- **SimpleStorage 인터페이스 유지**: Backend 교체 시 코드 수정 최소화

---

## C4 – Persistence & Metrics (DB/Redis & Docker-ready)

### 목표
- Storage backend 추상화 (BaseStorage 인터페이스)
- DB/Redis 설계 문서화 (실제 구현은 PHASE D)
- Metrics 스냅샷 스크립트 (CSV 기반)
- Docker-compose 인프라 스켈레톤

### 구현 내용

#### 1. Storage 인터페이스 리팩터링 (arbitrage/storage.py)
- **BaseStorage**: 추상 클래스 (모든 저장소 구현의 기본)
- **CsvStorage**: CSV 파일 기반 구현 (현재 기본, 기존 SimpleStorage 대체)
- **PostgresStorage**: PostgreSQL/TimescaleDB 기반 (PHASE D 예정, stub)
- **RedisCacheStorage**: Redis 캐시 헬퍼 (PHASE D 예정, stub)
- **get_storage()**: 팩토리 함수 (config.storage.backend 기반 선택)

#### 2. Config 확장 (config/base.yml)
```yaml
storage:
  backend: csv  # csv | postgres | hybrid
  postgres:
    dsn: postgresql://arbitrage:arbitrage@localhost:5432/arbitrage
    schema: public
    enable_timescale: false
  redis:
    url: redis://localhost:6379/0
    prefix: arbitrage
```

#### 3. DB Schema 설계 (docs/DB_SCHEMA.md)
- **PostgreSQL 테이블**: positions, orders, spreads, fx_rates, trades
- **TimescaleDB 확장**: hypertable 설정, retention policy, continuous aggregates
- **Redis 키 구조**: fx:usdkrw, spreads:{symbol}:last, health:*, metrics:*
- **마이그레이션 전략**: CSV → PostgreSQL 단계별 계획

#### 4. Metrics 스냅샷 스크립트 (scripts/run_metrics_snapshot.py)
- CSV 로그 파일 읽기 (positions.csv, orders.csv, spreads.csv)
- 메트릭 계산:
  - 총 PnL (KRW)
  - 승률 (%)
  - 심볼별 PnL
  - 슬리피지 통계 (PHASE C3+)
  - 최근 N개 트레이드 목록
- 콘솔 출력 (보기 좋은 포맷)

#### 5. Docker-compose 인프라 (infra/docker-compose.yml)
- **postgres**: TimescaleDB 최신 이미지 (pg16)
- **redis**: Redis 7 (Alpine)
- **adminer**: DB 관리 UI (포트 8080)
- 향후 추가 (PHASE D):
  - arbitrage-app: 봇 애플리케이션
  - prometheus: 메트릭 수집
  - grafana: 대시보드

#### 6. 모델 docstring 보완 (arbitrage/models.py)
- Position, SpreadOpportunity, OrderLeg에 DB Mapping 정보 추가
- PHASE D에서 어떤 테이블로 저장될지 명시

### 하위 호환성
- **SimpleStorage 별칭**: CsvStorage = SimpleStorage (기존 코드 호환)
- **get_storage() fallback**: postgres/hybrid backend 요청 시 CSV로 fallback + WARN 로그
- **기존 run_paper.py 등**: 코드 수정 없이 동작 (CsvStorage 자동 사용)

### 향후 확장 (PHASE D)
- **PostgresStorage 구현**: 실제 DB 연동 (psycopg2/asyncpg)
- **RedisCacheStorage 구현**: Redis 캐시 연동 (redis-py)
- **Docker-compose 확장**: app 컨테이너, prometheus, grafana 추가
- **마이그레이션 스크립트**: CSV → PostgreSQL 자동 변환

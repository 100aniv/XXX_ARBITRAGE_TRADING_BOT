# Configuration Design (D72-1)

**Version:** 1.0  
**Created:** 2025-11-21  
**Status:** ✅ IMPLEMENTED

---

## 📋 Overview

D72-1에서 구현된 Production-ready Configuration 시스템 설계 문서.

**핵심 원칙:**
- **SSOT** (Single Source of Truth): 모든 설정값은 하나의 소스에서 관리
- **Environment-aware**: dev/staging/prod 환경별 설정 분리
- **Type-safe**: dataclass 기반 타입 안전성
- **Validation**: 비즈니스 로직 기반 검증
- **Immutability**: frozen dataclass로 불변성 보장

---

## 🏗️ Architecture

### Directory Structure

```
config/
├── __init__.py               # Public API
├── base.py                   # Core config models (SSOT)
├── loader.py                 # Environment-based loader
├── validators.py             # Business logic validators
├── secrets.example.yaml      # Secrets template
└── environments/
    ├── __init__.py
    ├── development.py        # Dev config
    ├── staging.py            # Staging config
    └── production.py         # Prod config
```

### Class Diagram

```
ArbitrageConfig (SSOT)
├── ExchangeConfig          # API keys, WS settings
├── DatabaseConfig          # Redis, PostgreSQL
├── RiskConfig              # Risk limits
├── TradingConfig           # Spread, fees
├── MonitoringConfig        # Logging, metrics
└── SessionConfig           # Mode, runtime
```

---

## 🎯 Core Models

### 1. ExchangeConfig

거래소 연결 설정

```python
@dataclass(frozen=True)
class ExchangeConfig:
    # API Keys
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    
    # WebSocket settings
    ws_reconnect_max_attempts: int = 10
    ws_reconnect_delay: int = 1
    ws_max_reconnect_delay: int = 60
```

**Features:**
- 환경변수 자동 치환 (`${ENV_VAR}` 형식)
- Production에서는 API keys 필수 (live mode 시)

### 2. DatabaseConfig

Redis 및 PostgreSQL 연결 설정

```python
@dataclass(frozen=True)
class DatabaseConfig:
    # Redis
    redis_host: str = 'localhost'
    redis_port: int = 6380
    redis_password: Optional[str] = None
    
    # PostgreSQL
    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_database: str = 'arbitrage'
    postgres_user: str = 'arbitrage'
    postgres_password: str = 'arbitrage'
    
    # Connection pool
    postgres_pool_min: int = 2
    postgres_pool_max: int = 10
```

**Features:**
- 환경변수 치환 지원
- Connection pool 설정

### 3. RiskConfig

리스크 관리 설정

```python
@dataclass(frozen=True)
class RiskConfig:
    max_notional_per_trade: float = 5000.0
    max_open_trades: int = 1
    max_daily_loss: float = 10000.0
    max_daily_trades: int = 100
    position_size_usd: float = 1000.0
```

**Validation:**
- `max_daily_loss >= max_notional_per_trade`

### 4. TradingConfig

거래 전략 설정

```python
@dataclass(frozen=True)
class TradingConfig:
    min_spread_bps: float = 40.0
    taker_fee_a_bps: float = 10.0
    taker_fee_b_bps: float = 10.0
    slippage_bps: float = 5.0
    exchange_a_to_b_rate: float = 2.5
    bid_ask_spread_bps: float = 100.0
    close_on_spread_reversal: bool = True
```

**Validation:**
- `min_spread_bps > 1.5 * (fee_a + fee_b + slippage)`

### 5. MonitoringConfig

모니터링 및 로깅 설정

```python
@dataclass(frozen=True)
class MonitoringConfig:
    log_level: str = 'INFO'
    log_dir: Path = Path('logs')
    log_rotation: str = '1 day'
    log_retention: str = '30 days'
    metrics_enabled: bool = True
    metrics_interval_seconds: int = 60
    health_check_enabled: bool = True
```

### 6. SessionConfig

세션 관리 설정

```python
@dataclass(frozen=True)
class SessionConfig:
    mode: str = 'paper'              # 'paper', 'live', 'backtest'
    data_source: str = 'paper'       # 'paper', 'ws', 'backtest'
    max_runtime_seconds: Optional[int] = None
    loop_interval_ms: int = 100
    state_persistence_enabled: bool = True
    snapshot_interval_seconds: int = 300
```

---

## 🌍 Environment-specific Configs

### Development

**특징:**
- Debug 로깅
- Paper mode 기본
- API keys 불필요
- 낮은 리스크 한도

**주요 설정:**
```python
log_level='DEBUG'
mode='paper'
data_source='paper'
max_notional_per_trade=5000.0
min_spread_bps=40.0
```

### Staging

**특징:**
- INFO 로깅
- Paper mode + 실제 WS 데이터
- Read-only API keys 사용 가능
- 중간 리스크 한도
- 멀티 심볼 테스트

**주요 설정:**
```python
log_level='INFO'
mode='paper'
data_source='ws'
max_notional_per_trade=10000.0
symbols=['KRW-BTC', 'KRW-ETH']
```

### Production

**특징:**
- WARNING 로깅 (성능)
- 현재는 Paper mode (실거래 전 충분한 검증 필요)
- 모든 secrets 환경변수 필수
- 보수적인 리스크 한도
- 검증된 심볼만 사용

**주요 설정:**
```python
log_level='WARNING'
mode='paper'  # ⚠️ Live mode 전환 시 매우 신중
data_source='ws'
max_notional_per_trade=5000.0
max_daily_trades=50
```

---

## 🔐 Secrets Management

### 환경변수 치환

Config 값에 `${ENV_VAR}` 형식 사용 시 자동 치환:

```python
# production.py
exchange=ExchangeConfig(
    upbit_access_key='${UPBIT_ACCESS_KEY}',
    binance_api_key='${BINANCE_API_KEY}'
)

# 실행 시
export UPBIT_ACCESS_KEY=your_real_key
export BINANCE_API_KEY=your_real_key
```

### Secrets Template

`config/secrets.example.yaml` 제공:

```yaml
ENV=production
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
REDIS_PASSWORD=strong_redis_password
POSTGRES_PASSWORD=strong_postgres_password
```

**사용 방법:**
```bash
cp config/secrets.example.yaml .env
# .env 파일에 실제 값 입력
export $(cat .env | xargs)
```

---

## ✅ Validation Rules

### 1. Spread Profitability

```python
min_spread_bps > 1.5 * (fee_a + fee_b + slippage)
```

**이유:** 수수료와 슬리피지를 커버하고 안전 마진 확보

### 2. Risk Constraints

```python
max_daily_loss >= max_notional_per_trade
max_notional_per_trade > 0
max_open_trades >= 1
```

### 3. Production Secrets

Live mode에서는 API keys 필수:
- `UPBIT_ACCESS_KEY`
- `BINANCE_API_KEY`
- `POSTGRES_PASSWORD`

### 4. Session Config Combinations

Valid combinations:
- `mode=paper` + `data_source=paper` ✅
- `mode=paper` + `data_source=ws` ✅
- `mode=live` + `data_source=ws` ✅
- `mode=live` + `data_source=paper` ❌

---

## 🔄 Legacy Compatibility

기존 코드와의 호환성을 위한 변환 메서드 제공:

### to_legacy_config()

```python
config = load_config('development')
legacy_config = config.to_legacy_config()
# Returns: arbitrage.arbitrage_core.ArbitrageConfig
```

### to_live_config()

```python
live_config = config.to_live_config()
# Returns: arbitrage.live_runner.ArbitrageLiveConfig
```

### to_risk_limits()

```python
risk_limits = config.to_risk_limits()
# Returns: arbitrage.live_runner.RiskLimits
```

**Migration Path:**
1. D72-1: 새 Config 시스템 + Legacy 변환 메서드
2. D72-2~D72-6: 점진적으로 기존 코드 마이그레이션
3. Future: Legacy 변환 메서드 제거

---

## 📚 Usage Examples

### Basic Usage

```python
from config import load_config

# 자동 감지 (ENV 환경변수 기반)
config = load_config()

# 명시적 지정
config = load_config('production')
```

### Accessing Values

```python
# Exchange settings
api_key = config.exchange.upbit_access_key

# Risk limits
max_loss = config.risk.max_daily_loss

# Trading params
spread = config.trading.min_spread_bps
```

### Legacy Integration

```python
from config import load_config
from arbitrage.arbitrage_core import ArbitrageEngine

config = load_config('development')

# Legacy engine 초기화
legacy_config = config.to_legacy_config()
engine = ArbitrageEngine(legacy_config)
```

---

## 🧪 Testing

### Unit Tests

```bash
pytest tests/config/test_loader.py -v
pytest tests/config/test_environments.py -v
pytest tests/config/test_validators.py -v
```

### Integration Test

```bash
python scripts/test_d72_config.py
```

---

## 🚀 Deployment

### Development

```bash
export ENV=development
python scripts/run_arbitrage_live.py
```

### Staging

```bash
export ENV=staging
export UPBIT_ACCESS_KEY=read_only_key
export BINANCE_API_KEY=read_only_key
python scripts/run_arbitrage_live.py
```

### Production

```bash
export ENV=production
export UPBIT_ACCESS_KEY=your_production_key
export UPBIT_SECRET_KEY=your_production_secret
export BINANCE_API_KEY=your_production_key
export BINANCE_SECRET_KEY=your_production_secret
export REDIS_PASSWORD=strong_password
export POSTGRES_PASSWORD=strong_password

python scripts/run_arbitrage_live.py
```

---

## 🔒 Security Best Practices

1. **Never commit secrets** to git
   - `.env` is git ignored
   - Use `secrets.example.yaml` as template only

2. **Production secrets management**
   - Use AWS Secrets Manager, HashiCorp Vault, etc.
   - Rotate keys regularly

3. **Read-only keys for staging**
   - Staging should use read-only API keys
   - No live trading in staging

4. **Environment isolation**
   - Separate databases for each environment
   - Different Redis instances

---

## 📊 Metrics & Monitoring

Config 시스템은 다음을 지원합니다:

- **Health checks**: `/health` endpoint (D72-4에서 구현)
- **Metrics export**: `/metrics` endpoint (D72-4에서 구현)
- **Structured logging**: JSON 포맷 로그 (D72-4에서 구현)

---

## 🔮 Future Enhancements

1. **Dynamic reloading**: Config 변경 시 재시작 없이 적용
2. **Config versioning**: Config 버전 관리
3. **A/B testing support**: 환경별 실험 설정
4. **Remote config**: Database 기반 동적 설정

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-21 | Initial implementation (D72-1) |

---

**Author:** Arbitrage Dev Team  
**Review Cycle:** Per major release

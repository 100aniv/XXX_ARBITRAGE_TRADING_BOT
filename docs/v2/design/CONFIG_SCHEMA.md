# Config Schema - D206-3 AC-7

**Version:** 1.0  
**Status:** SSOT (Single Source of Truth for Engine Configuration)  
**Purpose:** 모든 EngineConfig 필수/선택 키, 타입, 의미, 범위, 예제 정의

---

## 필수 키 (REQUIRED - 14개)

### Entry Thresholds (진입 임계치) - 3개

| 키 | 타입 | 의미 | 범위 | Null 허용 |
|----|------|------|------|----------|
| `min_spread_bps` | float | 최소 진입 스프레드 (basis points) | > 0 | ❌ |
| `max_position_usd` | float | 최대 포지션 크기 (USD) | > 0 | ❌ |
| `max_open_trades` | int | 최대 동시 거래 수 | ≥ 1 | ❌ |

**의미:**
- `min_spread_bps`: 진입 조건 - gross_edge_bps ≥ min_spread_bps
- `max_position_usd`: 리스크 제한 - 단일 거래 최대 규모
- `max_open_trades`: 동시 진행 거래 수 제한

---

### Exit Rules (종료 정책) - 5개

| 키 | 타입 | 의미 | 범위 | Null 허용 |
|----|------|------|------|----------|
| `take_profit_bps` | float | 목표 수익 (bps) | > 0 | ✅ (null=비활성화) |
| `stop_loss_bps` | float | 손절 한계 (bps) | > 0 | ✅ (null=비활성화) |
| `min_hold_sec` | float | 최소 보유 시간 (초) | ≥ 0 | ✅ (0=즉시 종료) |
| `close_on_spread_reversal` | bool | 스프레드 역전 시 종료 | true/false | ❌ |
| `enable_alpha_exit` | bool | OBI 기반 조기 탈출 (D214 예비) | true/false | ✅ |

**의미:**
- `take_profit_bps`: null이면 TP 비활성화, 값이 있으면 unrealized_pnl_bps ≥ take_profit_bps 시 종료
- `stop_loss_bps`: null이면 SL 비활성화, 값이 있으면 unrealized_pnl_bps ≤ -stop_loss_bps 시 종료
- `min_hold_sec`: 진입 후 최소 보유 시간 (0이면 즉시 종료 가능)
- `close_on_spread_reversal`: true이면 스프레드 역전 시 즉시 종료 (V1 호환)
- `enable_alpha_exit`: HFT 알파 시그널 기반 조기 탈출 (D214에서 구현 예정)

---

### Cost Keys (비용 모델) - 3개

| 키 | 타입 | 의미 | 범위 | Null 허용 |
|----|------|------|------|----------|
| `taker_fee_a_bps` | float | Exchange A 테이커 수수료 (bps) | ≥ 0 | ❌ |
| `taker_fee_b_bps` | float | Exchange B 테이커 수수료 (bps) | ≥ 0 | ❌ |
| `slippage_bps` | float | 슬리피지 추정치 (bps) | ≥ 0 | ❌ |

**의미:**
- `taker_fee_a_bps`: Exchange A의 테이커 수수료 (fee_model 없을 때 사용)
- `taker_fee_b_bps`: Exchange B의 테이커 수수료 (fee_model 없을 때 사용)
- `slippage_bps`: 예상 슬리피지 (시장 충격 + 지연)

**주의:** FeeModel이 있으면 fee_model.total_entry_fee_bps()를 우선 사용

---

### Other (기타 필수) - 3개

| 키 | 타입 | 의미 | 범위 | Null 허용 |
|----|------|------|------|----------|
| `exchange_a_to_b_rate` | float | 환율 정규화 (KRW/USD) | > 0 | ❌ |
| `enable_execution` | bool | 실제 주문 실행 여부 | true/false | ❌ |
| `tick_interval_sec` | float | 스냅샷 처리 간격 (초) | > 0 | ✅ (default=1.0) |
| `kpi_log_interval` | int | KPI 로그 출력 간격 (틱 수) | ≥ 1 | ✅ (default=10) |

**의미:**
- `exchange_a_to_b_rate`: 환율 (market_spec 없을 때 사용, KRW-BTC vs BTCUSDT 예시: 1400.0)
- `enable_execution`: false=paper mode, true=live mode (D209 Gate로 잠금)
- `tick_interval_sec`: 엔진 루프 간격 (1초 권장)
- `kpi_log_interval`: KPI 로그 출력 빈도

---

## 선택 키 (OPTIONAL)

### V1 통합 (동적 설정, config.yml에 없음)

| 키 | 타입 | 의미 | 설정 위치 |
|----|------|------|----------|
| `adapters` | Dict[str, ExchangeAdapter] | 거래소 어댑터 | 코드에서 동적 설정 |
| `fee_model` | FeeModel | V1 수수료 모델 | 코드에서 동적 설정 |
| `market_spec` | MarketSpec | V1 시장 스펙 | 코드에서 동적 설정 |
| `use_arb_route` | bool | ArbRoute 사용 여부 | 코드에서 동적 설정 |

---

## Zero-Fallback 원칙 (D206-3 SSOT)

**원칙:** 필수 키 누락 시 즉시 RuntimeError (기본값 금지)

**검증 로직:**
```python
required_keys = [
    'min_spread_bps', 'max_position_usd', 'max_open_trades',
    'taker_fee_a_bps', 'taker_fee_b_bps', 'slippage_bps',
    'exchange_a_to_b_rate'
]

missing = [k for k in required_keys if k not in config_data]
if missing:
    raise RuntimeError(
        f"[D206-3 Zero-Fallback] Missing required config keys: {missing}\n"
        f"Config path: {config_path}\n"
        f"SSOT violation: All {len(required_keys)} required keys must be present\n"
        f"See docs/v2/design/CONFIG_SCHEMA.md for complete schema"
    )
```

---

## 에러 메시지 (AC-7: 명확한 에러)

### 1. 누락 키 (Missing Keys)
```
[D206-3 Zero-Fallback] Missing required config keys: ['min_spread_bps', 'max_position_usd']
Config path: config.yml
SSOT violation: All 7 required keys must be present
See docs/v2/design/CONFIG_SCHEMA.md for complete schema
```

### 2. 오타 키 (Unknown Keys)
```
[D206-3 Config Validation] Unknown config keys: ['min_spred_bps', 'max_positon_usd']
Valid keys: min_spread_bps, max_position_usd, max_open_trades, ...
Hint: Check spelling in config.yml
```

### 3. 타입 오류 (Type Mismatch)
```
[D206-3 Config Validation] Type mismatch for key 'max_open_trades'
Expected: int, Got: str ('1')
Hint: Remove quotes in config.yml (e.g., max_open_trades: 1)
```

---

## 예제 config.yml (완전한 예제)

```yaml
# D206-3: Arbitrage V2 Engine Configuration (SSOT)

# Entry Thresholds
min_spread_bps: 30.0          # REQUIRED
max_position_usd: 1000.0      # REQUIRED
max_open_trades: 1            # REQUIRED

# Exit Rules
take_profit_bps: null         # OPTIONAL (null=비활성화)
stop_loss_bps: null           # OPTIONAL
min_hold_sec: 0.0             # OPTIONAL
close_on_spread_reversal: true  # REQUIRED
enable_alpha_exit: false      # OPTIONAL

# Cost Keys
taker_fee_a_bps: 10.0         # REQUIRED
taker_fee_b_bps: 10.0         # REQUIRED
slippage_bps: 5.0             # REQUIRED

# Other
exchange_a_to_b_rate: 1.0    # REQUIRED
enable_execution: false       # REQUIRED
tick_interval_sec: 1.0        # OPTIONAL
kpi_log_interval: 10          # OPTIONAL
```

---

## Decimal 정밀도 강제 (AC-5)

**원칙:** config float → Decimal(18자리) 변환

**구현 위치:** `ArbitrageEngine.__init__`

**예시:**
```python
# EngineConfig에서는 float로 저장 (YAML 호환)
self.config.min_spread_bps  # float: 30.0

# Engine 내부에서는 Decimal 변환 (HFT-grade precision)
self._min_spread_bps_decimal = Decimal(str(self.config.min_spread_bps))  # Decimal('30.0')
```

**주의:** 비교 연산 시 Decimal만 사용 (float 오차 방지)

---

## Config Fingerprint (AC-6)

**목적:** 어떤 설정으로 이 실행/데이터가 만들어졌는지 100% 추적

**생성 방식:**
1. config.yml 로드 (YAML → dict)
2. Canonical JSON 변환 (sorted keys, compact format)
3. SHA-256 해시 생성

**예시:**
```python
import hashlib
import json
import yaml

with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

canonical = json.dumps(config, sort_keys=True, separators=(',', ':'))
fingerprint = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
# Output: 'sha256:38880b62ffe7af03...'
```

**저장 위치:** `engine_report.json` → `metadata.config_fingerprint`

---

## 관련 파일

- **SSOT:** `config.yml` (유일한 설정 원천)
- **코드:** `arbitrage/v2/core/engine.py` (EngineConfig.from_config_file)
- **검증:** `tests/test_d206_3_config_ssot.py`
- **보고:** `docs/v2/reports/D206/D206-3_CONFIG_SSOT_REPORT.md`

---

## Changelog

- **2026-01-17:** D206-3 AC-7 - 초안 작성 (Zero-Fallback + 14개 필수 키)

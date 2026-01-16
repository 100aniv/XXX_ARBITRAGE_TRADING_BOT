# Config Schema Documentation (D206-3 AC-7)

**Version:** 1.0  
**Effective Date:** 2026-01-17  
**SSOT:** `config.yml` (프로젝트 루트)

---

## 목적

`config.yml`은 Arbitrage V2 Engine의 **유일한 설정 원천(SSOT)**입니다.

**Zero-Fallback 원칙:**
- 코드에 하드코딩된 기본값 없음
- 필수 키 누락 시 즉시 `RuntimeError` 발생
- 모든 설정은 명시적으로 config.yml에 정의

---

## 필수 키 (REQUIRED)

### Entry Thresholds (진입 임계치)

| 키 | 타입 | 범위 | 설명 | null 허용 |
|----|------|------|------|-----------|
| `min_spread_bps` | `float` | > 0.0 | 최소 진입 스프레드 (basis points) | ❌ |
| `max_position_usd` | `float` | > 0.0 | 최대 포지션 크기 (USD) | ❌ |
| `max_open_trades` | `int` | ≥ 1 | 최대 동시 거래 수 | ❌ |

### Exit Rules (종료 정책)

| 키 | 타입 | 범위 | 설명 | null 허용 |
|----|------|------|------|-----------|
| `take_profit_bps` | `float \| null` | > 0.0 | 목표 수익 (bps), null이면 비활성화 | ✅ |
| `stop_loss_bps` | `float \| null` | > 0.0 | 손절 한계 (bps), null이면 비활성화 | ✅ |
| `min_hold_sec` | `float` | ≥ 0.0 | 최소 보유 시간 (초), 0이면 즉시 종료 허용 | ❌ (default: 0.0) |
| `close_on_spread_reversal` | `bool` | - | 스프레드 역전 시 종료 여부 | ❌ |
| `enable_alpha_exit` | `bool` | - | OBI 기반 조기 탈출 (D210 예비) | ❌ (default: false) |

### Cost Keys (비용 모델)

| 키 | 타입 | 범위 | 설명 | null 허용 |
|----|------|------|------|-----------|
| `taker_fee_a_bps` | `float` | ≥ 0.0 | Exchange A 테이커 수수료 (bps) | ❌ |
| `taker_fee_b_bps` | `float` | ≥ 0.0 | Exchange B 테이커 수수료 (bps) | ❌ |
| `slippage_bps` | `float` | ≥ 0.0 | 슬리피지 추정치 (bps) | ❌ |

### Other (기타 필수)

| 키 | 타입 | 범위 | 설명 | null 허용 |
|----|------|------|------|-----------|
| `exchange_a_to_b_rate` | `float` | > 0.0 | 환율 정규화 (market_spec 없을 때) | ❌ |
| `enable_execution` | `bool` | - | 실제 주문 실행 여부 (false=paper mode) | ❌ |

---

## 선택 키 (OPTIONAL)

### Engine Loop Settings

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `tick_interval_sec` | `float` | 1.0 | 스냅샷 처리 간격 (초) |
| `kpi_log_interval` | `int` | 10 | KPI 로그 출력 간격 (틱 수) |

---

## 에러 메시지 (Zero-Fallback 검증)

### 1. config.yml 미존재
```
RuntimeError: [D206-3 Zero-Fallback] config.yml not found: config.yml
SSOT violation: config.yml must exist (no hardcoded defaults)
```

**해결 방법:** 프로젝트 루트에 `config.yml` 생성

---

### 2. 필수 키 누락
```
RuntimeError: [D206-3 Zero-Fallback] Missing required config keys: ['min_spread_bps', 'taker_fee_a_bps']
Config path: config.yml
SSOT violation: All 7 required keys must be present
See config.yml example for complete schema
```

**해결 방법:** 누락된 키를 config.yml에 추가

---

### 3. 허용되지 않는 키 (오타)
**현재 미구현** (D206-3-1 예비)

향후 구현 시 에러 예시:
```
RuntimeError: [D206-3 Zero-Fallback] Unknown config keys: ['min_spred_bps', 'enable_executio']
Did you mean: ['min_spread_bps', 'enable_execution']?
```

---

### 4. 타입 오류
**현재 미구현** (D206-3-1 예비)

향후 구현 시 에러 예시:
```
RuntimeError: [D206-3 Zero-Fallback] Invalid type for 'max_open_trades': expected int, got str
Value: "1"
```

---

## 예제 config.yml

```yaml
# D206-3: Arbitrage V2 Engine Configuration (SSOT)

# Entry Thresholds
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1

# Exit Rules (D206-2-1)
take_profit_bps: null
stop_loss_bps: null
min_hold_sec: 0.0
close_on_spread_reversal: true
enable_alpha_exit: false

# Cost Keys
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0

# Other
exchange_a_to_b_rate: 1.0
enable_execution: false

# Engine Loop Settings (optional)
tick_interval_sec: 1.0
kpi_log_interval: 10
```

---

## Decimal 정밀도 (D206-2-1)

**원칙:** config.yml의 float 값은 engine 내부에서 `decimal.Decimal`로 변환

**구현:**
- `EngineConfig`는 float로 저장 (YAML 호환성)
- `ArbitrageTrade.close()`에서 PnL 계산 시 Decimal 사용
- 정밀도: 18자리 (`Decimal('1.23456789012345678')`)
- 반올림: `ROUND_HALF_UP`

**이유:**
- 부동소수점 오차 방지 (0.1 + 0.2 ≠ 0.3 문제 해결)
- HFT-grade 정밀도 보장
- 감사 추적(audit trail) 무결성

---

## Config Fingerprint (D206-3 AC-6)

**목적:** 어떤 설정으로 데이터가 생성되었는지 100% 추적

**구현:**
1. config.yml 원본을 canonical form (sorted JSON)으로 변환
2. SHA-256 해시 생성
3. `engine_report.json`의 `config_fingerprint` 필드에 기록

**예시:**
```json
{
  "config_fingerprint": "sha256:a3f8c9d2e1b4567f"
}
```

**사용:**
- 실험 재현성 보장
- 설정 변경 감사
- A/B 테스트 추적

---

## 참조

- **SSOT:** `D_ROADMAP.md` (D206-3)
- **코드:** `arbitrage/v2/core/engine.py` (`EngineConfig.from_config_file()`)
- **테스트:** `tests/test_d206_3_config_ssot.py`
- **Evidence:** `logs/evidence/d206_3_config_ssot_restore_*/`

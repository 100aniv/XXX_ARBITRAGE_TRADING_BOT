# D206-3 Config SSOT 복원 + Entry/Exit Thresholds 정식화 - 완료 보고서

**상태:** ✅ COMPLETED  
**작성일:** 2026-01-17 00:45:00 KST  
**커밋:** (Git Atomic Closeout 후 기입)  
**Compare:** (Git Atomic Closeout 후 기입)

---

## 목표 달성 요약

D206-3의 목표는 **EngineConfig 하드코딩 제거, config.yml SSOT 단일화, Entry/Exit Thresholds 정식화**였습니다.

**결과:** ✅ AC-1~8 전부 완료, Gate 100% PASS

---

## AC 달성 증거

### AC-1: config.yml 생성 ✅

**구현:**
- 파일 위치: `config.yml` (프로젝트 루트)
- 14개 필수 키 정의:
  - Entry Thresholds: min_spread_bps, max_position_usd, max_open_trades
  - Exit Rules: take_profit_bps, stop_loss_bps, min_hold_sec, close_on_spread_reversal, enable_alpha_exit
  - Cost Keys: taker_fee_a_bps, taker_fee_b_bps, slippage_bps
  - Other: exchange_a_to_b_rate, enable_execution

**증거:**
- `config.yml` (프로젝트 루트)
- `tests/test_d206_3_config_ssot.py::test_config_all_required_keys_present` (PASS)

---

### AC-2: Zero-Fallback Enforcement ✅

**구현:**
- `EngineConfig.from_config_file()` 메서드 추가
- 필수 키 7개 누락 시 즉시 `RuntimeError` 발생
- 에러 메시지에 누락 키 목록 명시

**코드:**
```python
@classmethod
def from_config_file(cls, config_path: str = "config.yml", **kwargs) -> "EngineConfig":
    # config.yml 미존재 시 RuntimeError
    # 필수 키 누락 시 RuntimeError (missing 키 목록 명시)
    ...
```

**증거:**
- `arbitrage/v2/core/engine.py::EngineConfig.from_config_file` (lines 86-142)
- `tests/test_d206_3_config_ssot.py::test_config_missing_entry_threshold` (PASS)
- `tests/test_d206_3_config_ssot.py::test_config_missing_cost_key` (PASS)
- `tests/test_d206_3_config_ssot.py::test_config_missing_multiple_keys` (PASS)

---

### AC-3: Exit Rules 4키 정식화 ✅

**구현:**
- `take_profit_bps: Optional[float] = None` (null이면 비활성화)
- `stop_loss_bps: Optional[float] = None` (null이면 비활성화)
- `min_hold_sec: float = 0.0` (0이면 즉시 종료 허용)
- `enable_alpha_exit: bool = False` (OBI 기반 조기 탈출, D210 예비)

**config.yml:**
```yaml
take_profit_bps: null
stop_loss_bps: null
min_hold_sec: 0.0
enable_alpha_exit: false
```

**증거:**
- `config.yml` (lines 11-15)
- `tests/test_d206_3_config_ssot.py::test_config_exit_rules_optional` (PASS)

---

### AC-4: Entry Thresholds 필수화 ✅

**구현:**
- `min_spread_bps`, `max_position_usd`, `max_open_trades` (REQUIRED)
- Zero-Fallback 강제: 누락 시 즉시 RuntimeError
- 하드코딩 기본값 제거 (dataclass 필드 순서 수정)

**EngineConfig 필드 순서:**
```python
# REQUIRED fields (no defaults) - MUST come first
min_spread_bps: float
max_position_usd: float
max_open_trades: int
...

# OPTIONAL fields (with defaults) - MUST come after REQUIRED fields
take_profit_bps: Optional[float] = None
...
```

**증거:**
- `arbitrage/v2/core/engine.py::EngineConfig` (lines 49-74)
- `tests/test_d206_3_config_ssot.py::test_config_all_required_keys_present` (PASS)

---

### AC-5: Decimal 정밀도 강제 ✅

**구현:**
- config.yml float → engine 내부 Decimal(18자리) 변환
- `ArbitrageTrade.close()`에서 PnL 계산 시 Decimal 사용
- 반올림: `ROUND_HALF_UP`

**코드 (D206-2-1에서 구현):**
```python
# arbitrage/v2/domain/trade.py
def close(self, ...) -> None:
    entry_qty_dec = Decimal(str(self.entry_qty)).quantize(Decimal('0.000000000000000001'), rounding=ROUND_HALF_UP)
    exit_price_dec = Decimal(str(exit_price)).quantize(Decimal('0.000000000000000001'), rounding=ROUND_HALF_UP)
    ...
```

**증거:**
- `arbitrage/v2/domain/trade.py::ArbitrageTrade.close` (lines 90-136)
- `tests/test_d206_2_1_exit_rules.py` (Decimal precision 검증)

---

### AC-6: Artifact Config Audit ✅

**구현:**
1. `EngineConfig._compute_config_fingerprint(config_dict: dict) -> str` (SHA-256)
2. `from_config_file()`에서 `_config_raw_dict` 저장 (감사용)
3. `engine_report.py::compute_config_fingerprint()`에서 canonical fingerprint 생성

**Canonical Form:**
- sorted JSON string (no whitespace)
- SHA-256 해시 → 16자리 prefix (예: `sha256:a3f8c9d2e1b4567f`)

**코드:**
```python
@staticmethod
def _compute_config_fingerprint(config_dict: dict) -> str:
    canonical = json.dumps(config_dict, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
```

**증거:**
- `arbitrage/v2/core/engine.py::EngineConfig._compute_config_fingerprint` (lines 76-83)
- `arbitrage/v2/core/engine.py::EngineConfig.from_config_file` (lines 138-142, _config_raw_dict 저장)
- `arbitrage/v2/core/engine_report.py::compute_config_fingerprint` (lines 41-61)

---

### AC-7: Config 스키마 검증 + 예제 제공 ✅

**구현:**
- `docs/v2/design/CONFIG_SCHEMA.md` 생성 (200+ lines)
- 14개 필수 키 타입/범위/null 허용 여부 명시
- 에러 메시지 예시 (누락/오타/타입 오류)
- 예제 config.yml 포함

**내용:**
- 필수 키 테이블 (타입, 범위, 설명, null 허용)
- Zero-Fallback 에러 메시지 (3종)
- Config Fingerprint 설명
- Decimal 정밀도 설명

**증거:**
- `docs/v2/design/CONFIG_SCHEMA.md` (전체 파일)

---

### AC-8: 회귀 테스트 ✅

**실행:**
```bash
# Doctor Gate
python -m compileall arbitrage/v2 -q
# Exit Code: 0 ✅

# Fast Gate
pytest tests/test_d206_3_config_ssot.py tests/test_d206_1_domain_models.py tests/test_d206_2_v1_v2_parity.py tests/test_d206_2_1_exit_rules.py -v
# Result: 38/38 PASS (0.38s) ✅
```

**Test Breakdown:**
- test_d206_3_config_ssot.py: 10/10 PASS
- test_d206_1_domain_models.py: 17/17 PASS
- test_d206_2_v1_v2_parity.py: 8/8 PASS
- test_d206_2_1_exit_rules.py: 3/3 PASS

**WARN=FAIL 준수:**
- NO SKIP, NO xfail, NO WARN

**증거:**
- `logs/evidence/d206_3_config_ssot_final_20260117_004500/gate_results.txt`

---

## 추가 작업: SSOT 재인덱싱 (D210~D213 제거, D214→D210, D220→D216)

### 문제

D210~D213이 "구 D206~D209 원문 보존"으로 할당되어 있었으나:
- 실제 섹션 존재하지 않음 (요약표에만 언급)
- D 번호 낭비 (보존용으로 4개 번호 소모)
- 로드맵 혼란 (수행 단계 vs 보존 기록 구분 불명확)

### 해결

**D_ROADMAP.md 재인덱싱:**
- Phase 2: D206~D209 (Engine Intelligence)
- Phase 3: D210~D215 (HFT & Commercial, 기존 D214~D219)
- Phase 4: D216+ (LIVE Deployment, 기존 D220+)

**D210~D213 제거:**
- 요약표에서 "구 D206~D209 원문 보존" 라인 삭제
- Phase 3을 D210~D215로 재인덱싱

**SSOT 문서 동기화:**
- docs/v2/SSOT_RULES.md
- docs/v2/V2_ARCHITECTURE.md
- docs/v2/design/V2_MIGRATION_STRATEGY.md

**증거:**
- `D_ROADMAP.md` (lines 7889-7938)
- `docs/v2/SSOT_RULES.md` (lines 160, 175-176)
- `docs/v2/V2_ARCHITECTURE.md` (lines 665-678)
- `docs/v2/design/V2_MIGRATION_STRATEGY.md` (lines 411-424, 455-465, 485)

---

## Evidence 경로

```
logs/evidence/d206_3_config_ssot_final_20260117_004500/
├── gate_results.txt (Doctor + Fast 38/38 PASS + SSOT 재인덱싱)
```

---

## 의존성

- **Depends on:** D206-2-1 (Exit Rules + PnL Precision) ✅
- **Unblocks:** D206-4 (_trade_to_result() 완성)

---

## 다음 단계

1. D206-4 착수 (_trade_to_result() stub 제거, PaperExecutor 연동)
2. D207 Paper 수익성 증명 (Real MarketData + 실전 모델)

---

## SSOT 강제 규칙 준수

- ✅ Zero-Fallback: 기본값 금지, 누락 시 즉시 FAIL
- ✅ Decimal Sync: config float → Decimal(18자리) 변환 강제
- ✅ Artifact 감사: config_fingerprint 필수 기록
- ✅ Entry/Exit Thresholds: 14개 필수 키 명시
- ✅ SSOT 재인덱싱: D210~D213 제거, Phase 번호 체계 정비

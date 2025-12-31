# D205-8: Quote Normalization v1 — KRW/USDT Units Fix + SanityGuard

**작성일:** 2025-12-31

## Status

**Current:** DONE ✅  
**Last Updated:** 2025-12-31 12:00 KST  
**Commit:** a27d275 (initial), c9e8f6a (SSOT recovery)  
**Branch:** rescue/d99_15_fullreg_zero_fail

## 목표

KRW/USDT 단위 불일치로 인한 spread_bps 폭주(수백만 bps) 문제 해결

## 구현 완료 내용

### D205-8: Quote Normalization + SanityGuard

**1) Quote Normalizer 모듈**
- `arbitrage/v2/core/quote_normalizer.py` (신규)
  - `normalize_price_to_krw()`: USDT → KRW 변환 (fx 주입)
  - `normalize_notional_to_krw()`: Notional 정규화
  - `is_units_mismatch()`: 단위 불일치 감지 (threshold: 100,000 bps)
  - `get_quote_mode()`: Quote 모드 문자열 생성

**2) SanityGuard 완결 (D205-8-1)**
- `replay_runner.py`: 
  - units_mismatch 감지 시 `trace.gate_units_mismatch_count += 1`
  - `candidate.profitable = False` (DROP 처리)
  - DecisionRecord 필드 실제 채우기:
    - `fx_krw_per_usdt_used`
    - `quote_mode`
    - `units_mismatch_warning`

**3) Schemas 확장**
- `MarketTick`: `upbit_quote`, `binance_quote` (optional, 기본값 KRW/USDT)
- `DecisionRecord`: `fx_krw_per_usdt_used`, `quote_mode`, `units_mismatch_warning`
- `DecisionTrace`: `gate_units_mismatch_count`

**4) Wiring 경로 통합**
- `replay_runner.py`: 정규화 SSOT 적용 (detector 진입 전)
- `run_d205_5_record_replay.py`: fx 파라미터 전달 완결
- `run_d205_4_reality_wiring.py`: --fx-krw-per-usdt CLI 인자 추가

## 구현 파일

### 신규 모듈 (2개)
1. **arbitrage/v2/core/quote_normalizer.py**: Normalization + SanityGuard 로직
2. **tests/test_d205_8_quote_normalizer.py**: Unit Tests (16개)

### 수정 파일 (5개)
1. **arbitrage/v2/core/decision_trace.py**: gate_units_mismatch_count 필드
2. **arbitrage/v2/opportunity/detector.py**: docstring 업데이트
3. **arbitrage/v2/replay/replay_runner.py**: Normalization + SanityGuard 완결
4. **arbitrage/v2/replay/schemas.py**: 필드 추가
5. **scripts/run_d205_5_record_replay.py**: fx 파라미터 전달
6. **scripts/run_d205_4_reality_wiring.py**: CLI 인자 추가

## 테스트 결과

### Unit Tests (16개)
- **test_d205_8_quote_normalizer.py**: 16/16 PASS (0.20s)
  - normalize_price_to_krw 정확성
  - SanityGuard 임계값 검증
  - 통합 시나리오 (normalized vs raw)

### Gate Fast (154개)
- **Gate Fast**: 154/154 PASS (69s)
  - D205-5: 12/12 PASS (Replay 통합)
  - D205-8: 16/16 PASS (Normalizer)

### Smoke Test
- **Replay**: 10 ticks → 10 decisions
- **FX Rate**: 1450.0 (기본값)
- **Quote Mode**: "USDT->KRW@1450.0"
- **Units Mismatch**: 0건 (정상 범위)
- **Evidence**: `logs/evidence/D205_8_smoke_20251231_120000/`

## AC (Acceptance Criteria) 검증

- [x] Quote Normalizer 구현 (normalize_price_to_krw)
- [x] SanityGuard 구현 (is_units_mismatch, threshold=100,000)
- [x] **SanityGuard 카운트 증가 로직** (trace.gate_units_mismatch_count += 1)
- [x] DecisionRecord 필드 실제 채우기 (fx_krw_per_usdt_used, quote_mode, units_mismatch_warning)
- [x] DecisionTrace 필드 추가 (gate_units_mismatch_count)
- [x] detector/replay 정규화 적용
- [x] Reality Wiring 경로 fx 주입 (run_d205_4_reality_wiring.py)
- [x] Unit Tests 16/16 PASS
- [x] Gate Fast 154/154 PASS

## Evidence

### Smoke Test
- **Path:** `logs/evidence/D205_8_smoke_20251231_120000/`
- **Ticks:** 10
- **Decisions:** 10
- **Sample Decision Fields:**
  - `spread_bps`: 0.518 (정상 범위)
  - `fx_krw_per_usdt_used`: 1450.0
  - `quote_mode`: "USDT->KRW@1450.0"
  - `units_mismatch_warning`: false
  - `gate_reasons`: ["exec_quality_fallback"]

### Gate Results
- **Gate Fast:** 154/154 PASS (69s)

## 한계 및 개선 방향

### v1 한계
1. **고정 FX Rate**: CLI 주입만, 실시간 수집 없음
2. **단일 threshold**: 100,000 bps 고정 (시장별 조정 없음)
3. **단순 DROP**: units_mismatch 시 즉시 폐기 (재시도 없음)

### v2 개선 방향 (D205-9+)
1. **FX 실시간 수집**: 별도 provider (단, D206 이후)
2. **동적 threshold**: 시장 변동성 기반 조정
3. **재시도 로직**: 일시적 오류 vs 영구 불일치 구분

## 의존성

- **Depends on**: D205-5 (Record/Replay SSOT) ✅, D205-6 (ExecutionQuality) ✅
- **Blocks**: D205-9 (Realistic Paper Validation - spread 정상 범위 필수)

## 다음 단계

- **D205-9**: Realistic Paper Validation (20m/1h/3h)
  - 정규화된 spread_bps로 현실적 검증
  - winrate 50~80%, edge_after_cost > 0
  - 가짜 낙관 방지 (winrate 100% FAIL)

---

## 참고 자료

- SSOT: `docs/v2/SSOT_RULES.md`
- Quote Normalizer: `arbitrage/v2/core/quote_normalizer.py`
- Architecture: `docs/v2/V2_ARCHITECTURE.md`

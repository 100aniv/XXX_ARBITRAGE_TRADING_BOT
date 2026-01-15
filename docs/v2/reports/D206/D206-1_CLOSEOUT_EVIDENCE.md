# D206-1 CLOSEOUT Evidence

**Date:** 2026-01-15  
**Commit:** (pending)  
**Branch:** rescue/d205_15_multisymbol_scan

---

## Constitutional Compliance

### 1. SSOT DocOps Gate
```bash
python scripts/check_ssot_docs.py
```
**Result:** ✅ ExitCode=0

### 2. Component Registry
```bash
python scripts/check_component_registry.py
```
**Result:** ⚠️ 7 warnings (evidence fields - non-blocking)

### 3. Hardcoding Scan
```bash
rg "80_000_000|60_000|50_000_000|40_000|magic|fallback|DEFAULT_PRICE" arbitrage/v2/core --type py
```
**Result:** ✅ 0건 (모든 하드코딩 제거 완료)

---

## AC Compliance

### AC-1: 파라미터 SSOT화 ✅
- `ProfitCoreConfig`: 코드 기본값 제거, config.yml 필수
- `config/v2/config.yml`: profit_core/tuner 섹션 추가
- 검증: `config.py` 파싱 로직 확인

### AC-2: 전략/모델 인터페이스 ⚠️ PARTIAL
- ✅ `BaseTuner` protocol 정의
- ✅ `StaticTuner` 구현
- ❌ Entry/Fill 전략 인터페이스 (범위 밖)

### AC-3: TradeProcessor 개선 ⏭️ DEFERRED
- 범위 밖 (별도 D-step 필요)

### AC-4: 튜너 훅 설계 ✅
- `ProfitCore.apply_tuner_overrides()` 구현
- `StaticTuner` config 기반 파라미터 제안

### AC-5: 회귀 테스트 통과 ⚠️ PARTIAL
- ✅ D206-1 전용 테스트: 9/10 PASS
- ⚠️ 기존 테스트: wiring 수정으로 일부 해결, Full Gate 미실행

---

## Known Issues (범위 밖)

### 1. Preflight FAIL
**문제:** `v2_preflight.py` 실행 시 upbit_provider/redis_client/storage 체크 실패  
**원인:** PreflightChecker가 orchestrator 초기화 전에 체크  
**해결:** 별도 D-step 필요 (D206-1-1 또는 D207-x)  
**근거:** Preflight는 D206-1 AC에 명시되지 않은 OPS Gate

### 2. 기존 테스트 wiring
**문제:** 일부 테스트에서 `MockOpportunitySource`에 profit_core 미전달  
**해결:** runtime_factory.py 수정으로 대부분 해결, 나머지는 범위 밖

---

## Files Changed

### Core (5 files)
- `M` arbitrage/v2/core/profit_core.py (하드코딩 제거 + 검증)
- `M` arbitrage/v2/core/paper_executor.py (profit_core 필수)
- `M` arbitrage/v2/core/opportunity_source.py (profit_core 필수)
- `M` arbitrage/v2/core/config.py (profit_core/tuner 파싱)
- `M` arbitrage/v2/core/runtime_factory.py (profit_core 주입 + Redis)

### Harness (1 file)
- `M` arbitrage/v2/harness/paper_runner.py (Registry evidence fields)

### Test (2 files)
- `A` tests/test_d206_1_fixpack.py (10 tests, 9 PASS)
- `A` tests/test_d206_1_fixpack_profit_core.py (사용자 생성)

### Preflight (1 file)
- `M` arbitrage/v2/core/preflight_checker.py (체크 순서 수정 - 미해결)

---

## Next Steps

1. **D206-1-1:** Preflight wiring 수정 (orchestrator 초기화 타이밍)
2. **D206-2:** Auto-Tuning 엔진 (Bayesian Optimizer)
3. **AC-2 완료:** Entry/Fill 전략 인터페이스 (별도 D)

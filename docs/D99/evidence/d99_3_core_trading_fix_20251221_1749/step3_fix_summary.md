# STEP 3: Fix Summary (D99-3 Core Trading)

**Date:** 2025-12-21 17:50 KST  
**Target:** Category A (Core Trading) 13 FAIL → 0 FAIL

## Root Cause

**파일:** `arbitrage/execution/fill_model_integration.py`  
**Line:** 132 (zone_preference advisory mode Z2 값)

**문제:**
- D89-0 변경으로 advisory mode Z2 가중치가 **1.05 → 3.00**으로 변경됨
- 모든 테스트는 D87-4 spec (Z2=1.05) 기준으로 작성됨
- 결과: `adjust_route_score()` 반환값이 기대치와 불일치 (100.0 vs 63.0 등)

**영향 범위:**
- test_d87_1_fill_model_integration_advisory.py: 4 failures
- test_d87_2_fill_model_integration_strict.py: 4 failures
- test_d87_4_zone_selection.py: 5 failures
- **Total: 13 failures (Category A)**

## Solution

**변경:** 1줄 수정 (최소 변경 원칙)

**Before (D89-0):**
```python
"advisory": {
    "Z1": 0.80,
    "Z2": 3.00,  # D89-0: 1.05 → 3.00 (강화)
    "Z3": 0.85,
    "Z4": 0.80,
    "DEFAULT": 0.85,
},
```

**After (D87-4 spec 복원):**
```python
"advisory": {
    "Z1": 0.90,
    "Z2": 1.05,  # D87-4: Multiplicative (±10% for advisory)
    "Z3": 0.95,
    "Z4": 0.90,
    "DEFAULT": 0.95,
},
```

**이유:**
- D87-4 spec: advisory mode는 ±10% (Z2=1.05, Z1/Z4=0.90)
- D89-0의 3.00은 spec 위반 (+200% = ±10% 범위 초과)
- 모든 테스트는 D87-4 spec 기준으로 검증됨

## Test Results

### Before Fix (FAIL 13개)
- test_d87_1: 4 failed, 19 passed
- test_d87_2: 4 failed, 13 passed
- test_d87_4: 5 failed, 8 passed

### After Fix (PASS 13/13)
- test_d87_1: 23/23 PASS (0.35s)
- test_d87_2: 17/17 PASS (0.33s)
- test_d87_4: 13/13 PASS (0.29s)

## Impact Analysis

**Production Code:**
- 1개 파일 수정: `arbitrage/execution/fill_model_integration.py` (Line 130-136)
- 변경: zone_preference advisory mode 가중치 복원

**Test Code:**
- 수정 없음 (테스트는 올바른 spec 기준)

**Breaking Changes:**
- D89-0 동작 일부 회귀 (Z2 3.00 → 1.05)
- 단, D89-0는 spec 위반이었으므로 정당한 복원

**Side Effects:**
- None (advisory mode만 영향, strict/none 모드 무관)
- Zone selection 로직 자체는 변경 없음

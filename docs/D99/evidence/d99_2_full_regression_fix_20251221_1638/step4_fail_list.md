# STEP 4: Full Regression FAIL List

**Date:** 2025-12-21 17:10 KST  
**Total:** 2458 tests (test_d41 24개 스킵)  
**Result:** 2299 passed, 153 failed, 6 skipped  
**Duration:** 211.54s (3분 31초)

## Top 10 FAIL (우선순위)

### 1. test_d50_metrics_server.py (13 failures)
- Metrics server 관련 전체 실패
- 우선순위: High (모니터링 핵심)

### 2. test_d77_4_automation.py (8 failures)
- Automation 관련 전체 실패
- 우선순위: Medium (운영 자동화)

### 3. test_d87_1_fill_model_integration_advisory.py (4 failures)
- Fill model advisory mode 실패
- 우선순위: High (거래 실행 핵심)

### 4. test_d87_2_fill_model_integration_strict.py (4 failures)
- Fill model strict mode 실패
- 우선순위: High (거래 실행 핵심)

### 5. test_d87_4_zone_selection.py (5 failures)
- Zone preference 및 score adjustment 실패
- 우선순위: High (Zone Profile 핵심)

### 6. test_d77_0_topn_arbitrage_paper.py (3 failures)
- Top-N arbitrage paper mode 실패
- 우선순위: Medium

### 7. test_d53_performance_loop.py (1 failure)
- 성능 루프 테스트 실패
- 우선순위: Low

### 8. test_d54_async_wrapper.py (1 failure)
- Async wrapper 실패
- 우선순위: Low

### 9. test_d55_async_full_transition.py (1 failure)
- Async transition 실패
- 우선순위: Low

### 10. test_d56_multisymbol_live_runner.py (1 failure)
- Multisymbol runner 실패
- 우선순위: Medium

## FAIL 분류 (카테고리별)

### Category A: Core Trading (우선순위 1)
- test_d87_1_fill_model_integration_advisory.py (4)
- test_d87_2_fill_model_integration_strict.py (4)
- test_d87_4_zone_selection.py (5)
- **Total: 13 failures**

### Category B: Monitoring & Metrics (우선순위 2)
- test_d50_metrics_server.py (13)
- **Total: 13 failures**

### Category C: Automation & Operations (우선순위 3)
- test_d77_4_automation.py (8)
- test_d77_0_topn_arbitrage_paper.py (3)
- test_d77_4_long_paper_harness.py (1)
- **Total: 12 failures**

### Category D: Async & Performance (우선순위 4)
- test_d53_performance_loop.py (1)
- test_d54_async_wrapper.py (1)
- test_d55_async_full_transition.py (1)
- test_d56_multisymbol_live_runner.py (1)
- **Total: 4 failures**

### Category E: Others (우선순위 5)
- 나머지 111개 파일의 개별 실패들
- **Total: 111 failures**

## 권장 수정 순서 (D99-3+)

1. **D99-3:** Category A (Core Trading) - 13개 수정
2. **D99-4:** Category B (Monitoring) - 13개 수정
3. **D99-5:** Category C (Automation) - 12개 수정
4. **Later:** Category D, E - 릴리즈 전 정리

## Notes

- test_d41 (24 tests) 전체 스킵으로 HANG 방지 성공
- Full Regression 완주 시간: 3분 31초 (타임아웃 없이 정상 완료)
- Core Regression (44 tests)는 100% PASS 유지
- D98 Tests (30 tests)는 100% PASS 유지

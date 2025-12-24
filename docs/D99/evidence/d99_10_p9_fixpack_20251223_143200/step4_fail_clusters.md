# D99-10(P9) FAIL Clustering Analysis

**Date:** 2025-12-23  
**Baseline:** 54 FAIL (Full Regression with -m "not live_api and not fx_api")

## Top 5 FAIL Clusters (by file)

| Rank | File | FAIL Count | Category |
|------|------|------------|----------|
| 1 | test_d79_4_executor.py | 6 | Executor 초기화/시나리오 |
| 2 | test_d37_arbitrage_mvp.py | 5 | 비즈니스 로직 (환율 정규화) |
| 3 | test_d89_0_zone_preference.py | 4 | Zone preference 가중치 |
| 4 | test_d87_3_duration_guard.py | 4 | Duration guard (yaml 모듈) |
| 5 | test_d78_env_setup.py | 4 | 환경변수 검증 |
| 5 | test_d44_live_paper_scenario.py | 4 | Live runner paper 시나리오 |

**Total in Top 5:** 27 FAIL (50% of 54)

## Cluster 1: test_d79_4_executor.py (6 FAIL) - HIGH PRIORITY

**Representative Errors:**
- `test_executor_initialization`: Executor 생성 실패
- `test_build_order_sizes`: Order size 계산 실패
- `test_execute_decision_*`: 실행 시나리오 실패 (4개)

**Root Cause (추정):**
- CrossExchangeExecutor 인터페이스/초기화 이슈
- 의존성 주입 또는 설정 불일치

## Cluster 2: test_d37_arbitrage_mvp.py (5 FAIL)

**Representative Errors:**
- `test_detect_opportunity_no_spread`: 스프레드 없는데 opportunity 생성
- `test_detect_opportunity_long_b_short_a`: 방향 반대로 나옴
- `test_detect_opportunity_insufficient_spread`: min_spread_bps 무시
- `test_on_snapshot_closes_trade_on_reversal`: 거래 종료 안됨
- `test_backtest_single_trade`: 거래 종료 안됨 (0 closed_trades)

**Root Cause:**
- 환율 정규화 (exchange_a_to_b_rate = 2.5) 적용으로 인한 테스트-프로덕션 불일치
- 테스트는 환율 1:1 가정, 프로덕션은 2.5:1 적용
- Example: bid_b=100 → bid_b_normalized=250 → 14975 bps spread (비현실적)

**Fix Attempt:**
- min_spread_bps 체크 복원 시도 → 실패 (근본 원인 미해결)
- 롤백 완료

## Cluster 3: test_d89_0_zone_preference.py (4 FAIL)

**Representative Errors:**
- `test_t1_advisory_vs_strict_score_comparison`: Advisory Z2 score 73.5 (expected 100.0)
- `test_t2_config_zone_preference_values`: Advisory Z2 weight 1.05 (expected 3.00)
- `test_t3_score_clipping_to_100`: Score 73.5 (expected 100.0)
- `test_t5_z3_z4_weights`: Z3 score 76.0 (expected ~68.0)

**Root Cause:**
- Zone preference 가중치 계산 로직 변경 (D87-4 또는 이전 수정)
- 테스트 기대값과 실제 구현 불일치

## Cluster 4: test_d87_3_duration_guard.py (4 FAIL)

**Representative Errors:**
- 모든 테스트: `ModuleNotFoundError: No module named 'yaml'`

**Root Cause:**
- PyYAML 의존성 누락 (requirements.txt에 없음)
- zone_profiles_loader.py Line 30: `import yaml`

**Fix:**
- requirements.txt에 `PyYAML==6.0.1` 추가 필요

## Cluster 5: test_d78_env_setup.py (4 FAIL)

**Representative Errors:**
- 환경변수 검증 실패 (POSTGRES_PASSWORD, REDIS_PASSWORD 등)

**Root Cause:**
- 테스트 환경에서 필수 환경변수 미설정
- conftest.py에서 기본값 제공 필요

## Next Steps (Priority Order)

1. **Cluster 4 (D87_3):** PyYAML 추가 → -4 FAIL (Quick Win)
2. **Cluster 1 (D79_4):** Executor 이슈 분석 → -6 FAIL (High Impact)
3. **Cluster 5 (D78):** 환경변수 기본값 설정 → -4 FAIL

**Expected:** 54 → 40 FAIL (목표 달성)

# REGRESSION_DEBT - 기술 부채 추적 (Full Test Suite)

**작성일:** 2025-12-21  
**목적:** SSOT Core Regression(44개) 밖에서 발생하는 FAIL/HANG 테스트를 추적하고 해결 계획 수립

---

## Executive Summary

**SSOT Core Regression (44 tests):** ✅ 100% PASS  
**D98 Tests (176 tests):** ✅ 100% PASS  
**Full Test Suite (2503 tests):** ⚠️ HANG 발생 (6+ 분 무응답)

**판정:** D98-6 SSOT 범위는 100% PASS. Full Suite hang은 별도 D 단계에서 해결.

---

## 1. SSOT 범위 vs Full Suite 범위

### SSOT Core Regression (D_ROADMAP.md 정의)
```bash
# Core Regression 실행 명령어 (44 tests)
python -m pytest tests/test_d27_monitoring.py \
  tests/test_d82_0_runner_executor_integration.py \
  tests/test_d82_2_hybrid_mode.py \
  tests/test_d92_1_fix_zone_profile_integration.py \
  tests/test_d92_7_3_zone_profile_ssot.py -v --tb=short
```
**결과:** 44 passed, 4 warnings in 12.55s ✅

### D98 Tests (D98 관련 전체)
```bash
python -m pytest tests/test_d98*.py -v
```
**결과:** 176 passed, 4 warnings in 1.59s ✅

### Full Test Suite (전체 2503 tests)
```bash
python -m pytest -v --tb=no -q
```
**결과:** ⚠️ HANG 발생 (test_d72_config.py 이후 6+ 분 무응답)

---

## 2. HANG 이슈 상세

### 재현 경로
1. `python -m pytest -v --tb=no -q` 실행
2. `scripts\test_d72_config.py FF.` 통과
3. `scripts\test_d73_1_symbol_universe.py ......` 통과
4. 이후 6분 이상 출력 없음 (CPU 사용률 8.9%, 메모리 171MB 유지)

### 시도한 해결책
- ❌ pytest-timeout 설치 및 설정 (120초)
- ❌ `test_d41_k8s_tuning_session_runner.py` 제외 실행
- ⚠️ 여전히 hang 발생 (다른 테스트에서)

### 근본 원인 (추정)
- 특정 테스트가 async/threading 관련 무한 대기 상태 진입
- pytest-timeout의 thread 방식이 Windows에서 제대로 동작하지 않음 가능성
- 여러 테스트 파일에 산재된 hang 유발 코드

---

## 3. FAIL 테스트 목록 (Partial)

### 확인된 FAIL (Full Suite 실행 초기)
| 파일 | 테스트 | 상태 | 근본 원인 (추정) |
|------|--------|------|-----------------|
| `scripts/test_d72_config.py` | 2개 | FAIL | Config 검증 로직 불일치 |
| (기타) | 미상 | HANG | Full suite 완료 불가로 미집계 |

---

## 4. 해결 계획 (로드맵 제안)

### Phase 1: HANG 테스트 격리 (우선순위 P0)
**목표:** Full Suite를 완주 가능하게 만들기

**작업:**
1. pytest-timeout을 signal 방식으로 변경 (Linux/Mac) 또는 subprocess 격리 (Windows)
2. HANG 유발 테스트 파일을 하나씩 제외하면서 범위 좁히기
3. 문제 테스트 파일 목록화 및 개별 수정

**제안 D 단계:** D99-1 (Full Regression HANG Rescue)

### Phase 2: FAIL 테스트 수정 (우선순위 P1)
**목표:** FAIL 테스트를 PASS로 전환

**작업:**
1. Phase 1 완료 후 Full Suite 실행하여 FAIL 목록 수집
2. 파일별/모듈별 FAIL 개수 집계
3. Top 10 우선순위 파일부터 순차 수정

**제안 D 단계:** D99-2 (Full Regression FAIL Rescue)

### Phase 3: SSOT 확장 검토 (우선순위 P2)
**목표:** Core Regression SSOT에 추가할 테스트 선정

**기준:**
- 핵심 기능 (Trading, Risk, Monitoring, Config)
- Regression 방지 중요도 높음
- 실행 시간 10초 이내 (Fast Gate 유지)

**제안 D 단계:** D100 (Core Regression SSOT v2)

---

## 5. 현재 상태 (D98-6 완료 판정)

**D98-6 Acceptance Criteria:**
- AC-6: D98 테스트 100% PASS ✅ (176/176 PASS)
- (참고) Core Regression 100% PASS ✅ (44/44 PASS)

**Full Suite FAIL/HANG:**
- ⚠️ D98-6 범위 밖 (SSOT에 포함되지 않음)
- ⚠️ 별도 D 단계(D99+)에서 해결 예정

**결론:** D98-6은 SSOT 기준으로 100% PASS. Full Suite 부채는 등록 완료.

---

## 6. 증거 파일

**SSOT Gate 증거:**
- `docs/D98/evidence/d98_6_rescue_v2/step4_d98_tests.txt` (176 passed)
- `docs/D98/evidence/d98_6_rescue_v2/step4_core_regression.txt` (44 passed)

**Full Suite HANG 증거:**
- `docs/D98/evidence/d98_6_rescue_v2/step5_full_regression.txt` (초기 실행, null bytes)
- `docs/D98/evidence/d98_6_rescue_v2/step5_full_regression_exclude_d41.txt` (d41 제외, 여전히 hang)

---

**Next:** D99-1 (Full Regression HANG Rescue) + D99-2 (Full Regression FAIL Rescue)

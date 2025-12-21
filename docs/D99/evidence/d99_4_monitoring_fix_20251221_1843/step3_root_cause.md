# STEP 3: Root Cause Analysis (D99-4 Monitoring)

**Date:** 2025-12-21 18:43 KST  
**Target:** test_d50_metrics_server.py (13 failures)

## FAIL 재현 결과

**Total:** 13 failed, 0 passed  
**Duration:** 0.39s

### FAIL 패턴 분석

**모든 13개 FAIL이 동일한 원인:**

```
ModuleNotFoundError: No module named 'fastapi'
ImportError: FastAPI is required for MetricsServer. Install with: pip install fastapi uvicorn
```

### Root Cause 확정

**Category:** ④ 환경 의존성 누락 (Environment Dependency Missing)

**문제:**
- `arbitrage/monitoring/metrics_server.py`는 FastAPI를 선택적 의존성(optional)으로 설계
- 테스트는 `@pytest.mark.skipif(not HAS_FASTAPI, ...)`로 skip 처리 시도
- 하지만 **FastAPI가 실제로 설치되지 않아 import 실패**

**영향:**
- 13개 테스트 전부 FastAPI import 필요
- HAS_FASTAPI=False → skipif 작동해야 하지만, 일부 테스트 메서드 내부에서 직접 `from fastapi.testclient import TestClient` 호출로 인해 FAIL 발생

### 패턴별 분류 (프롬프트 요구사항)

**① 포트 충돌:** 해당 없음  
**② 레지스트리 중복/오염:** 해당 없음  
**③ 서버/스레드 정리 누락:** 해당 없음  
**④ 환경 의존성 누락:** ✅ **13개 전부 해당**

### Solution (최소 변경)

**Option A:** FastAPI 설치 (환경 fix)
- `pip install fastapi uvicorn`
- requirements.txt 확인 및 업데이트 (필요 시)

**Option B:** 테스트 코드 수정 (코드 fix)
- 테스트 메서드 내부의 `from fastapi.testclient import TestClient`를 모듈 레벨로 이동
- 또는 try-except로 감싸기

**선택:** Option A (환경 fix)
- FastAPI는 D50 설계 당시 선택적 의존성이었으나, 테스트 실행 환경에서는 필수
- 프로덕션 코드는 변경 불필요
- 최소 변경 원칙 준수

### 예상 결과

FastAPI 설치 후:
- 13 failed → 0 failed (또는 다른 원인 발견)
- 테스트 정상 실행 가능

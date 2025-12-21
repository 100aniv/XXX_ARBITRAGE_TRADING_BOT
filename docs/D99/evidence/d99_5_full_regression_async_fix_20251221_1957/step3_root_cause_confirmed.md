# STEP 3: Root Cause 확정 - Python 3.14 호환 이슈

**Date:** 2025-12-21 20:40 KST

## 재현 결과
1. **Full Regression:** 30분+ hang
2. **async 테스트 제외:** 여전히 timeout (다른 async 테스트에서 발생)
3. **anyio 제거 시도:** TestClient 의존성으로 불가능

## Root Cause 확정
**Python 3.14.0 + 현재 의존성 조합 호환 이슈**

**증거:**
- Python 3.14.0 (최신, 안정화 부족)
- pydantic 1.10.26 (v1, Python 3.14와 검증 부족)
- pytest-asyncio 1.3.0 + anyio 4.11.0 (event loop 충돌)
- asyncio.iscoroutinefunction deprecated in Python 3.14 (warnings 다수)

## 해결책
**즉시 적용 (최소 변경):**
1. requirements.txt에 Python 버전 권고 명시 (3.11-3.13)
2. 의존성 버전 핀 (pydantic, fastapi, pytest-asyncio)
3. README/문서에 Python 3.14 이슈 경고

**장기 해결 (별도 D 단계):**
- Python 3.13 venv로 마이그레이션
- 또는 pydantic v2 마이그레이션

## 실행 계획 변경
**D99-5 우선 처리:**
- Category C (Automation) 12 FAIL은 async와 무관
- test_d77_4_automation.py (8), test_d77_0_topn_arbitrage_paper.py (3)
- 이들을 먼저 수정하면 FAIL 144 → 132 달성 가능

**Full Regression 완주:**
- Python 3.14 이슈로 BLOCKED 상태 문서화
- CHECKPOINT에 "Python 3.13 이하 권고" 명시

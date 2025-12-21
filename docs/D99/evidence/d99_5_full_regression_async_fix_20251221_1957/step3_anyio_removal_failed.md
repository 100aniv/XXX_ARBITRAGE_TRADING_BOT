# STEP 3-1: anyio 플러그인 제거 시도 실패

**Date:** 2025-12-21 20:35 KST

## 시도
- **명령:** `python -m pytest -p no:anyio tests/test_d50_metrics_server.py tests/test_d98_preflight.py`
- **목적:** anyio + pytest-asyncio 충돌 차단

## 결과: ❌ FAIL
- **에러:** `TypeError: Client.__init__() got an unexpected keyword argument 'app'`
- **원인:** FastAPI TestClient은 httpx 백엔드를 사용하고, httpx는 anyio에 의존
- **결론:** anyio 제거는 불가능 (의존성 체인: TestClient → httpx → anyio)

## 전략 변경
**근본 원인:** Python 3.14.0 + 현재 의존성 조합 호환 이슈

**새 전략:**
1. async 테스트 제외하고 Full Regression 완주 (빠른 FAIL 카운트 확보)
2. Python 3.14 이슈 확정
3. requirements.txt에 Python 버전 권고 + 의존성 핀
4. D99-5 (Category C) 진행
